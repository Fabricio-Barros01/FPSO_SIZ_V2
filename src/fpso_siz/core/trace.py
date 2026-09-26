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


# ---------------------------------------------------------------------------
# Rastro SEQUENCIAL do dimensionamento (port do CalcTrace Julia)
# ---------------------------------------------------------------------------
# O balanço usa CalcTrace (acima): indexado por (equação, escopo), com a última iteração
# prevalecendo, porque resolve um laço. O dimensionamento de equipamento avalia cada
# equação uma vez, em ordem, e o memorial lê essa ordem — daí uma sequência de entradas.
@dataclass(frozen=True, slots=True)
class TraceEntry:
    block: str      # "gas" | "settling" | "liquid" | "selection" ...
    eq: str         # "Eq. 11"
    var: str        # "V_t"
    formula: str    # "0,0036·[((ρl−ρg)/ρg)·(dm/CD)]^0,5"
    value: float
    unit: str


class Rastro:
    """Entradas em ordem de avaliação. `operandos` e `iteracoes` são o complemento
    documental (F11): os valores que cada equação consumiu, capturados no momento da
    avaliação, e o histórico dos laços. Ficam fora de `entries`, de modo que a projeção
    do rastro (JSON, fixtures do Julia) não muda."""
    __slots__ = ("entries", "operandos", "iteracoes")

    def __init__(self):
        self.entries = []
        self.operandos = {}   # (bloco, var) → {nome: valor}
        self.iteracoes = {}   # bloco → [{campo: valor}, ...]

    def anotar(self, block, var, **operandos):
        """Operandos da equação que produz `var` no bloco (mesmo valor, sem recálculo)."""
        self.operandos[(block, var)] = operandos

    def trace(self, block, eq, var, formula, value, unit):
        """Anota e devolve `value` (uso em linha, como `trace!` do Julia)."""
        self.entries.append(TraceEntry(block, eq, var, formula, value, unit))
        return value

    def block_entries(self, block):
        return [e for e in self.entries if e.block == block]

    def block_order(self):
        vistos = []
        for e in self.entries:
            if e.block not in vistos:
                vistos.append(e.block)
        return vistos

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)
