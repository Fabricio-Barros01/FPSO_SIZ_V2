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
import itertools
from dataclasses import asdict, dataclass, field, replace
from types import SimpleNamespace

from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.estado import ETAPA_PRELIMINAR, ETAPA_RATING
from fpso_siz.balanco.modelo import CARGAS_RATING, CORRENTES_RATING, aplicar_rating_termico, resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.contrato import infeasible_envelope
from fpso_siz.core.motor import size_envelope
from fpso_siz.core.parametros import with_defaults
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import kw_para_w, m_para_mm, mm_para_m, w_para_kw
from fpso_siz.sizing import rating
from fpso_siz.sizing.trocador import (AvaliadorGeometriaFixa, GeometriaRating,
                                      propriedades_declaradas)
from fpso_siz.sizing.servico import ConfiguracaoServico, buscar_layouts, frente_pareto
from fpso_siz.termo import servico as termo
from fpso_siz.pfd.ajustes import AUTOMATICO, MANUAL, EstadoTAG, canonico_estado, contexto_de
from fpso_siz.pfd.entradas import ARQUIVO, CONFIRMADA, USUARIO, cfg, especificacoes, montar, montar_manual
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
    # geometria instalada e rating (P-001 automático). Quando existe, ELA é o resultado do TAG:
    # não há envelope DESIGN paralelo (`resultado` fica None).
    operacao: object = None
    etapa_balanco: str = ""   # etapa do balanço de onde as entradas foram preparadas ("" = manual/avulso)

    @property
    def tag(self):
        return self.entradas.tag

    @property
    def status(self):
        if not any(c.ativo for c in self.entradas.casos):
            return INATIVO
        if not self.entradas.pronto:
            return AGUARDANDO
        if self.operacao is not None:
            return DIMENSIONADO if self.operacao.geometria is not None else INVIAVEL
        return DIMENSIONADO if self.resultado.feasible else INVIAVEL

    @property
    def restricoes(self):
        """Restrições não atendidas que o status sozinho não mostra (hoje: o P-001 instalado)."""
        return self.operacao.avaliacao()["restricoes"] if self.operacao is not None else []

    @property
    def decisoes_pendentes(self):
        """Critérios que dependem de uma decisão de projeto ainda não tomada (ex.: o default do
        método abaixo do domínio declarado da busca) — nem atendidos nem reprovados."""
        return self.operacao.avaliacao()["decisoes_pendentes"] if self.operacao is not None else []

    @property
    def verificacoes_incompletas(self):
        """Verificações que ficaram sem conclusão — grandeza ausente, sem critério vigente, só
        estimada, ou caso cujo rating não foi avaliado. Incompleta não é atendida nem reprovada."""
        if self.operacao is None or self.operacao.geometria is None:
            return []
        av = self.operacao.avaliacao()
        h = av["atendimento_hidraulico"]
        out = sorted(h["lacunas"]) if h["completude"] == INCOMPLETA else []
        if av["convergencia_numerica"]["status"] != ATENDE:
            out.append("rating")
        return out

    @property
    def limitacoes_aceitas(self):
        """Resultados limitados por premissa aceita (ADR 0005), nem violação nem lacuna: a
        recuperação parcial da geometria instalada e o teto Pinch nulo da aproximação mínima."""
        if self.operacao is None or self.operacao.geometria is None:
            return []
        t = self.operacao.avaliacao()["atendimento_termico"]
        return [nome for nome, casos in (("recuperacao_parcial", t["casos_parciais"]),
                                         ("teto_pinch_nulo", t["casos_teto_nulo"])) if casos]

    @property
    def concluido(self):
        return self.status in (DIMENSIONADO, INATIVO)


def areas_troca(rt):
    """Áreas de troca do TAG dimensionado — a única regra lida pela otimização e pelo pacote de
    avaliação: por unidade, em operação (a que troca calor) e instalada (inclui a reserva). Para
    o P-001 integrado é a da geometria instalada (`OperacaoP001.areas`, a mesma do rating, do JSON
    e do memorial); para um envelope DESIGN, a área do ponto escolhido, com os cascos em série ×
    paralelo do método quando houver (sem reserva: o método não modela standby). None se o TAG
    não é trocador ou não está dimensionado."""
    if rt.status != DIMENSIONADO:
        return None
    if rt.operacao is not None:
        return {**rt.operacao.areas, "origem": "geometria_instalada"}
    d, v2 = rt.resultado.derivados, rt.resultado.derivados_v2 or {}
    if "area" not in d:
        return None
    total = v2.get("area_total", d["area"])
    unidades = int(v2.get("cascos_serie", 1) * v2.get("cascos_paralelo", 1))
    return {"por_unidade_m2": v2.get("area_por_casco", d["area"]), "em_operacao_m2": total,
            "instalada_m2": total, "unidades_em_operacao": unidades, "unidades_reserva": 0,
            "origem": "envelope_design"}


