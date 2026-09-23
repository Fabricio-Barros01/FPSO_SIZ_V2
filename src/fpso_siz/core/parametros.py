"""ParameterSpec: descritor de parâmetro de entrada (port de src/interfaces.jl).

Invariante 4: a interface nunca cita um parâmetro pelo nome; itera os descritores que o
método declara. `group` ≠ "none" marca um campo de instância repetível (ex.: as N
correntes da Análise Pinch); `instance` 0 é o molde, ≥ 1 um campo concreto.
"""
from dataclasses import dataclass, replace

from fpso_siz.core.formato_julia import jl


@dataclass(frozen=True)
class ParameterSpec:
    key: str
    label: str
    unit: str
    default: float
    min: float
    max: float
    advanced: bool = False
    note: str = ""
    group: str = "none"
    instance: int = 0


def validate(spec, value):
    """None se válido; senão a mensagem (mesmo texto do Julia)."""
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        return f"{spec.label}: valor não numérico"
    if value < spec.min:
        return f"{spec.label}: abaixo do mínimo ({jl(spec.min)} {spec.unit})"
    if value > spec.max:
        return f"{spec.label}: acima do máximo ({jl(spec.max)} {spec.unit})"
    return None


def validar(specs, values):
    """Todas as mensagens de erro (vazio = tudo válido); não lança."""
    return [m for s in specs if s.key in values for m in [validate(s, values[s.key])] if m is not None]


def defaults(specs):
    return {s.key: s.default for s in specs}


def with_defaults(specs, values):
    """Valores fornecidos sobre os defaults, ignorando chaves desconhecidas."""
    out = defaults(specs)
    for k, v in values.items():
        if k in out:
            out[k] = float(v)
    return out


def instance_key(group, i, key):
    return f"{group}_{i}_{key}"


def in_group(s):
    return s.group != "none"


def is_template(s):
    return in_group(s) and s.instance == 0


def single_box(s):
    """Campo de grupo tem UMA caixa (não o par mín/máx): a contagem de cantos não pode
    crescer com o número de instâncias."""
    return in_group(s)


def group_instance(s, i, prefixo=""):
    if not is_template(s):
        raise ValueError(f"group_instance espera um molde de grupo; recebi '{s.key}' "
                         f"(group = {s.group}, instance = {s.instance})")
    if i < 1:
        raise ValueError(f"instância tem de ser ≥ 1; recebi {i}")
    return replace(s, key=instance_key(s.group, i, s.key),
                   label=(f"{prefixo} {i} — " if prefixo else "") + s.label, instance=int(i))


def group_specs(cfg):
    """Cabeçalhos [[group]]: key, label, min e max instâncias."""
    out = []
    for g in cfg.get("group", []):
        for f in ("key", "label", "min", "max"):
            if f not in g:
                raise ValueError(f"bloco [[group]] sem campo obrigatório '{f}': {g}")
        lo, hi = int(g["min"]), int(g["max"])
        if not 1 <= lo <= hi:
            raise ValueError(f"bloco [[group]] '{g['key']}': exige 1 ≤ min ≤ max, recebi min = {lo} e max = {hi}")
        out.append(dict(key=g["key"], label=g["label"], min=lo, max=hi))
    return out


def parameter_specs(cfg):
    """Blocos [[parameter]] de um TOML → descritores (grupo órfão é erro na carga)."""
    grupos = {g["key"] for g in group_specs(cfg)}
    specs = []
    for p in cfg.get("parameter", []):
        for f in ("key", "label", "unit", "default", "min", "max"):
            if f not in p:
                raise ValueError(f"bloco [[parameter]] sem campo obrigatório '{f}': {p}")
        g = p.get("group", "none")
        if g != "none" and g not in grupos:
            raise ValueError(f"parâmetro '{p['key']}' declara group = \"{g}\", que não tem bloco [[group]] "
                             "correspondente neste arquivo")
        specs.append(ParameterSpec(p["key"], p["label"], p["unit"], float(p["default"]), float(p["min"]),
                                   float(p["max"]), bool(p.get("advanced", False)), p.get("note", ""), g))
    return specs
