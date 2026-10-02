"""Busca discreta de layout de um TAG de trocador, com o conjunto INTEGRADO verificado
(ADR 0005; docs/validacao/43).

Um candidato é uma geometria discreta (diâmetro e passo do tubo, arranjo e espaçamento de
chicana, passes, comprimento máximo por casco, cascos em série, trens em paralelo) mais uma
filosofia de unidades físicas (trens em operação e trens de reserva INSTALADA, que a ET
exige). Os eixos, os valores de cada um e a fonte da faixa estão em
`config/pfd/layout_trocador.toml`; nenhum valor é inventado aqui.

Para cada candidato, a avaliação é o caminho produtivo inteiro, não um atalho:

1. o pré-aquecedor é dimensionado pelo caso de PROJETO e CLASSIFICADO nos demais, com as
   propriedades, as películas, o U, o F, as temperaturas e o Q de cada caso REAVALIADOS no
   ponto fixo da integração realizada (`pfd/integracao.py`) — U não é o do ponto de projeto;
2. velocidade, faixa da correlação de película, diâmetro de casco, comprimento por casco e
   perda de carga do lado tubo são exigidos em TODOS os casos (o motor já os cobra);
3. o calor efetivamente recuperado propaga às utilidades, e o aquecedor e o resfriador são
   REDIMENSIONADOS pelo envelope das cargas residuais;
4. só então a viabilidade é declarada — e ela exige o CONJUNTO: pré-aquecedor, aquecedor e
   resfriador dimensionados, nenhum caso sem rating avaliável, as temperaturas finais da ET
   alcançadas em todos os casos e a reserva instalada que a ET pede.

A comparação usa o contrato genérico de serviço (`sizing/servico.py`): `buscar_layouts` varre
os candidatos (DESIGN uma vez, RATING em todos os casos, candidato que viole o método é
rejeitado), a área INSTALADA conta a reserva e a operacional não, e `frente_pareto` dá a
frente física — área instalada, utilidade quente e utilidade fria —, sem dado econômico
inventado.
"""
import copy
import math
from dataclasses import dataclass, replace
from itertools import product

from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.sizing.servico import ConfiguracaoServico, buscar_layouts, frente_pareto

# chaves do TOML de eixos que NÃO são parâmetros do método do trocador
EIXOS_DE_SERVICO = ("standby",)


def cfg():
    return carregar("pfd/layout_trocador.toml")


@dataclass(frozen=True)
class Especificacao:
    """Um ponto dos eixos geométricos: {chave do descritor do método: valor}."""
    valores: tuple    # ((chave, valor), ...) — ordenada, para ser chave de dicionário

    @property
    def dict(self):
        return dict(self.valores)

    def __str__(self):
        return ", ".join(f"{k}={v:g}" for k, v in self.valores)


@dataclass(frozen=True)
class VerificacaoFinal:
    """Uma temperatura final que a ET exige, conferida no estado de processo REALIZADO."""
    rotulo: str
    corrente: str
    premissa: str
    pior: float
    limite: float
    atende: bool


@dataclass(frozen=True)
class CasoAvaliado:
    """Um caso do BOT no candidato: o que o rating realizou e o que as utilidades ainda exigem.

    `admissivel`, `utilidade_quente` e `utilidade_fria` são o que `sizing/servico.py` espera de
    um caso avaliado — é por eles que a busca aceita ou rejeita o candidato e monta a frente."""
    num: int
    nome: str
    ativo: bool
    estado: str
    admissivel: bool
    motivo: str
    q_alvo: float
    q_realizado: float
    utilidade_quente: float
    utilidade_fria: float
    dp: float
    v: float
    re: float
    u: float
    abaixo_v_min: bool
    dp_casco: float = math.nan      # kPa, lado casco do trem (Bell-Delaware, sem bocais)
    violacoes: tuple = ()           # ((natureza, texto), ...) do caso no feixe instalado


