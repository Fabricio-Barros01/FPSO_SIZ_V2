"""Rating térmico de geometria instalada finita.

O Pinch entrega somente ``q_rec_max``. A geometria, as propriedades do caso e as
temperaturas que o próprio Q produz determinam ``q_rating`` por uma raiz limitada.
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.sizing.trocador import lmtd


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
    estado: str
    mensagem: str
    diagnostico: dict

    @property
    def avaliavel(self):
        return self.estado != "nao_avaliavel"


@dataclass(frozen=True)
class _EstadoRating:
    t_fria_out: float
    t_quente_out: float
    ua: float
    fator_f: float
    dt_lm: float
    avaliavel: bool
    mensagem: str = ""
    diagnostico: dict = None


def _estado(caso, q, ua, fator):
    tc = caso.t_fria_in + q / caso.c_fria
    th = caso.t_quente_in - q / caso.c_quente
    if not all(math.isfinite(v) for v in (q, tc, th)):
        return _EstadoRating(tc, th, math.nan, math.nan, math.nan, False,
                            "temperaturas intermediárias não finitas")
    if hasattr(ua, "avaliar"):
        u, f, diagnostico = ua.avaliar(q, tc, th)
    else:
        u, f, diagnostico = ua(q, tc, th), fator(q, tc, th), {}
    dt = lmtd(caso.t_quente_in - tc, th - caso.t_fria_in)
    valores = (("UA", u), ("fator F", f), ("LMTD", dt))
    invalidos = [nome for nome, valor in valores if not math.isfinite(valor)]
    if invalidos:
        return _EstadoRating(tc, th, u, f, dt, False,
                            f"propriedade não finita: {', '.join(invalidos)}", diagnostico)
    if any(valor < 0 for _, valor in valores):
        return _EstadoRating(tc, th, u, f, dt, False,
                            "UA, fator F e LMTD devem ser não negativos", diagnostico)
    return _EstadoRating(tc, th, u, f, dt, True, "", diagnostico)


def _resultado(caso, q, estado, situacao, mensagem, iteracoes):
    convergiu = situacao in ("sem_carga", "convergido")
    if situacao == "nao_avaliavel":
        q_real = math.nan
        recuperacao = math.nan
    else:
        q_real = min(caso.q_rec_max, q)
        recuperacao = caso.q_rec_max - q_real
    return ResultadoRating(caso.q_rec_max, q, q_real, estado.t_fria_out,
                           estado.t_quente_out, estado.ua, estado.fator_f, estado.dt_lm,
                           recuperacao, convergiu, iteracoes, situacao, mensagem,
                           estado.diagnostico or {})


def rating(caso, ua, fator=lambda q, tc, th: 1.0):
    """Resolve ``Q = UA(Q) F(Q) LMTD(Q)`` por bisseção robusta.

    ``ua`` e ``fator`` recebem Q e as duas temperaturas de saída. Alternativamente,
    ``ua`` pode ser um avaliador de geometria fixa com método ``avaliar``; nesse caso
    UA, F e o diagnóstico físico são obtidos na mesma avaliação de cada ponto da raiz.
    """
    cfg = carregar("equipment/comum/servico.toml")["rating"]
    tol = float(cfg["tolerancia_relativa"])
    maxit = int(cfg["max_iteracoes"])
    margem = float(cfg["margem_temperatura_K"])
    entradas = (caso.t_fria_in, caso.t_quente_in, caso.c_fria, caso.c_quente,
                caso.q_rec_max)
    if not all(math.isfinite(v) for v in entradas):
        vazio = _EstadoRating(caso.t_fria_in, caso.t_quente_in, math.nan, math.nan,
                              math.nan, False, "entrada não finita")
        return _resultado(caso, math.nan, vazio, "nao_avaliavel",
                          "caso não avaliável: temperatura, capacidade térmica ou carga não finita", 0)
    if caso.c_fria <= 0 or caso.c_quente <= 0 or caso.q_rec_max < 0:
        raise ValueError("capacidades térmicas e alvo de recuperação inválidos")
    aproximacao = caso.t_quente_in - caso.t_fria_in
    q_cruzamento = max(0, aproximacao - margem) * min(caso.c_fria, caso.c_quente)
    hi = min(caso.q_rec_max, q_cruzamento)
    if hi <= 0:
        estado = _estado(caso, 0, ua, fator)
        if not estado.avaliavel:
            return _resultado(caso, math.nan, estado, "nao_avaliavel", estado.mensagem, 0)
        situacao = "sem_carga" if caso.q_rec_max == 0 else "convergido"
        mensagem = "caso sem carga térmica" if situacao == "sem_carga" else "carga limitada a zero pelo não cruzamento"
        return _resultado(caso, 0, estado, situacao, mensagem, 0)

    def residuo(q):
        estado = _estado(caso, q, ua, fator)
        if not estado.avaliavel:
            return math.nan, estado
        return estado.ua * estado.fator_f * estado.dt_lm - q, estado

    r_hi, estado_hi = residuo(hi)
    if not estado_hi.avaliavel:
        return _resultado(caso, math.nan, estado_hi, "nao_avaliavel", estado_hi.mensagem, 0)
    if r_hi >= 0:
        return _resultado(caso, hi, estado_hi, "convergido",
                          "alvo ou limite de não cruzamento atingido", 0)

    lo = 0
    estado = estado_hi
    q = hi
    convergiu = False
    for it in range(1, maxit + 1):
        q = (lo + hi) / 2
        r, estado = residuo(q)
        if not estado.avaliavel:
            return _resultado(caso, math.nan, estado, "nao_avaliavel", estado.mensagem, it)
        if abs(r) <= tol * max(1, q):
            convergiu = True
            break
        if r > 0:
            lo = q
        else:
            hi = q
    situacao = "convergido" if convergiu else "nao_convergido"
    mensagem = ("critério de resíduo satisfeito" if convergiu else
                f"critério de resíduo não satisfeito após {maxit} iterações")
    return _resultado(caso, q, estado, situacao, mensagem, it)


@dataclass(frozen=True)
class BalancoIntegrado:
    rating: ResultadoRating
    q_p002: float
    q_p003: float
    utilidade_quente_residual: float
    utilidade_fria_residual: float


def integrar(caso, resultado, t_tratamento, t_estocagem):
    """Propaga o Q realizado a P-002/P-003 sem alterar massa ou energia."""
    if not resultado.avaliavel:
        return BalancoIntegrado(resultado, math.nan, math.nan, math.nan, math.nan)
    qh = max(0, caso.c_fria * (t_tratamento - resultado.t_fria_out))
    qc = max(0, caso.c_quente * (resultado.t_quente_out - t_estocagem))
    return BalancoIntegrado(resultado, qh, qc, qh, qc)
