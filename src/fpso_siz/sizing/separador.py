"""Separador trifásico horizontal — Stewart & Arnold (2008) na forma de Alves & Komesu
(2025). Port de sizing/separator/stewart_arnold.jl. Três blocos:

* A — capacidade de gás (Eq. 9–15): d·Leff mínimo;
* B — decantação líquido-líquido (Eq. 16–21): teto de diâmetro d_max;
* C — capacidade de líquido (Eq. 22–24): d²·Leff mínimo.

Divergências documentadas em relação ao texto publicado (docs/validacao/05-vasos.md):
1. Eq. 22 usa 4,2152×10⁴ (derivado da forma de campo), não o 4,12×10⁴ impresso;
2. µ_g da Tabela 1 (0,6 cP) é viscosidade de líquido; µ_g é entrada explícita;
3. Eq. 21 publicada divide (h_w)max por β (altura do ÓLEO); a leitura geométrica usaria
   0,5 − β. Segue-se o publicado (reproduz o artigo) e a variante geométrica é emitida no
   rastro como "Eq. 21*", sem decidir nada;
4. Lss pela relação do bloco que governa (artigo), não pelo maior dos dois (livro).
"""
import math

from fpso_siz.core.contrato import Equipamento
from fpso_siz.core.corrente import field_units
from fpso_siz.core.formato_julia import jl_round
from fpso_siz.core.trace import Rastro
from fpso_siz.sizing.beta import beta_coefficient, water_area_fraction
from fpso_siz.sizing.capacidade_gas import EQS_GAS_ALVES, gas_capacity_dleff
from fpso_siz.sizing.vasos import (NAO_APLICAVEL_SEM_AGUA, SEM_FASE_AQUOSA, MetodoVaso, VesselConstraints,
                                   sem_fase_aquosa)


class Separator(Equipamento):
    method_id, label = "separator", "Separador Trifásico Horizontal"


class StewartArnold(MetodoVaso):
    method_id = "stewart_arnold"
    config = "equipment/separator/stewart_arnold.toml"
    rotulo_padrao = "Stewart & Arnold (2008)"

    def applies_to(self):
        return Separator()

    def slenderness_equation(self):
        return "Eq. 24"

    def lss_trace(self, gov):
        return ("Eq. 15", "Leff + d/1000") if gov == "gas" else ("Eq. 23", "(4/3)·Leff")

    def sizing_constraints(self, s, p, k):
        fu = field_units(s)
        tr = Rastro()
        dm_gas, dm_oil, dm_water = p["dm_gas"], p["dm_oil"], p["dm_water"]
        tr_o, tr_w = p["tr_oil"], p["tr_water"]
        c_eq14, c_eq17, c_eq22 = float(k["eq14_coefficient"]), float(k["eq17_coefficient"]), float(k["eq22_coefficient"])

        # ------------------------------------------------ bloco A
        ok_gas, d_leff_gas, msg_gas = gas_capacity_dleff(s, dm_gas, c_eq14, float(k["cd_initial"]),
                                                         float(k["cd_relaxation"]), tr, eqs=EQS_GAS_ALVES)
        if not ok_gas:
            return False, msg_gas, tr

        # ------------------------------------------------ bloco B
        if sem_fase_aquosa(fu):
            tr.trace("settling", "P-42", "Qw", NAO_APLICAVEL_SEM_AGUA, fu.q_w, "m³/h")
            d2_leff = c_eq22 * (tr_o * fu.q_o)
            tr.trace("liquid", "Eq. 22", "d²·Leff", "C·(tr)oQo — sem fase aquosa (P-42)", d2_leff, "mm²·m")
            return True, VesselConstraints(d_leff_gas, d2_leff, math.inf, SEM_FASE_AQUOSA,
                                           beta_coefficient(0.0), 0.0), tr
        dsg = fu.sg_w - fu.sg_o
        tr.trace("settling", "Eq. 16", "ΔSG", "(SG)w − (SG)o", dsg, "–")
        if not dsg > 0:
            return (False, f"Densidade do óleo ≥ densidade da água (ΔSG = {jl_round(dsg, 4)}): não há separação "
                           "gravitacional líquido-líquido.", tr)
        ho_max = c_eq17 * tr_o * dsg * (dm_water * dm_water) / fu.mu_o
        hw_max = c_eq17 * dsg * tr_w * (dm_oil * dm_oil) / fu.mu_w
        tr.trace("settling", "Eq. 17", "(h_o)max", "0,033·(tr)o·ΔSG·dm²/µo", ho_max, "mm")
        tr.trace("settling", "Eq. 20", "(h_w)max", "0,033·ΔSG·(tr)w·dm²/µw", hw_max, "mm")
        awa = water_area_fraction(fu.q_o, fu.q_w, tr_o, tr_w)
        beta = beta_coefficient(awa)
        tr.trace("settling", "Eq. 18", "Aw/A", "0,5·Qw(tr)w/((tr)oQo+(tr)wQw)", awa, "–")
        tr.trace("settling", "Fig. 3", "β", "0,5 − h_w/d (segmento circular, vaso meio cheio)", beta, "–")
        if not beta > 0:
            return (False, f"A fase aquosa ocupa toda a metade inferior do vaso (Aw/A = {jl_round(awa, 4)}): "
                           "não sobra altura para a camada de óleo.", tr)
        d_max_wio = ho_max / beta
        d_max_oiw = hw_max / beta
        tr.trace("settling", "Eq. 19", "d_max (água em óleo)", "(h_o)max/β", d_max_wio, "mm")
        tr.trace("settling", "Eq. 21", "d_max (óleo em água)", "(h_w)max/β", d_max_oiw, "mm")
        denom_geom = 0.5 - beta
        if denom_geom > 0:   # sem água livre β = 0,5 exato: linha documental omitida (não carimba Inf)
            tr.trace("settling", "Eq. 21*", "d_max (óleo em água)*",
                     "(h_w)max/(0,5−β) — variante não adotada; ver nota 3 em stewart_arnold.jl",
                     hw_max / denom_geom, "mm")
        d_max, mechanism = (d_max_wio, "water_in_oil") if d_max_wio <= d_max_oiw else (d_max_oiw, "oil_in_water")

        # ------------------------------------------------ bloco C
        d2_leff = c_eq22 * (tr_o * fu.q_o + tr_w * fu.q_w)
        tr.trace("liquid", "Eq. 22", "d²·Leff", "C·((tr)oQo + (tr)wQw)", d2_leff, "mm²·m")
        return True, VesselConstraints(d_leff_gas, d2_leff, d_max, mechanism, beta, awa), tr