@dataclass(frozen=True)
class Geometria:
    """A geometria de UM trem (os cascos em série dele), já dimensionada e classificada."""
    especificacao: Especificacao
    tubos_por_passe: float
    comprimento_por_casco: float
    cascos_serie: float
    diametro_casco: float
    area_unitaria: float            # área de troca de um trem
    casos: tuple                    # CasoAvaliado, na ordem do balanço
    integracao: object = None       # pfd.integracao.Integracao
    resultado: object = None        # EnvelopeResult do pré-aquecedor
    residuais: dict = None          # {TAG: ResultadoTAG} do aquecedor e do resfriador

    def caso(self, num):
        """O caso avaliado, ou um NÃO admissível se o candidato nem chegou a ser avaliado: a
        varredura genérica pergunta por todos os casos, e um candidato sem geometria tem de
        reprovar, não estourar."""
        return next((c for c in self.casos if c.num == num), NAO_AVALIADO)


NAO_AVALIADO = CasoAvaliado(-1, "", False, "nao_avaliado", False, "candidato sem geometria avaliada",
                            math.nan, math.nan, math.inf, math.inf, math.nan, math.nan, math.nan,
                            math.nan, False)
VAZIA = Geometria(Especificacao(()), math.nan, math.nan, math.nan, math.nan, math.inf, ())


@dataclass(frozen=True)
class Avaliacao:
    """Um candidato avaliado: viabilidade do CONJUNTO e as grandezas de comparação."""
    especificacao: Especificacao
    configuracao: ConfiguracaoServico
    viavel: bool
    motivo: str
    geometria: object = None
    verificacoes: tuple = ()
    ponto_fixo: tuple = ()          # (iterações, convergiu, desvio em K)
    avisos: tuple = ()

    @property
    def chave(self):
        return (self.especificacao, self.configuracao)

    @property
    def casos(self):
        return self.geometria.casos if self.geometria else ()

    @property
    def area_instalada(self):
        return self.configuracao.instaladas * self.geometria.area_unitaria if self.geometria else math.inf

    @property
    def area_operacional(self):
        return self.configuracao.duty_projeto * self.geometria.area_unitaria if self.geometria else math.inf

    @property
    def cascos_instalados(self):
        return self.configuracao.instaladas * self.geometria.cascos_serie if self.geometria else math.inf

    @property
    def recuperacao_alvo(self):
        return sum(c.q_alvo for c in self.casos) if self.casos else math.nan

    @property
    def recuperacao_realizada(self):
        return sum(c.q_realizado for c in self.casos) if self.casos else math.nan

    @property
    def fracao_realizada(self):
        alvo = self.recuperacao_alvo
        return self.recuperacao_realizada / alvo if alvo and alvo > 0 else math.nan

    @property
    def utilidade_quente(self):
        return sum(c.utilidade_quente for c in self.casos) if self.casos else math.inf

    @property
    def utilidade_fria(self):
        return sum(c.utilidade_fria for c in self.casos) if self.casos else math.inf

    @property
    def dp_maximo(self):
        return max((c.dp for c in self.casos if math.isfinite(c.dp)), default=math.nan)

    @property
    def dp_casco_maximo(self):
        return max((c.dp_casco for c in self.casos if math.isfinite(c.dp_casco)), default=math.nan)

    @property
    def casos_abaixo_v_min(self):
        return tuple(c.num for c in self.casos if c.ativo and c.abaixo_v_min)


# ------------------------------------------------------------------ eixos e candidatos
def eixos():
    """{chave: [valores]} dos eixos geométricos, na ordem do TOML."""
    return {k: list(v["valores"]) for k, v in cfg()["eixo"].items() if k not in EIXOS_DE_SERVICO}


def reserva_exigida():
    return float(cfg()["eixo"]["standby"].get("minimo_exigido", 0.0))


def configuracoes_de_servico(duty):
    """Filosofias de serviço com este duty: uma por número de trens de reserva declarado."""
    duty = int(duty)
    for standby in cfg()["eixo"]["standby"]["valores"]:
        yield ConfiguracaoServico(duty + int(standby), duty, int(standby), 1 / duty)


