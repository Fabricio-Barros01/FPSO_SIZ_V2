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


ESPECIAIS = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "_": r"\_", "#": r"\#", "$": r"\$",
             "{": r"\{", "}": r"\}", "^": r"\^{}", "~": r"\~{}"}


def tx(s):
    """Texto livre (fontes, dicas, mensagens) com todos os caracteres especiais do LaTeX
    escapados; esc() fica como está (paridade do memorial do balanço)."""
    return "".join(ESPECIAIS.get(ch, ch) for ch in str(s))


def ids(lista):
    return ", ".join(str(i) for i in lista)


def mbn(x, dmin=0, dmax=6):
    """mb() com pelo menos `dmin` casas e as que o valor exigir (até `dmax`): para premissas
    escritas no texto, que não podem ser arredondadas (0,015 não vira 0,01)."""
    frac = f"{x:.{dmax}f}".rstrip("0").split(".")[1] if "." in f"{x:.{dmax}f}" else ""
    return mb(x, max(dmin, len(frac)))


def sig(x, n=4):
    """`n` algarismos significativos em modo matemático, pt-BR (MC por TAG, F11): notação
    decimal para 10⁻² ≤ |x| < 10⁴ e científica fora disso; '--' para None/NaN/Inf."""
    if x is None or isinstance(x, bool) or not math.isfinite(x):
        return r"\text{--}"
    if x == 0:
        return "0"
    e = int(math.floor(math.log10(abs(x))))
    m = round(x / 10 ** e, n - 1)
    if abs(m) >= 10:
        m, e = m / 10, e + 1
    if -2 <= e < 4:
        return mb(x, max(n - 1 - e, 0))
    return f"{mb(m, n - 1)}\\times10^{{{e}}}"


def sigt(x, n=4):
    """sig() para texto corrido e tabelas."""
    return f"${sig(x, n)}$"


def texto_sig(x, n=4):
    """O número de sig() como aparece no texto extraído do PDF (teste PDF × JSON)."""
    return sig(x, n).replace("{,}", ",").replace("\\times10^", "×10").replace("{", "").replace("}", "")


UNIDADES_TEXTO = {"^3": "³", "^2": "²"}


def unid(u):
    """Unidade para \\text{} (os caracteres especiais são mapeados no preâmbulo)."""
    if u in ("–", "-", "--"):
        return ""
    for a, b in UNIDADES_TEXTO.items():
        u = u.replace(a, b)
    return tx(u)
