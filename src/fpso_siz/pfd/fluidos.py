"""Propriedades de fluido na condição do equipamento (F10a) — o detalhamento que o balanço
preliminar não faz e que o MC do equipamento expõe.

Cada função recebe a condição (T em °C, P em kPa) e os dados do balanço, devolve os valores
nas unidades do projeto e, se receber um `Rastro`, anota cada propriedade no bloco
"propriedades" com a fonte (rótulos e referências em config/fluidos.toml).

Regra das fontes: só entra o que tem fonte citável. O que não tem vira LACUNA — valor NaN,
anotado como tal — e nunca um número suposto. Condições fora da faixa de validade de uma
correlação não bloqueiam o cálculo: viram `avisos`, que o MC lista.
"""
import math
from dataclasses import dataclass, field

from fpso_siz.balanco.dados import constantes
from fpso_siz.balanco.propriedades import mu_interp
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_f, c_para_k, kpa_para_pa, mgl_para_kgm3, pas_para_cp
from fpso_siz.pfd import _chedl

BLOCO = "propriedades"


def cfg():
    return carregar("fluidos.toml")


def versoes():
    """Versões do thermo/chemicals efetivamente usadas (vão para o JSON e o MC)."""
    return _chedl.versoes()


@dataclass(frozen=True)
class Gas:
    Z: float
    rho: float      # kg/m³
    mu: float       # cP
    k: float        # W/(m·K)
    VF: float       # fração vaporizada prevista pela EOS (1 = só vapor)
    avisos: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class Liquido:
    rho: float      # kg/m³
    mu: float       # cP
    cp: float       # J/(kg·K)
    k: float        # W/(m·K); NaN = lacuna de entrada
    avisos: tuple = field(default_factory=tuple)
    nota: str = ""  # correção aplicada à μ (ex.: óleo vivo), para a fonte da entrada


def _anotar(rastro, fonte, var, formula, valor, unidade):
    if rastro is not None:
        rastro.trace(BLOCO, fonte, var, formula, valor, unidade)


# ------------------------------------------------------------------ gás
def gas(y, MW, T_C, P_kPa, rastro=None):
    """Gás de composição `y` (frações do balanço, corte N2–nC4, P-03) e massa molar `MW` do
    balanço, a (T, P). Z pela EOS; ρ = P·MW/(Z·R·T) com MW e R do balanço, para que a vazão
    real (ṁ/ρ) seja coerente com a massa do balanço."""
    c = cfg()["gas"]
    comp = c["componentes"]
    faltam = sorted(set(y) - set(comp))
    if faltam:
        raise ValueError(f"componentes do gás sem identificador em fluidos.toml: {faltam}")
    T = c_para_k(T_C)
    e = _chedl.estado_gas([comp[k] for k in y], list(y.values()), T, kpa_para_pa(P_kPa), c["eos"], c["kij"])
    R = constantes().R
    rho = P_kPa * MW / (e["Z"] * R * T)
    mu = pas_para_cp(e["mu"])
    avisos = []
    if e["VF"] < 1:
        avisos.append(f"a EOS prevê condensação parcial do gás a {T_C:.1f} °C e {P_kPa:.0f} kPa "
                      f"(fração vaporizada {e['VF']:.4f}); usadas as propriedades da fase vapor")
    _anotar(rastro, c["rotulo_eos"], "Z", f"EOS {c['eos']}, kij {c['kij']}, composição do balanço (P-03)", e["Z"], "–")
    _anotar(rastro, c["rotulo_z"], "ρ_g", "P·MW/(Z·R·T)", rho, "kg/m³")
    _anotar(rastro, c["rotulo_transporte"], "μ_g", f"mistura {e['metodo_mu']} sobre {'/'.join(e['metodo_mu_puros'])}",
            mu, "cP")
    _anotar(rastro, c["rotulo_transporte"], "k_g", f"mistura {e['metodo_k']}", e["k"], "W/(m·K)")
    return Gas(e["Z"], rho, mu, e["k"], e["VF"], tuple(avisos))


def gas_cp(y, T_C, P_kPa):
    """cp mássico [J/(kg·K)] e Z da fase vapor pela EOS (mesma composição e EOS de `gas`):
    comparação da F14 com o cp constante do balanço."""
    c = cfg()["gas"]
    comp = c["componentes"]
    e = _chedl.estado_gas([comp[k] for k in y], list(y.values()), c_para_k(T_C), kpa_para_pa(P_kPa), c["eos"],
                          c["kij"])
    return dict(cp=e["cp"], Z=e["Z"], VF=e["VF"])


