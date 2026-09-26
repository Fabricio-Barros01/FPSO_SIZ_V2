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


def kw_para_w(q):
    return q * 1000.0


def w_para_kw(q):
    return q / 1000.0


def kj_para_j(e):
    return e * 1000.0


def mgl_para_kgm3(c):
    """mg/L → kg/m³ (1 mg/L = 1 g/m³)."""
    return c / 1000.0


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


def sm3sm3_para_scf_stb(r):
    """Razão gás/óleo: Sm³/Sm³ → scf/STB (ft³ padrão por barril), fatores exatos."""
    return r * BARREL_M3 / CUFT_M3


def densidade_relativa(rho):
    return rho / RHO_AGUA_REF


def liquid_capacity_coefficient():
    """C da Eq. 22 (d[mm]²·Leff[m] = C·tr[min]·Q[m³/h]) a partir da forma de campo de
    Stewart & Arnold, d[in]²·Leff[ft] = 1,42·tr·Q[BPD]: C = 4,2152×10⁴ (o 4,12×10⁴ impresso
    em Alves & Komesu é erro tipográfico — ver docs/validacao/05-vasos.md)."""
    lhs = (INCH_M * 1000.0) ** 2 * FOOT_M
    rhs = 24.0 / BARREL_M3
    return lhs * 1.42 * rhs


def m_para_mm(x):
    return x * 1000.0


BAR_PA = 1.0e5


def potencia_hidraulica_kw(rho, q_m3h, h_m, eta, g):
    """P = ρ·g·Q·H/(3,6×10⁶·η), Q em m³/h: os 3600 s/h e 1000 W/kW são conversão exata."""
    return rho * g * q_m3h * h_m / (3.6e6 * eta)


# --- formas de campo × formas métricas das equações de Stewart & Arnold (memorial, F11)
# Só mudança de unidades, com os fatores exatos acima: o memorial mostra a constante de
# campo convertida ao lado do coeficiente métrico publicado, que é o usado no cálculo.
RANKINE_POR_KELVIN = 1.8
MM_POR_POLEGADA = INCH_M * 1000.0
MILHAO = 1e6


def coef_vt_metrico(c_campo):
    """V_t [ft/s] = c·√(Δρ/ρg·dm[µm]/C_D) → V_t [m/s] (a raiz não muda: densidades se
    cancelam e dm fica em µm nas duas formas)."""
    return c_campo * FOOT_M


def coef_gas_metrico(c_campo):
    """d[in]·Leff[ft] = c·T[°R]·Z·Qg[MMscfd]/P[psia]·K → d[mm]·Leff[m] = c'·T[K]·Z·Qg[Sm³/h]/P[kPa]·K.
    Volume padrão convertido como volume (ft³ → m³), sem ajuste entre as condições padrão."""
    return (c_campo * MM_POR_POLEGADA * FOOT_M * RANKINE_POR_KELVIN * HORAS_POR_DIA / (CUFT_M3 * MILHAO)
            * PSI_KPA)


def coef_liquido_metrico(c_campo):
    """d[in]²·Leff[ft] = c·tr[min]·Ql[bpd] → d[mm]²·Leff[m] = C·tr[min]·Ql[m³/h]."""
    return c_campo * MM_POR_POLEGADA ** 2 * FOOT_M * HORAS_POR_DIA / BARREL_M3


def coef_liquido_metrico_divisor(divisor_campo):
    """Forma de campo com divisor, d²·Leff = tr·Ql/c (S&A Eq. 3.9a)."""
    return coef_liquido_metrico(1.0 / divisor_campo)


def coef_espessura_metrico(c_campo):
    """h[in] = c·tr·ΔSG·dm²/µ → h[mm] (tr em min, dm em µm e µ em cP nas duas formas)."""
    return c_campo * MM_POR_POLEGADA


CONVERSOES_CAMPO = {"vt": coef_vt_metrico, "gas": coef_gas_metrico, "liquido": coef_liquido_metrico,
                    "liquido_divisor": coef_liquido_metrico_divisor, "espessura": coef_espessura_metrico}