def especificacoes():
    """Produto cartesiano dos eixos geométricos."""
    chaves = list(eixos())
    valores = eixos()
    return [Especificacao(tuple(zip(chaves, c))) for c in product(*(valores[k] for k in chaves))]


def candidatos():
    """[(Especificacao, ConfiguracaoServico)] de todos os candidatos declarados."""
    return [(e, c) for e in especificacoes()
            for c in configuracoes_de_servico(e.dict["cascos_paralelo"])]


# ------------------------------------------------------------------ avaliação de um candidato
def edicoes_de_estudo(ctx, ident):
    """{chave: valor} que a busca aplica a TODO TAG que ela dimensiona (`[estudo]`): o refino
    local da grade e o limite de ΔP do lado casco, lido da premissa declarada."""
    e = cfg().get("estudo", {})
    if ident not in e.get("tags", []):
        return {}
    out = {k: float(v) for k, v in e.get("edicoes", {}).items()}
    if e.get("limite_casco_premissa"):
        out["dp_max_casco"] = float(ctx.prem[e["limite_casco_premissa"]])
    return out


def _estado_do_candidato(ident, esp, ctx=None):
    """EstadoTAG do recuperador com a geometria do candidato como entrada do usuário."""
    est = servico.estado_inicial(ident)
    for chave, valor in {**(edicoes_de_estudo(ctx, ident) if ctx is not None else {}), **esp.dict}.items():
        est.editar(chave, float(valor))
    return est


def estado_residual(ctx, ident):
    """EstadoTAG de um TAG de carga residual na busca: o da sessão com as edições de estudo."""
    est = copy.deepcopy(ctx.estado_tag(ident))
    for chave, valor in edicoes_de_estudo(ctx, ident).items():
        est.editar(chave, float(valor))
    return est


def _casos_avaliados(integracao):
    out = []
    for ci in integracao.casos:
        op = ci.operacao or {}
        out.append(CasoAvaliado(
            ci.num, ci.nome, ci.ativo, ci.estado_rating, (not ci.ativo) or ci.avaliavel,
            "; ".join(ci.avisos), ci.q_alvo, ci.q_realizado,
            sum(l.q_residual for l in ci.lados if l.aquece),
            sum(l.q_residual for l in ci.lados if not l.aquece),
            op.get("dp", math.nan), op.get("v", math.nan), op.get("re", math.nan),
            op.get("u", math.nan), bool(op.get("abaixo_v_min", False)), op.get("dp_casco", math.nan),
            tuple(op.get("violacoes", ()))))
    return tuple(out)


def verificacoes_finais(ctx, integracao):
    """[VerificacaoFinal] das temperaturas finais que a ET exige, conferidas no estado de
    processo REALIZADO de cada caso — não no preliminar."""
    out = []
    for v in cfg()["verificacao_final"]:
        limite = float(ctx.prem[v["premissa"]])
        minimo = v["sentido"] == "minimo"
        valores = [r.T[v["corrente"]] for r in integracao.estados]
        pior = min(valores) if minimo else max(valores)
        atende = pior >= limite if minimo else pior <= limite
        out.append(VerificacaoFinal(v["rotulo"], v["corrente"], v["premissa"], pior, limite, atende))
    return tuple(out)


