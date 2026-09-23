"""Números como o Julia os imprime (`string(x::Float64)`), para mensagens idênticas.

Menor representação que volta ao mesmo float; notação científica quando o expoente
decimal é ≥ 6 ou < −4 (`1.0e6`, `1.234567e6`, `1.0e-5`), sempre com parte decimal
(`100.0`). Conferido contra tests/fixtures/julia/formatos_julia.json.
"""
import math
from decimal import Decimal


def jl(x):
    x = float(x)
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Inf" if x > 0 else "-Inf"
    if x == 0:
        return "-0.0" if math.copysign(1.0, x) < 0 else "0.0"
    sinal, digitos, exp = Decimal(repr(x)).normalize().as_tuple()
    ds = "".join(map(str, digitos))
    e10 = len(ds) + exp - 1
    s = "-" if sinal else ""
    if e10 >= 6 or e10 < -4:
        return f"{s}{ds[0]}.{ds[1:] or '0'}e{e10}"
    if e10 >= 0:
        inteira = ds[:e10 + 1].ljust(e10 + 1, "0")
        return f"{s}{inteira}.{ds[e10 + 1:] or '0'}"
    return f"{s}0.{'0' * (-e10 - 1)}{ds}"


def jl_round(x, digits=0):
    """`string(round(x, digits = d))`."""
    return jl(round(float(x), digits))
