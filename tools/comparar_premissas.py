"""Antes × depois de uma mudança de premissa, pelo caminho produtivo inteiro.

Dois contextos do mesmo serviço — as premissas vigentes e as vigentes com as alterações pedidas —,
cada um com balanço, trem, TVP, dimensionamento dos 11 TAGs e integração térmica realizada do P-001
(ADR 0005). Nada aqui é física: só se lê o que o serviço devolve e se põe lado a lado. É a tabela
que o usuário confere antes de uma premissa nova ser congelada (fase A: P-18/P-19, nota 44).

    uv run python tools/comparar_premissas.py --candidata fase_a_pressao [--saida saida/fase_a]
    uv run python tools/comparar_premissas.py --base P_D1=700 --base P_D2=200 \
        --premissa P_D1=500 --premissa P_D2=130     # fase A depois de consolidada (nota 44)
    uv run python tools/comparar_premissas.py --premissa P_D1=500 --premissa P_D2=130 \
        [--casos ARQ] [--saida saida/comparacao_premissas]

`--candidata` lê os valores de config/premissas_candidatas.toml (com origem e critério).
"""
import argparse
import json
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.core import memoria
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import otimizacao as ot
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
DERIVADOS = ("area_total", "area_instalada", "volume")   # extensivos que o relatório mostra, se o método os publica


