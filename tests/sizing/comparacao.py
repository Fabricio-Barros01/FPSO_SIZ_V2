"""Comparação estrutural resultado Python × fixture Julia (JSON), com tolerância relativa."""
import math
from dataclasses import fields, is_dataclass

ESPECIAIS = {"NaN": math.nan, "Inf": math.inf, "-Inf": -math.inf}


def puro(x):
    """Resultado Python → estrutura comparável ao JSON do Julia."""
    if is_dataclass(x):
        return {f.name: puro(getattr(x, f.name)) for f in fields(x)}
    if isinstance(x, dict):
        return {str(k): puro(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [puro(v) for v in x]
    return x


def num(v):
    return ESPECIAIS.get(v, v) if isinstance(v, str) else v


def diferencas(nosso, julia, rtol, caminho="", pior=None):
    """Lista (caminho, nosso, julia); `pior` acumula o maior desvio relativo numérico."""
    out = []
    j = num(julia)
    if isinstance(j, dict):
        if not isinstance(nosso, dict):
            return [(caminho, nosso, julia)]
        for k in set(j) | set(nosso):
            if k not in nosso or k not in j:
                out.append((f"{caminho}/{k}", nosso.get(k, "<falta>"), j.get(k, "<falta>")))
            else:
                out += diferencas(nosso[k], j[k], rtol, f"{caminho}/{k}", pior)
        return out
    if isinstance(j, list):
        if not isinstance(nosso, (list, tuple)) or len(nosso) != len(j):
            return [(caminho, nosso, julia)]
        for i, (a, b) in enumerate(zip(nosso, j)):
            out += diferencas(a, b, rtol, f"{caminho}[{i}]", pior)
        return out
    if isinstance(j, (int, float)) and not isinstance(j, bool) and isinstance(nosso, (int, float)):
        if math.isnan(j) and math.isnan(nosso):
            return []
        if nosso == j:
            return []
        d = abs(nosso - j) / max(abs(nosso), abs(j))
        if pior is not None:
            pior.append((d, caminho))
        return [] if d <= rtol else [(caminho, nosso, julia)]
    if isinstance(j, float) and math.isnan(j) and isinstance(nosso, float) and math.isnan(nosso):
        return []
    return [] if nosso == j else [(caminho, nosso, julia)]
