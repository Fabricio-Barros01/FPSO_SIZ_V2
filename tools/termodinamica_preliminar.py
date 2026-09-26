"""Relatório da F14: docs/validacao/15-termodinamica.md — balanço preliminar × ChEDL.

Compara, caso a caso, o cp constante do balanço com Laliberté (fase aquosa) e com a EOS de
Peng-Robinson (gás), o Z do gás e o efeito do cp aquoso na carga do P-002; lista as lacunas
de caracterização. Não altera o balanço. Determinístico para a versão do ChEDL registrada.

    uv run python tools/termodinamica_preliminar.py [--saida docs/validacao/15-termodinamica.md]
"""
import argparse
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import fluidos
from fpso_siz.pfd import termodinamica as td

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def f(x, casas):
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar():
    dados = carregar_casos(CASOS)
    prem = premissas(dados)
    R = resolver_todos(dados, prem)
    comp = td.comparar(R, prem)
    v = fluidos.versoes()
    out = ["# F14 — termodinâmica preliminar: balanço × propriedades do ChEDL", "",
           "Gerado por `tools/termodinamica_preliminar.py` (regra padrão do FWKO; balanço inalterado). "
           f"Versões: thermo {v['thermo']}, chemicals {v['chemicals']}. IAPWS-95/2008/2011 via `chemicals` "
           "(a mesma norma do pacote `iapws`, sem dependência nova).", ""]
    for grandeza, casas in (("cp da fase aquosa", 1), ("cp do gás", 1), ("Z do gás", 4)):
        linhas = [c for c in comp if c.grandeza == grandeza]
        if not linhas:
            continue
        desvios = [100 * c.desvio for c in linhas]
        out += [f"## {grandeza}", "", f"Fonte da referência: {linhas[0].fonte}.", "",
                f"Desvio do balanço: de {f(min(desvios), 2)} % a {f(max(desvios), 2)} %.", "",
                "| Caso | Corrente | Balanço | Referência | Unidade | Desvio (%) |", "|---|---|---|---|---|---|"]
        out += [f"| {c.caso} | {c.corrente} | {f(c.balanco, casas)} | {f(c.referencia, casas)} | {c.unidade} | "
                f"{f(100 * c.desvio, 2)} |" for c in linhas]
        out.append("")
    out += ["## Efeito do cp aquoso na carga do P-002 (sensibilidade)", "",
            "| Caso | ΔQ (kW) | Q do P-002 no balanço (kW) | ΔQ/Q (%) |", "|---|---|---|---|"]
    for r in R:
        e = td.efeito_carga_aquecedor(r, prem)
        if e is not None:
            out.append(f"| {r.num} | {f(e[0], 1)} | {f(e[1], 1)} | {f(100 * e[0] / e[1], 2)} |")
    out += ["", "## Lacunas de caracterização (não calculadas: sem fonte)", ""]
    out += [f"- **{l['grandeza']}** — {l['consequencia']}. Motivo: {l['motivo']}." for l in td.lacunas()]
    out += ["", "## Leitura", "",
            "- A fase aquosa do balanço (cp constante das P-11/P-12) fica próxima de Laliberté; o efeito na "
            "carga do aquecedor é pequeno frente às incertezas das premissas.",
            "- O cp do gás do balanço (gás ideal a 25 °C) fica abaixo do cp real da EOS na condição dos "
            "vasos e o Z se afasta de 1 no FWKO: afeta a entalpia das correntes de gás (saídas) e os "
            "índices de severidade (P-39), não as cargas dos trocadores de óleo.",
            "- O efeito dominante não calculado é o do gás dissolvido (flash, calor de flash, óleo vivo), que "
            "depende da caracterização do C20+ (lacuna acima).", ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "15-termodinamica.md")
    a = ap.parse_args()
    a.saida.write_text(gerar(), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