def avaliar(ctx, esp, configuracao):
    """Avaliacao do candidato: caminho produtivo inteiro; viabilidade só do conjunto integrado."""
    from fpso_siz.pfd import integracao_termica as integ
    c = cfg()
    est = _estado_do_candidato(c["tag"], esp, ctx)
    ctx.fixar_estado(est)
    integracao = ctx.integracao
    pf = (integracao.iteracoes, integracao.convergiu, integracao.desvio_K)

    def recusa(motivo, geo=None, verif=(), avisos=()):
        return Avaliacao(esp, configuracao, False, motivo, geo, verif, pf, tuple(avisos))

    if not integracao.aplicavel:
        return recusa(integracao.motivo)
    r = integracao.resultado.resultado
    casos = _casos_avaliados(integracao)
    v2 = r.derivados_v2
    geo = Geometria(esp, r.x, v2["comprimento_por_casco"], v2["cascos_serie"],
                    r.derivados["d_shell"], v2["area_total"] / max(v2["cascos_paralelo"], 1.0),
                    casos, integracao, r)
    avisos = [a for x in casos for a in ([x.motivo] if x.motivo else [])]
    if not integracao.convergiu:
        return recusa(f"o ponto fixo das propriedades não fechou (desvio {integracao.desvio_K:.3e} K)",
                      geo, (), avisos)
    nao_avaliaveis = [x.num for x in casos if not x.admissivel]
    if nao_avaliaveis:
        return recusa(f"rating não avaliável nos casos {nao_avaliaveis}", geo, (), avisos)
    # o CONJUNTO: aquecedor e resfriador redimensionados pelas cargas RESIDUAIS
    residuais = {t: servico.executar(ctx, estado_residual(ctx, t)) for t in c["tags_integrados"]}
    geo = replace(geo, residuais=residuais)
    verif = verificacoes_finais(ctx, integracao)
    pendentes = [t for t, rt in residuais.items() if not rt.concluido]
    if pendentes:
        return recusa("com as cargas residuais, " + ", ".join(
            f"{t} fica {residuais[t].status}" for t in pendentes), geo, verif, avisos)
    reprovadas = [v.rotulo for v in verif if not v.atende]
    if reprovadas:
        return recusa("temperatura final da ET não alcançada: " + ", ".join(reprovadas), geo, verif, avisos)
    if configuracao.standby < reserva_exigida():
        return recusa("sem a reserva instalada que a ET exige", geo, verif, avisos)
    return Avaliacao(esp, configuracao, True, "", geo, verif, pf, tuple(avisos))


# ------------------------------------------------------------------ busca e frente
def buscar(ctx, especs=None):
    """[Avaliacao] dos candidatos declarados (ou só dos `especs` dados), na ordem dos eixos.

    A varredura é a do contrato genérico de serviço: `buscar_layouts` chama o DESIGN uma vez
    por candidato, o RATING em cada caso e aceita apenas o candidato cujos casos sejam todos
    admissíveis. O que ele aceita é o insumo da frente de Pareto."""
    feitas = {}

    def design(configuracao, esp, _casos):
        av = avaliar(ctx, esp, configuracao)
        feitas[(esp, configuracao)] = av
        return av.geometria or VAZIA

    def avaliar_caso(_configuracao, geometria, caso):
        return geometria.caso(caso)

    especs = list(especificacoes() if especs is None else especs)
    por_duty = {}
    for esp in especs:
        por_duty.setdefault(esp.dict["cascos_paralelo"], []).append(esp)
    for duty, grupo in por_duty.items():
        for esp in grupo:
            nums = [ci.num for ci in (ctx.balanco or [])]
            buscar_layouts(configuracoes_de_servico(duty), [esp], tuple(nums), design, avaliar_caso)
    return [feitas[(e, c)] for e in especs for c in configuracoes_de_servico(e.dict["cascos_paralelo"])]


def frente(avaliacoes):
    """Frente de Pareto física (área instalada, utilidade quente, utilidade fria) entre os
    candidatos VIÁVEIS, pelo mesmo `frente_pareto` do contrato de serviço."""
    pares = [(a, _layout(a)) for a in avaliacoes if a.viavel]
    if not pares:
        return []
    escolhidos = frente_pareto([l for _, l in pares])
    return [a for a, l in pares if any(l is e for e in escolhidos)]


def _layout(av):
    from fpso_siz.sizing.servico import CandidatoLayout
    return CandidatoLayout(av.configuracao, av.geometria, av.casos, av.geometria.area_unitaria,
                           av.utilidade_quente, av.utilidade_fria)


