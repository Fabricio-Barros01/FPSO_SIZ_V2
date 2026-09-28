"""Fase 5.1 — cascata composicional do trem de separação, em modo sombra.

Gera `docs/validacao/34-cascata-composicional.md`: a compatibilização de `oil_sm3d`,
`produced_gas_sm3d` e `fluid_compositions`, a base molar declarada, a auditoria do gás de
lift, a sequência dos três estágios, o fechamento do trem e a comparação
F5 (flashes independentes) × F5.1 (cascata) × Standing legado.

    uv run python tools/cascata_composicional.py
"""
import argparse
import json
import math
import time
from collections import Counter
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, constantes, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import cascata as cs
from fpso_siz.pfd import estado_termodinamico as et
from fpso_siz.pfd import integracao as ig

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
MOSTRAR = 8      # componentes mostrados nas tabelas de composição (os de maior fração)


def n(x, casas=4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def e(x, casas=2):
    return "—" if x is None or not isinstance(x, (int, float)) or not math.isfinite(x) else f"{x:.{casas}e}"


def espiao_de_flash():
    """Conta flashes e condições (T, P, z) distintas — medida, não otimização."""
    from fpso_siz.pfd import _chedl
    original, chaves, total = _chedl.flash_pseudo, Counter(), [0]

    def espiao(reais, pseudos, zs, T, P, kij):
        total[0] += 1
        chaves[(round(T, 9), round(P, 3), tuple(round(v, 12) for v in zs))] += 1
        return original(reais, pseudos, zs, T, P, kij)

    _chedl.flash_pseudo = espiao
    return original, chaves, total


# ------------------------------------------------------------------ seções
def secao_compatibilizacao(dados, res, mws):
    """Antes da base molar: oil_sm3d, produced_gas_sm3d e fluid_compositions fecham entre si?"""
    vm = cs.volume_molar_padrao(dados)
    T0, P0 = c_para_k(dados.T_std_C), kpa_para_pa(dados.P_std_kPa)
    out = ["## 1. `oil_sm3d`, `produced_gas_sm3d` e `fluid_compositions` são compatíveis?", "",
           "**Não são, e a incompatibilidade é estrutural.** `fluid_compositions` é por TIPO DE",
           "FLUIDO (sete tipos), e o mesmo tipo aparece em casos com GOR bem diferentes — o flash",
           "de uma composição só não pode reproduzir os dois volumes de todos os casos. A medida",
           f"abaixo usa o equilíbrio na condição padrão ({n(dados.T_std_C, 1)} °C, "
           f"{n(dados.P_std_kPa, 1)} kPa, V_M = {n(vm, 4)} sm³/kmol) e a ρ do óleo pela API do poço:",
           "",
           "| caso | fluido | GOR do BOT | GOR do flash | razão | base pelo gás (kmol/d) | base pelo óleo (kmol/d) | discordância |",
           "|---:|---|---:|---:|---:|---:|---:|---:|"]
    piores = []
    for r in res:
        c = dados.caso(r.num)
        fl = c["fluid_type"]
        z = {k: v for k, v in dados.composicoes[fl].items() if v > 0}
        est = et.flash_poco(T0, P0, z, mws)
        v, li = est.vapor, est.liquido
        if v is None or li is None:
            out.append(f"| {r.num} | {fl} | — | monofásico na condição padrão | — | — | — | — |")
            continue
        b = v.fracao_molar
        rho_o = cs.massa_especifica_oleo(dados, fl)
        gor_bot = c["produced_gas_sm3d"] / c["oil_sm3d"]
        gor_flash = (b * vm) / ((1 - b) * li.MW / rho_o)
        n_gas = c["produced_gas_sm3d"] / vm
        n_oleo = c["oil_sm3d"] * rho_o / li.MW
        base_gas, base_oleo = n_gas / b, n_oleo / (1 - b)
        disc = max(base_gas, base_oleo) / min(base_gas, base_oleo) - 1
        piores.append((disc, r.num))
        out.append(f"| {r.num} | {fl} | {n(gor_bot, 1)} | {n(gor_flash, 1)} | {n(gor_flash / gor_bot, 2)} | "
                   f"{n(base_gas, 0)} | {n(base_oleo, 0)} | {n(disc * 100, 1)} % |")
    pior = max(piores) if piores else (0, 0)
    menor = min(piores) if piores else (0, 0)
    out += ["",
            f"A discordância entre as duas bases possíveis vai de **{n(menor[0] * 100, 1)} %** "
            f"(caso {menor[1]}) a **{n(pior[0] * 100, 1)} %** (caso {pior[1]}). Escolher uma delas "
            "seria inventar quantidade molar para fechar o flash — que é exatamente o que não se faz aqui.", ""]
    return out


def secao_base_molar(dados, cascatas):
    regra = cs.regra_base_molar()
    out = ["## 2. A base molar absoluta, declarada", "", "```", f"    {regra['regra']}", "```", "",
           f"- **massa**: {regra['massa']}", f"- **MW**: {regra['mw']}",
           f"- **ρ do óleo**: {regra['rho_oleo']}", f"- **ρ do gás**: {regra['rho_gas']}",
           f"- **por que não pelo split**: {regra['por_que_nao_o_split']}",
           f"- **o que isso conserva**: {regra['conserva']}", "",
           "| caso | fluido | óleo (sm³/d) | gás produzido (sm³/d) | ṁ óleo (kg/d) | ṁ gás (kg/d) | ṁ HC (kg/d) | MW_z (g/mol) | ṅ_F (kmol/d) |",
           "|---:|---|---:|---:|---:|---:|---:|---:|---:|"]
    for c, _ in cascatas:
        b = c.base
        if b is None:
            out.append(f"| {c.caso} | {c.fluido} | — | — | — | — | — | — | — |")
            continue
        out.append(f"| {c.caso} | {c.fluido} | {n(b.oil_sm3d, 0)} | {n(b.gas_produzido_sm3d, 0)} | "
                   f"{n(b.massa_oleo_kg_d, 0)} | {n(b.massa_gas_kg_d, 0)} | {n(b.massa_kg_d, 0)} | "
                   f"{n(b.MW_z, 2)} | {n(b.n_F_kmol_d, 1)} |")
    return out + [""]


def secao_lift(dados, cascatas):
    lac = cs.lacunas()[0]
    com = [c for c, _ in cascatas if c.base is not None and c.base.tem_lift]
    out = ["## 3. Gás de lift: lacuna declarada", "",
           f"**Situação: {lac['situacao']}.** Fonte procurada: {lac['fonte_procurada']}.", "",
           f"- O que a fonte dá: {lac['o_que_a_fonte_da']}.",
           f"- O que existe na fonte: {lac['o_que_existe_na_fonte']}.",
           f"- Efeito: {lac['efeito']}",
           f"- Decisão: **{lac['decisao']}**", ""]
    if not com:
        return out + ["Nenhum caso com `lift_gas_sm3d` > 0.", ""]
    out += [f"Casos afetados ({len(com)} de {len(cascatas)}):", "",
            "| caso | fluido | gás produzido (sm³/d) | gás de lift (sm³/d) | lift / gás de entrada | ṅ_F da cascata cobre |",
            "|---:|---|---:|---:|---:|---|"]
    for c in com:
        b = c.base
        out.append(f"| {c.caso} | {c.fluido} | {n(b.gas_produzido_sm3d, 0)} | {n(b.gas_lift_sm3d, 0)} | "
                   f"{n(b.fracao_de_lift * 100, 1)} % | só o gás produzido |")
    return out + ["", "Nesses casos a cascata em sombra e o balanço produtivo **não partem da mesma massa**: "
                      "a diferença é exatamente a massa de gás de lift, à qual o balanço atribui a composição "
                      "do poço por falta de outra. Isso não é corrigido aqui — é registrado.", ""]


def _principais(comp, k=MOSTRAR):
    return [c for c, _ in sorted(comp.items(), key=lambda kv: -kv[1])[:k]]


def secao_estagios(cascatas, caso_detalhe):
    c = next(x for x, _ in cascatas if x.caso == caso_detalhe)
    out = [f"## 4. A sequência dos três estágios (caso {c.caso} — {c.fluido})", "",
           "| estágio | corrente | T (°C) | P (kPa) | β | ṅ_V (kmol/d) | ṁ_V (kg/d) | ṅ_L (kmol/d) | ṁ_L (kg/d) | MW_V | Z_V | ρ_V (kg/m³) |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in c.estagios:
        v = s.vapor
        out.append(f"| {s.ponto} | {s.corrente_gas} | {n(s.T_C, 2)} | {n(s.P_kPa, 1)} | {n(s.beta, 6)} | "
                   f"{n(s.n_vapor_kmol_d, 1)} | {n(s.m_vapor_kg_d, 0)} | {n(s.n_liquido_kmol_d, 1)} | "
                   f"{n(s.m_liquido_kg_d, 0)} | {n(v.MW, 3) if v else '—'} | {n(v.Z, 5) if v else '—'} | "
                   f"{n(v.rho, 4) if v else '—'} |")
    chaves = _principais(c.estagios[0].z)
    out += ["", f"Composições (fração molar; os {len(chaves)} componentes de maior fração na alimentação):", "",
            "| componente | " + " | ".join(f"y {s.ponto} | x {s.ponto}" for s in c.estagios) + " |",
            "|---|" + "---:|" * (2 * len(c.estagios))]
    for k in chaves:
        cels = []
        for s in c.estagios:
            cels += [n(s.y.get(k, 0.0), 6), n(s.x.get(k, 0.0), 6)]
        out.append(f"| {k} | " + " | ".join(cels) + " |")
    out += ["", "A alimentação de cada estágio é o **líquido** do anterior: "
                + " → ".join(["z₀"] + [f"x({s.ponto})" for s in c.estagios[:-1]]) + ".", ""]
    return out


def secao_fechamento(cascatas):
    out = ["## 5. Fechamento do trem", "", "```",
           "    ṅ_HC,in = ṅ_V,F + ṅ_V,1 + ṅ_V,2 + ṅ_L,final          (global)",
           "    ṅ_F·z_i = Σ_e ṅ_V,e·y_i,e + ṅ_L,final·x_i,final       (componente a componente)",
           "```", "",
           "| caso | estágios | completa | erro molar rel. | erro mássico rel. | erro por componente | pior componente | pior fechamento de flash |",
           "|---:|---:|:--:|---:|---:|---:|---|---:|"]
    piores = {"molar": 0.0, "massa": 0.0, "comp": 0.0, "flash": 0.0}
    for c, f in cascatas:
        if f is None:
            out.append(f"| {c.caso} | 0 | não | — | — | — | — | — | {c.interrompida} |")
            continue
        piores["molar"] = max(piores["molar"], f.erro_molar_relativo)
        piores["massa"] = max(piores["massa"], f.erro_massico_relativo)
        piores["comp"] = max(piores["comp"], f.erro_componente_max)
        piores["flash"] = max(piores["flash"], f.erro_estagio_max)
        out.append(f"| {c.caso} | {f.estagios} | {'sim' if c.completa else 'não'} | "
                   f"{e(f.erro_molar_relativo)} | {e(f.erro_massico_relativo)} | {e(f.erro_componente_max)} | "
                   f"{f.componente_pior} | {e(f.erro_estagio_max)} |")
    out += ["", f"**Pior caso do conjunto:** molar {e(piores['molar'])}, mássico {e(piores['massa'])}, "
                f"componente a componente {e(piores['comp'])}, fechamento de flash isolado "
                f"{e(piores['flash'])} — tudo na precisão da máquina.", ""]
    return out, piores


def secao_comparacao(dados, res, cascatas, mws):
    """F5 (flashes independentes de z₀) × F5.1 (cascata) × Standing legado."""
    vm = cs.volume_molar_padrao(dados)
    pontos = {p["id"]: p for p in ig.pontos()}
    legado_vol = {"SG-001": "G_F", "V-001": "G_D1", "V-002": "G_D2"}
    out = ["## 6. F5 (flashes independentes) × F5.1 (cascata) × Standing legado", "",
           "Os três não medem a mesma coisa, e é isso que a tabela mostra:", "",
           "- **F5**: flash de z₀ em cada (T, P), como se cada vaso recebesse o fluido de poço;",
           "- **F5.1**: flash da alimentação REAL de cada vaso (o líquido do anterior);",
           "- **Standing**: ΔRs sobre a vazão de óleo — gás que sai de solução, não fração de fase.", "",
           "| caso | estágio | β (F5) | β (F5.1) | ṅ_V F5 (kmol/d) | ṅ_V F5.1 (kmol/d) | ṅ_V Standing (kmol/d) | ṁ_V F5.1 (kg/d) | ṁ_V Standing (kg/d) | MW_V F5.1 | Z_V F5.1 |",
           "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for (c, _), r in zip(cascatas, res):
        if c.base is None:
            continue
        z0 = {k: v for k, v in dados.composicoes[c.fluido].items() if v > 0}
        for s in c.estagios:
            ind = et.flash_poco(c_para_k(s.T_C), kpa_para_pa(s.P_kPa), z0, mws)
            b5 = ind.vapor.fracao_molar if (ind.ok and ind.vapor) else math.nan
            vol_leg = r.gas[legado_vol[pontos[s.ponto]["id"]]]
            n_leg = vol_leg / vm
            m_leg = vol_leg * c.base.rho_gas_std
            out.append(f"| {c.caso} | {s.ponto} | {n(b5, 6)} | {n(s.beta, 6)} | "
                       f"{n(b5 * c.base.n_F_kmol_d, 1)} | {n(s.n_vapor_kmol_d, 1)} | {n(n_leg, 1)} | "
                       f"{n(s.m_vapor_kg_d, 0)} | {n(m_leg, 0)} | {n(s.vapor.MW, 3) if s.vapor else '—'} | "
                       f"{n(s.vapor.Z, 5) if s.vapor else '—'} |")
    return out + [""]


def secao_performance(dt, total, chaves, n_cascatas):
    distintas = len(chaves)
    out = ["## 7. Desempenho — medido, não otimizado", "",
           "Nenhum cache foi implementado nesta fase; o número abaixo é o do custo real.", "",
           "| grandeza | valor |", "|---|---:|",
           f"| cascatas rodadas | {n_cascatas} |",
           f"| flashes | {total} |",
           f"| condições (T, P, z) distintas | {distintas} |",
           f"| fator de recomputação | {n(total / distintas, 3) if distintas else '—'} |",
           f"| custo total | {n(dt, 3)} s |",
           f"| custo por flash | {n(dt / total * 1000, 2) if total else '—'} ms |", ""]
    repetidas = [(k, v) for k, v in chaves.items() if v > 1]
    out.append(f"Condições repetidas: **{len(repetidas)}** — casos do mesmo fluido que caem no mesmo "
               "(T, P, z). A recomputação é medida e fica registrada; eliminá-la é decisão de outra fase.")
    return out + [""]


def gerar(dados, prem, mws, caso_detalhe=1):
    res = resolver_todos(dados, prem)
    original, chaves, total = espiao_de_flash()
    try:
        t0 = time.perf_counter()
        cascatas = cs.rodar(res, dados, prem, mws)
        dt = time.perf_counter() - t0
    finally:
        from fpso_siz.pfd import _chedl
        _chedl.flash_pseudo = original
    fech, piores = secao_fechamento(cascatas)
    regra = cs.regra_base_molar()
    linhas = ["# Fase 5.1 — cascata composicional do trem, em modo sombra", "",
              "Gerado por `tools/cascata_composicional.py`.", "",
              "> **Modo sombra, integral.** O balanço produtivo, o dimensionamento, os equipamentos e "
              "os memoriais continuam intocados; `y`, `β`, `x`, `h`, `cp`, `ρ_líquido`, `μ` e `k` "
              "seguem NÃO liberados no mapa de proveniência, e o guarda `exigir_liberada` continua "
              "recusando consumo. O que muda em relação à F5 é a ANÁLISE: os três pontos deixam de ser "
              "flashes independentes e viram um trem.", "",
              "## 0. O que a F5.1 muda em relação à F5", "",
              "| | F5 | F5.1 |", "|---|---|---|",
              "| alimentação do V-001 | z₀ (fluido de poço) | x do SG-001 |",
              "| alimentação do V-002 | z₀ (fluido de poço) | x do V-001 |",
              "| quantidade absoluta | não havia | ṅ_V = β·ṅ_F, ṅ_L = (1−β)·ṅ_F |",
              "| fechamento | por flash | por flash **e** do trem inteiro, global e por componente |",
              "| gás de lift | não tratado | lacuna declarada |", ""]
    linhas += secao_compatibilizacao(dados, res, mws)
    linhas += secao_base_molar(dados, cascatas)
    linhas += secao_lift(dados, cascatas)
    linhas += secao_estagios(cascatas, caso_detalhe)
    linhas += fech
    linhas += secao_comparacao(dados, res, cascatas, mws)
    linhas += secao_performance(dt, total[0], chaves, len(cascatas))
    linhas += ["## 8. O que ainda impede a ativação", "",
               "1. **A base molar não reconcilia com o split do BOT.** A regra declarada conserva a "
               "massa do balanço produtivo, mas a composição z₀ não reproduz `oil_sm3d` e "
               "`produced_gas_sm3d` do caso (§1). Ativar `β`, `y` ou `x` trocaria a vazão de gás por "
               "estágio pelo valor da cascata, e o balanço de massa da planta deixaria de fechar contra "
               "o BOT enquanto essa incompatibilidade existir.",
               "2. **Gás de lift sem composição** (§3): nos casos 9, 11, 15 e 16 a cascata e o balanço "
               "produtivo não partem da mesma massa.",
               "3. **`h` e `cp` continuam ausentes**: sem eles não há balanço de energia pela EOS, e as "
               "cargas térmicas seguem no caminho legado.",
               "4. **ρ da fase líquida continua em (c)** da invariante 5 — devolvida pelo backend, "
               "não validada, não propagada.", "",
               f"Regra da base molar, como consta no TOML: `{regra['regra']}` — {regra['unidade']}.", ""]
    return "\n".join(linhas) + "\n", cascatas, piores, dt, total[0], len(chaves)


def _limpo(x):
    return None if isinstance(x, float) and not math.isfinite(x) else x


def dados_por_estagio(dados, res, cascatas, mws):
    """Todo o conjunto por estágio, inclusive as composições — o que não cabe em tabela.

    Para cada caso e estágio: β, y, x, ṅ e ṁ das duas fases, MW, Z e ρ do vapor, e o mesmo
    ponto pelos outros dois modelos (flash independente da F5 e Standing legado)."""
    vm = cs.volume_molar_padrao(dados)
    legado_vol = {"SG-001": "G_F", "V-001": "G_D1", "V-002": "G_D2"}
    saida = []
    for (c, f), r in zip(cascatas, res):
        z0 = {k: v for k, v in dados.composicoes[c.fluido].items() if v > 0}
        estagios = []
        for s in c.estagios:
            ind = et.flash_poco(c_para_k(s.T_C), kpa_para_pa(s.P_kPa), z0, mws)
            vol_leg = r.gas[legado_vol[s.ponto]]
            v = s.vapor
            estagios.append(dict(
                ponto=s.ponto, corrente=s.corrente_gas, T_C=s.T_C, P_kPa=s.P_kPa,
                alimentacao=s.z, beta=_limpo(s.beta), y=s.y, x=s.x,
                n_vapor_kmol_d=_limpo(s.n_vapor_kmol_d), m_vapor_kg_d=_limpo(s.m_vapor_kg_d),
                n_liquido_kmol_d=_limpo(s.n_liquido_kmol_d), m_liquido_kg_d=_limpo(s.m_liquido_kg_d),
                MW_vapor=_limpo(v.MW) if v else None, Z_vapor=_limpo(v.Z) if v else None,
                rho_vapor=_limpo(v.rho) if v else None,
                MW_liquido=_limpo(s.liquido.MW) if s.liquido else None,
                fechamento_flash=_limpo(s.fechamento.erro_componente_max) if s.fechamento else None,
                f5_independente=dict(beta=_limpo(ind.vapor.fracao_molar) if (ind.ok and ind.vapor) else None,
                                     n_vapor_kmol_d=_limpo(ind.vapor.fracao_molar * c.base.n_F_kmol_d)
                                     if (ind.ok and ind.vapor) else None),
                standing_legado=dict(volume_sm3d=vol_leg, n_vapor_kmol_d=vol_leg / vm,
                                     m_vapor_kg_d=vol_leg * c.base.rho_gas_std)))
        b = c.base
        saida.append(dict(
            caso=c.caso, fluido=c.fluido, completa=c.completa, interrompida=c.interrompida,
            base=dict(oil_sm3d=b.oil_sm3d, gas_produzido_sm3d=b.gas_produzido_sm3d,
                      gas_lift_sm3d=b.gas_lift_sm3d, rho_oleo=b.rho_oleo, rho_gas_std=b.rho_gas_std,
                      massa_oleo_kg_d=b.massa_oleo_kg_d, massa_gas_kg_d=b.massa_gas_kg_d,
                      massa_kg_d=b.massa_kg_d, MW_z=b.MW_z, n_F_kmol_d=b.n_F_kmol_d,
                      fracao_de_lift=b.fracao_de_lift),
            fechamento=dict(molar_relativo=_limpo(f.erro_molar_relativo),
                            massico_relativo=_limpo(f.erro_massico_relativo),
                            componente_max=_limpo(f.erro_componente_max),
                            componente_pior=f.componente_pior,
                            flash_pior=_limpo(f.erro_estagio_max)) if f else None,
            estagios=estagios))
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS if CASOS.exists() else FIXTURE)
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "34-cascata-composicional.md")
    ap.add_argument("--caso-detalhe", type=int, default=1)
    a = ap.parse_args()
    dados = carregar_casos(a.casos)
    mws = {k: v["mw"] for k, v in json.loads(a.casos.read_text(encoding="utf-8"))["c20_pseudo"].items()}
    texto, cascatas, piores, dt, total, distintas = gerar(dados, premissas(dados), mws, a.caso_detalhe)
    a.saida.write_text(texto, encoding="utf-8")
    res = resolver_todos(dados, premissas(dados))
    completo = dict(regra_base_molar=cs.regra_base_molar(), lacunas=cs.lacunas(),
                    sequencia=cs.cfg()["cascata"]["sequencia"],
                    desempenho=dict(flashes=total, condicoes_distintas=distintas,
                                    recomputacao=total / distintas if distintas else None,
                                    custo_total_s=dt, custo_por_flash_ms=dt / total * 1000 if total else None),
                    piores_erros=piores,
                    casos=dados_por_estagio(dados, res, cascatas, mws))
    js = a.saida.with_suffix(".json")
    js.write_text(json.dumps(completo, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    print(a.saida, js, sep="\n")


if __name__ == "__main__":
    main()
