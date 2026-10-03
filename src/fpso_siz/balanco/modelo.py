"""Modelo de processo: o balanço preliminar de massa e energia (diagrama de blocos, 26
correntes), o ÚNICO resolvedor produtivo.

    resolver_caso(caso, dados, prem) -> EstadoProcesso
    resolver_todos(dados, prem) -> list[EstadoProcesso]

A ordem das operações de ponto flutuante é a do script de referência de onde o balanço foi
portado, inclusive onde ele recalcula grandezas (o pré-aquecedor e o aquecedor são resolvidos
duas vezes por iteração, e T_16 usa a primeira estimativa de T_08); a regressão
`tests/fixtures/python_ref/regressao_eficiencia.json` congela o resultado. Separação de água
livre no SG-001: a regra de eficiência (P-43, F10w).

Correntes: dict componente → kg/s, componentes O (óleo), W (água produzida),
D (água de diluição), G (gás), sempre nesta ordem (a ordem de soma importa).

Gás por estágio (SG-001, V-001, V-002): nos casos termodinamicamente avaliáveis (sem gás de
lift) sai do trem (`balanco/trem.py`): a composição do caso pela Nota 4 do BOT e a cascata de
flashes nas condições do próprio estado. O componente O de um líquido é o seu conteúdo de óleo
morto (o líquido levado à condição padrão) e G o gás que ele ainda libera. O vapor de um estágio
leva, como O, a parte do óleo morto da alimentação que vaporizou (componentes que condensariam na
condição padrão) e, como G, o resto: O e G se conservam cada um, e a energia sensível (P-14,
cp constante por componente) fecha sem calor latente, que o modelo não tem. A vazão de gás do
estágio é o vapor inteiro, ṅ_V·V_M. Nos casos não avaliáveis, o ΔRs de Standing (docs/validacao/39).
"""
import math
from dataclasses import replace

from fpso_siz.balanco import trem as trem_mod
from fpso_siz.balanco.dados import constantes, pocos, premissas
from fpso_siz.balanco.estado import COMP, ETAPA_PRELIMINAR, ETAPA_RATING, K_DIA, EstadoProcesso
from fpso_siz.balanco.propriedades import (gas_props, poco_do_fluido, split_eficiencia, split_water,
                                           standing_rs)
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.trace import CalcTrace
from fpso_siz.core.unidades import c_para_k
from fpso_siz.termo import proveniencia
from fpso_siz.termo.servico import mu_interp

LIQUIDOS = ("O", "W", "D")
# O que o segundo passe térmico (rating do P-001) pode mudar; massas, pressões e o trem não mudam.
# Um TAG cujas entradas citam uma destas correntes ou cargas depende do rating do P-001.
CORRENTES_RATING = ("C-07", "C-08", "C-23", "C-24", "C-25", "C-26")
CARGAS_RATING = ("Q_pre", "Q_H", "Q_C")


def corrente(**vazoes):
    """Corrente com todos os componentes (zeros onde não informado)."""
    desconhecidos = set(vazoes) - set(COMP)
    if desconhecidos:
        raise KeyError(f"componentes desconhecidos: {sorted(desconhecidos)}")
    s = {k: 0.0 for k in COMP}
    s.update(vazoes)
    return s