# ------------------------------------------------------------------ água
def agua(T_C, P_kPa, rastro=None):
    """Água sem sal (diluição, S_D = 0): IAPWS. cp não é usado (vem do balanço): NaN."""
    c = cfg()["agua"]
    e = _chedl.agua_iapws(c_para_k(T_C), kpa_para_pa(P_kPa))
    mu = pas_para_cp(e["mu"])
    _anotar(rastro, c["rotulo"], "ρ_w", "IAPWS-95", e["rho"], "kg/m³")
    _anotar(rastro, c["rotulo"], "μ_w", "IAPWS 2008", mu, "cP")
    _anotar(rastro, c["rotulo"], "k_w", "IAPWS 2011", e["k"], "W/(m·K)")
    return Liquido(e["rho"], mu, math.nan, e["k"])


def agua_saturada(T_C, rastro=None):
    """Água pura de utilidade (circuito fechado de água quente ou de resfriamento; BOT 2.7.3.7.16
    e 3.3.2) como líquido saturado a T: a pressão do circuito não é dado do balanço."""
    c = cfg()["agua"]
    e = _chedl.agua_saturada_iapws(c_para_k(T_C))
    mu = pas_para_cp(e["mu"])
    base = "líquido saturado a T"
    _anotar(rastro, c["rotulo"], "ρ_w", f"IAPWS-95, {base}", e["rho"], "kg/m³")
    _anotar(rastro, c["rotulo"], "μ_w", f"IAPWS 2008, {base}", mu, "cP")
    _anotar(rastro, c["rotulo"], "k_w", f"IAPWS 2011, {base}", e["k"], "W/(m·K)")
    _anotar(rastro, c["rotulo"], "cp_w", f"IAPWS-95, {base}", e["cp"], "J/(kg·K)")
    return Liquido(e["rho"], mu, e["cp"], e["k"])


def fracao_sal(S_mgL, rho_std):
    """Fração mássica de sal de uma água de salinidade S (mg/L) e massa específica padrão ρ."""
    return mgl_para_kgm3(S_mgL) / rho_std


def salmoura(T_C, S_mgL, rho_std, rastro=None):
    """Água produzida como solução de NaCl: fração mássica w = S/ρ_padrão (S_W e rho_W das
    premissas). ρ, μ e cp de Laliberté (2009); k é lacuna (sem NaCl no banco de Magomedov)."""
    return salmoura_fracao(T_C, fracao_sal(S_mgL, rho_std), rastro)


def salmoura_fracao(T_C, w, rastro=None):
    """Fase aquosa como solução de NaCl de fração mássica w (ex.: água produzida misturada à
    de diluição, com o sal de cada uma). ρ, μ e cp de Laliberté (2009); k é lacuna."""
    c = cfg()["salmoura"]
    v, faixas = _chedl.salmoura_laliberte(c_para_k(T_C), w, c["sal"])
    avisos = [f"{p}: fora da faixa de Laliberté (T {tmin:g}–{tmax:g} °C, w ≤ {wmax:.3f}; aqui {T_C:.1f} °C, "
              f"w = {w:.3f})" for p, (tmin, tmax, wmax) in faixas.items()
              if not (tmin <= T_C <= tmax and w <= wmax)]
    mu = pas_para_cp(v["mu"])
    _anotar(rastro, c["rotulo"], "w_NaCl", "massa de sal / massa da fase aquosa", w, "–")
    _anotar(rastro, c["rotulo"], "ρ_w", "Laliberté, densidade", v["rho"], "kg/m³")
    _anotar(rastro, c["rotulo"], "μ_w", "Laliberté, viscosidade", mu, "cP")
    _anotar(rastro, c["rotulo"], "cp_w", "Laliberté, capacidade calorífica", v["cp"], "J/(kg·K)")
    _anotar(rastro, c["rotulo_lacuna_k"], "k_w", "entrada do usuário", math.nan, "W/(m·K)")
    return Liquido(v["rho"], mu, v["cp"], math.nan, tuple(avisos))


# ------------------------------------------------------------------ óleo
def oleo(poco, rho_std, T_C, rastro=None, rs_scf_stb=None):
    """Óleo: μ de óleo morto da tabela do poço (BOT) com a regra P-40 do balanço e, se
    `rs_scf_stb` é dado, a correção de óleo vivo de Beggs & Robinson (1975) com o gás
    dissolvido da corrente; ρ padrão pelo API. cp vem do balanço e k é lacuna."""
    c = cfg()["oleo"]
    mu, marcador = mu_interp(poco.viscosidade, T_C)
    avisos = [] if marcador == "interp." else [f"viscosidade do óleo {marcador} (tabela do BOT; P-40)"]
    nota = ""
    if rs_scf_stb is None:
        _anotar(rastro, c["rotulo_viscosidade"], "μ_o", f"óleo morto, log-linear em T ({marcador})", mu, "cP")
    else:
        _anotar(rastro, c["rotulo_viscosidade"], "μ_od", f"óleo morto, log-linear em T ({marcador})", mu, "cP")
        mu_od = mu
        mu, av = oleo_vivo(mu_od, rs_scf_stb, poco.api, T_C, rastro)
        avisos += av
        if mu != mu_od:
            nota = f"óleo vivo, {cfg()['oleo_vivo']['rotulo']}"
    _anotar(rastro, c["rotulo_densidade"], "ρ_o", "condição padrão, sem correção por T e Bo", rho_std, "kg/m³")
    return Liquido(rho_std, mu, math.nan, math.nan, tuple(avisos), nota)


