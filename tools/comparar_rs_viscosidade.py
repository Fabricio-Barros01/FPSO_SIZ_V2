"""Fase B — μ do óleo vivo: Rs do trem (rota vigente, nota 40) × Rs da rota anterior (Standing).

A rota vigente é uma só e não muda aqui: o gás dissolvido de cada corrente sai do trem
(recombinação da Nota 4 + flash) e entra em Beggs & Robinson. A rota ANTERIOR é reconstruída como
ESTUDO, aplicada só à viscosidade: o Rs de cada corrente vem do balanço de Standing — o mesmo
caminho que o balanço usa hoje nos casos com gás de lift, aqui ligado nos 16 casos — e todo o resto
(correntes, cargas, gás por estágio, temperaturas) continua sendo o do trem. A μ continua sendo
calculada pela função do serviço (`termo.oleo`) na temperatura que cada TAG pede, inclusive no
ponto fixo da integração realizada do P-001. Nos casos 9, 11, 15 e 16 (sem flash avaliável) as duas
rotas são Standing e coincidem.

Bases conferidas (escritas no relatório): condição padrão do BOT × a da correlação, definição do Rs
(flash do líquido até a condição padrão / volume padrão do óleo de tanque) e conversão de unidades.

    uv run python tools/comparar_rs_viscosidade.py [--casos ARQ] [--saida saida/fase_b]
"""
import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from fpso_siz.balanco import trem as trem_mod
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.pfd import entradas
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.tags import tags

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comparar_premissas as cp  # noqa: E402  (ferramenta irmã: mesmas tabelas)

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
RS_ORIGINAL = entradas._rs


def consumidores():
    """[(TAG, chave, corrente do Rs, corrente da μ)] das entradas que usam a μ do óleo."""
    out = []
    for t in tags():
        for chave, e in t.entradas.items():
            if isinstance(e, dict) and e.get("regra") == "viscosidade_fase" and "oleo" in (e.get("fase"), e.get("continua")):
                out.append((t.tag, chave, e.get("rs", e["corrente"]), e["corrente"]))
    return out


def rs(r, corrente):
    """Rs [scf/STB] da corrente no estado `r`, pela MESMA fórmula do serviço."""
    return RS_ORIGINAL(SimpleNamespace(r=r), corrente)


def balanco_standing(dados, prem):
    """{num: estado} com o gás dissolvido de Standing em todos os casos (estudo)."""
    with mock.patch.object(trem_mod, "avaliavel", lambda caso: (False, "estudo: rota anterior (Standing)")):
        return {r.num: r for r in resolver_todos(dados, prem)}


def avaliar_rota_anterior(dados, std):
    def _rs(ctx, corrente):
        if ctx.r is not None and ctx.r.avaliavel:
            return rs(std[ctx.r.num], corrente)
        return RS_ORIGINAL(ctx, corrente)
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())
    with mock.patch.object(entradas, "_rs", _rs):
        return cp.avaliar_contexto(ctx)


def mus(av):
    """{(TAG, chave): {num: μ}} das entradas de μ do óleo, lidas do TAG preparado."""
    out = {}
    for ident, chave, _, _ in consumidores():
        rt = av["planta"].tag(ident)
        out[(ident, chave)] = {c.num: c.valores[chave].valor for c in rt.entradas.casos if c.ativo}
    return out


