"""Rating térmico de geometria instalada finita.

O Pinch entrega somente ``q_rec_max``. A geometria, as propriedades do caso e as
temperaturas que o próprio Q produz determinam ``q_rating`` por uma raiz limitada.
"""
import math
from dataclasses import dataclass, replace

from fpso_siz.core.configuracao import carregar
from fpso_siz.sizing.trocador import lmtd
from fpso_siz.sizing.trocador import avaliar_geometria


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


def _estado(caso, q, ua, fator):
    tc = caso.t_fria_in + q / caso.c_fria
    th = caso.t_quente_in - q / caso.c_quente
    dt = lmtd(caso.t_quente_in - tc, th - caso.t_fria_in)
    return tc, th, ua(q, tc, th), fator(q, tc, th), dt


def rating(caso, ua, fator=lambda q, tc, th: 1.0):
    """Resolve ``Q = UA(Q) F(Q) LMTD(Q)`` por bisseção robusta.

    ``ua`` e ``fator`` recebem Q e as duas temperaturas de saída, permitindo que
    propriedades, Reynolds, películas e F sejam reavaliados em cada iteração.
    """
    cfg = carregar("equipment/comum/servico.toml")["rating"]
    tol = float(cfg["tolerancia_relativa"])
    maxit = int(cfg["max_iteracoes"])
    margem = float(cfg["margem_temperatura_K"])
    if caso.c_fria <= 0 or caso.c_quente <= 0 or caso.q_rec_max < 0:
        raise ValueError("capacidades térmicas e alvo de recuperação inválidos")
    aproximacao = caso.t_quente_in - caso.t_fria_in
    q_cruzamento = max(0, aproximacao - margem) * min(caso.c_fria, caso.c_quente)
    hi = min(caso.q_rec_max, q_cruzamento)
    if hi <= 0:
        tc, th, u, f, dt = _estado(caso, 0, ua, fator)
        return ResultadoRating(caso.q_rec_max, 0, 0, tc, th, u, f, dt,
                               caso.q_rec_max, True, 0)

    def residuo(q):
        tc, th, u, f, dt = _estado(caso, q, ua, fator)
        transferencia = u * f * dt if all(math.isfinite(v) and v >= 0 for v in (u, f, dt)) else 0
        return transferencia - q, (tc, th, u, f, dt)

    r_hi, estado_hi = residuo(hi)
    if r_hi >= 0:
        q, estado, it = hi, estado_hi, 0
    else:
        lo, q, estado = 0, 0, residuo(0)[1]
        for it in range(1, maxit + 1):
            meio = (lo + hi) / 2
            r, atual = residuo(meio)
            q, estado = meio, atual
            if abs(r) <= tol * max(1, meio):
                break
            if r > 0:
                lo = meio
            else:
                hi = meio
    tc, th, u, f, dt = estado
    q_real = min(caso.q_rec_max, q)
    return ResultadoRating(caso.q_rec_max, q, q_real, tc, th, u, f, dt,
                           caso.q_rec_max - q_real, it == 0 or it < maxit, it)


@dataclass(frozen=True)
class BalancoIntegrado:
    rating: ResultadoRating
    q_p002: float
    q_p003: float
    utilidade_quente_residual: float
    utilidade_fria_residual: float


def integrar(caso, resultado, t_tratamento, t_estocagem):
    """Propaga o Q realizado a P-002/P-003 sem alterar massa ou energia."""
    qh = max(0, caso.c_fria * (t_tratamento - resultado.t_fria_out))
    qc = max(0, caso.c_quente * (resultado.t_quente_out - t_estocagem))
    return BalancoIntegrado(resultado, qh, qc, qh, qc)


def rating_saari(metodo, entrada, parametros, geometria, q_rec_max):
    """Adapta uma geometria Saari fixa ao solver, reavaliando U e F em cada Q."""
    c_fria = entrada.m_tubo * entrada.cp_tubo
    c_quente = entrada.m_casco * entrada.cp_casco
    caso = CasoRating(entrada.t_tubo_in, entrada.t_casco_in, c_fria, c_quente,
                      q_rec_max)
    constantes = metodo.constants()

    def estado(q, tc, th):
        if q <= 0:
            eps = carregar("equipment/comum/servico.toml")["rating"]["carga_semente_W"]
            q = min(float(eps), q_rec_max)
            tc = entrada.t_tubo_in + q / c_fria
        e = replace(entrada, t_tubo_out=tc)
        ok, cons, _ = metodo.sizing_constraints(e, parametros, constantes)
        if not ok:
            return None, None
        desempenho = avaliar_geometria(cons, geometria)
        return desempenho, cons

    def ua(q, tc, th):
        desempenho, _ = estado(q, tc, th)
        return desempenho["ua"] if desempenho and desempenho["ok"] else math.nan

    def fator(q, tc, th):
        _, cons = estado(q, tc, th)
        return cons.f if cons is not None else math.nan

    return rating(caso, ua, fator)
