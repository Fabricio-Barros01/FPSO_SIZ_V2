"""Formatação numérica pt-BR para LaTeX (idêntica à do script de referência)."""
import math


def br(x, d=0):
    """Número com separador de milhar '.' e decimal ','; '--' para None; zero sem sinal."""
    if x is None:
        return "--"
    if abs(x) < 0.5 * 10 ** (-d):
        x = 0.0
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def mb(x, d=0):
    """br() para modo matemático ({,} evita o espaço após a vírgula)."""
    return br(x, d).replace(",", "{,}")


def sci(x):
    """Notação científica com mantissa de 1 casa, em modo matemático."""
    if x == 0:
        return "$0$"
    e = int(math.floor(math.log10(abs(x))))
    m = x / 10 ** e
    return f"${mb(m, 1)}\\times10^{{{e}}}$"


def esc(s):
    return s.replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#")


def ids(lista):
    return ", ".join(str(i) for i in lista)


def mbn(x, dmin=0, dmax=6):
    """mb() com pelo menos `dmin` casas e as que o valor exigir (até `dmax`): para premissas
    escritas no texto, que não podem ser arredondadas (0,015 não vira 0,01)."""
    frac = f"{x:.{dmax}f}".rstrip("0").split(".")[1] if "." in f"{x:.{dmax}f}" else ""
    return mb(x, max(dmin, len(frac)))
