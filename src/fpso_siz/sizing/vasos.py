"""A família dos vasos: o contrato preenchido para equipamentos que se dimensionam
varrendo o diâmetro (port de sizing/constraints.jl).

Os blocos de Stewart & Arnold dão três números que não dependem de d, e é só disso que o
motor precisa:

    Leff_exigido(d) = max(d·Leff/d, d²·Leff/d²)      # gás, líquido
    d admissível   ⟺ d ≤ d_max                       # teto de decantação

Um método de vaso implementa `sizing_constraints` (os três números e o rastro),
`method_config` e, se quiser, `lss_from`. O resto — grade, Lss, esbeltez, banda, teto,
escolha, cartão — vem daqui. Os seis descritores que a família exige por nome: d_min,
d_max, d_step (grade) e sr_min, sr_max, sr_target (banda de esbeltez).
"""
import math
from dataclasses import dataclass

from fpso_siz.core.contrato import ResultField, SweepAxis, SweepColumn, der
from fpso_siz.core.formato_julia import jl, jl_round
from fpso_siz.core.grade import faixa_julia
from fpso_siz.core.unidades import mm_para_m
from fpso_siz.sizing.base import MetodoTOML, driver_case

SEM_EQUACAO = "—"


@dataclass(frozen=True)
class VesselConstraints:
    """d_leff_gas [mm·m], d2_leff [mm²·m], teto d_max_mm e o mecanismo que o impôs.
    Sem teto: d_max_mm = inf, mechanism = "none"; sem interface líquido-líquido: beta e
    aw_over_a = NaN (NaN e não zero: zero é um β possível)."""
    d_leff_gas: float
    d2_leff: float
    d_max_mm: float = math.inf
    mechanism: str = "none"
    beta: float = math.nan
    aw_over_a: float = math.nan


@dataclass(frozen=True)
class PhaseLayer:
    """Faixa de fase na seção transversal, do fundo para o topo (fração de altura)."""
    fase: str
    fracao: float


def vessel_volume(d_mm, l_m):
    """Volume do cilindro reto entre tampos, m³ (d em mm, l em m)."""
    r = mm_para_m(d_mm)
    return math.pi * (r * r) / 4 * l_m


def mechanism_label(m):
    return {"water_in_oil": "água em óleo", "oil_in_water": "óleo em água",
            "none": "sem teto de decantação"}.get(m, str(m))