def resolver_caso(caso, dados, prem=None):
    """Resolve um caso de projeto (laço de reciclo de água por substituição sucessiva).

    Separação de água livre no SG-001: η_A = máx(η_padrão; η_req), com η_req calculado
    dentro do laço para que o óleo de saída não passe de BSW_F,máx (BOT 2.7.1.2) —
    `split_eficiencia` (P-43)."""
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
    mws = {k: v["mw"] for k, v in dados.c20.items()}
    z_base = {k: v for k, v in dados.composicoes[fl].items() if v > 0}
    aval, motivo = trem_mod.avaliavel(caso)
    rec = None
    if aval:
        rec = trem_mod.recombinar(z_base, mws, caso["produced_gas_sm3d"], Ov, rhoO, VM, caso["T_C"], p["P_FWKO"],
                                  dados.T_std_C, dados.P_std_kPa)
        pior, erro_c = rec.componente
        t.reg("recombinacao", "caso",
              dict(n_gas=rec.n_gas_kmol_d, n_liquido=rec.n_liquido_kmol_d, n_total=rec.n_total_kmol_d,
                   massa=rec.massa_kg_d, q_gas_fwko=rec.reproducao.q_gas_fwko_sm3d,
                   q_oleo_tanque=rec.reproducao.q_oleo_tanque_m3d, q_gas_padrao=rec.q_gas_padrao_sm3d),
              Q_G=caso["produced_gas_sm3d"], Q_O=Ov, T_ref=caso["T_C"], P_ref=p["P_FWKO"], rho_O=rhoO, V_M=VM,
              beta_ref=rec.vapor_ref.fracao_molar, MW_v=rec.vapor_ref.MW, MW_l=rec.liquido_ref.MW,
              beta_std=rec.beta_std, erro_soma_z=rec.erro_soma_z, erro_molar=rec.erro_molar,
              erro_massico=rec.erro_massico, erro_componente=erro_c, componente_pior=pior,
              erro_gas=rec.reproducao.erro_gas_rel, erro_oleo=rec.reproducao.erro_oleo_rel)
        if not rec.ok:
            raise ValueError(f"caso {caso['num']}: a recombinação da Nota 4 não fecha")
        Gin_v = rec.q_gas_padrao_sm3d
        G01 = rec.massa_gas_padrao_kg_d * K_DIA
    else:
        Gin_v = caso["produced_gas_sm3d"] + caso["lift_gas_sm3d"]
        G01 = Gin_v * rho["G"] * K_DIA

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

    s01 = t.reg("vazao_massica_entrada", "C-01",
                corrente(O=m("O", Ov), W=m("W", Wv), G=G01), Q_O=Ov, Q_A=Wv, Q_G=Gin_v)
    T01 = caso["T_C"]
    carry = p["carry"]
    reciclo = corrente()
    T02 = p["T_trat"]
    TD1 = p["T_trat"]
    TD2 = p["T_trat"]
    tr = None
    refazer_trem = True

    for it in range(num["reciclo_max_iter"]):
        # ---------------- M-01
        s03 = t.reg("mistura", "C-03", {c: s01[c] + reciclo[c] for c in COMP}, C01=s01, C02=reciclo)
        T03 = t.reg("temperatura_mistura", "C-03",
                    (C(s01) * T01 + C(reciclo) * T02) / C(s03) if C(reciclo) > 0 else T01, T01=T01, T02=T02)
        # ---------------- SG-001 (FWKO)
        TF = T03
        if rec is not None:
            if refazer_trem:
                # o trem fica congelado enquanto o reciclo converge e é refeito nas condições
                # convergidas, até que elas parem de mudar (ponto fixo externo; trem.toml [acoplamento])
                cond = {"C-04": (TF, p["P_FWKO"]), "C-09": (TD1, p["P_D1"]), "C-17": (TD2, p["P_D2"])}
                tr = trem_mod.resolver(rec, [(e["id"], e["corrente_gas"], *cond[e["corrente_gas"]])
                                             for e in trem_mod.cfg()["estagio"]], mws, dados.T_std_C, dados.P_std_kPa)
                refazer_trem = False
                if not tr.completo:
                    raise ValueError(f"caso {caso['num']}: o trem não percorreu os três estágios ({tr.interrompido})")
                est = {e.corrente_gas: e for e in tr.estagios}
                for cid, e in est.items():
                    v = e.vapor
                    t.reg("flash_estagio", cid, dict(beta=e.beta, MW_v=v.MW, Z_v=v.Z, rho_v=v.rho),
                          T=e.T_C, P=e.P_kPa, n_F=e.n_entrada_kmol_d, n_V=e.n_vapor_kmol_d, n_L=e.n_liquido_kmol_d,
                          m_V=e.m_vapor_kg_d, oleo_tanque_L=e.m_oleo_tanque_kg_d, gas_dissolvido_L=e.m_gas_dissolvido_kg_d)
                G_Fv, G_D1v, G_D2v = (t.reg("gas_estagio_flash", cid, est[cid].q_vapor_sm3d, n_V=est[cid].n_vapor_kmol_d,
                                            V_M=VM) for cid in ("C-04", "C-09", "C-17"))
                # óleo morto de cada líquido: o que vaporizou dele vai no vapor do estágio como O
                morto = [s01["O"]] + [e.m_oleo_tanque_kg_d * K_DIA for e in tr.estagios]
                oleo_vap = {e.corrente_gas: morto[i] - morto[i + 1] for i, e in enumerate(tr.estagios)}
                gas_vap = {cid: est[cid].m_vapor_kg_d * K_DIA - oleo_vap[cid] for cid in est}
        else:
            dRsF = t.reg("rs_liberado", "SG-001", dRs(p["P_FWKO"], TF), P=p["P_FWKO"], T=TF)
            dRsD1 = t.reg("rs_liberado", "V-001", dRs(p["P_D1"], TD1), P=p["P_D1"], T=TD1)
            G_D2v = t.reg("gas_por_estagio", "C-17", dRsD1 * Ov, dRs=dRsD1, Q_O=Ov)
            G_D1v = t.reg("gas_por_estagio", "C-09", max(0.0, dRsF * Ov - G_D2v), dRs=dRsF, Q_O=Ov, Q_G_D2=G_D2v)
            G_Fv = t.reg("gas_por_estagio", "C-04", Gin_v - G_D1v - G_D2v, Q_G_in=Gin_v, Q_G_D1=G_D1v, Q_G_D2=G_D2v)
        carryF = t.reg("arraste_liquido", "C-04", m("O", carry * G_Fv), carry=carry, Q_G=G_Fv)
        oleo_gas_v = carry * G_Fv + (oleo_vap["C-04"] / rho["O"] / K_DIA if rec is not None else 0.0)
        wat_in_v = vol(s03, "W") + vol(s03, "D")
        wat06_v, wat05_v, oil05_v, eta_A, eta_req = split_eficiencia(
            vol(s03, "O"), wat_in_v, p["eta_F"], p["BSW_F"], p["C_OiW"], rho["O"], n_split,
            extra_oil_v=oleo_gas_v)
        O06_v = vol(s03, "O") - oleo_gas_v - oil05_v
        BSW_F = wat06_v / (wat06_v + O06_v) if wat06_v + O06_v > 0 else 0.0
        t.reg("eficiencia_fwko", "SG-001", eta_A, eta_padrao=p["eta_F"], eta_req=eta_req,
              BSW_lim=p["BSW_F"], Q_A_e=wat_in_v, Q_O=O06_v)
        t.reg("separacao_oleo_agua", "SG-001",
              dict(agua_no_oleo=wat06_v, agua_removida=wat05_v, oleo_na_agua=oil05_v),
              Q_O=vol(s03, "O"), Q_agua=wat_in_v, BSW=BSW_F)
        fW = vol(s03, "W") / wat_in_v if wat_in_v > 0 else 1.0
        oil05 = m("O", oil05_v)
        s04 = t.reg("corrente_separada", "C-04", _vapor_do_estagio(carryF, "C-04", tr and oleo_vap, tr and gas_vap,
                                                                    m("G", G_Fv)))
        s05 = t.reg("corrente_separada", "C-05",
                    corrente(O=oil05, W=m("W", wat05_v * fW), D=m("D", wat05_v * (1 - fW))), f_W=fW)
        G06 = s03["G"] - s04["G"] if tr else m("G", G_D1v + G_D2v)
        s06 = t.reg("corrente_separada", "C-06",
                    corrente(O=s03["O"] - s04["O"] - oil05, W=m("W", wat06_v * fW),
                             D=m("D", wat06_v * (1 - fW)), G=G06), f_W=fW)
        # ---------------- V-001
        carry1 = t.reg("arraste_liquido", "C-09", m("O", carry * G_D1v), carry=carry, Q_G=G_D1v)
        s09 = t.reg("corrente_separada", "C-09", _vapor_do_estagio(carry1, "C-09", tr and oleo_vap, tr and gas_vap,
                                                                    m("G", G_D1v)))
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
        s17 = t.reg("corrente_separada", "C-17", _vapor_do_estagio(carry2, "C-17", tr and oleo_vap, tr and gas_vap,
                                                                    m("G", G_D2v)))
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
        diff = max(abs(new_rec[c] - reciclo[c]) for c in COMP) + abs(newT02 - T02) + abs(T08 - TD1)
        t.reg("convergencia_reciclo", "M-03", diff, iteracao=it, tol=num["reciclo_tol"])
        reciclo, T02, TD1, TD2 = new_rec, newT02, T08, T16
        if it > num["reciclo_min_iter"] and diff < num["reciclo_tol"]:
            if tr is not None and _condicoes_mudaram(tr, T03, TD1, TD2):
                refazer_trem = True
                continue
            break

    s02 = reciclo
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
    # dRsD1 reportado com o T_D1 já atualizado (como no original); sem Standing no caso avaliável
    gas = dict(G_in=Gin_v, G_F=G_Fv, G_D1=G_D1v, G_D2=G_D2v, Dv=Dv,
               dRsF=None if tr else dRs(p["P_FWKO"], TF), dRsD1=None if tr else dRs(p["P_D1"], TD1))
    gas_padrao = _gas_padrao(streams, tr, G01, Gin_v) if tr else {}
    mu = mu_interp(poco.viscosidade, T03)
    t.reg("viscosidade_oleo", "SG-001", mu[0], T=T03, marcador=mu[1])
    # estado do SG-001: η adotado e se o BSW_F,máx do BOT 2.7.1.2 exigiu η acima do padrão
    # (informação, não exceção)
    exigido = eta_req is not None and eta_req > p["eta_F"]
    textos = carregar("constantes.toml")["modelo"]
    estado = "estado_sem_agua" if eta_A is None else "estado_exigido" if exigido else "estado_padrao"
    fwko = dict(eta=eta_A, eta_req=eta_req, eta_padrao=p["eta_F"], exigido_acima=exigido, estado=textos[estado])
    return EstadoProcesso(caso=caso, fluid=fl, well=well, api=api, rho=rho, cp=cp, gp=gp, Wv=Wv,
                          BSW01=BSW01, BSW_F=BSW_F, streams=streams, T=temps, P=press, duties=duties,
                          gas=gas, iters=it, residuo_reciclo=diff, VM=VM, mu=mu, T_ref=T_ref, trace=t, fwko=fwko,
                          composicao=z_base, mws_plus=mws,
                          proveniencia=proveniencia.consumidas("balanco", avaliavel=aval),
                          trem=tr if aval else trem_mod.nao_avaliavel(motivo), gas_padrao=gas_padrao,
                          T_tvp_C=p[trem_mod.cfg()["tvp"]["premissa_T"]])


