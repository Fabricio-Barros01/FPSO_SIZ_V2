"""Grade `a:passo:b` exatamente como o Julia a materializa (`collect(a:passo:b)` para
Float64), para a varredura cair nos MESMOS pontos do FPSO_Siz Julia.

O Julia tenta achar racionais exatos para início, passo e fim (`rat`) e, se consegue,
calcula cada ponto como (n0 + i·np)/den arredondado uma vez; senão toma os floats
literalmente, também sem erro acumulado. Ex.: com passo 6×25,4 = 152,39999999999998 a
soma ingênua a + i·passo erra no último dígito; o Julia não.
"""
from fractions import Fraction

MAX_INT_FLOAT32 = 16777216     # maxintfloat(Float32), limite de `rat` para Float64
MAX_INT_FLOAT64 = 9007199254740992


def rat(x):
    """Port de `Base.rat(x::Float64)`: aproximação racional por frações contínuas."""
    y = x
    a = d = 1
    b = c = 0
    m = MAX_INT_FLOAT32
    while abs(y) <= m:
        f = int(y)                      # trunc
        y -= f
        a, c = f * a + c, a
        b, d = f * b + d, b
        if max(abs(a), abs(b)) > m:
            return c, d
        if b != 0 and a / b == x:
            break
        y = 1.0 / y
    return a, b


def _div(a, b):
    """`div` do Julia: divisão inteira truncada em direção a zero."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def _entre(a, x, b):
    return a <= x <= b or b <= x <= a


def faixa_julia(inicio, passo, fim):
    inicio, passo, fim = float(inicio), float(passo), float(fim)
    if passo == 0:
        raise ValueError("range step cannot be zero")
    step_n, step_d = rat(passo)
    if step_d != 0 and step_n / step_d == passo:
        start_n, start_d = rat(inicio)
        stop_n, stop_d = rat(fim)
        if start_d != 0 and stop_d != 0 and start_n / start_d == inicio and stop_n / stop_d == fim:
            from math import lcm
            den = lcm(start_d, step_d)
            if den != 0 and abs(inicio * den) <= MAX_INT_FLOAT64 and abs(passo * den) <= MAX_INT_FLOAT64 \
                    and den % start_d == 0 and den % step_d == 0:
                s_n = round(inicio * den)
                p_n = round(passo * den)
                n = max(0, _div(den * stop_n - stop_d * s_n + p_n * stop_d, p_n * stop_d))
                if _entre(inicio, inicio + (n - 1) * passo, fim + passo / 2) and \
                        not _entre(inicio, inicio + n * passo, fim):
                    return tuple(float(Fraction(s_n + i * p_n, den)) for i in range(n))
    lf = (fim - inicio) / passo
    if lf < 0:
        n = 0
    elif lf == 0:
        n = 1
    else:
        n = round(lf) + 1
        fim_ = inicio + (n - 1) * passo
        n -= (inicio < fim < fim_) + (inicio > fim > fim_)
    a, p = Fraction(inicio), Fraction(passo)
    return tuple(float(a + i * p) for i in range(n))