def derivado(rt, nome):
    """Derivado do envelope DESIGN do TAG dimensionado (NaN se não há envelope ou derivado)."""
    if rt.status != DIMENSIONADO or rt.resultado is None:
        return math.nan
    return float(rt.resultado.derivados.get(nome, math.nan))


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
        # P-001 de que dependem os demais TAGs (ajustes da sessão; None = automático)
        self._estado_p001 = None
        self._integracao = None    # (chave do estado do P-001, entradas, operação, estados)

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

    # --- etapa térmica: balanço preliminar → rating do P-001 → estado operacional
    def definir_p001(self, estado):
        """Fixa o estado do P-001 de que os TAGs dependentes leem o estado operacional. Trocar o
        P-001 descarta a integração e os resultados em cache que dependiam dela."""
        if estado is not None and estado.avulso:
            raise ValueError("o estado do P-001 da planta não pode ser um avulso")
        def chave(e):
            return repr(canonico_estado(e if e is not None else estado_inicial(TAG_RATING)))
        if chave(estado) != chave(self._estado_p001):
            self._estado_p001 = estado
            self._integracao = None
            self.cache.clear()

    def integracao_p001(self):
        """(entradas, operação, estados operacionais) — calculada uma vez por estado do P-001."""
        estado = self._estado_p001 or estado_inicial(TAG_RATING)
        chave = repr(canonico_estado(estado))
        if self._integracao is None or self._integracao[0] != chave:
            self._integracao = (chave, *integrar_p001(self, estado))
        return self._integracao[1:]

    def balanco_operacional(self):
        """Estados depois do rating do P-001 (o preliminar, se não houve rating)."""
        return self.integracao_p001()[2]

    def etapa_do_tag(self, t):
        """Etapa do balanço de onde o TAG `t` é preparado: o P-001 e os TAGs que não leem nada
        que o rating altera usam o preliminar; os dependentes, o estado operacional."""
        if not depende_do_rating(t):
            return ETAPA_PRELIMINAR
        return self.balanco_operacional()[0].etapa

    def balanco_do_tag(self, t):
        return self.balanco_operacional() if depende_do_rating(t) else self.balanco

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
    return montar(t, ctx.balanco_do_tag(t), ctx.dados, ctx.prem, estado=estado, propostas=ctx.propostas)


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
    if not estado.avulso and estado.id == TAG_RATING:
        # o P-001 da planta define o estado operacional dos dependentes
        ctx.definir_p001(estado)
    if not estado.avulso and estado.id == TAG_RATING and estado.modo == AUTOMATICO:
        # a geometria instalada É o resultado: nenhum DESIGN refeito sobre o estado pós-rating
        entradas, operacao, _ = ctx.integracao_p001()
        rt = ResultadoTAG(entradas, None, estado, operacao, ETAPA_PRELIMINAR)
    else:
        rt = dimensionar(preparar(ctx, estado), estado)
        if not estado.avulso and estado.modo == AUTOMATICO:
            rt.etapa_balanco = ctx.etapa_do_tag(descritor(estado))
    ctx.cache[estado.id] = (chave, rt)
    return rt


def configurar_dependencias(ctx, ajustes):
    """Aplica ao contexto o estado salvo do TAG de que outros dependem (o P-001), para que o TAG
    isolado e a planta leiam o mesmo estado operacional."""
    ctx.definir_p001(ajustes.tags.get(TAG_RATING))


@dataclass(frozen=True)
class GeometriaP001:
    """Geometria física única usada no rating dos dezesseis casos."""
    tubos_por_passe: float
    comprimento_tubo: float
    area_unitaria: float
    diametro_externo_mm: float
    passes_tubo: int
    razao_passo: float
    layout_tubos_graus: int
    corte_chicana: float
    espacamento_chicana: float
    instaladas: int
    duty: int
    standby: int


@dataclass(frozen=True)
class CasoOperacaoP001:
    """Um caso no P-001 instalado. `Q_Pinch` e `preliminar` são o balanço preliminar (teto
    Pinch); `Q_real`, `t_*_out` e `q_p00*` são o estado depois do rating. Cargas em kW,
    temperaturas em °C."""
    num: int
    nome: str
    Q_Pinch: float
    Q_real: float
    t_fria_out: float
    t_quente_out: float
    q_p002: float
    q_p003: float
    diagnosticos: dict
    preliminar: dict = field(default_factory=dict)
    papel: str = ""
    convergencia: dict = field(default_factory=dict)
    termico: dict = field(default_factory=dict)
    hidraulico: dict = field(default_factory=dict)