def aplicar_rating_termico(estado, q_real, prem):
    """Refaz a etapa térmica depois do rating da geometria instalada do P-001.

    O primeiro passe do resolvedor determina massas, propriedades e o teto Pinch. O rating
    fornece a recuperação que o equipamento físico realmente entrega; este segundo passe
    recalcula as quatro correntes térmicas e as utilidades residuais sem reexecutar o trem.
    ``CalcTrace`` também é copiado e sobrescrito, para que estado e rastro continuem sendo uma
    única representação do mesmo cálculo.
    """
    if estado.etapa != ETAPA_PRELIMINAR:
        raise ValueError("o rating do P-001 parte do estado preliminar, nunca de um estado já ajustado")
    if not math.isfinite(q_real) or q_real < 0 or q_real > estado.duties["Q_pre"]:
        raise ValueError("Q_real deve estar entre zero e o teto Pinch do caso")

    cc = estado.C(estado.streams["C-06"])
    ch = estado.C(estado.streams["C-22"])
    t06, t22 = estado.T["C-06"], estado.T["C-22"]
    t07 = t06 + q_real / cc
    t23 = t22 - q_real / ch
    t08 = max(prem["T_trat"], t07)
    t24 = min(t23, prem["T_store"])
    qh = cc * (t08 - t07)
    qc = ch * (t23 - t24)

    trace = CalcTrace()
    for passo in estado.trace:
        trace.reg(passo.equacao, passo.escopo, passo.valor, **passo.entradas)
    trace.reg("carga_preaquecedor", "P-001", q_real, C_frio=cc, C_quente=ch,
              T_frio=t06, T_quente=t22, dT_app=prem["dT_app"], etapa="rating")
    trace.reg("temperatura_preaquecedor", "C-07", t07, T_in=t06, Q=q_real, C=cc,
              etapa="rating")
    trace.reg("temperatura_preaquecedor", "C-23", t23, T_in=t22, Q=q_real, C=ch,
              etapa="rating")
    trace.reg("carga_aquecedor", "P-002", qh, T07=t07, T08=t08, C=cc, etapa="rating")
    trace.reg("carga_resfriador", "P-003", qc, T23=t23, T24=t24, C=ch, etapa="rating")

    novas_t = {"C-07": t07, "C-08": t08, "C-23": t23, "C-24": t24, "C-25": t24, "C-26": t24}
    novas_q = {"Q_pre": q_real, "Q_H": qh, "Q_C": qc}
    antes = {"T": {k: estado.T[k] for k in CORRENTES_RATING},
             "duties": {k: estado.duties[k] for k in CARGAS_RATING}}
    return replace(estado, T=dict(estado.T, **novas_t), duties=dict(estado.duties, **novas_q), trace=trace,
                   etapa=ETAPA_RATING, antes_do_rating=antes)