class MetodoVaso(MetodoTOML):
    """Base dos métodos de vaso (AbstractVesselMethod)."""

    # --- geometria
    def lss_from(self, d_mm, leff, gov, k):
        """Lss [m]: Eq. 15 (gás governa: Leff + d) ou Eq. 23 (líquido: f·Leff)."""
        return leff + mm_para_m(d_mm) if gov == "gas" else float(k["lss_liquid_factor"]) * leff

    def cross_section(self, c):
        """Vaso meio cheio: 3 faixas com interface líquido-líquido, 2 sem; metade de cima é gás."""
        if math.isnan(c.beta):
            return [PhaseLayer("oil", 0.5), PhaseLayer("gas", 0.5)]
        return [PhaseLayer("water", 0.5 - c.beta), PhaseLayer("oil", c.beta), PhaseLayer("gas", 0.5)]

    # --- contrato do motor
    def sweep_axis(self, p):
        return SweepAxis("d", "diâmetro", "mm", faixa_julia(p["d_min"], p["d_step"], p["d_max"]))

    def global_keys(self):
        return ["d_min", "d_max", "d_step", "sr_min", "sr_max", "sr_target"]

    def requirement_spec(self):
        return ("comprimento efetivo Leff", "m")

    def requirement(self, d, c):
        return max(c.d_leff_gas / d, c.d2_leff / (d * d))

    def governing_of(self, d, c):
        return "gas" if c.d_leff_gas / d > c.d2_leff / (d * d) else "liquid"

    def ceiling_of(self, c):
        return c.d_max_mm

    def ceiling_mechanism_of(self, c):
        return c.mechanism

    def per_constraint(self, d, c):
        return {"gas": c.d_leff_gas / d, "liquid": c.d2_leff / (d * d)}

    def derived(self, d, leff, gov, cons, k, p):
        lss = self.lss_from(d, leff, gov, k)
        return {"lss": lss, "sr": lss / mm_para_m(d), "volume": vessel_volume(d, lss)}

    def admissible(self, d, der_, p):
        return p["sr_min"] <= der_["sr"] <= p["sr_max"]

    def objective(self, d, der_, p):
        return abs(der_["sr"] - p["sr_target"])

    def envelope_params(self, params):
        """Grade = UNIÃO (só amplia a busca); banda = INTERSEÇÃO (não afrouxa a exigência);
        alvo = média presa à banda (preferência, não restrição)."""
        sr_min = max(p["sr_min"] for p in params)
        sr_max = min(p["sr_max"] for p in params)
        if not sr_min <= sr_max:
            return (False, "As bandas de esbeltez pedidas pelos casos não se cruzam: o mais exigente pede "
                           f"SR ≥ {jl(sr_min)} e outro pede SR ≤ {jl(sr_max)}. Como o vaso é um só, não há "
                           "esbeltez que atenda a todos.")
        alvo = sum(p["sr_target"] for p in params) / len(params)
        return True, dict(d_min=min(p["d_min"] for p in params), d_max=max(p["d_max"] for p in params),
                          d_step=min(p["d_step"] for p in params), sr_min=sr_min, sr_max=sr_max,
                          sr_target=min(max(alvo, sr_min), sr_max))

    def selection_message(self, rows, ceiling, p, mechanism="none"):
        if all(r.y == 0 for r in rows):
            return ("As vazões informadas são nulas: não há corrente a separar e o comprimento efetivo é zero em "
                    "toda a grade, então não há diâmetro a dimensionar. Informe ao menos uma vazão positiva.")
        under = [r for r in rows if r.x <= ceiling]
        if not under:
            return (f"Nenhum diâmetro da grade respeita o teto de decantação d_max = {jl_round(ceiling, 0)} mm "
                    f"({mechanism_label(mechanism)}). Reduza d_min, ou reveja as viscosidades e os tempos de "
                    "retenção.")
        srs = [r.derivados["sr"] for r in under]
        return (f"Nenhum diâmetro admissível tem esbeltez na banda {jl(p['sr_min'])}–{jl(p['sr_max'])}: abaixo "
                f"do teto de decantação ({jl_round(ceiling, 0)} mm) o SR varia de {jl_round(min(srs), 2)} a "
                f"{jl_round(max(srs), 2)}. Amplie a grade de diâmetros ou a banda de SR.")

    def grid_hint(self, p):
        return f"Verifique d_min ({jl(p['d_min'])}), d_max ({jl(p['d_max'])}) e passo ({jl(p['d_step'])})."

    # --- memorial
    def slenderness_equation(self):
        return SEM_EQUACAO

    def lss_trace(self, gov):
        return (SEM_EQUACAO, "Leff + d/1000") if gov == "gas" else (SEM_EQUACAO, "f·Leff")

    def trace_selection(self, tr, best, p):
        eq_lss, formula_lss = self.lss_trace(best.governing)
        tr.trace("selection", eq_lss, "Lss", formula_lss, best.derivados["lss"], "m")
        tr.trace("selection", self.slenderness_equation(), "SR", "Lss/(d/1000)", best.derivados["sr"], "–")
        tr.trace("selection", "—", "d escolhido",
                 f"menor |SR − {jl(p['sr_target'])}| com {jl(p['sr_min'])} ≤ SR ≤ {jl(p['sr_max'])}", best.x, "mm")

    def trace_blocks(self):
        return [("gas", "Bloco A — capacidade de gás"), ("settling", "Bloco B — decantação"),
                ("liquid", "Bloco C — capacidade de líquido"), ("selection", "Seleção do diâmetro")]

    # --- apresentação
    def governing_label(self, g):
        return {"gas": "capacidade de gás", "liquid": "capacidade de líquido"}.get(g, str(g))

    def result_fields(self, r):
        tem = getattr(r, "feasible", True) and math.isfinite(r.x)

        def txt(v):
            return v if tem else "—"

        na_banda = "neutro" if not tem else ("ok" if getattr(r, "ok", True) else "erro")
        sob_teto = "neutro" if not tem or not math.isfinite(r.ceiling) else ("ok" if r.x <= r.ceiling else "erro")
        return [
            ResultField("Diâmetro d", r.x if tem else math.nan, unit="mm", digits=0, highlight=True),
            ResultField("Comprimento efetivo Leff", r.y if tem else math.nan, unit="m"),
            ResultField("Comprimento real Lss", der(r, "lss"), unit="m"),
            ResultField("Esbeltez SR", der(r, "sr"), status=na_banda),
            ResultField("Volume (casco, entre tampos)", der(r, "volume"), unit="m³", digits=0),
            ResultField("Restrição governante", txt(self.governing_label(r.governing))),
            ResultField("Caso governante", txt(driver_case(r))),
            ResultField("Teto de decantação", r.ceiling if math.isfinite(r.ceiling) else math.nan, unit="mm",
                        digits=0, status=sob_teto),
        ]

    def sweep_columns(self):
        return [SweepColumn("d (mm)", "x", 0), SweepColumn("Leff (m)", "y"), SweepColumn("Lss (m)", "lss"),
                SweepColumn("SR", "sr")]
