"""CalcTrace: o rastro das equações avaliadas (invariante 3).

Cada passo é identificado por (equação, escopo). Registrar de novo o mesmo par
sobrescreve o anterior, de modo que, num laço iterativo, o rastro final corresponde
à última iteração, isto é, aos valores devolvidos no resultado.
"""
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class Passo:
    equacao: str
    escopo: str
    valor: object
    entradas: MappingProxyType = field(default_factory=lambda: MappingProxyType({}))


class CalcTrace:
    __slots__ = ("_passos",)

    def __init__(self):
        self._passos = {}

    def reg(self, equacao, escopo, valor, **entradas):
        """Registra um passo e devolve `valor` (permite uso em linha)."""
        self._passos[(equacao, escopo)] = Passo(equacao, escopo, valor, MappingProxyType(entradas))
        return valor

    def passo(self, equacao, escopo):
        return self._passos[(equacao, escopo)]

    def pares(self):
        return set(self._passos)

    def __iter__(self):
        return iter(self._passos.values())

    def __len__(self):
        return len(self._passos)
