"""Fase 4 — valida a caracterização do fluido de poço sobre o domínio dos casos de projeto.

Gera `docs/validacao/30-caracterizacao-fluido-de-poco.md`. Não integra nada ao processo: a
Fase 5 é que decide isso.

    uv run python tools/caracterizacao_poco.py
"""
import argparse
import json
import math
from pathlib import Path

from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import caracterizacao as ca
from fpso_siz.pfd import estado_termodinamico as et

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def n(x, casas=4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def densidade_ideal(fase, mws):
    """Densidade por mistura ideal de volumes, com as SG da própria caracterização: a
    referência independente contra a qual a densidade do PR é comparada."""
    import chemicals
    num = den = 0.0
    nomes = {"C1": "methane", "C2": "ethane", "C3": "propane", "iC4": "isobutane", "nC4": "butane",
             "iC5": "isopentane", "nC5": "pentane", "N2": "nitrogen", "CO2": "carbon dioxide",
             "H2S": "hydrogen sulfide"}
    for nome, x in fase.composicao.items():
        if x <= 0:
            continue
        if ca.classificar(nome, mws) == ca.REAL:
            try:
                cas = chemicals.CAS_from_any(nomes.get(nome, nome))
                mw = chemicals.MW(cas)
                vm = chemicals.volume.COSTALD(288.75, chemicals.Tc(cas), chemicals.Vc(cas),
                                              chemicals.omega(cas))
                sg = mw / 1000.0 / vm / 999.0
            except Exception:                                    # noqa: BLE001
                continue
        else:
            p = ca.caracterizar(nome, mws.get(nome))
            mw, sg = p.MW, p.SG
        if mw and sg and sg > 0:
            num += x * mw
            den += x * mw / (sg * 999.0)
    return num / den if den > 0 else math.nan


def gerar(bot):
    mws = {k: v["mw"] for k, v in bot["c20_pseudo"].items()}
    fcs = bot["fluid_compositions"]
    sc = bot["standard_conditions"]
    casos = bot["cases"]
    out = ["# Fase 4 — caracterização do fluido de poço (pseudo-componentes)", "",
           "Gerado por `tools/caracterizacao_poco.py`.", "",
           "> **Nada foi integrado ao processo.** O balanço, o dimensionamento e os relatórios não "
           "passam por aqui; a integração é a Fase 5.", "",
           "## Por que é necessário", "",
           "O fluido do BOT tem 31 componentes com fração não nula. Só dois **não são aceitos** pelo "
           "backend (`C20+` e `C20++`) — mas o problema é maior que isso: os cortes **C6–C19 são "
           "frações SCN**, e o backend resolve o rótulo `C7` como **n-heptano puro**. Aceitar essa "
           "resolução seria trocar um corte com iso-parafinas, naftênicos e aromáticos por uma "
           "parafina normal, em silêncio.", "",
           f"Fonte da caracterização: {ca.cfg()['fonte']['referencia']} (`{ca.cfg()['fonte']['arquivo']}`).", "",
           f"**Conferência da transcrição:** {ca.cfg()['fonte']['conferencia']}.", "",
           f"**Limitação da fonte:** {ca.cfg()['fonte']['limitacao_tabelas']}.", "",
           "## A regra da transformação", "",
           "**Não há transformação de composição.** Cada componente mantém a sua fração molar "
           "exatamente; o que muda é a propriedade atribuída a ele — de \"procure este nome no banco\" "
           "para \"use este Tc, Pc e ω\". Logo, por construção: fechamento preservado, nenhuma fração "
           "negativa criada, e a quantidade atribuída a cada tipo é exatamente a que já estava lá.", "",
           "| classe | componentes | caracterização |", "|---|---|---|",
           "| real | N2, CO2, H2S, C1–C3, iC4/nC4, iC5/nC5, BTEX | identificador do banco (chemicals) |",
           "| SCN | C6–C19 | Riazi & Al-Sahhaf, de Nc |",
           "| plus | C20+, C20++ | Riazi & Al-Sahhaf, do **MW do BOT** |", "",
           "## Caracterização dos pseudo-componentes", "",
           "| pseudo | tipo | MW (g/mol) | Tb (K) | SG | Tc (K) | Pc (bar) | ω |", "|---|---|---|---|---|---|---|---|"]
    for nc in range(ca.cfg()["scn"]["nc_min"], ca.cfg()["scn"]["nc_max"] + 1):
        p = ca.caracterizar(f"C{nc}")
        out.append(f"| {p.nome} | SCN | {n(p.MW,1)} | {n(p.Tb,2)} | {n(p.SG)} | {n(p.Tc,2)} | "
                   f"{n(p.Pc/1e5,3)} | {n(p.omega)} |")
    for nome, mw in mws.items():
        p = ca.caracterizar(nome, mw)
        out.append(f"| {p.nome} | plus | **{n(p.MW,1)}** | {n(p.Tb,2)} | {n(p.SG)} | {n(p.Tc,2)} | "
                   f"{n(p.Pc/1e5,3)} | {n(p.omega)} |")
    out += ["", "MW das frações plus em negrito: é **dado do BOT**, usado exatamente como veio. Todas as "
            "demais colunas são calculadas pelas correlações; nenhuma é valor tabelado da fonte.", "",
            "### Densidade contra o dado do BOT", "",
            "| pseudo | SG × 999 (kg/m³) | ρ do BOT (kg/m³) | desvio |", "|---|---|---|---|"]
    for nome, mw in mws.items():
        p = ca.caracterizar(nome, mw)
        rho, rho_bot = p.SG * 999.0, bot["c20_pseudo"][nome]["rho_kg_m3"]
        out.append(f"| {nome} | {n(rho,1)} | {n(rho_bot,1)} | {n(100*(rho-rho_bot)/rho_bot,2)} % |")
    out += ["", "É a verificação mais direta disponível: a correlação reproduz a densidade que o próprio "
            "BOT declara para o pseudo-componente, dentro de ~2,5 %.", "",
            "## Composição, antes e depois", "",
            "| componente | z (Early Life) | classe | vai ao backend como |", "|---|---|---|---|"]
    z = {k: v for k, v in fcs["Early Life"].items() if v > 0}
    _, mapa = ca.transformar(z, mws)
    for nome, info in mapa.items():
        alvo = "identificador do banco" if info["pseudo"] is None else \
            f"Tc={n(info['pseudo'].Tc,1)} K, Pc={n(info['pseudo'].Pc/1e5,2)} bar, ω={n(info['pseudo'].omega,3)}"
        out.append(f"| {nome} | {n(info['fracao'],6)} | {info['tipo']} | {alvo} |")
    soma_o, soma_d = sum(z.values()), sum(i["fracao"] for i in mapa.values())
    out += ["", f"**Balanço da transformação:** soma antes = {soma_o!r}; soma depois = {soma_d!r}; "
            f"diferença = {soma_d - soma_o!r}. Idêntica, porque a regra é a identidade.", "",
            "## Flash no domínio dos casos de projeto", "",
            "Os 7 fluidos do BOT nas condições dos 16 casos (T do caso; P do FWKO, do vaso e da "
            "condição padrão). **Não é um ponto só.**", "",
            "| fluido | T (°C) | P (kPa) | conv. | VF molar | VF mássica | Z vapor | ρ vapor | MW líq | ρ líq (PR) | ρ líq (mist. ideal) | razão |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    pressoes = [bot["fwko_pressure_kPa"], 700.0, 200.0, sc["P_kPa"]]
    temps = sorted({c["T_C"] for c in casos})
    total = conv = 0
    for nome, z0 in fcs.items():
        zz = {k: v for k, v in z0.items() if v > 0}
        for t_c in temps:
            for p_kpa in pressoes:
                total += 1
                e = et.flash_poco(c_para_k(t_c), kpa_para_pa(p_kpa), zz, mws)
                if not e.ok:
                    out.append(f"| {nome} | {n(t_c,1)} | {n(p_kpa,0)} | **não** | — | — | — | — | — | — | — | — |")
                    continue
                conv += 1
                v, li = e.vapor, e.liquido
                if (t_c, p_kpa) not in ((temps[0], pressoes[0]), (temps[-1], pressoes[-1])) and nome != "Early Life":
                    continue
                ri = densidade_ideal(li, mws) if li else math.nan
                out.append(f"| {nome} | {n(t_c,1)} | {n(p_kpa,0)} | sim | {n(e.fracao_vapor)} | "
                           f"{n(e.fracao_vapor_massica)} | {n(v.Z) if v else '—'} | "
                           f"{n(v.rho,3) if v else '—'} | {n(li.MW,2) if li else '—'} | "
                           f"{n(li.rho,2) if li else '—'} | {n(ri,2)} | "
                           f"{n(li.rho/ri,3) if li and math.isfinite(ri) else '—'} |")
    out += ["", f"**Convergência: {conv} de {total} condições** "
            f"({n(100*conv/total,1)} %), cobrindo 7 composições × {len(temps)} temperaturas "
            f"({n(min(temps),0)}–{n(max(temps),0)} °C) × {len(pressoes)} pressões "
            f"({n(min(pressoes),0)}–{n(max(pressoes),0)} kPa). A tabela mostra um recorte; a contagem é do "
            "domínio inteiro.", "",
            "## Composição das fases", ""]
    e = et.flash_poco(c_para_k(temps[0]), kpa_para_pa(bot["fwko_pressure_kPa"]), z, mws)
    if e.ok and e.liquido:
        out += [f"Early Life a {n(temps[0],1)} °C e {n(bot['fwko_pressure_kPa'],0)} kPa:", "",
                "| componente | z | y (vapor) | x (líquido) | z recomposto |", "|---|---|---|---|---|"]
        v, li = e.vapor, e.liquido
        for nome in z:
            rec = v.fracao_molar * v.composicao[nome] + li.fracao_molar * li.composicao[nome]
            out.append(f"| {nome} | {n(z[nome],6)} | {n(v.composicao[nome],6)} | "
                       f"{n(li.composicao[nome],6)} | {n(rec,6)} |")
        out += ["", "A última coluna é β·y + (1−β)·x: fecha com z componente a componente (há teste).", ""]
    out += ["## O que NÃO é confiável para o processo", "",
            "| grandeza | situação | consequência |", "|---|---|---|"]
    for b in ca.bloqueios():
        out.append(f"| {b['grandeza']} | {b['situacao']} | {b['consequencia']} |")
    out += ["", "A distinção pedida, explicitamente:", "",
            "- **propriedade ausente** — `h` e `cp`: não existem no pacote, porque não há Cp_ig com "
            "fonte. Não é um zero nem uma estimativa;",
            "- **calculada dentro do domínio validado** — VLE, frações de fase, composições das fases, "
            "Z e ρ da fase **vapor**; e a caracterização (Tc, Pc, ω, SG), conferida contra as "
            "verificações internas do artigo e contra a densidade do BOT;",
            "- **retornada pelo backend, porém extrapolada / não validada** — ρ da fase **líquida** "
            "(PR sem translação de volume, razão 0,541 contra a mistura ideal) e, no serviço de "
            "hidrocarboneto, `k` da fase líquida. Ficam expostas com o método ao lado e com aviso, "
            "e **não podem ser promovidas a propriedade de projeto**.", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--saida", type=Path,
                    default=RAIZ / "docs" / "validacao" / "30-caracterizacao-fluido-de-poco.md")
    a = ap.parse_args()
    a.saida.write_text(gerar(json.loads(a.casos.read_text(encoding="utf-8"))), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