@dataclass(frozen=True)
class OperacaoP001:
    """Geometria instalada do P-001, o rating dela nos casos e a classificação do resultado.
    `geometria` None = nenhuma geometria do domínio pôde ser avaliada (inviável, com mensagem)."""
    geometria: GeometriaP001
    casos: tuple
    criterio_desempate: tuple = ()
    mensagem: str = ""
    geometria_derivada: dict = field(default_factory=dict)
    areas: dict = field(default_factory=dict)
    restricoes_geometricas: tuple = ()
    caso_projeto: int = 0
    premissa_comprimento: dict = field(default_factory=dict)   # a MESMA que a busca consultou

    def caso(self, num):
        return next(c for c in self.casos if c.num == num)

    def avaliacao(self):
        """Convergência numérica, atendimento térmico, atendimento hidráulico (separado da
        completude da verificação), restrições e decisões pendentes — cada um em separado."""
        conclusoes = carregar("pfd/p_001_busca.toml")["avaliacao"]["conclusoes"]
        def casos_com(chave, campo, valores):
            return [c.num for c in self.casos if getattr(c, chave).get(campo) in valores]
        nao_conv = casos_com("convergencia", "estado", ("nao_convergido",))
        nao_aval = casos_com("convergencia", "estado", ("nao_avaliavel",))
        parciais = casos_com("termico", "status", (TERMICO_PARCIAL,))
        teto_nulo = casos_com("termico", "status", (TERMICO_TETO_NULO,))
        violados, alertas, lacunas, informativos = {}, {}, {}, {}
        avaliados, sem_avaliacao, nao_aplicaveis = [], [], []
        for c in self.casos:
            h = c.hidraulico
            if h.get("atendimento") == NAO_APLICAVEL:
                nao_aplicaveis.append(c.num)
                continue
            if h.get("atendimento") == NAO_AVALIADO:
                sem_avaliacao.append(c.num)
            else:
                avaliados.append(c.num)
            for crit in h.get("criterios", []):
                destino = {NAO_ATENDE: violados, ALERTA: alertas}.get(crit["status"]) if crit["com_limite"] else None
                if destino is not None:
                    destino.setdefault(crit["criterio"], []).append(c.num)
                if crit["status"] == SEM_CRITERIO and crit["valor"] is not None and math.isfinite(crit["valor"]):
                    informativos.setdefault(crit["criterio"], []).append(c.num)
            for lac in h.get("lacunas", []):
                lacunas.setdefault(lac["criterio"], []).append(c.num)
        atendimento = (NAO_ATENDE if violados else ALERTA if alertas else ATENDE if avaliados else NAO_AVALIADO)
        completude = INCOMPLETA if (lacunas or sem_avaliacao) else COMPLETA
        geo = [r["criterio"] for r in self.restricoes_geometricas if r["status"] == NAO_ATENDE]
        decisoes = [r["criterio"] for r in self.restricoes_geometricas if r["status"] == DECISAO_PENDENTE]
        restricoes = [*geo, *violados]
        if self.geometria is None:
            situacao = "inviavel"
        elif nao_conv or nao_aval:
            situacao = NAO_AVALIADO
        elif restricoes:
            situacao = "com_restricoes"
        else:
            situacao = DECISAO_PENDENTE if decisoes else ATENDE
        return {
            "situacao": situacao,
            "restricoes": restricoes,
            "decisoes_pendentes": decisoes,
            "convergencia_numerica": {"status": ATENDE if not (nao_conv or nao_aval) else NAO_ATENDE,
                                      "casos_nao_convergidos": nao_conv, "casos_nao_avaliaveis": nao_aval},
            "atendimento_termico": {"status": TERMICO_PARCIAL if parciais else TERMICO_PLENO,
                                    "casos_parciais": parciais, "casos_teto_nulo": teto_nulo},
            "atendimento_hidraulico": {"atendimento": atendimento, "completude": completude,
                                       "conclusao": _conclusao(conclusoes, atendimento, completude),
                                       "nao_atende": violados, "alertas": alertas, "lacunas": lacunas,
                                       "informativos": informativos, "casos_avaliados": avaliados,
                                       "casos_nao_avaliados": sem_avaliacao,
                                       "casos_nao_aplicaveis": nao_aplicaveis},
            "restricoes_geometricas": [dict(r) for r in self.restricoes_geometricas],
            "premissa_comprimento": dict(self.premissa_comprimento),
        }

    def estrutura(self):
        return _sem_nao_finitos({
            "geometria": asdict(self.geometria) if self.geometria is not None else None,
            "geometria_derivada": dict(self.geometria_derivada), "areas": dict(self.areas),
            "mensagem": self.mensagem, "caso_projeto": self.caso_projeto,
            "etapas": {"entradas_do_rating": ETAPA_PRELIMINAR, "estado_operacional": ETAPA_RATING},
            "avaliacao": self.avaliacao(),
            "criterio_desempate": list(self.criterio_desempate),
            "casos": [asdict(c) for c in self.casos]})


# Vocabulário da classificação (o mesmo no JSON, no CSV e no memorial).
ATENDE, NAO_ATENDE, ALERTA = "atende", "nao_atende", "alerta"
NAO_AVALIADO, NAO_APLICAVEL, SEM_CRITERIO = "nao_avaliado", "nao_aplicavel", "sem_criterio_vigente"
DECISAO_PENDENTE = "decisao_pendente"
COMPLETA, INCOMPLETA = "completa", "incompleta"
# teto_nulo: o balanço preliminar não deixa nada a recuperar (aproximação disponível entre as entradas
# abaixo da mínima da P-32) — Q_real = 0 por construção, não por limitação da geometria
TERMICO_PLENO, TERMICO_PARCIAL, TERMICO_TETO_NULO = "pleno", "parcial", "teto_nulo"
CONVERGENCIA_INTERVALO_NULO = "intervalo_nulo"
# papel HIDRÁULICO do caso (P-45: pela vazão volumétrica no tubo, não pela carga térmica)
PROJETO, TURNDOWN, SEM_VAZAO = "projeto", "turndown", "sem_vazao"
CORRELACAO_APLICAVEL, ESTIMATIVA_INDICATIVA = "correlacao_aplicavel", "estimativa_indicativa"
TAG_RATING = "P-001"