def area_especifica(av):
    """Área INSTALADA por kW recuperado (m²/kW), somando os casos. Infinito quando não há
    recuperação avaliada — um candidato sem recuperação nunca ganha por divisão por zero."""
    r = av.recuperacao_realizada
    if not (math.isfinite(r) and r > 0):
        return math.inf
    return av.area_instalada / r


REGRAS = {
    "area_especifica": lambda a: (area_especifica(a), a.cascos_instalados, -a.recuperacao_realizada),
    "maior_recuperacao": lambda a: (-a.recuperacao_realizada, a.area_instalada, a.cascos_instalados),
}


def com_fonte_no_acervo(avaliacoes):
    """Só os candidatos cujo comprimento máximo de tubo tem fonte no acervo.

    A faixa pedida pelo usuário (6 a 9 m) é VARRIDA e comparada; o que passa de `6 m` repousa
    só no pedido, e não numa fonte do acervo (Branan declara 4 a 20 ft). O candidato que vai
    para o catálogo do TAG fica no que o acervo sustenta — a regra das fontes do projeto. Se
    nenhum candidato cumprir o limite, a lista volta inteira: filtrar até o vazio esconderia
    que a restrição é a que não tem solução."""
    limite = cfg()["selecao"].get("l_tubo_max_com_fonte")
    if limite is None:
        return list(avaliacoes)
    dentro = [a for a in avaliacoes if a.especificacao.dict.get("l_tubo_max", limite) <= limite]
    return dentro or list(avaliacoes)


def selecionar(avaliacoes, regra=None, so_com_fonte=True):
    """O candidato escolhido entre os da FRENTE, pela regra declarada em
    `config/pfd/layout_trocador.toml` (`[selecao] regra`).

    Não é otimização econômica: sem dado de custo no acervo, a troca entre área instalada e
    utilidade é decisão de projeto. As duas regras possíveis estão declaradas no TOML, com o
    que cada uma significa; `regra` permite comparar as duas na mesma rodada. `so_com_fonte`
    restringe ao comprimento de tubo com fonte no acervo (o default, e o que vai ao catálogo);
    com False, a comparação vê a faixa inteira que o usuário pediu."""
    f = frente(avaliacoes)
    if so_com_fonte:
        f = com_fonte_no_acervo(f)
    if not f:
        return None
    nome = regra or cfg()["selecao"]["regra"]
    return min(f, key=REGRAS[nome])


# ------------------------------------------------------------------ geometria CLASSIFICADA (Fase C)
def eixos_classificada():
    """Eixos térmicos da busca classificada: os do P-001 com as substituições de `[classificada]`.
    O empacotamento (cascos em série) não é eixo: sai do caminho total de tubo."""
    e = eixos()
    e.update({k: list(v["valores"]) for k, v in cfg()["classificada"].get("eixo", {}).items()})
    return e


def especificacoes_classificada(l_tubo_max):
    """Geometrias térmicas da busca classificada, com o comprimento máximo por casco dado."""
    e = eixos_classificada()
    e["l_tubo_max"], e["cascos_serie"] = [float(l_tubo_max)], [1.0]
    chaves = list(e)
    return [Especificacao(tuple(zip(chaves, c))) for c in product(*(e[k] for k in chaves))]


def tubos_pela_velocidade(ctx, esp, v):
    """Tubos por passe que dão a velocidade `v` [m/s] no tubo do caso de projeto de UM trem (o de
    maior vazão volumétrica no tubo, a mesma regra da P-45)."""
    est = _estado_do_candidato(cfg()["tag"], esp, ctx)
    e = servico.preparar(ctx, est)
    ativos = [c for c in e.casos if c.ativo]
    if not ativos:
        return math.nan
    vol = max(c.valores["m_tubo"].valor / c.valores["rho_tubo"].valor for c in ativos)
    c0 = ativos[0].valores
    d_i = (c0["d_externo"].valor - 2 * c0["espessura"].valor) / 1000.0
    n = vol / esp.dict["cascos_paralelo"] / (v * math.pi * d_i * d_i / 4)
    return float(max(round(n), 1))


