"""Casos, faixas e expansão em cantos — a entrada do motor de envelope
(port de src/types/cases.jl).

Uma entrada escalar pode ser dada como Interval; faixas viram casos de canto (produto
dos extremos), porque as restrições não são monótonas em cada entrada isolada.
A ordem dos cantos segue o `Iterators.product` do Julia: o PRIMEIRO eixo varia mais
rápido (paridade de nomes e ordem com o FPSO_Siz Julia).
"""
from dataclasses import dataclass, field

from fpso_siz.core.configuracao import carregar


def max_cantos_padrao():
    return carregar("constantes.toml")["motor"]["max_cantos"]


@dataclass(frozen=True)
class Interval:
    lo: float
    hi: float

    def __post_init__(self):
        lo, hi = float(self.lo), float(self.hi)
        if lo > hi:
            lo, hi = hi, lo
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)


def corners(x):
    if isinstance(x, Interval):
        return (x.lo,) if x.lo == x.hi else (x.lo, x.hi)
    return (x,)


def _asvalue(v):
    if isinstance(v, Interval):
        return v
    if isinstance(v, (list, tuple)):
        if len(v) != 2:
            raise ValueError(f"faixa deve ter exatamente 2 elementos [min, max]; recebi {len(v)}")
        return Interval(v[0], v[1])
    return float(v)


def _scalar(v):
    return v.lo if isinstance(v, Interval) else v  # Interval só se degenerado


@dataclass(frozen=True)
class Case:
    name: str
    values: dict
    enabled: bool = True

    def __post_init__(self):
        object.__setattr__(self, "name", str(self.name))
        object.__setattr__(self, "values", {k: _asvalue(v) for k, v in self.values.items()})

    def interval_keys(self):
        return sorted(k for k, v in self.values.items() if isinstance(v, Interval) and v.lo != v.hi)

    def corner_count(self):
        return 2 ** len(self.interval_keys())


@dataclass(frozen=True)
class CaseSet:
    cases: list = field(default_factory=list)

    def active(self):
        return [c for c in self.cases if c.enabled]

    def corner_count(self):
        return sum(c.corner_count() for c in self.active())

    def expand(self, max_corners=None):
        """[(nome, {chave: float})] — um por canto; nome com sufixo "[k↓ j↑]" se havia faixa."""
        max_corners = max_cantos_padrao() if max_corners is None else max_corners
        total = self.corner_count()
        if total == 0:
            return []
        if total > max_corners:
            raise ValueError(f"expansão geraria {total} casos de canto (limite {max_corners}). "
                             "Reduza o número de entradas dadas como faixa.")
        out = []
        for c in self.active():
            chaves = c.interval_keys()
            base = {k: _scalar(v) for k, v in c.values.items()}
            if not chaves:
                out.append((c.name, base))
                continue
            for combo in _produto_julia([corners(c.values[k]) for k in chaves]):
                vals = dict(base)
                tags = []
                for k, v in zip(chaves, combo):
                    vals[k] = v
                    tags.append(k + ("↓" if v == c.values[k].lo else "↑"))
                out.append((f"{c.name} [{' '.join(tags)}]", vals))
        return out


def _produto_julia(eixos):
    """Produto cartesiano com o primeiro eixo variando mais rápido (Iterators.product)."""
    combos = [()]
    for eixo in eixos:
        combos = [c + (v,) for v in eixo for c in combos]
    return combos


def case_set_from_config(cfg):
    """Blocos [[case]] de um TOML: name, enabled (opcional) e entradas (número ou [min, max])."""
    casos = []
    for b in cfg.get("case", []):
        if "name" not in b:
            raise ValueError(f"bloco [[case]] sem 'name': {b}")
        vals = {k: v for k, v in b.items() if k not in ("name", "enabled")}
        casos.append(Case(b["name"], vals, b.get("enabled", True)))
    return CaseSet(casos)
