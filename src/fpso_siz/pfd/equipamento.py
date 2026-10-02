"""Serviço por equipamento/TAG (F10c): preparar as entradas e dimensionar UM equipamento.

É a única orquestração entre entradas e motor: o TAG isolado (`dimensionar --tag`), o PFD
(`pfd`, planta.py) e o modo interativo chamam estas funções. O serviço devolve dados e
estados — não pergunta, não imprime, não desenha, não grava.

- Contexto: arquivo de casos, premissas, balanço (resolvido uma vez, e só se algum TAG
  automático precisar) e versões. Resultados ficam em cache no próprio contexto, pela
  forma canônica do estado do TAG: editar recalcula só aquele TAG; trocar o contexto
  (outro arquivo de casos, outras premissas) descarta tudo o que dependia dele.
- Inviabilidade física é estado (`feasible = False` + mensagem); lacuna mantém o TAG
  aguardando entrada; entrada inválida ou contexto incompatível é ValueError.
"""
import math
from dataclasses import asdict, dataclass, replace
from types import SimpleNamespace

from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.contrato import infeasible_envelope
from fpso_siz.core.motor import size_envelope
from fpso_siz.core.parametros import with_defaults
from fpso_siz.core.unidades import kw_para_w, mm_para_m, w_para_kw
from fpso_siz.sizing import rating
from fpso_siz.sizing.servico import ConfiguracaoServico, buscar_layouts
from fpso_siz.termo import servico as termo
from fpso_siz.pfd.ajustes import AUTOMATICO, MANUAL, EstadoTAG, canonico_estado, contexto_de
from fpso_siz.pfd.entradas import cfg, especificacoes, montar, montar_manual
from fpso_siz.pfd.propostas import NENHUMA, conferir_casos
from fpso_siz.pfd.tags import avulso, tag, tags

AGUARDANDO = "aguardando_entrada"
DIMENSIONADO = "dimensionado"
INVIAVEL = "inviavel"
INATIVO = "inativo"
ESTADOS = (DIMENSIONADO, AGUARDANDO, INVIAVEL, INATIVO)


@dataclass
class ResultadoTAG:
    entradas: object          # EntradasTAG
    resultado: object = None  # EnvelopeResult, ou None se aguardando entrada / inativo
    estado: object = None     # EstadoTAG usado (modo, ajustes, revisões)
    operacao: object = None   # avaliação integrada da geometria instalada, quando aplicável

    @property
    def tag(self):
        return self.entradas.tag

    @property
    def status(self):
        if not any(c.ativo for c in self.entradas.casos):
            return INATIVO
        if not self.entradas.pronto:
            return AGUARDANDO
        return DIMENSIONADO if self.resultado.feasible else INVIAVEL

    @property
    def concluido(self):
        return self.status in (DIMENSIONADO, INATIVO)