def n(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _json(o):
    """JSON estrito: não finito vira null."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    return o


def avaliar(dados, alteracoes):
    """Tudo o que a comparação mostra, de um contexto: por caso e por TAG."""
    return avaliar_contexto(servico.Contexto(dados, alteracoes=alteracoes, propostas=mod_propostas.padrao()),
                            alteracoes)


def avaliar_contexto(ctx, alteracoes=None):
    """O mesmo, de um contexto já montado (outras ferramentas de comparação o reaproveitam)."""
    alteracoes = alteracoes or {}
    planta = dimensionar(contexto=ctx)
    itg = ctx.integracao
    por_itg = {c.num: c for c in itg.casos} if itg.aplicavel else {}
    gas = ot.subproblema("pressao")["relatorio_gas"]
    casos = []
    for r in ctx.balanco:
        c = por_itg.get(r.num)
        lados = {l.tag_residual: l for l in c.lados} if c is not None else {}
        casos.append(dict(
            num=r.num, avaliavel=r.avaliavel, tvp_kPa=r.tvp_kPa,
            q_pre=r.duties["Q_pre"], q_real=c.q_realizado if c is not None else math.nan,
            estado=c.estado_rating if c is not None else "",
            q_h=lados["P-002"].q_residual if "P-002" in lados else r.duties["Q_H"],
            q_d=r.duties["Q_D"],
            q_c=lados["P-003"].q_residual if "P-003" in lados else r.duties["Q_C"],
            w=sum(r.duties[k] for k in ("W_Bo", "W_B1", "W_B2")),
            gas={k: r.gas[k] for k in gas}))
    tags = []
    for rt in planta.tags:
        res, m = rt.resultado, rt.entradas.metodo
        campos = []
        if res is not None:
            campos = [(f.label, f.value, f.unit) for f in m.result_fields(res) if f.highlight]
            extra = {**res.derivados_v2, **res.derivados}
            campos += [(k, float(extra[k]), "") for k in DERIVADOS if k in extra]
        op = memoria.operacao(res) if res is not None and res.feasible else None
        npsh = [dict(caso=nome, npsh=o["npsh"], exigido=o["npsh_exigido"], folga=o["folga_npsh"],
                     p_suc=c.valores["pressure"].valor if "pressure" in c.valores else math.nan)
                for (nome, o), c in zip(op or [], [c for c in rt.entradas.casos if c.ativo])
                if "npsh" in o]
        tags.append(dict(tag=rt.tag.tag, status=rt.status, campos=campos, npsh=npsh,
                         governante=(m.governing_label(res.governing) if res is not None and res.governing else ""),
                         caso=(res.driver_case if res is not None else "")))
    return dict(premissas={k: ctx.prem[k] for k in alteracoes}, alteracoes=dict(ctx.alteracoes),
                casos=casos, tags=tags, completa=planta.completa, planta=planta,
                integracao=dict(aplicavel=itg.aplicavel, alvo=itg.q_alvo_total if itg.aplicavel else math.nan,
                                realizado=itg.q_realizado_total if itg.aplicavel else math.nan))


def tabela_casos(a, b):
    out = ["| caso | TVP antes (kPa) | TVP depois (kPa) | Q P-001 balanço antes → depois (kW) "
           "| Q P-001 realizado antes → depois (kW) | Q_H P-002 (kW) | Q_C P-003 (kW) | Q DWH-001 (kW) "
           "| W bombas (kW) |", "|---:|---:|---:|---|---|---|---|---|---|"]
    for x, y in zip(a["casos"], b["casos"], strict=True):
        tvp = (lambda c: n(c["tvp_kPa"]) if c["avaliavel"] else "não verificada")
        out.append(f"| {x['num']} | {tvp(x)} | {tvp(y)} | {n(x['q_pre'])} → {n(y['q_pre'])} "
                   f"| {n(x['q_real'])} → {n(y['q_real'])} | {n(x['q_h'])} → {n(y['q_h'])} "
                   f"| {n(x['q_c'])} → {n(y['q_c'])} | {n(x['q_d'])} → {n(y['q_d'])} | {n(x['w'])} → {n(y['w'])} |")
    return out


def tabela_gas(a, b):
    chaves = list(a["casos"][0]["gas"])
    out = ["| caso | " + " | ".join(f"{k} antes → depois (Sm³/d)" for k in chaves) + " |",
           "|---:|" + "---|" * len(chaves)]
    for x, y in zip(a["casos"], b["casos"], strict=True):
        out.append(f"| {x['num']} | " + " | ".join(f"{n(x['gas'][k], 0)} → {n(y['gas'][k], 0)}" for k in chaves) + " |")
    return out


def tabela_tags(a, b):
    out = ["| TAG | grandeza | antes | depois | variação | governante antes → depois |",
           "|---|---|---:|---:|---:|---|"]
    for x, y in zip(a["tags"], b["tags"], strict=True):
        gov = f"{x['governante']} ({x['caso']}) → {y['governante']} ({y['caso']})"
        if x["status"] != y["status"] or not x["campos"]:
            out.append(f"| {x['tag']} | estado | {x['status']} | {y['status']} | | {gov} |")
        depois = {rot: (v, u) for rot, v, u in y["campos"]}
        for rot, v, u in x["campos"]:
            w = depois.get(rot, (math.nan, u))[0]
            var = (f"{n(100 * (w / v - 1))} %" if isinstance(v, float) and isinstance(w, float) and v
                   and math.isfinite(v) and math.isfinite(w) else "")
            rotulo = f"{rot} [{u}]" if u else rot
            out.append(f"| {x['tag']} | {rotulo} | {n(v, 3) if isinstance(v, float) else v} "
                       f"| {n(w, 3) if isinstance(w, float) else w} | {var} | {gov} |")
            gov = ""
    return out


def tabela_npsh(a, b):
    """NPSH disponível por caso nas bombas. O NPSH exigido é NPSHr + margem: hoje valores PROPOSTOS
    (pendencias_propostas.toml), não curva de fabricante — a comparação com o NPSHr fica pendente."""
    out = ["| bomba | caso | P sucção antes → depois (kPa) | NPSHd antes → depois (m) | NPSHr + margem (m) "
           "| folga antes → depois (m) |", "|---|---|---|---|---:|---|"]
    for x, y in zip(a["tags"], b["tags"], strict=True):
        for p, q in zip(x["npsh"], y["npsh"], strict=True):
            out.append(f"| {x['tag']} | {p['caso']} | {n(p['p_suc'])} → {n(q['p_suc'])} | {n(p['npsh'], 3)} → "
                       f"{n(q['npsh'], 3)} | {n(q['exigido'], 1)} | {n(p['folga'], 3)} → {n(q['folga'], 3)} |")
    return out


def relatorio(a, b):
    tvps = [(c["tvp_kPa"], c["num"]) for c in b["casos"] if c["avaliavel"]]
    tvps_a = [(c["tvp_kPa"], c["num"]) for c in a["casos"] if c["avaliavel"]]
    lin = ["# Comparação de premissas — antes × depois", "",
           "Gerado por `tools/comparar_premissas.py`; todos os números saem do serviço "
           "(balanço → trem → TVP → 11 TAGs → integração térmica realizada).", "",
           "| premissa | antes | depois |", "|---|---:|---:|"]
    lin += [f"| {k} | {n(a['premissas'][k])} | {n(b['premissas'][k])} |" for k in b["premissas"]]
    lin += ["", f"TVP máxima nos casos avaliáveis: antes {n(max(tvps_a)[0])} kPa (caso {max(tvps_a)[1]}), "
                f"depois {n(max(tvps)[0])} kPa (caso {max(tvps)[1]}). Casos sem TVP verificada (gás de lift sem "
                f"composição): {', '.join(str(c['num']) for c in b['casos'] if not c['avaliavel'])}.",
            f"Planta completa: antes {a['completa']}, depois {b['completa']}.",
            "P-001, soma entre os 16 casos (indicador comparativo — os casos não operam simultaneamente; "
            "não é demanda nem energia anual): "
            f"balanço {n(a['integracao']['alvo'])} → {n(b['integracao']['alvo'])} kW; "
            f"realizado {n(a['integracao']['realizado'])} → {n(b['integracao']['realizado'])} kW.",
            "", "## Por caso", "", *tabela_casos(a, b), "", "## Gás por estágio", "", *tabela_gas(a, b),
            "", "## Equipamentos (resultado principal e caso governante)", "", *tabela_tags(a, b),
            "", "## NPSH disponível das bombas", "",
            "O líquido sai do vaso no ponto de bolha (Pv = P do vaso): NPSHd = (P₀ − Pv)/(ρg) + h₀ − h_atrito,suc "
            "≈ h₀ − h_atrito,suc. O NPSH exigido é NPSHr + margem PROPOSTOS (sem curva de fabricante): a "
            "comparação com o NPSHr do fabricante está PENDENTE.", "", *tabela_npsh(a, b), ""]
    return "\n".join(lin)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", default=str(CASOS))
    ap.add_argument("--premissa", action="append", default=[], metavar="NOME=VALOR")
    ap.add_argument("--candidata", help="id em config/premissas_candidatas.toml")
    ap.add_argument("--base", action="append", default=[], metavar="NOME=VALOR",
                    help="alterações do lado ANTES (ex.: as premissas de antes de uma consolidação)")
    ap.add_argument("--saida", default=str(RAIZ / "saida" / "comparacao_premissas"))
    args = ap.parse_args()
    candidata = carregar("premissas_candidatas.toml")[args.candidata] if args.candidata else {}
    alteracoes = {k: float(v) for k, v in candidata.get("valores", {}).items()}
    alteracoes |= {k: float(v) for k, v in (p.split("=", 1) for p in args.premissa)}
    if not alteracoes:
        ap.error("informe --candidata ou ao menos uma --premissa NOME=VALOR")
    dados = carregar_casos(Path(args.casos))
    base = {k: float(v) for k, v in (p.split("=", 1) for p in args.base)}
    antes, depois = avaliar(dados, base), avaliar(dados, alteracoes)
    antes["premissas"] = {k: servico.Contexto(dados, alteracoes=base).prem[k] for k in alteracoes}
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    cabeca = "".join(f"- **{k}:** {candidata[k]}\n" for k in ("estado", "origem", "criterio", "ressalva", "nota")
                     if k in candidata)
    texto = relatorio(antes, depois)
    if cabeca:
        texto = texto.replace("\n\n| premissa |", f"\n\nCandidata `{args.candidata}`:\n\n{cabeca}\n| premissa |", 1)
    (saida / "comparacao.md").write_text(texto, encoding="utf-8")
    for x in (antes, depois):
        x.pop("planta")
    (saida / "comparacao.json").write_text(json.dumps(_json(dict(antes=antes, depois=depois)), ensure_ascii=False,
                                                      indent=1), encoding="utf-8")
    print(f"gravados: {saida / 'comparacao.md'}, {saida / 'comparacao.json'}")


if __name__ == "__main__":
    main()
