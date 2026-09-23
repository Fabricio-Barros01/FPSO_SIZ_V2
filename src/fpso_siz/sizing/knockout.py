"""Vaso de knockout gás-líquido horizontal, meio cheio — Stewart & Arnold (2008), cap. 3.
Port de sizing/knockout/two_phase.jl. Blocos A (o MESMO do trifásico, Eq. 3.8b) e C
(Eq. 3.9b, uma fase); sem bloco B, logo sem teto (d_max = inf). Lss pelo MAIOR dos dois
candidatos (§3.8.4, regra do livro). O líquido único ocupa a posição do óleo na corrente
e é reetiquetado "líquido" no formulário.
Erratum do Exemplo 3.2: dLeff = 55,04 in·ft no texto, mas a Tabela 3.4 só fecha com 39,85.
"""
import math
from fpso_siz.core.contrato import Equipamento
from fpso_siz.core.corrente import field_units
from fpso_siz.core.trace import Rastro
from fpso_siz.core.unidades import mm_para_m
from fpso_siz.sizing.capacidade_gas import EQS_GAS_LIVRO, gas_capacity_dleff
from fpso_siz.sizing.vasos import MetodoVaso, VesselConstraints


class KnockoutDrum(Equipamento):
    method_id, label = "knockout", "Vaso de Knockout Bifásico (gás–líquido)"


class StewartArnoldTwoPhase(MetodoVaso):
    method_id = "stewart_arnold_2f"
    config = "equipment/knockout/stewart_arnold_2f.toml"
    rotulo_padrao = "Stewart & Arnold (2008) — bifásico"
    ajustes_corrente = "equipment/knockout/stewart_arnold_2f_corrente.toml"

    def applies_to(self):
        return KnockoutDrum()

    def stream_keys(self):
        return ("q_oil", "q_gas", "rho_oil", "rho_gas", "mu_gas", "pressure", "temperature", "z")

    def sizing_constraints(self, s, p, k):
        tr = Rastro()
        fu = field_units(s)
        ok, d_leff_gas, msg = gas_capacity_dleff(s, p["dm_gas"], float(k["gas_capacity_coefficient"]),
                                                 float(k["cd_initial"]), float(k["cd_relaxation"]), tr,
                                                 eqs=EQS_GAS_LIVRO)
        if not ok:
            return False, msg, tr
        d2_leff = float(k["liquid_capacity_coefficient"]) * p["tr_liquid"] * fu.q_o
        tr.trace("liquid", "Eq. 3.9b", "d²·Leff", "42441·tr·Ql", d2_leff, "mm²·m")
        if not math.isfinite(d2_leff):
            return (False, "Vazão de líquido não informada ou inválida: a capacidade de líquido (Eq. 3.9b) não "
                           "pôde ser avaliada.", tr)
        return True, VesselConstraints(d_leff_gas, d2_leff), tr

    def lss_from(self, d_mm, leff, gov, k):
        return max(leff + mm_para_m(d_mm), float(k["lss_liquid_factor"]) * leff)

    def slenderness_equation(self):
        return "§3.8.5"

    def lss_trace(self, gov):
        return ("§3.8.4", "max(Leff + d/1000 ; (4/3)·Leff)")
