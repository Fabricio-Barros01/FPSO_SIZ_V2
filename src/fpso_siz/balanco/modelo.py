"""Motor do balanço preliminar de massa e energia (diagrama de blocos, 26 correntes).

Port de `solve_case` do script de referência com PARIDADE NUMÉRICA: a ordem das
operações de ponto flutuante é a do original, inclusive onde ele recalcula grandezas
(o pré-aquecedor e o aquecedor são resolvidos duas vezes por iteração, e T_16 usa a
primeira estimativa de T_08). Não "simplifique" sem rever o oráculo em
tests/fixtures/python_ref.

Correntes: dict componente → kg/s, componentes O (óleo), W (água produzida),
D (água de diluição), G (gás), sempre nesta ordem (a ordem de soma importa).
"""
from dataclasses import dataclass, field

from fpso_siz.balanco.dados import constantes, pocos, premissas
from fpso_siz.balanco.propriedades import (gas_props, mu_interp, poco_do_fluido, split_eficiencia, split_water,
                                           standing_rs)
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.trace import CalcTrace
from fpso_siz.core.unidades import SEGUNDOS_POR_DIA, c_para_k

COMP = ("O", "W", "D", "G")
LIQUIDOS = ("O", "W", "D")
K_DIA = 1 / SEGUNDOS_POR_DIA  # (m³/d → m³/s)


def corrente(**vazoes):
    """Corrente com todos os componentes (zeros onde não informado)."""
    desconhecidos = set(vazoes) - set(COMP)
    if desconhecidos:
        raise KeyError(f"componentes desconhecidos: {sorted(desconhecidos)}")
    s = {k: 0.0 for k in COMP}
    s.update(vazoes)
    return s


@dataclass(frozen=True)
class ResultadoCaso:
    caso: dict
    fluid: str
    well: str
    api: float
    rho: dict
    cp: dict
    gp: dict
    Wv: float
    BSW01: float
    BSW_F: float
    streams: dict
    T: dict
    P: dict
    duties: dict
    gas: dict
    iters: int
    residuo_reciclo: float
    VM: float  # volume molar padrão usado (m³/kmol), exposto para a auditoria
    mu: tuple
    T_ref: float
    trace: CalcTrace
    fwko: dict = field(default_factory=dict)  # regra, η adotado, η_req, η_padrão, exigido_acima, estado

    @property
    def num(self):
        return self.caso["num"]

    @property
    def convergiu(self):
        """O original não sinaliza reciclo não convergido; aqui ele é explícito."""
        return self.residuo_reciclo < constantes().numerico["reciclo_tol"]

    def C(self, s):
        """Capacidade térmica da corrente, kW/K."""
        return sum(s[c] * self.cp[c] for c in COMP)

    def H(self, s, t):
        """Entalpia sensível relativa a T_ref, kW (P-14)."""
        return sum(s[c] * self.cp[c] for c in COMP) * (t - self.T_ref)

    def vol(self, s, c):
        """Vazão volumétrica padrão do componente, m³/d (Sm³/d para gás)."""
        return s[c] / self.rho[c] / K_DIA


REFERENCIA, EFICIENCIA = "referencia", "eficiencia"


def regra_fwko_padrao():
    """Regra de separação de água livre do SG-001 em uso (constantes.toml [modelo])."""
    return carregar("constantes.toml")["modelo"]["regra_fwko"]


