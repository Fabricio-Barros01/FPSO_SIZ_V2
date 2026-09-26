"""Relatório dos alarmes de inviabilidade (F13): docs/validacao/14-alarmes.md.

Roda a planta com óleo morto (--oleo-morto) e, com o óleo vivo padrão, sem e com as propostas
(config/pfd/pendencias_propostas.toml); lista os
TAGs inviáveis com a evidência do motor, as hipóteses de config/pfd/alarmes.toml e o
resultado de cada variante pelo mesmo serviço por TAG. Para o SG-001, refaz a cadeia de
decantação do caso do teto a partir dos operandos do rastro (conferência numérica).
Determinístico: os números vêm do código; nada é digitado.

    uv run python tools/investigar_alarmes.py [--saida docs/validacao/14-alarmes.md]
"""
import argparse
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import investigacao as inv
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
PROPOSTAS = RAIZ / "src" / "fpso_siz" / "config" / "pfd" / "pendencias_propostas.toml"


def f(x, casas=0):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def secao_planta(titulo, ctx, planta):
    if not inv.alarmes(planta):
        return [f"## {titulo}", "", "Nenhum TAG inviável: não há alarme a investigar.", ""]
    out = [f"## {titulo}", "", "| TAG | Estado | Casos com solução isolados | Casos sem solução isolados | Motivo do motor |",
           "|---|---|---|---|---|"]
    for rt, ev, _ in inv.alarmes(planta):
        viaveis = ", ".join(f"{n[:6]} ({f(x)})" for n, x in ev.casos_viaveis) or "—"
        inviaveis = ", ".join(n[:6] for n, _ in ev.casos_inviaveis) or "—"
        out.append(f"| {rt.tag.tag} | inviável (alarme) | {viaveis} | {inviaveis} | {ev.mensagem[:220]}… |")
    out += ["", "### Variantes executadas (mesmo motor)", "",
            "| TAG | Variante | Origem do valor | Resultado |", "|---|---|---|---|"]
    for ident, _, v, rt in inv.investigar(ctx, planta):
        r = rt.resultado
        if r.feasible:
            res = f"viável, x = {f(r.x)}"
        else:
            teto = f" (teto {f(r.ceiling)} mm, {r.ceiling_case})" if math.isfinite(r.ceiling) else ""
            res = f"segue inviável{teto}: {r.message[:160]}…"
        out.append(f"| {ident} | {v['rotulo']} | {v['origem']} | {res} |")
    return out + [""]


def _teto(rt):
    """Linha da conta à mão do teto de decantação no caso do teto (operandos do rastro)."""
    r = rt.resultado
    i = r.case_names.index(r.ceiling_case)
    tr = r.per_case[i].trace
    ho = tr.operandos[("settling", "(h_o)max")]
    beta = tr.operandos[("settling", "d_max (água em óleo)")]
    ho_mao = ho["coef"] * ho["tr_o"] * ho["dsg"] * ho["dm"] ** 2 / ho["mu_o"]
    dmax_mao = ho_mao / beta["beta"]
    return (f"caso {r.ceiling_case}: (h_o)max = {ho['coef']} · {ho['tr_o']} min · ΔSG {f(ho['dsg'], 4)} · "
            f"({f(ho['dm'])} µm)² / {f(ho['mu_o'], 2)} cP = {f(ho_mao, 1)} mm; β = {f(beta['beta'], 4)}; "
            f"d_max = {f(dmax_mao, 1)} mm. Rastro: {f(r.ceiling, 1)} mm (diferença {abs(dmax_mao - r.ceiling):.1e} mm)")


def conferencia_sg001(morto, vivo):
    rm, rv = morto.tag("SG-001"), vivo.tag("SG-001")
    return ["## Conferência numérica do teto do SG-001", "",
            f"- Óleo morto ({rm.status}): {_teto(rm)}.",
            f"- Óleo vivo ({rv.status}, D = {f(rv.resultado.x)} mm): {_teto(rv)}.", "",
            "A cadeia não tem erro numérico: o teto decorre das entradas. A única diferença entre as duas linhas é "
            "µ_o (óleo morto do BOT × óleo vivo por Beggs & Robinson com o Rs da saída de óleo C-06): a hipótese de "
            "premissa da viscosidade explica o alarme (docs/validacao/16-oleo-vivo.md).", ""]


def hipoteses():
    out = ["## Hipóteses registradas (config/pfd/alarmes.toml)", ""]
    classes = inv.cfg()["classes"]
    for a in inv.cfg()["alarme"]:
        out += [f"### {a['tag']} — investigação {a['estado']}", "", a["resumo"], ""]
        out += [f"- **{classes[h['classe']]}**: {h['texto']}" for h in a["hipoteses"]]
        out.append("")
    return out


def gerar():
    dados = carregar_casos(CASOS)
    ctxm = servico.Contexto(dados, oleo_vivo=False)
    pm = dimensionar(contexto=ctxm)
    ctx0 = servico.Contexto(dados)
    p0 = dimensionar(contexto=ctx0)
    ctx1 = servico.Contexto(dados, propostas=mod_propostas.carregar(PROPOSTAS))
    p1 = dimensionar(contexto=ctx1)
    linhas = ["# F13 — alarmes de inviabilidade: anotação e investigação", "",
              "Gerado por `tools/investigar_alarmes.py`; todos os números saem do motor e do rastro.", "",
              "A unidade do BOT (I-ET-3010.2K-1200-941-P4X-001, rev. C, em `docs/bot/`) é um projeto básico real:",
              "um TAG sem equipamento que atenda aos casos é **alarme** de erro de premissa, numérico ou de modelo,",
              "nunca conclusão de projeto. Nenhuma variante altera o cálculo padrão; a decisão é do usuário.", ""]
    linhas += secao_planta("Planta com óleo morto (--oleo-morto), sem propostas", ctxm, pm)
    linhas += secao_planta("Planta sem propostas (catálogo com fonte; óleo vivo)", ctx0, p0)
    linhas += secao_planta("Planta com as propostas (pendencias_propostas.toml, status proposto; óleo vivo)", ctx1, p1)
    linhas += conferencia_sg001(pm, p0)
    linhas += hipoteses()
    return "\n".join(linhas) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "14-alarmes.md")
    a = ap.parse_args()
    a.saida.write_text(gerar(), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