class Contexto:
    """Dados compartilhados por todos os TAGs de uma execução ou sessão."""

    def __init__(self, dados, prem=None, alteracoes=None, balanco=None, propostas=None):
        self.dados = dados
        # valores propostos para as lacunas (pfd/propostas.py); vazio = nenhum arquivo carregado
        self.propostas = propostas if propostas is not None else NENHUMA
        if self.propostas and dados is not None:
            conferir_casos(self.propostas, [c["num"] for c in dados.casos])
        base = premissas(dados)
        if prem is None:
            prem = premissas(dados, **(alteracoes or {}))
        self.prem = prem
        self.alteracoes = {k: v for k, v in prem.items() if v != base[k]}
        self._resultados = balanco
        self._balanco = None
        self._versoes = None
        self.cache = {}

    @property
    def resultados_balanco(self):
        """Balanço dos casos, sem validação (o menu do balanço mostra a não convergência)."""
        if self._resultados is None:
            if self.dados is None:
                raise ValueError("carregue um arquivo de casos (JSON do BOT) antes do balanço")
            self._resultados = resolver_todos(self.dados, self.prem)
        return self._resultados

    @property
    def balanco(self):
        """Balanço validado para alimentar os TAGs automáticos."""
        if self._balanco is None:
            b = self.resultados_balanco
            if not b or len({r.num for r in b}) != len(b):
                raise ValueError("balanço sem casos ou com números de caso duplicados")
            if {r.num for r in b} != {c["num"] for c in self.dados.casos}:
                raise ValueError("casos do balanço não correspondem ao arquivo de entrada")
            if any(not r.convergiu for r in b):
                raise ValueError("balanço não convergiu; reveja os casos antes de dimensionar a planta")
            self._balanco = b
        return self._balanco

    @property
    def balanco_resolvido(self):
        return self._resultados is not None

    @property
    def versoes(self):
        if self._versoes is None:
            self._versoes = termo.versoes()
        return self._versoes

    def casos(self):
        """[(num, nome)] dos casos do arquivo, com o nome usado no envelope."""
        if self.dados is None:
            raise ValueError("carregue um arquivo de casos (JSON do BOT) para trabalhar com os TAGs da planta")
        return [(c["num"], cfg()["nome_caso"].format(num=c["num"], nome=c.get("name", c["fluid_type"])))
                for c in self.dados.casos]

    def identidade(self):
        return contexto_de(self.dados, self.alteracoes, self.versoes)


def estado_inicial(ident, modo=AUTOMATICO):
    t = tag(ident)
    return EstadoTAG(t.tag, t.equipamento, t.metodo, modo)


def descritor(estado):
    return avulso(estado.id, estado.equipamento, estado.metodo) if estado.avulso else tag(estado.id)


def especificacoes_de(equipamento, metodo, pfd=True):
    """{chave: ParameterSpec} do método (com as faixas de apresentação do PFD, se `pfd`)."""
    return especificacoes(avulso("", equipamento, metodo), pfd)[2]


def ordem_chaves(estado):
    """Chaves na ordem do formulário (método, depois insumos do TAG)."""
    t = descritor(estado)
    return [*especificacoes(t, not estado.avulso)[2], *t.insumos]


def preparar(ctx, estado):
    """EntradasTAG do equipamento no modo do estado (automático: balanço + propriedades;
    manual: usuário, arquivo e defaults com fonte)."""
    if estado.avulso:
        casos = [(i, n) for i, n in enumerate(estado.nomes_casos, 1)]
        return montar_manual(descritor(estado), casos, estado, pfd=False)
    t = tag(estado.id)
    if (estado.equipamento, estado.metodo) != (t.equipamento, t.metodo):
        raise ValueError(f"{t.tag}: o estado usa {estado.equipamento}/{estado.metodo}, mas o TAG é "
                         f"dimensionado por {t.equipamento}/{t.metodo}")
    return preparar_tag(ctx, t, estado)


def preparar_tag(ctx, t, estado):
    """preparar com o descritor `t` dado (o do catálogo, ou uma topologia alternativa de estudo)."""
    if estado.modo == MANUAL:
        return montar_manual(t, ctx.casos(), estado, propostas=ctx.propostas)
    return montar(t, ctx.balanco, ctx.dados, ctx.prem, estado=estado, propostas=ctx.propostas)


def dimensionar(entradas, estado=None):
    """Envelope do equipamento, se as entradas dos casos ativos estão completas. Conta
    impossível com as entradas dadas (ex.: raiz de número negativo) é inviabilidade com
    diagnóstico, não exceção: o motor já converte os erros aritméticos; aqui entram os de
    domínio das funções matemáticas."""
    r = None
    if entradas.pronto and any(c.ativo for c in entradas.casos):
        try:
            r = size_envelope(entradas.equipamento, entradas.metodo, entradas.case_set())
        except ValueError as e:
            r = infeasible_envelope(cfg()["mensagens"]["conta_impossivel"].format(erro=e))
    return ResultadoTAG(entradas, r, estado)