def _empacotar(esp, caminho):
    """Especificação com os cascos em série que o caminho total pede no comprimento máximo dado,
    e o comprimento por casco."""
    d = esp.dict
    serie = max(math.ceil(caminho / d["l_tubo_max"] - 1e-9), 1)
    novo = Especificacao(tuple((k, float(serie) if k == "cascos_serie" else v) for k, v in esp.valores))
    return novo, caminho / serie


def avaliar_classificada(ctx, esp, configuracao, n, caminho):
    """Avaliacao de uma geometria CLASSIFICADA em todos os casos: `n` tubos por passe e caminho
    total de tubo `caminho` [m] por trem, dividido em cascos de até `l_tubo_max`. Nenhum caso
    dimensiona; a recuperação de cada um é a que a geometria entrega, e o que falta vai às
    utilidades. Recusa: integração inválida ou sem ponto fixo, rating não avaliável, e qualquer
    violação HIDRÁULICA ou de DOMÍNIO DA CORRELAÇÃO em qualquer caso. Coeficiente de ΔP não
    validado vira aviso, não recusa."""
    c = cfg()
    esp2, l_casco = _empacotar(esp, caminho)
    est = _estado_do_candidato(c["tag"], esp2, ctx)
    for chave, valor in (("n_min", n), ("n_max", n), ("n_step", 1.0), ("l_instalado", l_casco)):
        est.editar(chave, float(valor))
    ctx.fixar_estado(est)
    integracao = ctx.integracao
    pf = (integracao.iteracoes, integracao.convergiu, integracao.desvio_K)

    def recusa(motivo, geo=None, verif=(), avisos=()):
        return Avaliacao(esp2, configuracao, False, motivo, geo, verif, pf, tuple(avisos))

    if not integracao.aplicavel or integracao.resultado is None or integracao.resultado.resultado is None:
        return recusa(integracao.motivo)
    r = integracao.resultado.resultado
    casos = _casos_avaliados(integracao)
    v2 = r.derivados_v2
    geo = Geometria(esp2, float(n), l_casco, v2["cascos_serie"], r.derivados["d_shell"],
                    v2["area_total"] / max(v2["cascos_paralelo"], 1.0), casos, integracao, r)
    avisos = [f"caso {x.num}: {t}" for x in casos for nat, t in x.violacoes if nat == "nao_validado"]
    if not integracao.convergiu:
        return recusa(f"o ponto fixo das propriedades não fechou (desvio {integracao.desvio_K:.3e} K)", geo)
    nao_avaliaveis = [x.num for x in casos if not x.admissivel]
    if nao_avaliaveis:
        return recusa(f"rating não avaliável nos casos {nao_avaliaveis}", geo)
    violacoes = [f"caso {x.num}: {t}" for x in casos for nat, t in x.violacoes
                 if nat in ("hidraulica", "dominio_correlacao", "verificacao_pendente")]
    if violacoes:
        return recusa("; ".join(violacoes), geo, (), avisos)
    verif = verificacoes_finais(ctx, integracao)
    reprovadas = [v.rotulo for v in verif if not v.atende]
    if reprovadas:
        return recusa("temperatura final da ET não alcançada: " + ", ".join(reprovadas), geo, verif, avisos)
    if configuracao.standby < reserva_exigida():
        return recusa("sem a reserva instalada que a ET exige", geo, verif, avisos)
    return Avaliacao(esp2, configuracao, True, "", geo, verif, pf, tuple(avisos))


def _dp_por_metro(av, caminho):
    """(ΔP do tubo, ΔP do casco) por metro de caminho [kPa/m], o pior caso de cada lado."""
    tubo = max((x.dp for x in av.casos if x.ativo and math.isfinite(x.dp)), default=math.nan)
    casco = max((x.dp_casco for x in av.casos if x.ativo and math.isfinite(x.dp_casco)), default=math.nan)
    return tubo / caminho, casco / caminho