def oleo_vivo(mu_od, rs_scf_stb, api, T_C, rastro=None):
    """(μ_o [cP], avisos): Beggs & Robinson (1975), μ_o = A·μ_od^B com A e B função do gás
    dissolvido Rs [scf/STB]; coeficientes e faixa de dados em fluidos.toml [oleo_vivo].
    Abaixo da faixa de Rs a correlação não é extrapolada: com os coeficientes arredondados ela
    não volta a μ_od quando Rs → 0 (dá um óleo vivo mais viscoso que o morto), e o valor medido
    do óleo morto (BOT) é mantido, conservador para a decantação."""
    c = cfg()["oleo_vivo"]
    rs_min, rs_max = c["faixa_rs_scf_stb"]
    if not rs_scf_stb >= rs_min:
        avisos = []
        if round(rs_scf_stb) > 0:
            avisos.append(f"Rs = {rs_scf_stb:.0f} scf/STB abaixo da faixa de Beggs & Robinson ({rs_min:g}–{rs_max:g} "
                          "scf/STB): mantido o óleo morto do BOT")
        _anotar(rastro, c["rotulo"], "μ_o", "Rs abaixo da faixa da correlação: óleo morto mantido", mu_od, "cP")
        return mu_od, avisos
    A = c["a"] * (rs_scf_stb + c["b"]) ** c["c"]
    B = c["d"] * (rs_scf_stb + c["e"]) ** c["f"]
    mu = A * mu_od ** B
    t_f = c_para_f(T_C)
    avisos = []
    if rs_scf_stb > rs_max:
        avisos.append(f"Rs = {rs_scf_stb:.0f} scf/STB acima da faixa de Beggs & Robinson ({rs_min:g}–{rs_max:g} scf/STB)")
    if not c["faixa_api"][0] <= api <= c["faixa_api"][1]:
        avisos.append(f"API {api:g} fora da faixa de Beggs & Robinson ({c['faixa_api'][0]:g}–{c['faixa_api'][1]:g})")
    if not c["faixa_t_f"][0] <= t_f <= c["faixa_t_f"][1]:
        avisos.append(f"T = {t_f:.0f} °F fora da faixa de Beggs & Robinson ({c['faixa_t_f'][0]:g}–{c['faixa_t_f'][1]:g} °F)")
    _anotar(rastro, c["rotulo"], "Rs", "gás dissolvido da corrente (balanço, Standing)", rs_scf_stb, "scf/STB")
    _anotar(rastro, c["rotulo"], "μ_o", "óleo vivo: A·μ_od^B", mu, "cP")
    return mu, avisos


# ------------------------------------------------------------------ emulsão
def _fora(x, faixa):
    return not faixa[0] <= x <= faixa[1]


def emulsao(mu_c, mu_d, frac_d, rastro=None):
    """Viscosidade de emulsão (Zanker; Branan eq. 27-4):
    μ = (μ_C/δ_C)·(1 + a·μ_D·δ_D/(μ_D + μ_C)), δ_C = 1 − δ_D. Devolve (μ, avisos)."""
    c = cfg()["emulsao"]
    frac_c = 1 - frac_d
    mu = mu_c / frac_c * (1 + c["a"] * mu_d * frac_d / (mu_d + mu_c))
    checagens = [("μ da fase contínua", mu_c, c["mu_continua_cP"]), ("μ da fase dispersa", mu_d, c["mu_dispersa_cP"]),
                 ("fração contínua", frac_c, c["fracao_continua"]), ("fração dispersa", frac_d, c["fracao_dispersa"])]
    avisos = [f"{nome} = {v:.4g} fora da faixa de validade de Zanker ({faixa[0]:g}–{faixa[1]:g})"
              for nome, v, faixa in checagens if _fora(v, faixa)]
    _anotar(rastro, c["rotulo"], "μ_emulsão", f"(μC/δC)·(1 + {c['a']:g}·μD·δD/(μD + μC))", mu, "cP")
    return mu, tuple(avisos)


# ------------------------------------------------------------------ pressão de vapor
def pressao_vapor_saturado(P_vaso_kPa, rastro=None):
    """Líquido que sai de um vaso de separação está no ponto de bolha: Pv = P do vaso."""
    c = cfg()["vapor"]
    _anotar(rastro, c["rotulo"], "Pv", "líquido no ponto de bolha: Pv = P do vaso a montante", P_vaso_kPa, "kPa")
    return P_vaso_kPa
