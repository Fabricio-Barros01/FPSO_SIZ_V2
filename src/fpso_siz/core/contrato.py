"""Contrato entre um método de dimensionamento e o motor (port de src/engine/contract.jl,
src/types/results.jl e src/interfaces.jl).

Todo dimensionamento deste programa tem a mesma forma:

    para cada x da grade (sweep_axis):
        y(x) = max sobre os casos de requirement(m, x, restrições_do_caso)
        d(x) = derived(m, x, y, ...)
        admissível se x ≤ teto, case_admissible em TODO caso e admissible(m, ...)
    escolhe-se o x admissível que minimiza objective(m, ...)

O motor não cita grandeza nenhuma (invariante 4): quem sabe que um vaso tem esbeltez e uma
bomba tem NPSH é o método, pelos hooks abaixo. Os nomes dos hooks são os do Julia, para
que o port de cada método seja linha a linha. Inviabilidade é estado retornado
(feasible = False + mensagem), nunca exceção.
"""
import math
from dataclasses import dataclass, field

from fpso_siz.core.corrente import STREAM_KEYS, stream_from_case, stream_parameters
from fpso_siz.core.trace import Rastro


# ------------------------------------------------------------------ descritores de apresentação
@dataclass(frozen=True)
class SweepAxis:
    key: str
    label: str
    unit: str
    values: tuple


@dataclass(frozen=True)
class ResultField:
    """Campo do cartão de resultados; `value` é número ou texto. status: neutro|ok|erro."""
    label: str
    value: object
    unit: str = ""
    digits: int = 2
    highlight: bool = False
    status: str = "neutro"

    def __post_init__(self):
        if not isinstance(self.value, str):
            object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True)
class SweepColumn:
    label: str
    key: str        # "x" | "y" | chave dos derivados
    digits: int = 2


# ------------------------------------------------------------------ resultados
@dataclass(frozen=True)
class SweepRow:
    x: float
    y: float
    per_constraint: dict
    derivados: dict
    governing: str
    ok: bool
    presentation: object = None


@dataclass(frozen=True)
class SizingResult:
    feasible: bool
    message: str
    x: float
    y: float
    derivados: dict
    governing: str
    ceiling: float
    ceiling_mechanism: str
    method_id: str
    sweep: list
    trace: Rastro


def infeasible(method_id, message, sweep=(), trace=None, ceiling=math.nan, ceiling_mechanism="none"):
    return SizingResult(False, str(message), math.nan, math.nan, {}, "none", ceiling, ceiling_mechanism,
                        method_id, list(sweep), trace if trace is not None else Rastro())


@dataclass(frozen=True)
class EnvelopeRow:
    x: float
    y: float
    derivados: dict
    governing: str
    driver_case: str
    per_case_y: list
    ok: bool
    presentation: object = None


@dataclass(frozen=True)
class EnvelopeResult:
    feasible: bool
    message: str
    x: float
    y: float
    derivados: dict
    governing: str
    driver_case: str
    ceiling: float
    ceiling_case: str
    ceiling_mechanism: str
    case_names: list
    rows: list
    slack: list
    per_case: list


def infeasible_envelope(message, case_names=(), rows=(), per_case=(), ceiling=math.nan, ceiling_case="",
                        ceiling_mechanism="none"):
    return EnvelopeResult(False, str(message), math.nan, math.nan, {}, "none", "", ceiling, ceiling_case,
                          ceiling_mechanism, list(case_names), list(rows), [], list(per_case))


def column_value(row, col):
    """Valor da coluna numa linha de varredura; derivado ausente vira NaN (tela: travessão)."""
    if col.key == "x":
        return row.x
    if col.key == "y":
        return row.y
    return row.derivados.get(col.key, math.nan)


def der(r, k):
    return r.derivados.get(k, math.nan)


# ------------------------------------------------------------------ equipamento e método
class Equipamento:
    """Um tipo de equipamento (separador, bomba...). Só identidade: a física é do método."""
    method_id = ""
    label = ""


class MetodoDimensionamento:
    """Base de todo método. Hooks sem default levantam NotImplementedError."""
    method_id = ""
    label = ""

    # --- identidade e entradas
    def applies_to(self):
        raise NotImplementedError

    def parameters(self):
        """Descritores dos parâmetros do método (list[ParameterSpec])."""
        raise NotImplementedError

    def parameter_groups(self):
        return []

    def global_keys(self):
        return []

    def stream_keys(self):
        return STREAM_KEYS

    def stream_parameters(self):
        chaves = self.stream_keys()
        return [s for s in stream_parameters() if s.key in chaves]

    def case_input(self, vals):
        """Dicionário de um caso → entrada da física (default: StreamState). ValueError se faltar."""
        return stream_from_case(vals, required=self.stream_keys())

    def method_config(self):
        """TOML do método (dict), com [constants] e [[parameter]]."""
        raise NotImplementedError

    def constants(self):
        return self.method_config().get("constants", {})

    # --- física
    def sizing_constraints(self, entrada, p, k):
        """(ok, restrições | mensagem, Rastro). Nunca lança por inviabilidade."""
        raise NotImplementedError

    def size_equipment(self, eq, entrada, params):
        from fpso_siz.core.motor import size_single
        return size_single(eq, self, entrada, params)

    # --- varredura
    def sweep_axis(self, p):
        raise NotImplementedError

    def requirement(self, x, cons):
        raise NotImplementedError

    def governing_of(self, x, cons):
        raise NotImplementedError

    def ceiling_of(self, cons):
        return math.inf

    def ceiling_mechanism_of(self, cons):
        return "none"

    def per_constraint(self, x, cons):
        return {}

    def derived(self, x, y, gov, cons, k, p):
        raise NotImplementedError

    def presentation_data(self, x, cons, k, p):
        return None

    def admissible(self, x, der, p):
        raise NotImplementedError

    def case_admissible(self, x, cons, p):
        return True

    def objective(self, x, der, p):
        raise NotImplementedError

    def envelope_params(self, params):
        """(ok, p_env | mensagem): uma grade e uma banda para N casos (o equipamento é um só)."""
        raise NotImplementedError

    def selection_message(self, rows, ceiling, p, mechanism="none"):
        raise NotImplementedError

    def grid_hint(self, p):
        return ""

    def trace_selection(self, tr, best, p):
        return None

    # --- apresentação
    def governing_label(self, g):
        return str(g)

    def result_fields(self, r):
        raise NotImplementedError

    def sweep_columns(self):
        raise NotImplementedError

    def trace_blocks(self):
        return []

    def requirement_spec(self):
        return ("exigência", "")

    def action_label(self):
        return "Dimensionar"