def dividir_vazao(ctx, estado, chaves, fator):
    """Divide as `chaves` de vazão do TAG por `fator` unidades iguais em paralelo, caso a caso,
    a partir das entradas que o próprio TAG prepara. Lacuna ou faixa fica como está — e aí o
    TAG não fica pronto, de modo que ninguém conta N unidades de um vaso que ainda passa o
    serviço inteiro. Edita `estado` e o devolve (trens da otimização e variantes de alarme)."""
    for c in preparar(ctx, estado).casos:
        for chave in chaves:
            v = c.valores.get(chave)
            if v is not None and not v.lacuna and not v.faixa and math.isfinite(v.valor):
                estado.editar(chave, v.valor / fator, [c.num], {})
    return estado


def executar(ctx, estado):
    """preparar + dimensionar, com cache no contexto pela forma canônica do estado."""
    chave = repr(canonico_estado(estado))
    guardado = ctx.cache.get(estado.id)
    if guardado is not None and guardado[0] == chave:
        return guardado[1]
    rt = dimensionar(preparar(ctx, estado), estado)
    ctx.cache[estado.id] = (chave, rt)
    return rt


@dataclass(frozen=True)
class GeometriaP001:
    """Geometria física única usada no rating dos dezesseis casos."""
    tubos_por_passe: float
    comprimento_tubo: float
    area_unitaria: float


@dataclass(frozen=True)
class CasoOperacaoP001:
    num: int
    nome: str
    Q_Pinch: float
    Q_real: float
    t_fria_out: float
    t_quente_out: float
    q_p002: float
    q_p003: float
    diagnosticos: dict


@dataclass(frozen=True)
class OperacaoP001:
    geometria: GeometriaP001
    casos: tuple

    def caso(self, num):
        return next(c for c in self.casos if c.num == num)

    def estrutura(self):
        return {"geometria": asdict(self.geometria), "casos": [asdict(c) for c in self.casos]}


