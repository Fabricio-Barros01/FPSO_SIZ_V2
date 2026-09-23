"""Divisão com a semântica IEEE 754 do Julia: x/0 dá ±Inf (ou NaN para 0/0) em vez de
levantar ZeroDivisionError. Usada onde a física depende de o Inf/NaN se propagar até uma
checagem que o transforma em mensagem de inviabilidade (ex.: Prandtl com k = 0)."""
import math


def div(a, b):
    a, b = float(a), float(b)
    if b != 0.0:
        return a / b
    if a == 0.0 or math.isnan(a):
        return math.nan
    return math.copysign(math.inf, a) * math.copysign(1.0, b)