def _sem_nao_finitos(obj):
    """Valor ausente é None (com o motivo ao lado, na classificação), nunca NaN nem zero."""
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    if isinstance(obj, dict):
        return {k: _sem_nao_finitos(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sem_nao_finitos(v) for v in obj]
    return obj


def _grade(inicio, fim, passo):
    n = round((fim - inicio) / passo)
    return tuple(inicio + i * passo for i in range(n + 1))


def _espaco_p001():
    """Traduz o TOML de engenharia para os objetos da busca genérica."""
    c = carregar("pfd/p_001_busca.toml")
    reserva = int(c["reserva_et"]["standby_minimo"])
    servicos = tuple(ConfiguracaoServico(int(s["instaladas"]), int(s["duty"]), int(s["standby"]),
                                         1 / int(s["duty"]), int(s["minimo_ativas"]))
                     for s in c["servico"] if int(s["standby"]) >= reserva)
    g = c["geometria"]
    geometrias = itertools.product(
        _grade(**{"inicio": c["tubos_por_passe"]["min"], "fim": c["tubos_por_passe"]["max"],
                  "passo": c["tubos_por_passe"]["passo"]}),
        _grade(**{"inicio": c["comprimento_m"]["min"], "fim": c["comprimento_m"]["max"],
                  "passo": c["comprimento_m"]["passo"]}),
        g["diametros_externos_mm"], g["passes_tubo"], g["razoes_passo"], g["layouts_tubos_graus"],
        g["cortes_chicana"], g["espacamentos_chicana_sobre_casco"])
    return c, servicos, tuple(geometrias)


def _criterio(criterio, escopo, valor, limite, unidade, status, fonte="", motivo="", com_limite=True,
              natureza="", obrigatorio=True):
    """`com_limite` False: grandeza sem critério de aceitação vigente — aparece (e a ausência
    dela também), mas não decide atendimento. `obrigatorio`: faz parte da verificação
    hidráulica (sem ela a verificação fica incompleta); False = diagnóstico informativo.
    `natureza`: correlação aplicável à geometria × estimativa indicativa."""
    return {"criterio": criterio, "escopo": escopo, "valor": valor, "limite": limite, "unidade": unidade,
            "status": status, "com_limite": com_limite, "fonte": fonte, "motivo": motivo, "natureza": natureza,
            "obrigatorio": obrigatorio}


def _conclusao(conclusoes, atendimento, completude):
    """Frase inequívoca: atendimento dos critérios avaliados; completude da verificação."""
    if atendimento == NAO_APLICAVEL:
        return conclusoes[NAO_APLICAVEL]
    return f"{conclusoes['atendimento'][atendimento]}; {conclusoes['completude'][completude]}."


def _resumo_hidraulico(criterios, conclusoes):
    """Atendimento (só critérios vigentes efetivamente avaliados), completude (há grandeza da
    verificação ausente, sem critério ou só estimada?) e lacunas com motivo. Ausência nunca vira
    atendimento, e valor sem limite nunca vira aprovação."""
    avaliados = [c["status"] for c in criterios if c["com_limite"] and c["status"] in (ATENDE, NAO_ATENDE, ALERTA)]
    atendimento = (NAO_ATENDE if NAO_ATENDE in avaliados else ALERTA if ALERTA in avaliados
                   else ATENDE if avaliados else NAO_AVALIADO)
    lacunas = [{"criterio": c["criterio"], "motivo": c["motivo"]} for c in criterios
               if c["obrigatorio"] and (c["status"] in (NAO_AVALIADO, SEM_CRITERIO)
                                        or c["natureza"] == ESTIMATIVA_INDICATIVA)]
    completude = INCOMPLETA if lacunas else COMPLETA
    return {"atendimento": atendimento, "completude": completude,
            "conclusao": _conclusao(conclusoes, atendimento, completude),
            "lacunas": lacunas, "criterios": criterios}


def _fonte(caso_tag, chave):
    v = caso_tag.valores.get(chave)
    return v.fonte if v is not None else ""


def _perda_carga(nome, escopo, valor, re, regime, motivos, natureza, extra="", ausencia=""):
    """Perda de carga: não há limite vigente (valor só informativo); ausência só com o motivo."""
    complemento = f" {extra}" if extra else ""
    if math.isfinite(valor):
        return _criterio(nome, escopo, valor, None, "Pa", SEM_CRITERIO, motivo=motivos["sem_criterio_dp"] + complemento,
                         com_limite=False, natureza=natureza)
    if ausencia:
        motivo = ausencia
    else:
        kh = carregar("equipment/comum/trocador.toml")["rating_hidraulica"]
        motivo = motivos["dp_regime"].format(re=re, regime=regime or "indefinido",
                                             re_lam=kh["reynolds_laminar_max"], re_turb=kh["reynolds_turbulent_min"])
    return _criterio(nome, escopo, None, None, "Pa", NAO_AVALIADO, motivo=motivo + complemento, com_limite=False,
                     natureza=natureza)


def _classificar_hidraulica(caso_tag, p, papel, d, motivos, conclusoes, fonte_p45, sem_carga, rho_casco):
    """Critérios vigentes no caso com vazão (P-45: teto de velocidade no tubo em todos os casos,
    piso no de projeto e alerta no turndown — escopo hidráulico, independente da carga térmica),
    validade da película só onde há troca térmica e perda de carga sem limite vigente."""
    escopo = "todos os casos com vazão"
    v = d.get("v", math.nan)
    crit = []
    if not math.isfinite(v):
        crit.append(_criterio("velocidade_tubo", escopo, None, None, "m/s", NAO_AVALIADO,
                              motivo=d.get("mensagem", "") or motivos["sem_diagnostico"]))
    else:
        crit.append(_criterio("velocidade_maxima_tubo", escopo, v, p["v_max"], "m/s",
                              ATENDE if v <= p["v_max"] else NAO_ATENDE, _fonte(caso_tag, "v_max")))
        if papel == PROJETO:
            status = ATENDE if v >= p["v_min"] else NAO_ATENDE
        else:
            status = ATENDE if v >= p["v_min"] else ALERTA
        crit.append(_criterio("velocidade_minima_tubo", "caso de projeto" if papel == PROJETO else "turndown",
                              v, p["v_min"], "m/s", status, f"{_fonte(caso_tag, 'v_min')}; {fonte_p45}"))
    if sem_carga:
        crit.append(_criterio("pelicula_tubo", "casos com carga térmica", d.get("re", math.nan), None, "–",
                              NAO_APLICAVEL, motivo=motivos["pelicula_sem_carga"], obrigatorio=False))
    else:
        valido = d.get("nu_valido")
        crit.append(_criterio("pelicula_tubo", "casos com carga térmica", d.get("re", math.nan), None, "–",
                              ATENDE if valido else (NAO_AVALIADO if valido is None else NAO_ATENDE),
                              d.get("correlacao", ""),
                              "" if valido else motivos["pelicula_fora"].format(motivo=d.get("motivo", ""))))
    sem_rho = "" if math.isfinite(rho_casco.valor) else motivos["rho_casco_ausente"].format(fonte=rho_casco.fonte)
    v_s = d.get("velocidade_casco", math.nan)
    crit.append(_criterio("velocidade_casco", escopo, v_s if math.isfinite(v_s) else None, None, "m/s",
                          SEM_CRITERIO if math.isfinite(v_s) else NAO_AVALIADO,
                          motivo=motivos["sem_criterio_v_casco"] if math.isfinite(v_s) else
                          (sem_rho or motivos["sem_diagnostico"]), com_limite=False, obrigatorio=False))
    crit.append(_perda_carga("perda_carga_tubo", escopo, d.get("perda_carga_tubo", math.nan), d.get("re", math.nan),
                             d.get("regime_hidraulico_tubo"), motivos, CORRELACAO_APLICAVEL))
    crit.append(_perda_carga("perda_carga_casco", escopo, d.get("perda_carga_casco", math.nan),
                             d.get("re_casco", math.nan), d.get("regime_hidraulico_casco"), motivos,
                             ESTIMATIVA_INDICATIVA, motivos["dp_casco_indicativa"], sem_rho))
    return _resumo_hidraulico(crit, conclusoes)


def _nao_aplicavel(motivo, conclusoes):
    return {"atendimento": NAO_APLICAVEL, "completude": NAO_APLICAVEL,
            "conclusao": _conclusao(conclusoes, NAO_APLICAVEL, NAO_APLICAVEL), "motivo": motivo,
            "lacunas": [], "criterios": []}


def premissa_comprimento(caso_tag, config_busca):
    """A premissa EFETIVA de comprimento de tubo do P-001, consultada pela busca, pela avaliação e
    pelo memorial. O `l_tubo_max` do TAG é default do método (Branan, estoque de 6 m) até ser
    informado ou confirmado pelo usuário; só então é limite do projeto e a busca o aplica.
    Default não confirmado abaixo do domínio declarado da busca = divergência explícita, com a
    decisão necessária — nem se impõe o default, nem se troca o limite para aprovar o candidato."""
    v = caso_tag.valores["l_tubo_max"]
    dominio = config_busca["comprimento_m"]
    confirmado = v.origem in (USUARIO, ARQUIVO) or v.revisao == CONFIRMADA
    excede = dominio["max"] > v.valor
    estado = "consistente" if not excede else ("limite_aplicado" if confirmado else "divergente")
    textos = config_busca["avaliacao"]["comprimento"]
    return {"chave": "l_tubo_max", "limite_m": v.valor, "origem": v.origem, "revisao": v.revisao, "fonte": v.fonte,
            "natureza": "limite_do_projeto" if confirmado else "padrao_do_metodo",
            "dominio_busca_m": [dominio["min"], dominio["max"]], "fonte_dominio": config_busca["fonte"],
            "aplicado_na_busca": confirmado, "estado": estado,
            "explicacao": textos[estado].format(limite=v.valor, dmin=dominio["min"], dmax=dominio["max"],
                                                origem=v.origem, revisao=v.revisao or "sem revisão")}


def avaliar_p001(estados, entradas):
    """DESIGN único seguido de RATING off-design do P-001 nos 16 estados de processo.

    Os estados são os PRELIMINARES: o alvo de cada caso é o ``Q_pre`` do Pinch/balanço. A
    geometria escolhida é a que o rating avaliou; nada depois disto a redimensiona. A busca não
    muda os limites do método: eles são aplicados na classificação do resultado.
    """
    if entradas.tag.tag != TAG_RATING or len(estados) != len(entradas.casos):
        raise ValueError("a avaliação integrada exige os estados e entradas completos do P-001")
    if any(e.etapa != ETAPA_PRELIMINAR for e in estados):
        raise ValueError("o rating do P-001 parte do balanço preliminar")
    metodo = entradas.metodo
    specs, constantes = metodo.parameters(), metodo.constants()
    preparados = []
    for estado, caso in zip(estados, entradas.casos):
        valores = {k: v.valor for k, v in caso.valores.items() if not v.lacuna and not v.ausente}
        p = with_defaults(specs, valores)
        entrada = metodo.case_input(valores)
        preparados.append((estado, caso, entrada, p))

    config_busca, configuracoes, especificacoes = _espaco_p001()
    motivos = config_busca["avaliacao"]["motivos"]
    conclusoes = config_busca["avaliacao"]["conclusoes"]
    tol = float(carregar("equipment/comum/servico.toml")["rating"]["tolerancia_relativa"])
    # P-45: caso de projeto = maior vazão volumétrica no tubo entre os casos COM VAZÃO. O escopo
    # da P-45 é hidráulico ("o teto vale em todos os casos"): carga térmica nula não tira o caso.
    com_vazao = [x for x in preparados if x[2].m_tubo > 0]
    projeto = max(com_vazao, key=lambda x: x[2].m_tubo / x[2].rho_tubo)[0].num if com_vazao else 0
    # uma premissa de comprimento só, a mesma da classificação e do memorial
    premissa = premissa_comprimento(next((x[1] for x in preparados if x[1].ativo), preparados[0][1]), config_busca)
    if premissa["aplicado_na_busca"]:
        especificacoes = tuple(e for e in especificacoes if e[1] <= premissa["limite_m"])

    def design(configuracao, especificacao, casos):
        del casos
        n_tubos, comprimento, d_ext, passes, razao, layout, corte, espacamento = especificacao
        area = n_tubos * passes * math.pi * mm_para_m(d_ext) * comprimento
        return GeometriaP001(n_tubos, comprimento, area, d_ext, int(passes), razao, int(layout), corte,
                             espacamento, configuracao.instaladas, configuracao.duty_projeto,
                             configuracao.standby)

    def avaliar(configuracao, geometria, preparado):
        estado, caso_tag, entrada, p = preparado
        # cópia: a busca não pode alterar os parâmetros (nem os limites) do caso
        p = dict(p, d_externo=geometria.diametro_externo_mm, passes_tubo=float(geometria.passes_tubo),
                 razao_passo=geometria.razao_passo, layout_tubos=float(geometria.layout_tubos_graus),
                 corte_chicana=geometria.corte_chicana, espacamento_chicana=geometria.espacamento_chicana)
        entrada_unidade = replace(entrada, m_tubo=entrada.m_tubo / configuracao.duty_projeto,
                                  m_casco=entrada.m_casco / configuracao.duty_projeto)
        alvo = kw_para_w(estado.duties["Q_pre"])
        c_rating = rating.CasoRating(entrada.t_tubo_in, entrada.t_casco_in,
                                     entrada.m_tubo * entrada.cp_tubo,
                                     entrada.m_casco * entrada.cp_casco, alvo)

        # O óleo não possui k validado no serviço termodinâmico; portanto o P-001 conserva
        # explicitamente as propriedades propostas. O avaliador ainda refaz toda a física
        # termo-hidráulica a cada Q e outros serviços podem fornecer adaptadores de `termo`.
        # ρ do casco não é entrada do método: vem da corrente do casco (C-22) pela mesma regra
        # da ρ do tubo (`Tag.auxiliares`). Só a velocidade e a perda de carga do casco a usam;
        # h_o (Bell-Delaware) depende do fluxo mássico, não de ρ. Ausente = NaN + motivo.
        rho_casco = caso_tag.auxiliares.get("rho_casco")
        if rho_casco is None:
            raise ValueError("P-001: o TAG não declara a auxiliar rho_casco (ρ da corrente do casco)")
        prop_t = propriedades_declaradas(entrada_unidade.rho_tubo, entrada_unidade.mu_tubo,
                                         entrada_unidade.cp_tubo, entrada_unidade.k_tubo)
        prop_s = propriedades_declaradas(rho_casco.valor, entrada_unidade.mu_casco,
                                         entrada_unidade.cp_casco, entrada_unidade.k_casco)
        avaliador = AvaliadorGeometriaFixa(
            metodo, GeometriaRating(geometria.tubos_por_passe, geometria.comprimento_tubo,
                                    geometria.area_unitaria, configuracao.duty_projeto),
            entrada_unidade, p, constantes, prop_t, prop_s)
        rr = rating.rating(c_rating, avaliador)
        d = rr.diagnostico
        integrado = rating.integrar(c_rating, rr, estado.T["C-08"], estado.T["C-24"])
        caso_inativo = alvo == 0
        # Atividade térmica ≠ passagem de vazão: o balanço não modela bypass nem isolamento do
        # P-001 (C-07 = C-06 e C-23 = C-22 em massa), então com Q = 0 as correntes ATRAVESSAM o
        # equipamento e a hidráulica é avaliada. Só a ausência de vazão a torna não aplicável.
        sem_vazao = not (entrada.m_tubo > 0 or entrada.m_casco > 0)
        papel = SEM_VAZAO if sem_vazao else (PROJETO if estado.num == projeto else TURNDOWN)
        if caso_inativo:
            # a equação do balanço que zerou o teto diz por quê: T das entradas e ΔT_app (P-32)
            teto = estado.trace.passo("carga_preaquecedor", TAG_RATING).entradas
            aproximacao = teto["T_quente"] - teto["T_frio"]
            termico = {"status": TERMICO_TETO_NULO,
                       "motivo": motivos["teto_nulo"].format(aprox=aproximacao, dt_app=teto["dT_app"]),
                       "aproximacao_disponivel_K": aproximacao, "aproximacao_minima_K": teto["dT_app"],
                       "fracao_recuperada": None}
        elif not rr.avaliavel:
            termico = {"status": NAO_AVALIADO, "motivo": motivos["nao_avaliavel"].format(mensagem=rr.mensagem)}
        else:
            pleno = rr.q_real >= rr.q_rec_max * (1 - tol)
            termico = {"status": TERMICO_PLENO if pleno else TERMICO_PARCIAL,
                       "fracao_recuperada": rr.q_real / rr.q_rec_max, "mecanismo": rr.mensagem}
        if sem_vazao:
            hidraulico = _nao_aplicavel(motivos["sem_vazao"], conclusoes)
        elif not rr.avaliavel:
            hidraulico = {"atendimento": NAO_AVALIADO, "completude": INCOMPLETA,
                          "conclusao": _conclusao(conclusoes, NAO_AVALIADO, INCOMPLETA),
                          "motivo": motivos["nao_avaliavel"].format(mensagem=rr.mensagem),
                          "lacunas": [{"criterio": "rating", "motivo": rr.mensagem}], "criterios": []}
        else:
            hidraulico = _classificar_hidraulica(caso_tag, p, papel, d, motivos, conclusoes,
                                                 _fonte(caso_tag, "banda_caso_projeto"), caso_inativo, rho_casco)
        resultado = CasoOperacaoP001(
            estado.num, caso_tag.nome, w_para_kw(rr.q_rec_max), w_para_kw(rr.q_real),
            rr.t_fria_out, rr.t_quente_out, w_para_kw(integrado.q_p002), w_para_kw(integrado.q_p003),
            {"Q_rating_kW": w_para_kw(rr.q_rating), "UA_W_K": rr.ua, "F": rr.fator_f,
             "dT_lm_K": rr.dt_lm, "recuperacao_nao_realizada_kW": w_para_kw(rr.recuperacao_nao_realizada),
             "convergiu": rr.convergiu, "iteracoes": rr.iteracoes,
             "Re_tubo": d.get("re"), "Re_casco": d.get("re_casco"),
             "regime_pelicula_tubo": d.get("regime", ""), "pelicula_tubo_valida": d.get("nu_valido"),
             "h_tubo_W_m2K": d.get("h_i"), "h_casco_W_m2K": d.get("h_o"),
             "U_W_m2K": d.get("u"),
             # _feixe_fixo devolve o diâmetro em metros (SI); o rótulo diz mm, então converte-se
             "diametro_casco_mm": m_para_mm(d["d_shell"]) if "d_shell" in d else None,
             "velocidade_tubo_m_s": d.get("v"), "velocidade_casco_m_s": d.get("velocidade_casco"),
             "rho_casco_kg_m3": rho_casco.valor, "rho_tubo_kg_m3": entrada.rho_tubo,
             "vazao_tubo_kg_s": entrada.m_tubo, "vazao_casco_kg_s": entrada.m_casco,
             "regime_hidraulico_tubo": d.get("regime_hidraulico_tubo", ""),
             "regime_hidraulico_casco": d.get("regime_hidraulico_casco", ""),
             "perda_carga_tubo_Pa": d.get("perda_carga_tubo"),
             # estimativa indicativa (Darcy-Weisbach sobre L/d_o; sem correlação de casco no acervo)
             "perda_carga_casco_indicativa_Pa": d.get("perda_carga_casco")},
            preliminar={"T_C07": estado.T["C-07"], "T_C23": estado.T["C-23"],
                        "Q_H_kW": estado.duties["Q_H"], "Q_C_kW": estado.duties["Q_C"]},
            papel=papel,
            # teto nulo: o intervalo da bisseção é [0, 0] — não há o que convergir (rating.py devolve
            # "sem_carga"); declara-se isso, sem confundir com caso sem serviço
            convergencia=({"estado": CONVERGENCIA_INTERVALO_NULO, "mensagem": motivos["convergencia_teto_nulo"]}
                          if caso_inativo and rr.avaliavel else {"estado": rr.estado, "mensagem": rr.mensagem}),
            termico=termico, hidraulico=hidraulico)
        return SimpleNamespace(admissivel=rr.convergiu and (caso_inativo or bool(d.get("ok"))),
                               avaliavel=rr.avaliavel, diagnostico=d,
                               recuperacao=rr.q_real, utilidade_quente=integrado.utilidade_quente_residual,
                               utilidade_fria=integrado.utilidade_fria_residual, resultado=resultado)

    desempate = tuple(config_busca["selecao"]["desempate"])
    layouts = buscar_layouts(configuracoes, especificacoes, tuple(preparados), design, avaliar)
    if not layouts:
        return OperacaoP001(None, (), desempate, mensagem="P-001: nenhuma geometria do domínio de busca "
                            "convergiu com coeficiente global finito em todos os casos BOT",
                            premissa_comprimento=premissa)
    frente = frente_pareto(layouts)
    escolhido = min(frente, key=lambda x: (x.utilidade_quente + x.utilidade_fria, x.area_instalada,
        x.configuracao.instaladas, x.configuracao.duty_projeto, x.geometria.tubos_por_passe,
        x.geometria.comprimento_tubo, x.geometria.diametro_externo_mm, x.geometria.passes_tubo,
        x.geometria.layout_tubos_graus, x.geometria.razao_passo, x.geometria.corte_chicana,
        x.geometria.espacamento_chicana))
    g = escolhido.geometria
    d = next((x.diagnostico for x in escolhido.casos if "d_shell" in x.diagnostico), {})
    derivada = {"tubos_total": d.get("n_total", math.nan),
                "diametro_feixe_mm": m_para_mm(d["d_casco"]) if "d_casco" in d else math.nan,
                "diametro_casco_mm": m_para_mm(d["d_shell"]) if "d_shell" in d else math.nan}
    # limites geométricos do método, como estão nas entradas do TAG (não os da busca)
    _, caso0, _, p0 = preparados[0]
    if g.comprimento_tubo <= premissa["limite_m"]:
        st_comprimento, motivo_comprimento = ATENDE, ""
    elif premissa["natureza"] == "limite_do_projeto":
        st_comprimento, motivo_comprimento = NAO_ATENDE, ""
    else:
        st_comprimento, motivo_comprimento = DECISAO_PENDENTE, premissa["explicacao"]
    geometricas = (
        _criterio("comprimento_tubo", "geometria instalada", g.comprimento_tubo, premissa["limite_m"], "m",
                  st_comprimento, premissa["fonte"], motivo_comprimento),
        _criterio("diametro_casco", "geometria instalada", derivada["diametro_casco_mm"], p0["d_casco_max"], "mm",
                  NAO_AVALIADO if not math.isfinite(derivada["diametro_casco_mm"]) else
                  ATENDE if derivada["diametro_casco_mm"] <= p0["d_casco_max"] else NAO_ATENDE,
                  _fonte(caso0, "d_casco_max")))
    totais = escolhido.configuracao.totais_extensivos(g.area_unitaria, escolhido.configuracao.duty_projeto)
    areas = {"por_unidade_m2": totais["unitario"], "em_operacao_m2": totais["operando"],
             "instalada_m2": totais["instalado"], "unidades_em_operacao": escolhido.configuracao.duty_projeto,
             "unidades_reserva": escolhido.configuracao.standby}
    return OperacaoP001(g, tuple(x.resultado for x in escolhido.casos), desempate,
                        geometria_derivada=derivada, areas=areas, restricoes_geometricas=geometricas,
                        caso_projeto=projeto, premissa_comprimento=premissa)


def referencias_rating(t):
    """Correntes e cargas que o rating do P-001 altera e que as regras do TAG `t` citam."""
    def nomes(v):
        return [v] if isinstance(v, str) else list(v or ())
    refs = {t.condicao, *(n for v in t.inativo_se.values() for n in nomes(v))}
    for regra in (*t.entradas.values(), *t.auxiliares.values()):
        for chave in ("corrente", "carga", "processo", "t"):
            refs.update(nomes(regra.get(chave)) if isinstance(regra, dict) else ())
    return refs & {*CORRENTES_RATING, *CARGAS_RATING}


def depende_do_rating(t):
    """O TAG lê alguma corrente ou carga que o rating do P-001 altera? (o próprio P-001 não:
    ele é preparado do balanço preliminar, que é o alvo do rating)."""
    return t.tag != TAG_RATING and bool(referencias_rating(t))


def integrar_p001(ctx, estado):
    """(entradas, operação, estados operacionais) do P-001 automático.

    É a ÚNICA definição da geometria instalada: o P-001 apresenta esta operação, e os TAGs que
    dependem dela (P-002, P-003) são preparados dos estados devolvidos aqui. Sem P-001
    automático pronto, ou sem geometria viável, o estado operacional é o preliminar."""
    if estado is None or estado.modo != AUTOMATICO:
        return None, None, ctx.balanco
    entradas = preparar(ctx, estado)
    if not entradas.pronto or not any(c.ativo for c in entradas.casos):
        return entradas, None, ctx.balanco
    operacao = avaliar_p001(ctx.balanco, entradas)
    if operacao.geometria is None:
        return entradas, operacao, ctx.balanco
    atualizados, casos = [], []
    for r in ctx.balanco:
        op = operacao.caso(r.num)
        atualizado = aplicar_rating_termico(r, op.Q_real, ctx.prem)
        # A operação e o resolvedor usam a mesma equação. Esta conferência impede que o
        # objeto publicado pelo P-001 divirja do estado que alimenta P-002/003.
        publicados = (op.t_fria_out, op.t_quente_out, op.q_p002, op.q_p003)
        resolvidos = (atualizado.T["C-07"], atualizado.T["C-23"], atualizado.duties["Q_H"],
                      atualizado.duties["Q_C"])
        if not all(math.isclose(a, b) for a, b in zip(resolvidos, publicados)):
            raise ValueError(f"P-001: segunda etapa térmica divergiu no caso {r.num}")
        atualizados.append(atualizado)
        casos.append(replace(op, t_fria_out=atualizado.T["C-07"], t_quente_out=atualizado.T["C-23"],
                             q_p002=atualizado.duties["Q_H"], q_p003=atualizado.duties["Q_C"]))
    return entradas, replace(operacao, casos=tuple(casos)), atualizados


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