def avaliar_p001(estados, entradas):
    """DESIGN único seguido de RATING off-design do P-001 nos 16 estados de processo.

    O alvo de cada caso é o ``Q_pre`` que veio do Pinch/balanço. O comprimento instalado é
    limitado ao tubo físico declarado pelo método; ele não é recalculado durante o rating.
    """
    if entradas.tag.tag != "P-001" or len(estados) != len(entradas.casos):
        raise ValueError("a avaliação integrada exige os estados e entradas completos do P-001")
    metodo = entradas.metodo
    specs, constantes = metodo.parameters(), metodo.constants()
    preparados = []
    for estado, caso in zip(estados, entradas.casos):
        valores = {k: v.valor for k, v in caso.valores.items() if not v.lacuna and not v.ausente}
        p = with_defaults(specs, valores)
        # Contracorrente é a geometria materializável para rating parcial; o arranjo 1-2
        # falha antes de produzir geometria no alvo ideal do balanço.
        p["passes_tubo"] = float(cfg()["p001_integrado"]["passes_tubo"])
        entrada = metodo.case_input(valores)
        preparados.append((estado, caso, entrada, p))

    projeto = max(preparados, key=lambda x: x[2].m_tubo / x[2].rho_tubo)
    p_projeto = projeto[3]
    eixo = metodo.sweep_axis(p_projeto)
    n = min(eixo.values, key=lambda x: abs(x - p_projeto["n_min"]))
    comprimento = float(p_projeto["l_tubo_max"])

    def design(configuracao, especificacao, casos):
        del configuracao, casos
        n_tubos = especificacao
        d_o = mm_para_m(p_projeto["d_externo"])
        area = n_tubos * p_projeto["passes_tubo"] * math.pi * d_o * comprimento
        return GeometriaP001(n_tubos, comprimento, area)

    def avaliar(configuracao, geometria, preparado):
        del configuracao
        estado, caso_tag, entrada, p = preparado
        alvo = kw_para_w(estado.duties["Q_pre"])
        c_rating = rating.CasoRating(entrada.t_tubo_in, entrada.t_casco_in,
                                     entrada.m_tubo * entrada.cp_tubo,
                                     entrada.m_casco * entrada.cp_casco, alvo)

        def coeficientes(q, tc, th):
            e = replace(entrada, t_tubo_out=tc)
            ok, cons, _ = metodo.sizing_constraints(e, p, constantes)
            if not ok:
                return 0.0, 0.0
            derivados = metodo.derived(geometria.tubos_por_passe, geometria.comprimento_tubo,
                                       "termica", cons, constantes, p)
            return derivados.get("u", 0.0) * geometria.area_unitaria, cons.f

        rr = rating.rating(c_rating, lambda q, tc, th: coeficientes(q, tc, th)[0],
                           lambda q, tc, th: coeficientes(q, tc, th)[1])
        integrado = rating.integrar(c_rating, rr, estado.T["C-08"], estado.T["C-24"])
        resultado = CasoOperacaoP001(
            estado.num, caso_tag.nome, w_para_kw(rr.q_rec_max), w_para_kw(rr.q_real),
            rr.t_fria_out, rr.t_quente_out, w_para_kw(integrado.q_p002), w_para_kw(integrado.q_p003),
            {"Q_rating_kW": w_para_kw(rr.q_rating), "UA_W_K": rr.ua, "F": rr.fator_f,
             "dT_lm_K": rr.dt_lm, "recuperacao_nao_realizada_kW": w_para_kw(rr.recuperacao_nao_realizada),
             "convergiu": rr.convergiu, "iteracoes": rr.iteracoes})
        return SimpleNamespace(admissivel=rr.convergiu, utilidade_quente=integrado.utilidade_quente_residual,
                               utilidade_fria=integrado.utilidade_fria_residual, resultado=resultado)

    configuracao = ConfiguracaoServico(1, 1, 0, 1.0)
    layouts = buscar_layouts((configuracao,), (n,), tuple(preparados), design, avaliar)
    if not layouts:
        raise ValueError("P-001: nenhuma geometria fixa pôde ser avaliada nos casos BOT")
    escolhido = min(layouts, key=lambda x: (x.utilidade_quente + x.utilidade_fria, x.area_instalada))
    return OperacaoP001(escolhido.geometria, tuple(x.resultado for x in escolhido.casos))


def blocos_sem_dimensionamento(topologia):
    mapeados = {t.bloco for t in tags()}
    return [b["id"] for b in topologia["blocos"] if b["id"] not in mapeados]


def fontes_propriedades():
    return termo.cfg()


def limitacoes():
    """Limitações da modelagem adicional (vão para o JSON e o MC de cada TAG)."""
    return list(cfg()["limitacoes"])


def rotulo_origem(origem):
    return cfg()["origens"][origem]


def dimensionar_arquivo(cfg_casos, equipamento=None, metodo=None):
    """Equipamento avulso a partir de um arquivo de casos (`dimensionar --exemplo|--casos`): o
    arquivo e, para as chaves ausentes, os defaults do método. É a entrada dos exemplos
    resolvidos da literatura (config/exemplos/) e de um equipamento fora da planta; o avulso
    da sessão interativa passa pelo adaptador manual. (eq, m, casos, r)."""
    declarado = cfg_casos.get("equipment")
    if equipamento and declarado and declarado != equipamento:
        raise ValueError(f"o arquivo declara equipment = {declarado!r}, mas --equipamento = {equipamento!r}")
    eq_id = equipamento or declarado
    if not eq_id:
        raise ValueError("informe --equipamento: o arquivo de casos não declara `equipment`")
    eq, m = registro.resolver(eq_id, metodo)
    casos = case_set_from_config(cfg_casos)
    return eq, m, casos, size_envelope(eq, m, casos)
