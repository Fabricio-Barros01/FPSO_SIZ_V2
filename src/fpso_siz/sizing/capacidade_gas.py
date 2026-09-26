"""Bloco A — capacidade de gás, o MESMO nos vasos de Stewart & Arnold:

    d·Leff = 34,5·[T·Z·Qg/P]·K,   K = [(ρg/(ρl−ρg))·(C_D/dm)]^0,5

Eq. 14 em Alves & Komesu (2025) = Eq. 3.8b em Stewart & Arnold (2008). Muda só a
numeração citada no memorial (cada método cita a fonte que o leitor vai conferir).
Port de sizing/gas_capacity.jl.
"""
from fpso_siz.core.corrente import field_units
from fpso_siz.core.formato_julia import jl_round
from fpso_siz.sizing.arrasto import constantes_arrasto, converge_drag, souders_brown

EQS_GAS_ALVES = dict(cd="Eq. 9–11", vt="Eq. 11", re="Eq. 10", ksb="Eq. 13", dleff="Eq. 14")
EQS_GAS_LIVRO = dict(cd="Eq. 3.6", vt="Eq. 3.7b", re="S&A §3.7", ksb="Eq. 3.1", dleff="Eq. 3.8b")


def gas_capacity_dleff(s, dm_gas, coef, cd0, relax, trace, eqs=EQS_GAS_ALVES):
    """(ok, d·Leff [mm·m], mensagem), com o rastro escrito em `trace`."""
    fu = field_units(s)
    historico = []
    drag = converge_drag(fu.rho_o, fu.rho_g, dm_gas, fu.mu_g, cd0=cd0, relax=relax, historico=historico)
    ka = constantes_arrasto()
    trace.iteracoes["gas"] = historico
    trace.anotar("gas", "C_D", a=ka["cd_a"], b=ka["cd_b"], c=ka["cd_c"], cd0=cd0, relaxacao=relax,
                 tolerancia=ka["tolerancia"], iteracoes=drag.iterations, convergiu=drag.converged)
    trace.anotar("gas", "V_t", coef=ka["coef_vt"], rho_l=fu.rho_o, rho_g=fu.rho_g, dm=dm_gas, cd=drag.cd)
    trace.anotar("gas", "Re", coef=ka["coef_re"], rho_g=fu.rho_g, dm=dm_gas, vt=drag.vt, mu_g=fu.mu_g)
    trace.trace("gas", eqs["cd"], "C_D", "iteração sub-relaxada de 24/Re + 3/√Re + 0,34", drag.cd, "–")
    trace.trace("gas", eqs["vt"], "V_t", "0,0036·[((ρl−ρg)/ρg)·(dm/C_D)]^0,5", drag.vt, "m/s")
    trace.trace("gas", eqs["re"], "Re", "0,001·ρg·dm·V_t/µg", drag.re, "–")
    if not drag.converged:
        return (False, float("nan"),
                f"O coeficiente de arrasto não convergiu em {drag.iterations} iterações. "
                f"Verifique a viscosidade do gás (µ_g = {jl_round(fu.mu_g, 4)} cP).")
    K = souders_brown(fu.rho_o, fu.rho_g, dm_gas, drag.cd)
    trace.anotar("gas", "K", rho_l=fu.rho_o, rho_g=fu.rho_g, dm=dm_gas, cd=drag.cd)
    trace.trace("gas", eqs["ksb"], "K", "[(ρg/(ρl−ρg))·(C_D/dm)]^0,5", K, "–")
    d_leff_gas = coef * (fu.t_k * fu.z * fu.q_g / fu.p_kpa) * K
    trace.anotar("gas", "d·Leff", coef=coef, t_k=fu.t_k, z=fu.z, q_g=fu.q_g, p_kpa=fu.p_kpa, k=K)
    trace.trace("gas", eqs["dleff"], "d·Leff", "34,5·[T·Z·Qg/P]·K", d_leff_gas, "mm·m")
    return True, d_leff_gas, ""
