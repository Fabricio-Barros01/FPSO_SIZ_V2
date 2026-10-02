"""Integração térmica REALIZADA: o que o pré-aquecedor entrega de fato, e o que sobra para o
aquecedor e para o resfriador (ADR 0005; docs/validacao/43).

O balanço preliminar fixa a carga do pré-aquecedor como máxima recuperação na aproximação P-32
— alvo TERMODINÂMICO, o mesmo que a Análise Pinch devolve. A geometria instalada é finita: ela
realiza o alvo no caso de PROJETO e menos que isso nos casos de turndown, onde o óleo cai no
laminar e o U despenca. O que ela não realiza continua exigido do processo, e é esse resíduo
que dimensiona o aquecedor e o resfriador.

Três coisas fazem esta camada ser honesta:

- o DESTINO de cada lado é a PREMISSA (temperatura de tratamento, de estocagem), não a
  temperatura que o arranjo realizou — a mesma decisão de `pfd/pinch.py`;
- as PROPRIEDADES são reavaliadas na temperatura média REALIZADA, por ponto fixo: o rating
  muda a saída, a saída muda µ(T) e ρ(T), e com elas Reynolds, película e U. O U não é o do
  ponto de projeto;
- nada do balanço é reescrito além da carga recuperada, das duas saídas do pré-aquecedor e das
  duas cargas de utilidade, e isso é VERIFICADO caso a caso. Se num caso a saída realizada
  cruzar o destino da premissa, o reciclo do balanço mudaria — e aí o caso sai com aviso
  declarado, sem o balanço ser reaberto por conta própria.

Nenhuma corrente, carga ou premissa é nomeada neste módulo: tudo vem de
`config/pfd/integracao.toml`.
"""
import math
from dataclasses import dataclass, replace

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import w_para_kw
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd.tags import tag
from fpso_siz.sizing.rating import NAO_AVALIAVEL

# estado do caso no pré-aquecedor, do ponto de vista da integração. Os quatro primeiros são os
# do rating (sizing/rating.py); este é o do caso que não tem carga a recuperar — o óleo já
# chega à temperatura de tratamento e o TAG está inativo nele.
SEM_CARGA = "sem_carga"
# caso em que o recuperador foi declarado fora de operação (cenário explícito de bypass): Q_real = 0
BYPASS = "bypass"
# cenário da integração inteira (Fase C, nota 46)
REALIZADA, CENARIO_BYPASS, INVALIDA, TRIVIAL = "realizada", "bypass", "invalida", "sem_carga"


def cfg():
    return carregar("pfd/integracao_termica.toml")


@dataclass(frozen=True)
class LadoIntegrado:
    """Um lado do pré-aquecedor num caso: alvo, realizado e a utilidade que ainda falta."""
    id: str
    rotulo: str
    sentido: str               # "aquecer" (lado frio) | "resfriar" (lado quente)
    capacidade: float          # kW/K (a do balanço)
    t_in: float
    t_out_alvo: float
    t_out_real: float
    t_destino: float
    t_destino_alvo: float      # a temperatura de destino que o balanço preliminar escreveu
    carga_residual: str
    tag_residual: str
    q_residual_preliminar: float   # kW, do balanço preliminar
    q_residual: float              # kW, com a saída realizada
    destino_cruzado: bool

    @property
    def aquece(self):
        return self.sentido == "aquecer"


@dataclass(frozen=True)
class CasoIntegrado:
    num: int
    nome: str
    ativo: bool
    motivo: str
    estado_rating: str
    q_alvo: float              # kW — alvo do Pinch (o Q_pre do balanço preliminar)
    q_realizado: float         # kW
    lados: tuple
    operacao: dict             # v, Re, U, ΔP, película, alertas do caso no feixe instalado
    avisos: tuple

    @property
    def q_nao_recuperado(self):
        return self.q_alvo - self.q_realizado

    @property
    def fracao_realizada(self):
        if not self.q_alvo > 0:
            return 1.0
        return self.q_realizado / self.q_alvo

    @property
    def avaliavel(self):
        return self.estado_rating != NAO_AVALIAVEL

    @property
    def dimensionante(self):
        """Este caso é o que dimensiona a geometria (o caso de projeto)?"""
        return self.operacao.get("dimensiona", False)

    def lado(self, ident):
        return next(l for l in self.lados if l.id == ident)


