"""Tratador eletrostático horizontal — Stewart & Arnold (2008), §4.7–4.9.6.
Port de sizing/treater/electrostatic.jl. Vaso CHEIO de líquido (α = 1): sem bloco de gás
(d·Leff de gás = 0, não NaN); decantação (Eq. 4.5b/4.9b/4.16–4.18) com o ganho do campo
elétrico entrando só pelo tamanho de gotícula (hipótese de coalescência, (d_m/500)²);
retenção pela Eq. 4.15b. Coeficiente de decantação 0,033 (não os 0,0033 impressos na
Eq. 4.5b) e 1320 na Eq. 4.9b (não 1520) — ver docs/validacao/05-vasos.md.
"""
import math
from fpso_siz.core.contrato import Equipamento
from fpso_siz.core.corrente import field_units
from fpso_siz.core.formato_julia import jl_round
from fpso_siz.core.trace import Rastro
from fpso_siz.core.unidades import mm_para_m
from fpso_siz.sizing.beta import segment_height_fraction
from fpso_siz.sizing.vasos import (NAO_APLICAVEL_SEM_AGUA, SEM_FASE_AQUOSA, MetodoVaso, PhaseLayer,
                                   VesselConstraints, sem_fase_aquosa)


class ElectrostaticTreater(Equipamento):
    method_id, label = "treater", "Tratador Eletrostático Horizontal"


class ArnoldElectrostatic(MetodoVaso):
    method_id = "arnold_electrostatic"
    config = "equipment/treater/electrostatic.toml"
    rotulo_padrao = "Stewart & Arnold (2008) — §4.9"
    ajustes_corrente = "equipment/treater/electrostatic_corrente.toml"

    def applies_to(self):
        return ElectrostaticTreater()

    def stream_keys(self):
        return ("q_oil", "q_water", "rho_oil", "rho_water", "mu_oil", "mu_water")

    def sizing_constraints(self, s, p, k):
        tr = Rastro()
        fu = field_units(s)
        alpha = float(k["liquid_area_fraction"])
        c_set = float(k["settling_coefficient"])
        c_ret = float(k["retention_coefficient"])
        dm_ref = float(k["untreated_droplet_um"])
        dm_w, dm_o = p["dm_water"], p["dm_oil"]
        tr_o, tr_w = p["tr_oil"], p["tr_water"]

        if sem_fase_aquosa(fu):
            tr.trace("settling", "P-42", "Qw", NAO_APLICAVEL_SEM_AGUA, fu.q_w, "m³/h")
            d2_leff = c_ret * (tr_o * fu.q_o) / alpha
            tr.trace("liquid", "Eq. 4.15b", "d²·Leff", "21000·(tr)oQo/α — sem fase aquosa (P-42)", d2_leff, "mm²·m")
            if not (math.isfinite(d2_leff) and d2_leff > 0):
                return (False, "Vazões não informadas ou inválidas: a capacidade de líquido (Eq. 4.15b) não pôde ser "
                               "avaliada.", tr)
            return True, VesselConstraints(0.0, d2_leff, math.inf, SEM_FASE_AQUOSA,
                                           segment_height_fraction(alpha), 0.0), tr

        dsg = fu.sg_w - fu.sg_o
        tr.trace("settling", "Eq. 4.16", "ΔSG", "(SG)w − (SG)o", dsg, "–")
        if not dsg > 0:
            return (False, f"Densidade do óleo ≥ densidade da água (ΔSG = {jl_round(dsg, 4)}): não há separação "
                           "gravitacional líquido-líquido, e o campo elétrico coalesce mas não decanta.", tr)
        r = dm_w / dm_ref
        tr.trace("settling", "Eq. 4.2b", "ganho do campo",
                 f"(d_m/{round(dm_ref)} µm)² — hipótese de coalescência, não correlação", r * r, "×")
        ho_max = c_set * tr_o * dsg * (dm_w * dm_w) / fu.mu_o
        hw_max = c_set * tr_w * dsg * (dm_o * dm_o) / fu.mu_w
        tr.trace("settling", "Eq. 4.5b", "(h_o)max", "0,033·(tr)o·ΔSG·d_m²/µ_o", ho_max, "mm")
        tr.trace("settling", "Eq. 4.9b", "(h_w)max", "0,033·(tr)w·ΔSG·d_m²/µ_w", hw_max, "mm")
        aw = alpha * fu.q_w * tr_w / (tr_o * fu.q_o + tr_w * fu.q_w) if (tr_o * fu.q_o + tr_w * fu.q_w) != 0 else math.nan
        if not math.isfinite(aw):
            return (False, "As vazões e os tempos de retenção não permitem repartir a seção entre óleo e água "
                           "(Eq. 4.16): confira se ao menos uma das duas vazões é positiva.", tr)
        beta_w = segment_height_fraction(aw)
        beta_l = segment_height_fraction(alpha)
        tr.trace("settling", "Eq. 4.16", "a_w", "α·Qw(tr)w/((tr)oQo + (tr)wQw)", aw, "–")
        tr.trace("settling", "Eq. 4.17", "β_w", "altura do segmento de área a_w", beta_w, "–")
        beta_o = beta_l - beta_w
        if not beta_o > 0:
            return (False, f"A fase aquosa ocupa toda a seção do vaso (a_w = {jl_round(aw, 4)}): não sobra altura "
                           "para a camada de óleo, e o bloco de decantação não tem onde acontecer.", tr)
        d_max_wio = ho_max / beta_o
        d_max_oiw = hw_max / beta_w if beta_w != 0 else math.inf
        tr.trace("settling", "Eq. 4.18", "d_max (água em óleo)", "(h_o)max/(β_l − β_w)", d_max_wio, "mm")
        if beta_w > 0:
            tr.trace("settling", "Eq. 4.18*", "d_max (óleo em água)",
                     "(h_w)max/β_w — contraparte geométrica; ver a nota 3 em electrostatic.jl", d_max_oiw, "mm")
        d_max, mechanism = (d_max_wio, "water_in_oil") if d_max_wio <= d_max_oiw else (d_max_oiw, "oil_in_water")

        d2_leff = c_ret * (tr_o * fu.q_o + tr_w * fu.q_w) / alpha
        tr.trace("liquid", "Eq. 4.15b", "d²·Leff", "21000·((tr)oQo + (tr)wQw)/α", d2_leff, "mm²·m")
        if not (math.isfinite(d2_leff) and d2_leff > 0):
            return (False, "Vazões não informadas ou inválidas: a capacidade de líquido (Eq. 4.15b) não pôde ser "
                           "avaliada.", tr)
        return True, VesselConstraints(0.0, d2_leff, d_max, mechanism, beta_o, aw), tr

    lss_pela_maior = True

    def lss_from(self, d_mm, leff, gov, k):
        return max(leff + mm_para_m(d_mm), float(k["lss_liquid_factor"]) * leff)

    def slenderness_equation(self):
        return "§4.9.2"

    def lss_trace(self, gov):
        return ("§4.9.1", "max(Leff + d/1000 ; (4/3)·Leff)")

    def per_constraint(self, d, c):
        return {"liquid": c.d2_leff / (d * d)}

    def cross_section(self, c):
        return [PhaseLayer("water", 1.0 - c.beta), PhaseLayer("oil", c.beta)]

    def trace_blocks(self):
        return [("settling", "Bloco B — decantação líquido-líquido"), ("liquid", "Bloco C — capacidade de líquido"),
                ("selection", "Seleção do diâmetro")]

    def governing_label(self, g):
        return {"liquid": "capacidade de líquido (retenção)", "gas": "capacidade de gás"}.get(g, str(g))