def _condicoes_mudaram(tr, TF, TD1, TD2):
    """As temperaturas convergidas do reciclo se afastaram das que o trem usou?"""
    tol = trem_mod.cfg()["acoplamento"]["tolerancia_condicao_C"]
    usadas = [e.T_C for e in tr.estagios]
    return max(abs(a - b) for a, b in zip(usadas, (TF, TD1, TD2))) > tol


def _vapor_do_estagio(arraste, cid, oleo_vap, gas_vap, gas_standing):
    """Corrente de gás de um estágio. No caso avaliável: O = arraste + óleo morto vaporizado,
    G = o resto do vapor; no não avaliável: O = arraste, G = gás de Standing."""
    if not oleo_vap:
        return corrente(O=arraste, G=gas_standing)
    return corrente(O=arraste + oleo_vap[cid], G=gas_vap[cid])


def _gas_padrao(streams, tr, G01, Gin_v):
    """Sm³/d do componente G de cada corrente num caso avaliável. A corrente de gás de um estágio
    é o vapor inteiro (ṅ_V·V_M, a vazão que o vaso recebe); o gás de entrada é o da
    recombinação; o gás dissolvido num líquido tem o volume que o líquido do seu estágio libera
    até a condição padrão (trem.toml [reservatorio_gas])."""
    q = {e.corrente_gas: e.q_vapor_sm3d for e in tr.estagios}
    reserv = {"C-01": (G01, Gin_v)}
    dissolvido = {e.ponto: (e.m_gas_dissolvido_kg_d * K_DIA, e.q_gas_dissolvido_sm3d) for e in tr.estagios}
    for cid, sids in trem_mod.cfg()["reservatorio_gas"].items():
        for sid in sids:
            reserv[sid] = reserv[cid] if cid in reserv else dissolvido[cid]
    out = {}
    for sid, s in streams.items():
        m, v = reserv.get(sid, (0.0, 0.0))
        out[sid] = q[sid] if sid in q else (s["G"] * v / m if m > 0 else 0.0)
    return out


def resolver_todos(dados, prem=None):
    return [resolver_caso(c, dados, prem) for c in dados.casos]
