"""Rating térmico de geometria instalada finita (ADR 0005; docs/validacao/43).

O Pinch entrega somente ``q_rec_max``, que é limite TERMODINÂMICO. A geometria instalada, as
propriedades do caso e as temperaturas que o próprio Q produz determinam ``q_rating`` por uma
raiz limitada em ``[0, q_rec_max]``, sem cruzamento de temperatura.

Ausência é estado declarado (invariante 5), nunca zero disfarçado. O resultado diz, em
``estado``, qual das quatro situações é a do caso:

``limitado_pelo_alvo``   a área instalada transferiria MAIS do que o alvo do Pinch; quem
                         limita é a termodinâmica, e ``q_real = q_rec_max``;
``limitado_pela_area``   a raiz é interior: a área instalada entrega menos que o alvo, e a
                         diferença é recuperação NÃO realizada, que o processo continua
                         exigindo das utilidades;
``sem_forca_motriz``     o lado quente não entra acima do frio — não há calor a recuperar, e
                         ``q_real = 0`` é resultado, não falta de dado;
``nao_avaliavel``        o U·A do caso não pôde ser avaliado (propriedade ausente, película
                         fora da correlação declarada). ``q_rating`` e ``q_real`` são NaN e o
                         motivo vai em ``motivo``. NÃO se devolve zero: zero afirmaria que a
                         geometria não troca calor, o que não foi calculado.
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.sizing.lmtd import lmtd

LIMITADO_PELO_ALVO = "limitado_pelo_alvo"
LIMITADO_PELA_AREA = "limitado_pela_area"
SEM_FORCA_MOTRIZ = "sem_forca_motriz"
NAO_AVALIAVEL = "nao_avaliavel"


@dataclass(frozen=True)
class CasoRating:
    t_fria_in: float
    t_quente_in: float
    c_fria: float
    c_quente: float
    q_rec_max: float


@dataclass(frozen=True)
class ResultadoRating:
    q_rec_max: float
    q_rating: float
    q_real: float
    t_fria_out: float
    t_quente_out: float
    ua: float
    fator_f: float
    dt_lm: float
    recuperacao_nao_realizada: float
    convergiu: bool
    iteracoes: int
    estado: str = LIMITADO_PELA_AREA
    motivo: str = ""

    @property
    def avaliavel(self):
        return self.estado != NAO_AVALIAVEL

    @property
    def fracao_do_alvo(self):
        """q_real/q_rec_max; NaN quando não avaliável e 1 quando não há alvo a realizar."""
        if not self.avaliavel:
            return math.nan
        if not self.q_rec_max > 0:
            return 1.0
        return self.q_real / self.q_rec_max


class _NaoAvaliavel(Exception):
    """U·A não avaliável no ponto — propaga como estado, nunca como zero."""


def _cfg():
    return carregar("equipment/comum/servico.toml")["rating"]


def _estado(caso, q, ua, fator):
    tc = caso.t_fria_in + q / caso.c_fria
    th = caso.t_quente_in - q / caso.c_quente
    dt = lmtd(caso.t_quente_in - tc, th - caso.t_fria_in)
    u = ua(q, tc, th)
    if not (isinstance(u, float) or isinstance(u, int)) or not math.isfinite(u) or u < 0:
        raise _NaoAvaliavel(f"U·A não avaliável em Q = {q:.6g} W (valor {u!r})")
    return tc, th, u, fator(q, tc, th), dt


def _sem_transferencia(caso, ua, fator, estado, motivo):
    """Resultado com Q = 0 (ou NaN), com o estado declarado e sem inventar temperaturas."""
    nulo = estado == NAO_AVALIAVEL
    try:
        tc, th, u, f, dt = _estado(caso, 0.0, ua, fator)
    except _NaoAvaliavel as e:
        nulo, motivo = True, motivo or str(e)
        tc = caso.t_fria_in
        th = caso.t_quente_in
        u = f = dt = math.nan
    q = math.nan if nulo else 0.0
    nao_realizada = math.nan if nulo else caso.q_rec_max
    return ResultadoRating(caso.q_rec_max, q, q, tc, th, u, f, dt, nao_realizada, True, 0,
                           NAO_AVALIAVEL if nulo else estado, motivo)


def rating(caso, ua, fator=lambda q, tc, th: 1.0):
    """Resolve ``Q = UA(Q)·F(Q)·ΔT_lm(Q)`` por bisseção limitada por ``[0, q_rec_max]``.

    ``ua`` e ``fator`` recebem Q e as duas temperaturas de saída, de modo que propriedades,
    Reynolds, películas e F sejam REAVALIADOS em cada iteração — o U não é congelado no ponto
    de projeto. ``ua`` que devolva valor não finito é ausência declarada (``nao_avaliavel``),
    não transferência nula; ``F`` ou ``ΔT_lm`` não finitos são recusa de DOMÍNIO naquele Q (o
    arranjo não fecha, ou haveria cruzamento), e a bisseção procura o Q em que fecham.
    """
    cfg = _cfg()
    tol = float(cfg["tolerancia_relativa"])
    maxit = int(cfg["max_iteracoes"])
    margem = float(cfg["margem_temperatura_K"])
    if not (caso.c_fria > 0 and caso.c_quente > 0):
        raise ValueError("capacidades térmicas do rating devem ser positivas e finitas")
    if not caso.q_rec_max >= 0:
        raise ValueError("alvo de recuperação do rating deve ser finito e não negativo")
    aproximacao = caso.t_quente_in - caso.t_fria_in
    if not math.isfinite(aproximacao):
        return _sem_transferencia(caso, ua, fator, NAO_AVALIAVEL,
                                  "temperaturas de entrada não finitas: a força motriz não pôde ser avaliada")
    q_cruzamento = max(0.0, aproximacao - margem) * min(caso.c_fria, caso.c_quente)
    hi = min(caso.q_rec_max, q_cruzamento)
    if not hi > 0:
        motivo = ("o lado quente não entra acima do lado frio" if aproximacao <= margem
                  else "o alvo de recuperação do caso é nulo")
        return _sem_transferencia(caso, ua, fator, SEM_FORCA_MOTRIZ, motivo)

    def residuo(q):
        tc, th, u, f, dt = _estado(caso, q, ua, fator)
        # F ou ΔT_lm não finitos: naquele Q o arranjo não fecha (recusa de DOMÍNIO). A
        # transferência ali é tratada como nula para que a bisseção ande para Q menor — não é
        # afirmação sobre a geometria, e por isso NÃO vira resultado por si só.
        transferencia = u * f * dt if all(math.isfinite(v) and v >= 0 for v in (f, dt)) else 0.0
        return transferencia - q, (tc, th, u, f, dt)

    try:
        r_hi, estado_hi = residuo(hi)
        if r_hi >= 0:   # a área instalada daria mais: quem limita é o alvo termodinâmico
            tc, th, u, f, dt = estado_hi
            q_real = min(caso.q_rec_max, hi)
            return ResultadoRating(caso.q_rec_max, hi, q_real, tc, th, u, f, dt,
                                   caso.q_rec_max - q_real, True, 0, LIMITADO_PELO_ALVO,
                                   "a geometria instalada transferiria mais do que o alvo do Pinch")
        lo, q, estado, convergiu, it = 0.0, 0.0, residuo(0.0)[1], False, 0
        for it in range(1, maxit + 1):
            meio = (lo + hi) / 2
            r, atual = residuo(meio)
            q, estado = meio, atual
            if abs(r) <= tol * max(1.0, meio):
                convergiu = True
                break
            if r > 0:
                lo = meio
            else:
                hi = meio
    except _NaoAvaliavel as e:
        return _sem_transferencia(caso, ua, fator, NAO_AVALIAVEL, str(e))
    tc, th, u, f, dt = estado
    q_real = min(caso.q_rec_max, q)
    return ResultadoRating(caso.q_rec_max, q, q_real, tc, th, u, f, dt,
                           caso.q_rec_max - q_real, convergiu, it, LIMITADO_PELA_AREA,
                           "a raiz é interior: a área instalada entrega menos que o alvo")


@dataclass(frozen=True)
class BalancoIntegrado:
    rating: ResultadoRating
    q_p002: float
    q_p003: float
    utilidade_quente_residual: float
    utilidade_fria_residual: float


def integrar(caso, resultado, t_tratamento, t_estocagem):
    """Propaga o Q realizado às utilidades, sem alterar massa nem capacidade térmica.

    O destino de cada lado é a PREMISSA (temperatura de tratamento, temperatura de
    estocagem), como em `pfd/pinch.py`: é isso que faz a utilidade residual ser o que o
    processo ainda exige, e não o que o arranjo já fez. Rating não avaliável propaga NaN —
    não se declara utilidade residual sobre um Q que não foi calculado."""
    if not resultado.avaliavel:
        return BalancoIntegrado(resultado, math.nan, math.nan, math.nan, math.nan)
    qh = max(0.0, caso.c_fria * (t_tratamento - resultado.t_fria_out))
    qc = max(0.0, caso.c_quente * (resultado.t_quente_out - t_estocagem))
    return BalancoIntegrado(resultado, qh, qc, qh, qc)
