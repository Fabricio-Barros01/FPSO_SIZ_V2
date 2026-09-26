"""Bomba centrífuga e linha de recalque — Moran (2016), "Pump Sizing", CEP.
Port de sizing/pump/moran.jl. Não é vaso: varre o diâmetro nominal da série comercial
(Figura 3), a exigência é a carga do sistema H = h_est + h_atrito, e cada caso restringe
o DN pela banda de velocidade, pela folga de NPSH e pela validade da correlação de atrito
(case_admissible). Escolhe-se o MENOR DN admissível.
"""
import math
from dataclasses import dataclass, replace

from fpso_siz.core.contrato import Equipamento, ResultField, SweepAxis, SweepColumn, der
from fpso_siz.core.corrente import field_units
from fpso_siz.core.formato_julia import jl, jl_round
from fpso_siz.core.trace import Rastro
from fpso_siz.core.unidades import kpa_para_pa, m3h_para_m3s, mm_para_m, potencia_hidraulica_kw
from fpso_siz.sizing.base import MetodoTOML, driver_case
from fpso_siz.sizing.hidraulica import (antoine_pressure, darcy_friction, fittings_head, flow_regime,
                                        friction_equation, reynolds_pipe, straight_run_head)


class CentrifugalPump(Equipamento):
    method_id, label = "pump", "Bomba Centrífuga e Linha de Recalque"


@dataclass(frozen=True)
class PumpConstraints:
    q_m3s: float
    q_m3h: float
    rho: float
    mu: float
    h_est: float
    npsh_estatico: float
    npsh_exigido: float
    l_suc: float
    k_suc: float
    l_rec: float
    k_rec: float
    rugosidade_m: float
    rendimento: float
    g: float
    k: dict


def _hidraulica(c, dn_mm):
    d = mm_para_m(dn_mm)
    if not d > 0:
        return dict(d=d, v=math.inf, re=math.nan, f=math.nan, regime="indefinido", confiavel=False, hf_suc=math.inf,
                    hf_rec=math.inf, h_atrito=math.inf, h_total=math.inf, npsh=-math.inf)
    v = c.q_m3s / (math.pi * (d * d) / 4)
    re = reynolds_pipe(c.rho, v, d, c.mu)
    f, regime, confiavel = darcy_friction(re, c.rugosidade_m / d, c.k)
    hf_suc = straight_run_head(f, c.l_suc, d, v, c.g) + fittings_head(c.k_suc, v, c.g)
    hf_rec = straight_run_head(f, c.l_rec, d, v, c.g) + fittings_head(c.k_rec, v, c.g)
    return dict(d=d, v=v, re=re, f=f, regime=regime, confiavel=confiavel, hf_suc=hf_suc, hf_rec=hf_rec,
                h_atrito=hf_suc + hf_rec, h_total=c.h_est + hf_suc + hf_rec, npsh=c.npsh_estatico - hf_suc)


def _politica_transicao(hid, k):
    """P-44b — POLÍTICA conservadora de engenharia, não correlação: na zona de transição
    laminar-turbulento nenhuma correlação desta implementação é válida (Moran 2016 declara
    Colebrook-White só para Re > 4000). Num caso de turndown, o f avaliado por Colebrook-White
    é aceito como estimativa conservadora quando não é menor que o de Hagen-Poiseuille (64/Re)
    no mesmo Re, o que tende a superestimar a perda e subestimar o NPSH. Não é limite superior
    demonstrado do f real na transição."""
    return hid["regime"] == "transicao" and hid["f"] >= float(k["laminar_coefficient"]) / hid["re"]