@dataclass(frozen=True)
class Integracao:
    """O pré-aquecedor no ponto fixo, os casos integrados e o estado de processo realizado."""
    resultado: object          # ResultadoTAG do TAG recuperador (None se não dimensionado)
    casos: tuple               # CasoIntegrado, na ordem do balanço
    estados: tuple             # EstadoProcesso realizado, na ordem do balanço
    iteracoes: int
    convergiu: bool
    desvio_K: float
    aplicavel: bool
    motivo: str = ""
    cenario: str = REALIZADA    # realizada | bypass | invalida | sem_carga

    @property
    def valida(self):
        """A avaliação integrada descreve um estado operacional avaliado? Inválida = o
        recuperador não tem geometria avaliada e ninguém declarou o bypass."""
        return self.cenario != INVALIDA

    def caso(self, num):
        return next(c for c in self.casos if c.num == num)

    @property
    def q_alvo_total(self):
        return sum(c.q_alvo for c in self.casos)

    @property
    def q_realizado_total(self):
        return sum(c.q_realizado for c in self.casos)

    def residual_total(self, carga):
        return sum(l.q_residual for c in self.casos for l in c.lados if l.carga_residual == carga)


# ------------------------------------------------------------------ ponto fixo
def _temperaturas_realizadas(rt, lados):
    """{num do caso: {corrente de saída: T realizada}} do resultado do TAG recuperador."""
    op = _operacao_por_caso(rt)
    out = {}
    for num, o in op.items():
        r = o.get("rating") or {}
        if not r.get("avaliavel", False):
            continue
        valores = {"tubo": r.get("t_tubo_out"), "casco": r.get("t_casco_out")}
        temps = {l["saida"]: valores[l["id"]] for l in lados
                 if l["id"] in valores and valores[l["id"]] is not None
                 and math.isfinite(valores[l["id"]])}
        if temps:
            out[num] = temps
    return out


def _operacao_por_caso(rt):
    """{num do caso: operação} do TAG no feixe escolhido, lida do que o motor já avaliou."""
    r = rt.resultado
    if r is None or not r.feasible or r.metodo is None or r.p_env is None:
        return {}
    cons = [c for _, _, c, _ in r.preparo]
    if any(c is None for c in cons) or not hasattr(r.metodo, "operacao_por_caso"):
        return {}
    nomes = [n for n, *_ in r.preparo]
    ativos = [c.num for c in rt.entradas.casos if c.ativo]
    por_nome = dict(zip(nomes, r.metodo.operacao_por_caso(cons, r.x, list(r.pcs))))
    return dict(zip(ativos, (por_nome[n] for n in nomes)))


def dimensionar_recuperador(ctx, estado=None, max_iteracoes=None):
    """(ResultadoTAG, temperaturas, iterações, convergiu, desvio) do TAG recuperador no ponto
    fixo das propriedades. Cada passagem reprepara as entradas com as propriedades avaliadas na
    temperatura média REALIZADA da passagem anterior e redimensiona."""
    c = cfg()
    it_cfg = c["iteracao"]
    tol = float(it_cfg["tolerancia_K"])
    maxit = int(max_iteracoes if max_iteracoes is not None else it_cfg["max_iteracoes"])
    t = tag(c["tag_recuperador"])
    est = estado if estado is not None else ctx.estado_tag(t.tag)
    temps, rt, desvio, it = {}, None, math.inf, 0
    for it in range(1, maxit + 1):
        rt = servico.dimensionar(servico.preparar_tag(ctx, t, est, temperaturas=temps), est)
        if rt.status != servico.DIMENSIONADO:
            return rt, temps, it, True, 0.0
        novas = _temperaturas_realizadas(rt, c["lado"])
        desvio = max((abs(v - temps.get(num, {}).get(corrente, math.inf))
                      for num, d in novas.items() for corrente, v in d.items()), default=0.0)
        temps = novas
        if desvio <= tol:
            return rt, temps, it, True, desvio
    return rt, temps, it, False, desvio


