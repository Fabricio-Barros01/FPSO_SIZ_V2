"""Fase 3 — exercita o serviço termodinâmico sobre as correntes reais da planta.

Gera `docs/validacao/29-servico-termodinamico.md`. O serviço (`pfd/estado_termodinamico.py`)
ainda NÃO alimenta o balanço nem o dimensionamento — integrar é a Fase 5. Este relatório existe
para mostrar o que ele entrega hoje, corrente a corrente, e onde ele se recusa a responder.

    uv run python tools/servico_termodinamico.py [--casos ...] [--saida ...]
"""
import argparse
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import estado_termodinamico as et
from fpso_siz.pfd import fluidos

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def n(x, casas=4):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fracao_sal(r, sid, prem):
    sal = carregar("pfd/pfd.toml")["sal"]
    massa = {c: r.streams[sid][c] for c in ("W", "D")}
    w = {c: fluidos.fracao_sal(prem[sal[c][0]], prem[sal[c][1]]) for c in massa}
    total = sum(massa.values())
    return sum(massa[c] * w[c] for c in massa) / total if total > 0 else 0.0


def gerar(dados, prem):
    tcfg = carregar("pfd/termodinamica.toml")
    resultados = resolver_todos(dados, prem)
    r = resultados[0]
    # a fase aquosa só existe nos casos com água (o caso 1 é seco, BSW = 0): escolhe-se o
    # primeiro caso que a tem, e o relatório diz qual é
    r_aq = next((x for x in resultados
                 if any(x.streams[s]["W"] + x.streams[s]["D"] > 0
                        for s in carregar("pfd/termodinamica.toml")["correntes_aquosas"])), None)
    s = et.cfg()["servico"]
    out = ["# Fase 3 — serviço termodinâmico ativo, exercitado na planta", "",
           "Gerado por `tools/servico_termodinamico.py`. O serviço é "
           "`pfd/estado_termodinamico.py`: `flash_tp(T, P, z, fluido) → EstadoTermodinamico`.", "",
           "> **O serviço ainda NÃO alimenta o balanço nem o dimensionamento.** Esta fase o "
           "disponibiliza; integrar ao processo é a Fase 5, e a fração pesada (surrogate "
           "n-C40/n-C33) é a Fase 4. Nenhum número do programa mudou — há paridade bit a bit.", "",
           f"Unidades do serviço: {s['unidades']}.", "",
           "## Fluidos atendidos", "",
           "| id | modelo | base de `z` | fases | referência de entalpia |", "|---|---|---|---|---|"]
    for f in et.fluidos_declarados():
        d = et.declaracao(f)
        out.append(f"| `{f}` | {d['modelo']} | {d['base_composicao']} | {', '.join(d['fases'])} | "
                   f"{d['referencia_entalpia']} |")
    out += ["", "As fontes de cada modelo estão no TOML do serviço e em `fluidos.toml`. **As bases de "
            "composição não são iguais**: hidrocarboneto e água recebem fração molar; salmoura recebe a "
            "fração mássica de sal. **As referências de entalpia também não são comuns** — só diferenças "
            "do mesmo fluido têm significado.", ""]

    # --- gás dos vasos, pelo serviço
    out += ["## Gás dos vasos (Peng-Robinson)", "",
            f"Composição do balanço (corte N2–nC4, P-03), caso {r.num}. `VF` é a fração molar de vapor "
            "que a EOS prevê na condição — abaixo de 1 a EOS já condensa parte do gás.", "",
            "| corrente | T (°C) | P (kPa) | VF | Z | ρ (kg/m³) | cp (J/kg·K) | μ (µPa·s) | k (W/m·K) |",
            "|---|---|---|---|---|---|---|---|---|"]
    for sid in tcfg["correntes_gas"]:
        if not r.streams[sid]["G"] > 0:
            continue
        e = et.flash_tp(c_para_k(r.T[sid]), kpa_para_pa(r.P[sid]), r.gp["y"], "hidrocarboneto")
        if not e.ok:
            out.append(f"| {sid} | {n(r.T[sid],1)} | {n(r.P[sid],0)} | não convergiu: {e.mensagem} |||||")
            continue
        v = e.vapor
        out.append(f"| {sid} | {n(r.T[sid],1)} | {n(r.P[sid],0)} | {n(e.fracao_vapor,4)} | {n(v.Z,4)} | "
                   f"{n(v.rho,3)} | {n(v.cp,1)} | {n(v.mu*1e6,3)} | {n(v.k,5)} |")
    out.append("")

    # --- fase aquosa, pelo serviço
    out += ["## Fase aquosa (Laliberté)", ""]
    if r_aq is None:
        out += ["Nenhum caso deste arquivo tem fase aquosa.", ""]
    else:
        out += [f"Caso {r_aq.num} — o caso {r.num} é seco (BSW = 0) e não tem fase aquosa a avaliar.", "",
                "`k` e `h` saem **NaN**: são lacunas declaradas do modelo, não zeros nem valores supostos.", "",
                "| corrente | T (°C) | w sal | ρ (kg/m³) | cp (J/kg·K) | μ (mPa·s) | k | h |",
                "|---|---|---|---|---|---|---|---|"]
        for sid in tcfg["correntes_aquosas"]:
            if not r_aq.streams[sid]["W"] + r_aq.streams[sid]["D"] > 0:
                continue
            w = fracao_sal(r_aq, sid, prem)
            e = et.flash_tp(c_para_k(r_aq.T[sid]), kpa_para_pa(r_aq.P[sid]), {"NaCl": w}, "salmoura")
            a = e.aquosa
            out.append(f"| {sid} | {n(r_aq.T[sid],1)} | {n(w,5)} | {n(a.rho,3)} | {n(a.cp,1)} | "
                       f"{n(a.mu*1e3,4)} | {n(a.k)} | {n(a.h)} |")
        out.append("")

    # --- água de utilidade
    sid = tcfg["correntes_gas"][0]
    out += ["## Água de utilidade (IAPWS-95)", "",
            "O que o serviço acrescenta ao caminho de hoje: **cp e h**. ρ, μ e k saem idênticos aos de "
            "`fluidos.agua` — é a mesma norma, e há teste que prende isso.", "",
            "| T (°C) | P (kPa) | ρ (kg/m³) | cp (J/kg·K) | μ (mPa·s) | k (W/m·K) | h (kJ/kg) |",
            "|---|---|---|---|---|---|---|"]
    for t_c in (25.0, 40.0, 60.0, 90.0):
        e = et.flash_tp(c_para_k(t_c), kpa_para_pa(r.P[sid]), {"H2O": 1.0}, "agua")
        li = e.liquido
        out.append(f"| {n(t_c,1)} | {n(r.P[sid],0)} | {n(li.rho,3)} | {n(li.cp,1)} | {n(li.mu*1e3,4)} | "
                   f"{n(li.k,5)} | {n(li.h/1000,2)} |")
    out.append("")

    # --- o que o serviço recusa
    out += ["## O que o serviço recusa hoje", "",
            "Recusar é resultado: o serviço não inventa caracterização que não tem.", "",
            "| fluido | grandeza | motivo | quando |", "|---|---|---|---|"]
    for x in et.lacunas():
        out.append(f"| `{x['fluido']}` | {x['grandeza']} | {x['motivo']} | {x['quando']} |")
    out += ["", "O caso mais importante é o primeiro: **o fluido de poço completo não é flasheável "
            "hoje**. Pedir o flash de uma composição que inclua a fração pesada levanta erro com a "
            "lacuna nomeada, em vez de devolver um número. A Fase 4 resolve isso com o surrogate.", "",
            "## Equilíbrio de duas fases", "",
            "Para mostrar que o contrato entrega o equilíbrio inteiro, e não só a fase vapor, uma "
            "condição em que a EOS prevê as duas fases:", ""]
    e = et.flash_tp(250.0, 5.0e6, r.gp["y"], "hidrocarboneto")
    if e.ok and not e.monofasico:
        out += [f"T = 250,00 K, P = 5.000 kPa, VF molar = {n(e.fracao_vapor,4)}, "
                f"VF mássica = {n(e.fracao_vapor_massica,4)}.", "",
                "| fase | β molar | β mássica | Z | ρ (kg/m³) | MW | cp (J/kg·K) |",
                "|---|---|---|---|---|---|---|"]
        for f in e.fases:
            out.append(f"| {f.nome} | {n(f.fracao_molar,4)} | {n(f.fracao_massica,4)} | {n(f.Z,4)} | "
                       f"{n(f.rho,3)} | {n(f.MW,3)} | {n(f.cp,1)} |")
        out += ["", "| componente | z | y (vapor) | x (líquido) |", "|---|---|---|---|"]
        v, li = e.vapor, e.liquido
        for comp in r.gp["y"]:
            out.append(f"| {comp} | {n(r.gp['y'][comp],5)} | {n(v.composicao[comp],5)} | "
                       f"{n(li.composicao[comp],5)} |")
        out += ["", "O balanço por componente fecha: z = β·y + (1 − β)·x, conferido por teste.", ""]
        for a in e.avisos:
            out += [f"> **Aviso do serviço:** {a}", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "29-servico-termodinamico.md")
    a = ap.parse_args()
    dados = carregar_casos(a.casos)
    a.saida.write_text(gerar(dados, premissas(dados)), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