def resolver_caso(caso, dados, prem=None, regra_fwko=None):
    """Resolve um caso de projeto (laço de reciclo de água por substituição sucessiva).

    `regra_fwko` escolhe a separação de água livre no SG-001:
    - "referencia": BSW_F = mín(BSW_F,máx; BSW de chegada), a do script de referência
      (paridade bit a bit com o oráculo);
    - "eficiencia": η_A = máx(η_padrão; η_req), com η_req calculado dentro do laço para que o
      óleo de saída não passe de BSW_F,máx (BOT 2.7.1.2) — `split_eficiencia`."""
    regra_fwko = regra_fwko or regra_fwko_padrao()
    if regra_fwko not in (REFERENCIA, EFICIENCIA):
        raise ValueError(f"regra do FWKO desconhecida: {regra_fwko!r} (use {REFERENCIA!r} ou {EFICIENCIA!r})")
    const = constantes()
    num = const.numerico
    ks = const.standing
    n_split = num["split_iter"]
    T_ref = const.T_ref_C
    p = premissas(dados) if prem is None else prem
    t = CalcTrace()

    fl = caso["fluid_type"]
    well = poco_do_fluido(dados, fl)
    poco = pocos()[well]
    api = poco.api
    VM = const.R * c_para_k(dados.T_std_C) / dados.P_std_kPa
    gp = gas_props(dados.composicoes[fl], const, VM)
    t.reg("gas_massa_molar", "caso", gp["MW"], y=gp["y"], frac_leves=gp["frac_lights"])
    t.reg("gas_cp", "caso", gp["cp"], MW=gp["MW"])
    t.reg("gas_densidade_relativa", "caso", gp["gamma"], MW=gp["MW"], MW_ar=const.MW_ar)
    t.reg("gas_massa_especifica_std", "caso", gp["rho_std"], MW=gp["MW"], VM=VM)

    rhoO = t.reg("rho_oleo_api", "caso", const.api_a / (const.api_b + api) * const.rho_agua_15_6C, API=api)
    rho = {"O": rhoO, "W": p["rho_W"], "D": p["rho_D"], "G": gp["rho_std"]}
    cp = {"O": p["cp_O"], "W": p["cp_W"], "D": p["cp_D"], "G": gp["cp"]}
    Ov = caso["oil_sm3d"]
    Wv = caso["liquid_sm3d"] - Ov
    Gin_v = caso["produced_gas_sm3d"] + caso["lift_gas_sm3d"]

    def m(comp, v):  # m³/d → kg/s
        return v * rho[comp] * K_DIA

    def vol(s, c):  # kg/s → m³/d
        return s[c] / rho[c] / K_DIA

    def C(s):
        return sum(s[c] * cp[c] for c in COMP)

    def Vdot(s):  # m³/s de líquido
        return sum(s[c] / rho[c] for c in LIQUIDOS)

    def dRs(P, T_):
        return max(0.0, standing_rs(P, T_, gp["gamma"], api, ks)
                   - standing_rs(dados.P_std_kPa, T_ref, gp["gamma"], api, ks))

    BSW01 = t.reg("bsw_chegada", "caso", Wv / (Wv + Ov) if Wv + Ov > 0 else 0.0, Q_A=Wv, Q_O=Ov)
    BSW_F = min(p["BSW_F"], BSW01)  # na regra de eficiência, é substituído pelo BSW que sai do laço
    if regra_fwko == REFERENCIA:
        t.reg("bsw_fwko", "caso", BSW_F, BSW_F_max=p["BSW_F"], BSW_chegada=BSW01)

    s01 = t.reg("vazao_massica_entrada", "C-01",
                corrente(O=m("O", Ov), W=m("W", Wv), G=m("G", Gin_v)), Q_O=Ov, Q_A=Wv, Q_G=Gin_v)
    T01 = caso["T_C"]
    carry = p["carry"]
    rec = corrente()
    T02 = p["T_trat"]
    TD1 = p["T_trat"]

    for it in range(num["reciclo_max_iter"]):
        # ---------------- M-01
        s03 = t.reg("mistura", "C-03", {c: s01[c] + rec[c] for c in COMP}, C01=s01, C02=rec)
        T03 = t.reg("temperatura_mistura", "C-03",
                    (C(s01) * T01 + C(rec) * T02) / C(s03) if C(rec) > 0 else T01, T01=T01, T02=T02)
        # ---------------- SG-001 (FWKO)
        TF = T03
        dRsF = t.reg("rs_liberado", "SG-001", dRs(p["P_FWKO"], TF), P=p["P_FWKO"], T=TF)
        dRsD1 = t.reg("rs_liberado", "V-001", dRs(p["P_D1"], TD1), P=p["P_D1"], T=TD1)
        G_D2v = t.reg("gas_por_estagio", "C-17", dRsD1 * Ov, dRs=dRsD1, Q_O=Ov)
        G_D1v = t.reg("gas_por_estagio", "C-09", max(0.0, dRsF * Ov - G_D2v), dRs=dRsF, Q_O=Ov, Q_G_D2=G_D2v)
        G_Fv = t.reg("gas_por_estagio", "C-04", Gin_v - G_D1v - G_D2v, Q_G_in=Gin_v, Q_G_D1=G_D1v, Q_G_D2=G_D2v)
        carryF = t.reg("arraste_liquido", "C-04", m("O", carry * G_Fv), carry=carry, Q_G=G_Fv)
        wat_in_v = vol(s03, "W") + vol(s03, "D")
        if regra_fwko == EFICIENCIA:
            wat06_v, wat05_v, oil05_v, eta_A, eta_req = split_eficiencia(
                vol(s03, "O"), wat_in_v, p["eta_F"], p["BSW_F"], p["C_OiW"], rho["O"], n_split,
                extra_oil_v=carry * G_Fv)
            O06_v = vol(s03, "O") - carry * G_Fv - oil05_v
            BSW_F = wat06_v / (wat06_v + O06_v) if wat06_v + O06_v > 0 else 0.0
            t.reg("eficiencia_fwko", "SG-001", eta_A, eta_padrao=p["eta_F"], eta_req=eta_req,
                  BSW_lim=p["BSW_F"], Q_A_e=wat_in_v, Q_O=O06_v)
        else:
            wat06_v, wat05_v, oil05_v = split_water(vol(s03, "O"), wat_in_v, BSW_F, p["C_OiW"],
                                                    rho["O"], n_split, extra_oil_v=carry * G_Fv)
            eta_A, eta_req = (wat05_v / wat_in_v if wat_in_v > 0 else None), None
        t.reg("separacao_oleo_agua", "SG-001",
              dict(agua_no_oleo=wat06_v, agua_removida=wat05_v, oleo_na_agua=oil05_v),
              Q_O=vol(s03, "O"), Q_agua=wat_in_v, BSW=BSW_F)
        fW = vol(s03, "W") / wat_in_v if wat_in_v > 0 else 1.0
        oil05 = m("O", oil05_v)
        s04 = t.reg("corrente_separada", "C-04", corrente(O=carryF, G=m("G", G_Fv)))
        s05 = t.reg("corrente_separada", "C-05",
                    corrente(O=oil05, W=m("W", wat05_v * fW), D=m("D", wat05_v * (1 - fW))), f_W=fW)
        s06 = t.reg("corrente_separada", "C-06",
                    corrente(O=s03["O"] - carryF - oil05, W=m("W", wat06_v * fW),
                             D=m("D", wat06_v * (1 - fW)), G=m("G", G_D1v + G_D2v)), f_W=fW)
        # ---------------- V-001
        carry1 = t.reg("arraste_liquido", "C-09", m("O", carry * G_D1v), carry=carry, Q_G=G_D1v)
        s09 = t.reg("corrente_separada", "C-09", corrente(O=carry1, G=m("G", G_D1v)))
        s10 = t.reg("corrente_diferenca", "C-10", {c: s06[c] - s09[c] for c in COMP}, entrada="C-08", outras=("C-09",))
        # ---------------- TO-001
        O10v = vol(s10, "O")
        w10v = vol(s10, "W") + vol(s10, "D")
        w11v, w12v, oil12_v = split_water(O10v, w10v, p["BSW_pre"], p["C_OiW"], rho["O"], n_split)
        t.reg("separacao_oleo_agua", "TO-001",
              dict(agua_no_oleo=w11v, agua_removida=w12v, oleo_na_agua=oil12_v),
              Q_O=O10v, Q_agua=w10v, BSW=p["BSW_pre"])
        f10 = vol(s10, "W") / w10v if w10v > 0 else 1.0
        s12 = t.reg("corrente_separada", "C-12",
                    corrente(O=m("O", oil12_v), W=m("W", w12v * f10), D=m("D", w12v * (1 - f10))), f_W=f10)
        s11 = t.reg("corrente_diferenca", "C-11", {c: s10[c] - s12[c] for c in COMP}, entrada="C-10", outras=("C-12",))
        # ---------------- água de diluição (critério de salinidade)
        S_res = p["S_spec"] / p["BSW_t"]
        w11_all = vol(s11, "W") + vol(s11, "D")
        Dv = w11_all * (p["S_W"] / S_res - 1) / p["eta_mix"] if w11_all > 0 else 0.0
        Dv = t.reg("agua_diluicao", "C-14", max(Dv, 0.0), Q_A_C11=w11_all, S_W=p["S_W"], S_res=S_res,
                   eta_mix=p["eta_mix"])
        s14 = t.reg("corrente_separada", "C-14", corrente(D=m("D", Dv)))
        s15 = dict(s14)
        s16 = t.reg("mistura", "C-16", {c: s11[c] + s15[c] for c in COMP}, C11=s11, C15=s15)
        # ---------------- V-002
        carry2 = t.reg("arraste_liquido", "C-17", m("O", carry * G_D2v), carry=carry, Q_G=G_D2v)
        s17 = t.reg("corrente_separada", "C-17", corrente(O=carry2, G=m("G", G_D2v)))
        s18 = t.reg("corrente_diferenca", "C-18", {c: s16[c] - s17[c] for c in COMP}, entrada="C-16", outras=("C-17",))
        # ---------------- TO-002
        O18v = vol(s18, "O")
        w18v = vol(s18, "W") + vol(s18, "D")
        w21v, w19v, oil19_v = split_water(O18v, w18v, p["BSW_t"], p["C_OiW"], rho["O"], n_split)
        t.reg("separacao_oleo_agua", "TO-002",
              dict(agua_no_oleo=w21v, agua_removida=w19v, oleo_na_agua=oil19_v),
              Q_O=O18v, Q_agua=w18v, BSW=p["BSW_t"])
        f18 = vol(s18, "W") / w18v if w18v > 0 else 1.0
        s19 = t.reg("corrente_separada", "C-19",
                    corrente(O=m("O", oil19_v), W=m("W", w19v * f18), D=m("D", w19v * (1 - f18))), f_W=f18)
        s21 = t.reg("corrente_diferenca", "C-21", {c: s18[c] - s19[c] for c in COMP}, entrada="C-18", outras=("C-19",))
        # ---------------- bombas
        W_Bo = t.reg("potencia_bomba", "B-001", Vdot(s21) * (p["P_pump_oil"] - p["P_D2"]) / p["eta_pump"],
                     V=Vdot(s21), P_suc=p["P_D2"], P_desc=p["P_pump_oil"], eta=p["eta_pump"])
        W_B1 = t.reg("potencia_bomba", "B-002", Vdot(s12) * (p["P_rec"] - p["P_D1"]) / p["eta_pump"],
                     V=Vdot(s12), P_suc=p["P_D1"], P_desc=p["P_rec"], eta=p["eta_pump"])
        W_B2 = t.reg("potencia_bomba", "B-003", Vdot(s19) * (p["P_rec"] - p["P_D2"]) / p["eta_pump"],
                     V=Vdot(s19), P_suc=p["P_D2"], P_desc=p["P_rec"], eta=p["eta_pump"])
        new_rec = {c: s12[c] + s19[c] for c in COMP}
        # ---------------- energia (1ª estimativa com T_D1 da iteração anterior)
        T06 = TF
        T22 = (TD1 + W_Bo / C(s21)) if C(s21) > 0 else TD1
        Cc, Ch = C(s06), C(s21)
        Q_pre = min(Cc, Ch) * max(0.0, T22 - T06 - p["dT_app"])
        T07 = T06 + Q_pre / Cc
        T23 = T22 - Q_pre / Ch
        T08 = max(p["T_trat"], T07)
        Q_H = Cc * (T08 - T07)
        Q_D = t.reg("carga_diluicao", "DWH-001", C(s14) * (p["T_dil_out"] - p["T_dil_in"]),
                    C=C(s14), T_in=p["T_dil_in"], T_out=p["T_dil_out"])
        T16 = t.reg("temperatura_mistura", "C-16",
                    (C(s11) * T08 + C(s15) * p["T_dil_out"]) / C(s16) if C(s16) > 0 else T08,
                    T11=T08, T15=p["T_dil_out"])
        T12 = T08
        T13 = t.reg("temperatura_bomba", "C-13", T12 + (W_B1 / C(s12) if C(s12) > 0 else 0), T_in=T12, W=W_B1)
        T19 = T16
        T20 = t.reg("temperatura_bomba", "C-20", T19 + (W_B2 / C(s19) if C(s19) > 0 else 0), T_in=T19, W=W_B2)
        T22 = t.reg("temperatura_bomba", "C-22", T16 + (W_Bo / C(s21) if C(s21) > 0 else 0), T_in=T16, W=W_Bo)
        # ---------------- trocador refeito com T22 correto
        Q_pre = t.reg("carga_preaquecedor", "P-001", min(Cc, Ch) * max(0.0, T22 - T06 - p["dT_app"]),
                      C_frio=Cc, C_quente=Ch, T_frio=T06, T_quente=T22, dT_app=p["dT_app"])
        T07 = t.reg("temperatura_preaquecedor", "C-07", T06 + Q_pre / Cc, T_in=T06, Q=Q_pre, C=Cc)
        T23 = t.reg("temperatura_preaquecedor", "C-23", T22 - Q_pre / Ch, T_in=T22, Q=Q_pre, C=Ch)
        T08 = max(p["T_trat"], T07)
        Q_H = t.reg("carga_aquecedor", "P-002", Cc * (T08 - T07), T07=T07, T08=T08, C=Cc)
        T24 = min(T23, p["T_store"]) if T23 > p["T_store"] else T23
        Q_C = t.reg("carga_resfriador", "P-003", Ch * (T23 - T24), T23=T23, T24=T24, C=Ch)
        newT02 = (C(s12) * T13 + C(s19) * T20) / C(new_rec) if C(new_rec) > 0 else p["T_trat"]
        t.reg("mistura", "C-02", new_rec, C13=s12, C20=s19)
        t.reg("temperatura_mistura", "C-02", newT02, T13=T13, T20=T20)
        diff = max(abs(new_rec[c] - rec[c]) for c in COMP) + abs(newT02 - T02) + abs(T08 - TD1)
        t.reg("convergencia_reciclo", "M-03", diff, iteracao=it, tol=num["reciclo_tol"])
        rec, T02, TD1 = new_rec, newT02, T08
        if it > num["reciclo_min_iter"] and diff < num["reciclo_tol"]:
            break

    s02 = rec
    s13 = dict(s12)
    s20 = dict(s19)
    s07 = dict(s06)
    s08 = dict(s06)
    s22 = dict(s21)
    s23 = dict(s21)
    s24 = dict(s21)
    s25 = corrente()
    streams = {"C-01": s01, "C-02": s02, "C-03": s03, "C-04": s04, "C-05": s05, "C-06": s06,
               "C-07": s07, "C-08": s08, "C-09": s09, "C-10": s10, "C-11": s11, "C-12": s12,
               "C-13": s13, "C-14": s14, "C-15": s15, "C-16": s16, "C-17": s17, "C-18": s18,
               "C-19": s19, "C-20": s20, "C-21": s21, "C-22": s22, "C-23": s23, "C-24": s24,
               "C-25": dict(s24), "C-26": s25}
    temps = {"C-01": T01, "C-02": T02, "C-03": T03, "C-04": TF, "C-05": TF, "C-06": T06, "C-07": T07,
             "C-08": T08, "C-09": T08, "C-10": T08, "C-11": T08, "C-12": T08, "C-13": T13,
             "C-14": p["T_dil_in"], "C-15": p["T_dil_out"], "C-16": T16, "C-17": T16, "C-18": T16,
             "C-19": T16, "C-20": T20, "C-21": T16, "C-22": T22, "C-23": T23, "C-24": T24,
             "C-25": T24, "C-26": T24}
    Pf = p["P_FWKO"]
    P_resf = p["P_pump_oil"] - p["dP_HX"] - p["dP_cooler"]
    press = {"C-01": Pf, "C-02": Pf, "C-03": Pf, "C-04": Pf, "C-05": Pf, "C-06": Pf,
             "C-07": Pf - p["dP_HX"], "C-08": Pf - 2 * p["dP_HX"], "C-09": p["P_D1"], "C-10": p["P_D1"],
             "C-11": p["P_D1"], "C-12": p["P_D1"], "C-13": p["P_rec"], "C-14": p["P_D1"], "C-15": p["P_D1"],
             "C-16": p["P_D2"], "C-17": p["P_D2"], "C-18": p["P_D2"], "C-19": p["P_D2"], "C-20": p["P_rec"],
             "C-21": p["P_D2"], "C-22": p["P_pump_oil"], "C-23": p["P_pump_oil"] - p["dP_HX"],
             "C-24": P_resf, "C-25": P_resf, "C-26": P_resf}
    duties = dict(Q_pre=Q_pre, Q_H=Q_H, Q_D=Q_D, Q_C=Q_C, W_Bo=W_Bo, W_B1=W_B1, W_B2=W_B2)
    # dRsD1 reportado com o T_D1 já atualizado (como no original)
    gas = dict(G_in=Gin_v, G_F=G_Fv, G_D1=G_D1v, G_D2=G_D2v, Dv=Dv,
               dRsF=dRs(p["P_FWKO"], TF), dRsD1=dRs(p["P_D1"], TD1))
    mu = mu_interp(poco.viscosidade, T03)
    t.reg("viscosidade_oleo", "SG-001", mu[0], T=T03, marcador=mu[1])
    # estado do SG-001: regra usada, η adotado e, na regra de eficiência, se o BSW_F,máx do
    # BOT 2.7.1.2 exigiu η acima do padrão (informação, não exceção)
    exigido = regra_fwko == EFICIENCIA and eta_req is not None and eta_req > p["eta_F"]
    textos = carregar("constantes.toml")["modelo"]
    estado = ("estado_sem_agua" if eta_A is None else "estado_exigido" if exigido
              else "estado_padrao" if regra_fwko == EFICIENCIA else "estado_referencia")
    fwko = dict(regra=regra_fwko, eta=eta_A, eta_req=eta_req,
                eta_padrao=p["eta_F"] if regra_fwko == EFICIENCIA else None,
                exigido_acima=exigido, estado=textos[estado])
    return ResultadoCaso(caso=caso, fluid=fl, well=well, api=api, rho=rho, cp=cp, gp=gp, Wv=Wv,
                         BSW01=BSW01, BSW_F=BSW_F, streams=streams, T=temps, P=press, duties=duties,
                         gas=gas, iters=it, residuo_reciclo=diff, VM=VM, mu=mu, T_ref=T_ref, trace=t, fwko=fwko)


def resolver_todos(dados, prem=None, regra_fwko=None):
    return [resolver_caso(c, dados, prem, regra_fwko) for c in dados.casos]
