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
from dataclasses import dataclass

from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.contrato import infeasible_envelope
from fpso_siz.core.motor import size_envelope
from fpso_siz.termo import servico as termo
from fpso_siz.pfd.ajustes import AUTOMATICO, MANUAL, Ajustes, EstadoTAG, canonico_estado, contexto_de
from fpso_siz.pfd.entradas import Lacuna, cfg, especificacoes, montar, montar_manual
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

    def __init__(self, dados, prem=None, alteracoes=None, balanco=None, propostas=None, ajustes=None,
                 cenario_recuperador=None):
        self.dados = dados
        # Fase C (nota 46): o que fazer quando o recuperador da integração realizada não tem
        # geometria avaliada. None = a avaliação integrada é INVÁLIDA e os TAGs de carga residual
        # ficam aguardando; "bypass" = cenário EXPLÍCITO de recuperador fora de operação (Q_real = 0).
        self.cenario_recuperador = cenario_recuperador
        # estado de sessão dos TAGs: o serviço precisa dele para dimensionar o recuperador no
        # modo salvo quando monta a integração realizada (ADR 0005)
        self.ajustes = ajustes if ajustes is not None else Ajustes()
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
        self._integracao = None
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

    def estado_tag(self, ident):
        """EstadoTAG salvo na sessão, ou o inicial (automático)."""
        return self.ajustes.tags.get(ident) or estado_inicial(ident)

    def adotar_ajustes(self, ajustes):
        """Passa a usar `ajustes` como estado de sessão. O cache é pela forma canônica do estado
        de cada TAG e continua válido; só o que depende do RECUPERADOR (a integração realizada e
        os TAGs de carga residual) é descartado, e só se o estado dele mudou."""
        from fpso_siz.pfd import integracao_termica as integracao
        rec = integracao.cfg()["tag_recuperador"]
        antes = repr(canonico_estado(self.estado_tag(rec)))
        self.ajustes = ajustes
        if repr(canonico_estado(self.estado_tag(rec))) != antes:
            self._integracao = None
            for ident in [rec, *(l["tag_residual"] for l in integracao.cfg()["lado"])]:
                self.cache.pop(ident, None)

    def fixar_estado(self, estado):
        """Troca o estado de sessão de UM TAG e descarta o que dependia dele.

        É o que a busca discreta de layout (`pfd/layout.py`) precisa: cada candidato é um
        estado diferente do mesmo TAG, e tanto a integração realizada quanto os TAGs que
        consomem carga residual têm de ser recalculados. O balanço NÃO é descartado: ele não
        depende do candidato, e resolvê-lo de novo por candidato só gastaria tempo."""
        self.ajustes.tags[estado.id] = estado
        self.cache.clear()
        self._integracao = None

    @property
    def integracao(self):
        """Integração térmica REALIZADA (ADR 0005): o recuperador dimensionado no ponto fixo das
        propriedades e o estado de processo realizado de cada caso. Resolvida uma vez por
        contexto, e só se algum TAG consumir carga residual."""
        if self._integracao is None:
            from fpso_siz.pfd import integracao_termica as integracao
            self._integracao = integracao.integrar(self)
        return self._integracao

    def resultado_integrado(self, estado):
        """O ResultadoTAG do TAG recuperador é o do PONTO FIXO das propriedades, e não o de uma
        passagem só: é um caminho produtivo só (ADR 0005).

        Sem isto, a planta dimensionaria o recuperador numa passagem (propriedades na
        temperatura do ALVO) enquanto a integração realizada o dimensionaria no ponto fixo
        (propriedades na temperatura REALIZADA) — dois números para o mesmo TAG na mesma
        execução. None para qualquer outro TAG, e também para um estado que não é o da sessão
        (uma variante de estudo é avaliada sozinha, sem o laço)."""
        from fpso_siz.pfd import integracao_termica as integracao
        if estado.avulso or estado.id != integracao.cfg()["tag_recuperador"]:
            return None
        if repr(canonico_estado(estado)) != repr(canonico_estado(self.estado_tag(estado.id))):
            return None
        integrada = self.integracao
        return integrada.resultado if integrada.aplicavel or integrada.resultado is not None else None

    def lacuna_integracao(self, ident, entradas):
        """Lacuna NÃO editável de um TAG de carga residual quando a integração realizada é
        inválida (Fase C, nota 46): a carga que ele receberia seria a da recuperação preliminar,
        idealizada, e não a do estado operacional avaliado. None nos demais casos."""
        from fpso_siz.pfd import integracao_termica as integracao
        c = integracao.cfg()
        if ident not in {l["tag_residual"] for l in c["lado"]} or self.integracao.aplicavel:
            return None
        ativos = tuple(x.num for x in entradas.casos if x.ativo)
        if not ativos:
            return None
        tag_rec = c["tag_recuperador"]
        return Lacuna(c["lacuna"]["chave"], c["lacuna"]["rotulo"].format(tag=tag_rec), "", (),
                      c["lacuna"]["dica"].format(tag=tag_rec, motivo=self.integracao.motivo), ativos,
                      editavel=False)

    def balanco_do_tag(self, ident):
        """O estado de processo com que ESTE TAG é preparado.

        Quem consome CARGA RESIDUAL do pré-aquecedor (config/pfd/integracao.toml) é preparado
        com o estado REALIZADO: a carga que ainda falta depois do que a geometria instalada
        recuperou de fato. Todos os outros — inclusive o próprio recuperador, cujo alvo é o
        limite do Pinch — são preparados com o balanço preliminar. A escolha é declarada no
        TOML, não aqui."""
        from fpso_siz.pfd import integracao_termica as integracao
        if ident not in {l["tag_residual"] for l in integracao.cfg()["lado"]}:
            return self.balanco
        integrada = self.integracao
        return list(integrada.estados) if integrada.aplicavel else self.balanco

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


