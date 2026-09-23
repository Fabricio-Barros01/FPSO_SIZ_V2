"""Fatores de conversão EXATOS. Único módulo autorizado a conter literais numéricos
fora de {0, 1, 2, 10} (invariante 2); tudo que é aproximado vive em TOML."""

SEGUNDOS_POR_DIA = 86400
SEGUNDOS_POR_HORA = 3600
HORAS_POR_DIA = 24
POR_CENTO = 100
PPM_POR_UNIDADE = 1e6
ZERO_CELSIUS_K = 273.15


def c_para_k(t_c):
    return t_c + ZERO_CELSIUS_K


def c_para_f(t_c):
    """°C → °F na mesma ordem de operações do script de referência (T·9/5 + 32)."""
    return t_c * 9 / 5 + 32


def c_para_f_linear(t_c):
    """°C → °F na forma T·1,8 + 32 (a da auditoria independente do original)."""
    return t_c * 1.8 + 32


def m3h_para_m3s(q):
    return q / 3600.0


def cp_para_pas(mu):
    return mu / 1000.0


def kpa_para_pa(p):
    return p * 1000.0


def m3s_para_m3h(q):
    return q * 3600.0


def pas_para_cp(mu):
    return mu * 1000.0


def pa_para_kpa(p):
    return p / 1000.0


def mm_para_m(x):
    return x / 1000.0


# Unidades inglesas (exatas por definição, exceto a psi, derivada) — Units.jl do Julia
INCH_M = 0.0254
FOOT_M = 0.3048
BARREL_M3 = 0.158987294928
PSI_KPA = 6.894757293168361
LB_KG = 0.45359237
CUFT_M3 = 0.028316846592

# Massa específica de referência da água (convenção de densidade relativa, Units.jl)
RHO_AGUA_REF = 1000.0


def densidade_relativa(rho):
    return rho / RHO_AGUA_REF


def liquid_capacity_coefficient():
    """C da Eq. 22 (d[mm]²·Leff[m] = C·tr[min]·Q[m³/h]) a partir da forma de campo de
    Stewart & Arnold, d[in]²·Leff[ft] = 1,42·tr·Q[BPD]: C = 4,2152×10⁴ (o 4,12×10⁴ impresso
    em Alves & Komesu é erro tipográfico — ver docs/validacao/05-vasos.md)."""
    lhs = (INCH_M * 1000.0) ** 2 * FOOT_M
    rhs = 24.0 / BARREL_M3
    return lhs * 1.42 * rhs
