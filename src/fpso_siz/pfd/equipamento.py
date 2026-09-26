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
from dataclasses import dataclass

from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.contrato import infeasible_envelope
from fpso_siz.core.motor import size_envelope
from fpso_siz.pfd import fluidos
from fpso_siz.pfd.ajustes import AUTOMATICO, MANUAL, EstadoTAG, canonico_estado, contexto_de
from fpso_siz.pfd.entradas import cfg, especificacoes, montar, montar_manual
from fpso_siz.pfd.propostas import NENHUMA, conferir_casos
from fpso_siz.pfd.tags import avulso, tag, tags, topologia_alternativa

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

    def __init__(self, dados, prem=None, alteracoes=None, balanco=None, propostas=None, oleo_vivo=True,
                 topologia_julia=False):
        self.dados = dados
        # alocação de correntes: a do projeto (padrão; P-46 no P-002/P-003) ou a do PFD F1 do
        # Julia (paridade das fixtures e da regressão F10b)
        self.topologia_julia = topologia_julia
        # viscosidade do óleo: vivo (Beggs & Robinson sobre o óleo morto do BOT, padrão) ou só
        # morto (o modo das fases F10b–F13 e das fixtures do PFD F1 do Julia)
        self.oleo_vivo = oleo_vivo
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
            self._versoes = fluidos.versoes()
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
    if ctx.topologia_julia and t.topologia_julia:
        t = topologia_alternativa(t.topologia_julia)
    if (estado.equipamento, estado.metodo) != (t.equipamento, t.metodo):
        raise ValueError(f"{t.tag}: o estado usa {estado.equipamento}/{estado.metodo}, mas o TAG é "
                         f"dimensionado por {t.equipamento}/{t.metodo}")
    return preparar_tag(ctx, t, estado)


def preparar_tag(ctx, t, estado):
    """preparar com o descritor `t` dado (o do catálogo, ou uma topologia alternativa de estudo)."""
    if estado.modo == MANUAL:
        return montar_manual(t, ctx.casos(), estado, propostas=ctx.propostas)
    return montar(t, ctx.balanco, ctx.dados, ctx.prem, estado=estado, propostas=ctx.propostas,
                  oleo_vivo=ctx.oleo_vivo)


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


def executar(ctx, estado):
    """preparar + dimensionar, com cache no contexto pela forma canônica do estado."""
    chave = repr(canonico_estado(estado))
    guardado = ctx.cache.get(estado.id)
    if guardado is not None and guardado[0] == chave:
        return guardado[1]
    rt = dimensionar(preparar(ctx, estado), estado)
    ctx.cache[estado.id] = (chave, rt)
    return rt


def blocos_sem_dimensionamento(topologia):
    mapeados = {t.bloco for t in tags()}
    return [b["id"] for b in topologia["blocos"] if b["id"] not in mapeados]


def fontes_propriedades():
    return fluidos.cfg()


def limitacoes(oleo_vivo=True):
    """Limitações da modelagem adicional (vão para o JSON e o MC de cada TAG)."""
    return [cfg()["limitacao_oleo"]["vivo" if oleo_vivo else "morto"], *cfg()["limitacoes"]]


def rotulo_origem(origem):
    return cfg()["origens"][origem]


def dimensionar_arquivo(cfg_casos, equipamento=None, metodo=None):
    """Entrada avulsa no contrato do Julia (`dimensionar --exemplo|--casos`): o arquivo e,
    para as chaves ausentes, os defaults do método Julia. Preservada para a paridade com
    as fixtures; o fluxo por TAG/avulso novo usa o adaptador manual. (eq, m, casos, r)."""
    declarado = cfg_casos.get("equipment")
    if equipamento and declarado and declarado != equipamento:
        raise ValueError(f"o arquivo declara equipment = {declarado!r}, mas --equipamento = {equipamento!r}")
    eq_id = equipamento or declarado
    if not eq_id:
        raise ValueError("informe --equipamento: o arquivo de casos não declara `equipment`")
    eq, m = registro.resolver(eq_id, metodo)
    casos = case_set_from_config(cfg_casos)
    return eq, m, casos, size_envelope(eq, m, casos)