# ------------------------------------------------------------------ integração por caso
def _lado_integrado(spec, r, prem, q_real, avisos):
    """LadoIntegrado de um lado do pré-aquecedor no caso `r`, com a carga realizada `q_real`."""
    sentido = 1.0 if spec["sentido"] == "aquecer" else -1.0
    capacidade = r.C(r.streams[spec["capacidade"]])
    t_in = r.T[spec["entrada"]]
    t_out_alvo = r.T[spec["saida"]]
    t_destino = float(prem[spec["destino_premissa"]])
    t_out_real = t_in + sentido * q_real / capacidade if capacidade > 0 else t_in
    # o destino é PISO para quem aquece e TETO para quem resfria: é o que o balanço escreve
    atingido_alvo = max(t_destino, t_out_alvo) if sentido > 0 else min(t_destino, t_out_alvo)
    atingido_real = max(t_destino, t_out_real) if sentido > 0 else min(t_destino, t_out_real)
    q_prelim = capacidade * sentido * (atingido_alvo - t_out_alvo)
    q_res = capacidade * sentido * (atingido_real - t_out_real)
    # A integração realizada só é absorvida pelo balanço preliminar enquanto a temperatura de
    # DESTINO não muda: é ela que o balanço propaga adiante (T_08 alimenta o reciclo, T_24 sai
    # da planta). Se ela mudar, o reciclo mudaria — e isso é aviso declarado, não silêncio.
    tol = float(cfg()["iteracao"]["tolerancia_K"])
    cruzado = math.isfinite(atingido_real) and abs(atingido_real - atingido_alvo) > tol
    if cruzado:
        chave = "destino_frio" if sentido > 0 else "destino_quente"
        avisos.append(cfg()["avisos"][chave].format(t_real=f"{t_out_real:.2f}",
                                                    t_destino=f"{t_destino:.2f}"))
    return LadoIntegrado(spec["id"], spec["rotulo"], spec["sentido"], capacidade, t_in, t_out_alvo,
                         t_out_real, t_destino, atingido_alvo, spec["carga_residual"],
                         spec["tag_residual"], q_prelim, q_res, cruzado)


def _caso_integrado(spec_lados, r, prem, nome, operacao, ativo, motivo, nome_tag):
    avisos = []
    rat = (operacao or {}).get("rating") or {}
    estado = rat.get("estado", "")
    q_alvo = float(r.duties[cfg()["carga_recuperada"]])
    if not ativo:
        # caso sem carga no pré-aquecedor: o alvo é nulo e o realizado é nulo — resultado, não
        # lacuna. As utilidades residuais são as do balanço preliminar.
        q_real, estado = 0.0, SEM_CARGA
    elif estado == BYPASS:
        q_real = 0.0
    elif estado == NAO_AVALIAVEL or not rat:
        avisos.append(cfg()["avisos"]["nao_avaliavel"].format(motivo=rat.get("motivo", "sem rating")))
        q_real = math.nan
    else:
        q_real = w_para_kw(float(rat["q_realizado"]))
    lados = tuple(_lado_integrado(s, r, prem, q_real, avisos) for s in spec_lados)
    return CasoIntegrado(r.num, nome, ativo, motivo, estado or NAO_AVALIAVEL, q_alvo, q_real,
                         lados, dict(operacao or {}), tuple(avisos))


def estado_realizado(r, ci, nome_tag):
    """EstadoProcesso com a carga recuperada, as saídas do pré-aquecedor e as utilidades
    substituídas pelas REALIZADAS, e com a proveniência de cada substituição declarada."""
    c = cfg()
    notas = c["notas"]
    if not ci.ativo or not ci.avaliavel:
        return r
    T, duties = dict(r.T), dict(r.duties)
    duties[c["carga_recuperada"]] = ci.q_realizado
    integ = {c["carga_recuperada"]: notas["carga"].format(tag=nome_tag)}
    especificacoes = {s["id"]: s for s in c["lado"]}
    for l in ci.lados:
        spec = especificacoes[l.id]
        T[spec["saida"]] = l.t_out_real
        T[spec["corrente_destino"]] = (max(l.t_destino, l.t_out_real) if spec["sentido"] == "aquecer"
                                       else min(l.t_destino, l.t_out_real))
        for corrente in spec["correntes_no_destino"]:
            T[corrente] = T[spec["corrente_destino"]]
        duties[l.carga_residual] = l.q_residual
        integ[spec["saida"]] = notas["temperatura"].format(tag=nome_tag)
        integ[l.carga_residual] = notas["residual"].format(tag=nome_tag)
    return replace(r, T=T, duties=duties, integracao=integ)