def preparar(ctx, estado, temperaturas=None):
    """EntradasTAG do equipamento no modo do estado (automático: balanço + propriedades;
    manual: usuário, arquivo e defaults com fonte)."""
    if estado.avulso:
        casos = [(i, n) for i, n in enumerate(estado.nomes_casos, 1)]
        return montar_manual(descritor(estado), casos, estado, pfd=False)
    t = tag(estado.id)
    if (estado.equipamento, estado.metodo) != (t.equipamento, t.metodo):
        raise ValueError(f"{t.tag}: o estado usa {estado.equipamento}/{estado.metodo}, mas o TAG é "
                         f"dimensionado por {t.equipamento}/{t.metodo}")
    return preparar_tag(ctx, t, estado, temperaturas=temperaturas)


def preparar_tag(ctx, t, estado, temperaturas=None):
    """preparar com o descritor `t` do catálogo.

    `temperaturas`: {num do caso: {corrente: T}} em que as PROPRIEDADES são avaliadas, no lugar
    das do balanço — o ponto fixo da integração realizada (pfd/integracao.py, ADR 0005)."""
    if estado.modo == MANUAL:
        return montar_manual(t, ctx.casos(), estado, propostas=ctx.propostas)
    entradas = montar(t, ctx.balanco_do_tag(t.tag), ctx.dados, ctx.prem, estado=estado,
                      propostas=ctx.propostas, temperaturas=temperaturas)
    lacuna = ctx.lacuna_integracao(t.tag, entradas)
    if lacuna is not None:
        entradas.lacunas.append(lacuna)
    return entradas


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
    """preparar + dimensionar, com cache no contexto pela forma canônica do estado.

    O TAG recuperador da integração térmica (ADR 0005) tem o seu resultado vindo do ponto fixo
    das propriedades — ver `Contexto.resultado_integrado`. Qualquer outro TAG, e qualquer
    variante de estudo, é dimensionado aqui mesmo, numa passagem."""
    chave = repr(canonico_estado(estado))
    guardado = ctx.cache.get(estado.id)
    if guardado is not None and guardado[0] == chave:
        return guardado[1]
    rt = ctx.resultado_integrado(estado)
    if rt is None:
        rt = dimensionar(preparar(ctx, estado), estado)
    ctx.cache[estado.id] = (chave, rt)
    return rt


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