def relatorio(dados, a, b, std):
    prod = {r.num: r for r in a["planta"].contexto.balanco}
    sc = dados.bruto["standard_conditions"]
    corr = sorted({c for _, _, c, _ in consumidores()})
    lin = ["# Fase B — μ do óleo vivo: Rs do trem × Rs da rota anterior (Standing)", "",
           "Gerado por `tools/comparar_rs_viscosidade.py`. Rota vigente: Rs do trem → Beggs & Robinson (nota 40). "
           "Rota anterior: Rs do balanço de Standing aplicado SÓ à viscosidade; correntes, cargas e gás são os do "
           "trem nas duas colunas. Casos sem flash avaliável (Standing nas duas rotas): "
           + ", ".join(str(n) for n, r in prod.items() if not r.avaliavel) + ".", "",
           "## Bases", "",
           f"- Condição padrão do arquivo de casos: {sc['T_C']} °C e {sc['P_kPa']} kPa. A de Beggs & Robinson é a do "
           "campo petrolífero (60 °F = 15,56 °C, 14,696 psia = 101,325 kPa): mesma base, diferença de 0,02 % em P.",
           "- Rs = gás que o líquido da corrente libera num flash até a condição padrão (Sm³) / volume padrão do óleo de "
           "tanque da corrente (m³, ρ padrão pelo API). É a razão gás-óleo em solução por flash único até o tanque.",
           "- Conversão Sm³/Sm³ → scf/STB com os fatores exatos de `core/unidades.py` (barril e pé cúbico).",
           "- Faixa da correlação (`termo/fluidos.toml [oleo_vivo]`): abaixo do Rs mínimo a μ do óleo morto do BOT é "
           "mantida (conservador para decantação); fora de API ou T, aviso.", "",
           "## Rs por corrente (scf/STB): trem → Standing", "",
           "| caso | " + " | ".join(corr) + " |", "|---:|" + "---|" * len(corr)]
    for n, r in prod.items():
        marca = "" if r.avaliavel else " (Standing)"
        lin.append(f"| {n}{marca} | " + " | ".join(f"{cp.n(rs(r, c))} → {cp.n(rs(std[n], c) if r.avaliavel else rs(r, c))}"
                                                   for c in corr) + " |")
    ma, mb = mus(a), mus(b)
    lin += ["", "## μ do óleo nas entradas dos TAGs (cP): Rs do trem → Rs de Standing", ""]
    for (ident, chave, rs_c, mu_c) in consumidores():
        va, vb = ma[(ident, chave)], mb[(ident, chave)]
        lin += [f"**{ident} `{chave}`** (μ de {mu_c}, Rs de {rs_c})", "",
                "| caso | trem | Standing | variação |", "|---:|---:|---:|---:|"]
        for num in va:
            var = f"{cp.n(100 * (vb[num] / va[num] - 1))} %" if va[num] else ""
            lin.append(f"| {num} | {cp.n(va[num], 3)} | {cp.n(vb[num], 3)} | {var} |")
        lin.append("")
    lin += ["## Por caso (P-001 e utilidades): Rs do trem → Rs de Standing", "",
            "Somas entre casos são indicador comparativo, não demanda simultânea.", "",
            *[li.replace("TVP antes (kPa) | TVP depois (kPa)", "TVP trem (kPa) | TVP Standing (kPa)")
              for li in cp.tabela_casos(a, b)],
            "", "## Equipamentos (resultado principal e caso governante): Rs do trem → Rs de Standing", "",
            *cp.tabela_tags(a, b), "", "## NPSH das bombas", "", *cp.tabela_npsh(a, b), ""]
    return "\n".join(lin)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", default=str(CASOS))
    ap.add_argument("--saida", default=str(RAIZ / "saida" / "fase_b"))
    args = ap.parse_args()
    dados = carregar_casos(Path(args.casos))
    vigente = cp.avaliar_contexto(servico.Contexto(dados, propostas=mod_propostas.padrao()))
    std = balanco_standing(dados, vigente["planta"].contexto.prem)
    anterior = avaliar_rota_anterior(dados, std)
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "comparacao.md").write_text(relatorio(dados, vigente, anterior, std), encoding="utf-8")
    mu = {f"{k[0]}.{k[1]}": dict(trem=v, standing=mus(anterior)[k]) for k, v in mus(vigente).items()}
    for x in (vigente, anterior):
        x.pop("planta")
    (saida / "comparacao.json").write_text(json.dumps(cp._json(dict(trem=vigente, standing=anterior, mu=mu)),
                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravados: {saida / 'comparacao.md'}, {saida / 'comparacao.json'}")


if __name__ == "__main__":
    main()