def integrar(ctx, estado=None):
    """Integração realizada da planta: dimensiona o TAG recuperador no ponto fixo e devolve os
    casos integrados e o estado de processo realizado de cada caso."""
    c = cfg()
    nome_tag = c["tag_recuperador"]
    est = estado if estado is not None else ctx.estado_tag(nome_tag)
    if est.modo != servico.AUTOMATICO:
        # entradas manuais não vêm do balanço: não há alvo do Pinch a classificar, e tocar o
        # balanço aqui o resolveria sem ninguém ter pedido (uma planta só manual não o resolve)
        return Integracao(None, (), (), 0, True, 0.0, False,
                          c["avisos"]["manual"].format(tag=nome_tag), INVALIDA)
    rt, _temps, it, convergiu, desvio = dimensionar_recuperador(ctx, est)
    balanco = ctx.balanco
    if rt.status == servico.INATIVO:     # nenhum caso tem carga a recuperar: integração trivial
        casos = tuple(_caso_integrado(c["lado"], r, ctx.prem, ce.nome, None, False, ce.motivo, nome_tag)
                      for r, ce in zip(balanco, rt.entradas.casos))
        return Integracao(rt, casos, tuple(balanco), it, True, 0.0, True, c["cenarios"][TRIVIAL], TRIVIAL)
    if rt.status != servico.DIMENSIONADO:
        status = c["estados"].get(rt.status, rt.status)
        if getattr(ctx, "cenario_recuperador", None) == CENARIO_BYPASS:
            return _integracao_bypass(ctx, rt, balanco, nome_tag, status)
        motivo = c["avisos"]["nao_dimensionado"].format(tag=nome_tag, status=status)
        return Integracao(rt, (), tuple(balanco), it, True, 0.0, False, motivo, INVALIDA)
    operacoes = _operacao_por_caso(rt)
    ativos = {ce.num: ce for ce in rt.entradas.casos}
    casos = []
    for r in balanco:
        ce = ativos.get(r.num)
        ativo = bool(ce and ce.ativo)
        ci = _caso_integrado(c["lado"], r, ctx.prem, ce.nome if ce else "", operacoes.get(r.num),
                             ativo, ce.motivo if ce else "", nome_tag)
        if not convergiu and ativo:
            ci = replace(ci, avisos=ci.avisos + (
                c["avisos"]["sem_ponto_fixo"].format(iteracoes=it, desvio=f"{desvio:.3e}"),))
        casos.append(ci)
    estados = tuple(estado_realizado(r, ci, nome_tag) for r, ci in zip(balanco, casos))
    return Integracao(rt, tuple(casos), estados, it, convergiu, desvio, True)


def _integracao_bypass(ctx, rt, balanco, nome_tag, status):
    """Cenário EXPLÍCITO de bypass: o recuperador declarado fora de operação. Q_real = 0 nos casos
    com carga; as saídas do pré-aquecedor ficam nas de entrada e as utilidades recebem a carga
    inteira — o estado operacional que de fato se avalia, e não a recuperação preliminar."""
    c = cfg()
    ativos = {ce.num: ce for ce in rt.entradas.casos}
    casos = []
    for r in balanco:
        ce = ativos.get(r.num)
        ativo = bool(ce and ce.ativo)
        casos.append(_caso_integrado(c["lado"], r, ctx.prem, ce.nome if ce else "",
                                     {"rating": {"estado": BYPASS}} if ativo else None,
                                     ativo, ce.motivo if ce else "", nome_tag))
    estados = tuple(estado_realizado(r, ci, nome_tag) for r, ci in zip(balanco, casos))
    motivo = c["avisos"]["bypass"].format(tag=nome_tag, status=status)
    return Integracao(rt, tuple(casos), estados, 0, True, 0.0, True, motivo, CENARIO_BYPASS)