class MoranPumpSizing(MetodoTOML):
    method_id = "moran"
    config = "equipment/pump/moran.toml"
    rotulo_padrao = "Moran (2016) — carga do sistema"
    ajustes_corrente = "equipment/pump/moran_corrente.toml"
    config_extensoes = "equipment/pump/moran_extensoes.toml"

    def applies_to(self):
        return CentrifugalPump()

    def stream_keys(self):
        return ("q_oil", "rho_oil", "mu_oil", "pressure", "temperature")

    def sizing_constraints(self, s, p, k):
        tr = Rastro()
        fu = field_units(s)
        g = float(k["gravity"])
        rho, mu, q_h = fu.rho_o, s.oil.viscosity, fu.q_o
        if not (math.isfinite(rho) and rho > 0):
            return (False, "Densidade do líquido não informada ou inválida: sem ela não há carga estática por pressão "
                           "nem Reynolds.", tr)
        if not (math.isfinite(mu) and mu > 0):
            return (False, "Viscosidade do líquido não informada ou inválida: o fator de atrito de Darcy não pôde ser "
                           "avaliado.", tr)
        if not (math.isfinite(q_h) and q_h > 0):
            return False, "Vazão bombeada não informada ou inválida.", tr
        p_suc = kpa_para_pa(fu.p_kpa)
        p_rec = kpa_para_pa(p["p_recalque"])
        h_pressao = (p_rec - p_suc) / (rho * g)
        h_est = p["h_geometrica"] + h_pressao
        tr.trace("estatica", "—", "Δz", "cota de recalque − cota de sucção", p["h_geometrica"], "m")
        tr.trace("estatica", "—", "h_pressão", "(P_rec − P_suc)/(ρg)", h_pressao, "m")
        tr.trace("estatica", "—", "h_est", "Δz + h_pressão", h_est, "m")
        if not math.isnan(p["pv_informada"]):
            if not math.isfinite(p["pv_informada"]) or p["pv_informada"] < 0:
                return False, "Pressão de vapor informada deve ser finita e não negativa.", tr
            # extensão V2: pressão de vapor dada (ex.: líquido saturado no vaso de sucção)
            pv = kpa_para_pa(p["pv_informada"])
            tr.trace("npsh", "—", "Pv", "informada", pv, "Pa")
        else:
            pv = antoine_pressure(p["antoine_a"], p["antoine_b"], p["antoine_c"], fu.t_k)
            if not math.isfinite(pv):
                return (False, "A equação de Antoine não pôde ser avaliada (confira A, B, C e a temperatura): sem "
                               "pressão de vapor não há NPSH disponível.", tr)
            tr.trace("npsh", "Eq. 5", "Pv", "10^(A − B/(T+C)) bar", pv, "Pa")
        npsh_est = (p_suc - pv) / (rho * g) + p["h_sucao"]
        tr.trace("npsh", "Eq. 6", "NPSH sem atrito", "(P₀ − Pv)/(ρg) + h₀", npsh_est, "m")
        tr.trace("npsh", "—", "NPSH exigido", "NPSHr + margem", p["npsh_requerido"] + p["npsh_margem"], "m")
        cons = PumpConstraints(m3h_para_m3s(q_h), q_h, rho, mu, h_est, npsh_est, p["npsh_requerido"] + p["npsh_margem"],
                               p["l_sucao"], p["k_sucao"], p["l_recalque"], p["k_recalque"],
                               mm_para_m(p["rugosidade"]), p["rendimento"], g, dict(k))
        return True, cons, tr

    def sweep_axis(self, p):
        serie = [float(d) for d in self.constants()["nominal_diameters"]]
        return SweepAxis("dn", "diâmetro nominal", "mm", tuple(d for d in serie if p["dn_min"] <= d <= p["dn_max"]))

    def global_keys(self):
        return ["dn_min", "dn_max", "v_min", "v_max"]

    def requirement(self, dn, c):
        return _hidraulica(c, dn)["h_total"]

    def governing_of(self, dn, c):
        return "atrito" if _hidraulica(c, dn)["h_atrito"] > c.h_est else "estatica"

    def per_constraint(self, dn, c):
        return {"estatica": c.h_est, "atrito": _hidraulica(c, dn)["h_atrito"]}

    def derived(self, dn, h, gov, c, k, p):
        hid = _hidraulica(c, dn)
        return {"v": hid["v"], "re": hid["re"], "f": hid["f"], "h_est": c.h_est, "h_atrito": hid["h_atrito"],
                "npsh": hid["npsh"], "folga_npsh": hid["npsh"] - c.npsh_exigido,
                "confiavel": 1.0 if hid["confiavel"] else 0.0,
                "re_min_correlacao": float(k["reynolds_turbulent_min"]),
                "re_max_laminar": float(k["reynolds_laminar_max"]),
                "potencia": potencia_hidraulica_kw(c.rho, c.q_m3h, h, c.rendimento, c.g)}

    def case_admissible(self, dn, c, p):
        hid = _hidraulica(c, dn)
        return p["v_min"] <= hid["v"] <= p["v_max"] and hid["npsh"] >= c.npsh_exigido and \
            (hid["confiavel"] or (p.get("aceita_transicao", 0.0) and _politica_transicao(hid, c.k)))

    def admissible(self, dn, der_, p):
        return True

    def objective(self, dn, der_, p):
        return dn

    def envelope_params(self, params):
        v_min = max(p["v_min"] for p in params)
        v_max = min(p["v_max"] for p in params)
        if not v_min <= v_max:
            return (False, f"As bandas de velocidade pedidas pelos casos não se cruzam: um exige v ≥ {jl(v_min)} m/s e "
                           f"outro v ≤ {jl(v_max)} m/s. Como a linha é uma só, não há velocidade que atenda a todos.")
        return True, dict(dn_min=min(p["dn_min"] for p in params), dn_max=max(p["dn_max"] for p in params),
                          v_min=v_min, v_max=v_max,
                          piso_caso_projeto=max(p.get("piso_caso_projeto", 0.0) for p in params),
                          transicao_turndown=max(p.get("transicao_turndown", 0.0) for p in params))

    def envelope_case_params(self, conss, p_env):
        """P-44 (piso_caso_projeto): o piso v_min só no caso de projeto, o de maior vazão
        volumétrica; os demais casos, na mesma linha, só com o teto (turndown). P-44b
        (transicao_turndown): no turndown, a zona de transição pela política conservadora."""
        if not p_env.get("piso_caso_projeto", 0.0) or not conss:
            return super().envelope_case_params(conss, p_env)
        projeto = self.caso_projeto(conss)
        turndown = {**p_env, "v_min": 0.0, "aceita_transicao": p_env.get("transicao_turndown", 0.0)}
        return [p_env if i == projeto else turndown for i in range(len(conss))]

    def caso_projeto(self, conss):
        """Índice do caso de projeto da linha (maior vazão volumétrica)."""
        return max(range(len(conss)), key=lambda i: conss[i].q_m3s)

    def selection_message(self, rows, teto, p, mechanism="none"):
        if not rows:
            return "A grade de diâmetros nominais ficou vazia."
        banda = f"{jl(p['v_min'])}–{jl(p['v_max'])} m/s"
        vs = [r.derivados.get("v", math.nan) for r in rows]
        na_banda = [i for i, v in enumerate(vs) if p["v_min"] <= v <= p["v_max"]]
        if not na_banda:
            fin = [v for v in vs if math.isfinite(v)]
            return (f"Nenhum diâmetro da grade mantém a velocidade na banda {banda}: na grade oferecida ela varia de "
                    f"{jl_round(min(fin), 2)} a {jl_round(max(fin), 2)} m/s. Amplie a grade de DN, ou reveja a banda.")
        validos = [i for i in na_banda if rows[i].derivados.get("confiavel", 1.0) != 0.0]
        if not validos:
            res = [x for x in (rows[i].derivados.get("re", math.nan) for i in na_banda) if math.isfinite(x)]
            d0 = rows[na_banda[0]].derivados
            lam, turb = jl_round(d0["re_max_laminar"], 0), jl_round(d0["re_min_correlacao"], 0)
            return (f"Na banda de velocidade {banda} todos os diâmetros caem na zona de transição do escoamento (Re "
                    f"de {jl_round(min(res), 0)} a {jl_round(max(res), 0)}, entre {lam} e {turb}), onde nenhuma "
                    f"correlação de atrito desta implementação vale: o artigo declara Colebrook-White para Re > {turb} "
                    f"e f = 64/Re só até Re {lam}. O programa não extrapola. Reveja a viscosidade ou a temperatura do "
                    "líquido, ou mude a banda de velocidade para deslocar o Reynolds.")
        melhor = max(rows[i].derivados.get("folga_npsh", math.nan) for i in validos)
        if not (math.isfinite(melhor) and melhor < 0):
            return (f"Há diâmetros na banda de velocidade {banda}, e neles o NPSH tem folga (a maior é "
                    f"{jl_round(melhor, 2)} m). A recusa não veio deste caso.")
        return (f"Na banda de velocidade {banda} todos os diâmetros cavitam: a maior folga de NPSH é "
                f"{jl_round(melhor, 2)} m, e ela precisa ser ≥ 0. Suba o nível do reservatório de sucção, encurte a "
                "linha de sucção, reduza a temperatura, ou escolha bomba de menor NPSH requerido.")

    # --- memorial (F10x): mesma hidráulica do dimensionamento
    def curva_sistema(self, cons, dn, fracoes):
        """[(Q [m³/h], H [m])] da linha com o DN escolhido, com a vazão de projeto multiplicada
        por cada fração. Q = 0: só a carga estática. Ponto sem correlação de atrito válida
        (transição laminar-turbulento) fica NaN: o programa não extrapola."""
        pontos = []
        for f in fracoes:
            if f == 0:
                pontos.append((0.0, cons.h_est))
                continue
            hid = _hidraulica(replace(cons, q_m3s=cons.q_m3s * f, q_m3h=cons.q_m3h * f), dn)
            pontos.append((cons.q_m3h * f, hid["h_total"] if hid["confiavel"] else math.nan))
        return pontos

    def envelope_derived(self, dn, conss, pcs, p_env):
        """As três potências de eixo, separadas (extensão do V2; o `potencia` dos derivados é a
        do caso governante, como no Julia):
        - caso governante: a do caso que exige a maior carga H;
        - máxima operacional: a maior entre os casos, cada um no seu (Q, H, ρ, η);
        - nominal requerida: no ponto nominal (Q máximo, H máximo, ρ máximo e η mínimo entre
          os casos), sem margem de acionador (margem é dado de norma ou fabricante, fora do
          acervo)."""
        if not conss:
            return {}
        op = self.operacao_por_caso(conss, dn, pcs)
        governante = max(range(len(op)), key=lambda i: op[i]["h"])
        nominal = dict(q=max(c.q_m3h for c in conss), h=max(o["h"] for o in op), rho=max(c.rho for c in conss),
                       rendimento=min(c.rendimento for c in conss))
        return {"potencia_caso_governante": op[governante]["potencia"],
                "potencia_max_operacional": max(o["potencia"] for o in op),
                "potencia_nominal": potencia_hidraulica_kw(nominal["rho"], nominal["q"], nominal["h"],
                                                           nominal["rendimento"], conss[0].g),
                "q_nominal": nominal["q"], "h_nominal": nominal["h"], "caso_projeto": float(self.caso_projeto(conss))}

    def operacao_por_caso(self, conss, dn, pcs):
        """Operação de cada caso na linha escolhida (mesma hidráulica do dimensionamento):
        papel do caso (projeto/turndown pela P-44), v, Re, regime, f, H, folga de NPSH, potência
        e se o atrito veio da política conservadora de transição (P-44b)."""
        projeto = self.caso_projeto(conss) if conss else -1
        out = []
        for i, (c, pc) in enumerate(zip(conss, pcs)):
            h = _hidraulica(c, dn)
            out.append(dict(papel="projeto" if i == projeto else "turndown", q=c.q_m3h, v=h["v"], re=h["re"],
                            regime=h["regime"], f=h["f"], h=h["h_total"], folga_npsh=h["npsh"] - c.npsh_exigido,
                            potencia=potencia_hidraulica_kw(c.rho, c.q_m3h, h["h_total"], c.rendimento, c.g),
                            politica_transicao=not h["confiavel"] and bool(pc.get("aceita_transicao", 0.0))
                            and _politica_transicao(h, c.k)))
        return out

    def npsh_exigido(self, cons):
        return cons.npsh_exigido

    def npsh_disponivel(self, derivados):
        return derivados["npsh"]

    def governing_label(self, g):
        return {"atrito": "perda por atrito", "estatica": "carga estática"}.get(g, str(g))

    def requirement_spec(self):
        return ("carga do sistema", "m")

    def result_fields(self, r):
        tem = getattr(r, "feasible", True) and math.isfinite(r.x)

        def txt(v):
            return v if tem else "—"

        ok = "neutro" if not tem else ("ok" if getattr(r, "ok", True) else "erro")
        v2 = getattr(r, "derivados_v2", {}) or {}
        folga = der(r, "folga_npsh")
        st_npsh = "neutro" if not tem or not math.isfinite(folga) else ("ok" if folga >= 0 else "erro")
        return [
            ResultField("Diâmetro nominal DN", r.x if tem else math.nan, unit="mm", digits=0, highlight=True),
            ResultField("Carga do sistema H", r.y if tem else math.nan, unit="m", highlight=True),
            ResultField("Velocidade v", der(r, "v"), unit="m/s", status=ok),
            ResultField("Carga estática", der(r, "h_est"), unit="m"),
            ResultField("Perda de carga", der(r, "h_atrito"), unit="m"),
            ResultField("Reynolds", der(r, "re"), digits=0),
            ResultField("Fator de atrito f", der(r, "f"), digits=4),
            ResultField("NPSH disponível", der(r, "npsh"), unit="m"),
            ResultField("Folga de NPSH", folga, unit="m", status=st_npsh),
            *([ResultField("Potência de eixo", der(r, "potencia"), unit="kW")] if not v2 else [
                ResultField("Potência no caso governante", v2["potencia_caso_governante"], unit="kW"),
                ResultField("Potência máxima operacional", v2["potencia_max_operacional"], unit="kW"),
                ResultField("Potência nominal requerida", v2["potencia_nominal"], unit="kW", highlight=True)]),
            ResultField("Parcela governante", txt(self.governing_label(r.governing))),
            ResultField("Caso governante", txt(driver_case(r))),
        ]

    def sweep_columns(self):
        return [SweepColumn("DN (mm)", "x", 0), SweepColumn("H (m)", "y"), SweepColumn("v (m/s)", "v"),
                SweepColumn("NPSHd (m)", "npsh"), SweepColumn("P (kW)", "potencia")]

    def trace_blocks(self):
        return [("estatica", "Bloco A — carga estática"), ("npsh", "Bloco B — NPSH disponível"),
                ("selection", "Seleção do diâmetro nominal")]

    def grid_hint(self, p):
        return (f"A grade é a série da Figura 3 recortada por DN mínimo ({jl(p['dn_min'])}) e DN máximo "
                f"({jl(p['dn_max'])}).")

    def trace_selection(self, tr, best, p):
        d = best.derivados
        re = d.get("re", math.nan)
        k = self.constants()
        regime, confiavel = flow_regime(re, k)
        fonte_f, forma_f = friction_equation(regime)
        tr.trace("selection", "—", "DN escolhido",
                 f"menor DN com {jl(p['v_min'])} ≤ v ≤ {jl(p['v_max'])} m/s, NPSH folgado e correlação de atrito válida",
                 best.x, "mm")
        tr.trace("selection", "—", "v", "Q/(πD²/4)", d.get("v", math.nan), "m/s")
        tr.trace("selection", "Eq. 3", "Re", "ρvD/µ", re, "–")
        tr.trace("selection", "§ regime", "regime",
                 f"laminar até Re {jl_round(float(k['reynolds_laminar_max']), 0)}; turbulento a partir de "
                 f"{jl_round(float(k['reynolds_turbulent_min']), 0)} — aqui: {regime}", 1.0 if confiavel else 0.0,
                 "válida?")
        tr.trace("selection", fonte_f, "f", forma_f, d.get("f", math.nan), "–")
        tr.trace("selection", "Eq. 1/4", "h_atrito", "f·(L/D)·v²/2g + Σk·v²/2g", d.get("h_atrito", math.nan), "m")
        tr.trace("selection", "—", "H", "h_est + h_atrito", best.y, "m")
        tr.trace("selection", "Eq. 6", "NPSH disponível", "(P₀−Pv)/(ρg) + h₀ − h_atrito,suc", d.get("npsh", math.nan), "m")
        tr.trace("selection", "Eq. 7", "P", "ρgQH/(3,6×10⁶·η)", d.get("potencia", math.nan), "kW")