def classificadas(ctx, esp, configuracao, v):
    """[Avaliacao] de uma geometria térmica na velocidade de projeto `v`: o caminho MÁXIMO que cabe
    na P-17 dos dois lados (medido num caminho de referência e reduzido até caber) e as frações
    declaradas dele."""
    k = cfg()["classificada"]
    n = tubos_pela_velocidade(ctx, esp, v)
    if not math.isfinite(n):
        return []
    ref = esp.dict["l_tubo_max"]
    av = avaliar_classificada(ctx, esp, configuracao, n, ref)
    if av.geometria is None or not av.casos:
        return [av]
    dpt, dps = _dp_por_metro(av, ref)
    lim_t = float(ctx.prem[cfg()["estudo"]["limite_casco_premissa"]])
    lim_s = edicoes_de_estudo(ctx, cfg()["tag"]).get("dp_max_casco", lim_t)
    limites = [x for x in (lim_t / dpt if dpt > 0 else math.inf, lim_s / dps if dps > 0 else math.inf)
               if math.isfinite(x)]
    if not limites:
        return [av]
    teto = max(cfg()["eixo"]["cascos_serie"]["valores"]) * ref
    caminho = min(min(limites), teto)
    out = []
    for frac in sorted(k["fracoes_caminho"], reverse=True):
        p = caminho * frac
        a = avaliar_classificada(ctx, esp, configuracao, n, p)
        for _ in range(int(k["max_reducoes"])):
            if a.viavel or not a.casos or not any(nat == "hidraulica" for x in a.casos for nat, _t in x.violacoes):
                break
            p *= float(k["reducao"])
            a = avaliar_classificada(ctx, esp, configuracao, n, p)
        out.append(a)
    return out


def caminho_de(av):
    return av.geometria.comprimento_por_casco * av.geometria.cascos_serie


# ------------------------------------------------------------------ busca RESIDUAL (P-002, P-003)
def eixos_residual():
    return {k: list(v["valores"]) for k, v in cfg()["residual"]["eixo"].items()}


def especificacoes_residual(serie=None, l_max=None):
    e = eixos_residual()
    if serie is not None:
        e["cascos_serie"], e["l_tubo_max"] = [float(serie)], [float(l_max)]
    chaves = list(e)
    return [Especificacao(tuple(zip(chaves, c))) for c in product(*(e[k] for k in chaves))]


@dataclass(frozen=True)
class AvaliacaoResidual:
    """Um aquecedor ou resfriador com a geometria dada, dimensionado nas cargas residuais."""
    tag: str
    especificacao: Especificacao
    resultado: object        # ResultadoTAG

    @property
    def viavel(self):
        return self.resultado.status == servico.DIMENSIONADO

    def _v2(self, chave, padrao=math.nan):
        r = self.resultado.resultado
        return (r.derivados_v2 or {}).get(chave, padrao) if r is not None and r.feasible else padrao

    @property
    def area_operacional(self):
        return self._v2("area_total", math.inf)

    @property
    def area_instalada(self):
        return self._v2("area_instalada", self.area_operacional)

    @property
    def cascos_instalados(self):
        d = self.especificacao.dict
        return d["cascos_serie"] * (d["cascos_paralelo"] + self._v2("trens_reserva", 0.0))

    @property
    def caminho(self):
        r = self.resultado.resultado
        return self.especificacao.dict["cascos_serie"] * r.y if r is not None and r.feasible else math.nan


def avaliar_residual(ctx, ident, esp):
    """O TAG de carga residual com a geometria `esp`, as edições de estudo e o resto do estado da
    sessão: o mesmo serviço por TAG, no estado realizado do recuperador já fixado no contexto."""
    est = estado_residual(ctx, ident)
    for chave, valor in esp.valores:
        est.editar(chave, float(valor))
    return AvaliacaoResidual(ident, esp, servico.executar(ctx, est))


def selecionar_residual(avaliacoes):
    """Menor área instalada entre os viáveis; empate pelo menor número de cascos instalados."""
    viaveis = [a for a in avaliacoes if a.viavel]
    return min(viaveis, key=lambda a: (a.area_instalada, a.cascos_instalados)) if viaveis else None
