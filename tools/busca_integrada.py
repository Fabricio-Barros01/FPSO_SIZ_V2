#!/usr/bin/env python3
"""Busca integrada da Fase C (docs/validacao/46): pré-aquecedor com geometria CLASSIFICADA em todos
os casos e aquecedor/resfriador redimensionados nas cargas residuais, com a ΔP dos dois lados
verificada contra a P-17.

    uv run python tools/busca_integrada.py --estagio classificada --processos 4
    uv run python tools/busca_integrada.py --estagio residual --processos 4
    uv run python tools/busca_integrada.py --estagio comparativo

A física é toda de `fpso_siz.pfd.layout` e do serviço por TAG; aqui ficam a paralelização (cada
candidato é avaliação independente, `Pool.imap` preserva a ordem — paralelizar não muda número),
a seleção pelas regras declaradas em `config/pfd/layout_trocador.toml` e os arquivos.
"""
import argparse
import copy
import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fpso_siz.sizing  # noqa: F401,E402  (registra os métodos)
from fpso_siz.balanco.dados import carregar_casos  # noqa: E402
from fpso_siz.pfd import equipamento as servico  # noqa: E402
from fpso_siz.pfd import layout  # noqa: E402
from fpso_siz.pfd import propostas as mod_propostas  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "design_cases_bot.json"
SAIDA = RAIZ / "saida" / "layout_trocador"
_CTX = {}


def _limpo(obj):
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _limpo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_limpo(v) for v in obj]
    return obj


def _gravar(obj, nome):
    SAIDA.mkdir(parents=True, exist_ok=True)
    caminho = SAIDA / nome
    caminho.write_text(json.dumps(_limpo(obj), indent=1, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return caminho


def _contexto(**kw):
    ctx = servico.Contexto(carregar_casos(CASOS), propostas=mod_propostas.padrao(), **kw)
    ctx.balanco  # noqa: B018
    return ctx


def resumo(av):
    """Números do candidato do pré-aquecedor (o que trafega entre processos)."""
    g = av.geometria
    return {
        "especificacao": dict(av.especificacao.valores),
        "servico": {"instaladas": av.configuracao.instaladas, "duty": av.configuracao.duty_projeto,
                    "standby": av.configuracao.standby},
        "viavel": av.viavel, "motivo": av.motivo, "avisos": list(av.avisos),
        "tubos_por_passe": g.tubos_por_passe if g else None,
        "comprimento_por_casco": g.comprimento_por_casco if g else None,
        "cascos_serie": g.cascos_serie if g else None, "diametro_casco": g.diametro_casco if g else None,
        "caminho": layout.caminho_de(av) if g else None,
        "area_operacional": av.area_operacional, "area_instalada": av.area_instalada,
        "cascos_instalados": av.cascos_instalados,
        "recuperacao_alvo": av.recuperacao_alvo, "recuperacao_realizada": av.recuperacao_realizada,
        "fracao_realizada": av.fracao_realizada,
        "utilidade_quente": av.utilidade_quente, "utilidade_fria": av.utilidade_fria,
        "dp_tubo_max": av.dp_maximo, "dp_casco_max": av.dp_casco_maximo,
        "casos": [{"num": c.num, "ativo": c.ativo, "estado": c.estado, "q_alvo": c.q_alvo,
                   "q_realizado": c.q_realizado, "q_h": c.utilidade_quente, "q_c": c.utilidade_fria,
                   "dp": c.dp, "dp_casco": c.dp_casco, "v": c.v, "re": c.re, "u": c.u,
                   "violacoes": [list(x) for x in c.violacoes]} for c in av.casos],
    }


# ------------------------------------------------------------------ estágio: classificada
def _abrir():
    _CTX["ctx"] = _contexto()


def _classificar(par):
    esp, v = par
    conf = layout.configuracoes_de_servico(esp.dict["cascos_paralelo"])
    conf = next(c for c in conf if c.standby >= layout.reserva_exigida())
    return [dict(resumo(a), velocidade_projeto=v) for a in layout.classificadas(_CTX["ctx"], esp, conf, v)]


def estagio_classificada(processos, l_max):
    vs = layout.cfg()["classificada"]["velocidades_projeto"]
    pares = [(e, v) for e in layout.especificacoes_classificada(l_max) for v in vs]
    print(f"{len(pares)} geometrias térmicas × velocidades, l_tubo_max = {l_max} m", flush=True)
    with Pool(processos, initializer=_abrir) as pool:
        out = []
        for i, r in enumerate(pool.imap(_classificar, pares, chunksize=4), 1):
            out.extend(r)
            if i % 200 == 0:
                print(f"  {i}/{len(pares)}", flush=True)
    return out


# ------------------------------------------------------------------ seleção do pré-aquecedor
def _area_especifica(r):
    rec = r["recuperacao_realizada"]
    return r["area_instalada"] / rec if rec and rec > 0 else math.inf


def frente(resumos):
    """Frente de Pareto (área instalada, utilidade quente, utilidade fria) dos viáveis."""
    v = [r for r in resumos if r["viavel"]]
    chave = lambda r: (r["area_instalada"], r["utilidade_quente"], r["utilidade_fria"])  # noqa: E731
    return [r for r in v if not any(all(a <= b for a, b in zip(chave(o), chave(r))) and chave(o) != chave(r)
                                    for o in v)]


def chave_regra():
    """A chave de ordenação da regra de seleção declarada para a busca classificada."""
    regra = layout.cfg()["classificada"].get("regra", layout.cfg()["selecao"]["regra"])
    if regra == "area_especifica":
        return lambda r: (_area_especifica(r), r["cascos_instalados"], -r["recuperacao_realizada"])
    return lambda r: (-r["recuperacao_realizada"], r["area_instalada"], r["cascos_instalados"])


def selecionar(resumos):
    f = frente(resumos)
    return min(f, key=chave_regra()) if f else None


def _reavaliar(ctx, r, n=None, caminho=None, l_max=None):
    """O candidato `r` reavaliado (outro n, outro caminho ou outro comprimento máximo por casco)."""
    e = dict(r["especificacao"])
    if l_max is not None:
        e["l_tubo_max"] = float(l_max)
    esp = layout.Especificacao(tuple((k, e[k]) for k in layout.eixos()))
    conf = next(c for c in layout.configuracoes_de_servico(e["cascos_paralelo"])
                if c.standby == r["servico"]["standby"])
    av = layout.avaliar_classificada(ctx, esp, conf, n or r["tubos_por_passe"], caminho or r["caminho"])
    return dict(resumo(av), velocidade_projeto=r.get("velocidade_projeto"))


def refinar(ctx, r):
    """Refino local do número de tubos (de um em um) no caminho máximo do candidato, mantendo a
    P-17: para cada n, o caminho é reescalado pela ΔP por metro medida no próprio candidato."""
    k = layout.cfg()["classificada"]
    out = [r]
    for dn in range(-int(k["refino_tubos"]), int(k["refino_tubos"]) + 1):
        if dn == 0:
            continue
        n = r["tubos_por_passe"] + dn
        cand = _reavaliar(ctx, r, n=n)
        while not cand["viavel"] and cand["caminho"] and any(
                x[0] == "hidraulica" for c in cand["casos"] for x in c["violacoes"]):
            novo = cand["caminho"] * float(k["reducao"])
            if novo < 0.5 * r["caminho"]:
                break
            cand = _reavaliar(ctx, r, n=n, caminho=novo)
        out.append(cand)
    viaveis = [x for x in out if x["viavel"]]
    return min(viaveis, key=chave_regra()) if viaveis else r


# ------------------------------------------------------------------ estágio: residual
def _abrir_residual(p001):
    ctx = _contexto()
    est = servico.estado_inicial("P-001")
    for k_, v in p001.items():
        est.editar(k_, float(v))
    ctx.fixar_estado(est)
    ctx.integracao  # noqa: B018
    _CTX["ctx"] = ctx


def _residual(par):
    ident, esp = par
    a = layout.avaliar_residual(_CTX["ctx"], ident, esp)
    r = a.resultado.resultado
    return {"tag": ident, "especificacao": dict(esp.valores), "viavel": a.viavel,
            "status": a.resultado.status, "motivo": "" if a.viavel else (r.message if r else ""),
            "x": r.x if a.viavel else None, "y": r.y if a.viavel else None, "caminho": a.caminho,
            "area_operacional": a.area_operacional, "area_instalada": a.area_instalada,
            "cascos_instalados": a.cascos_instalados if a.viavel else None,
            "dp_tubo": r.derivados.get("dp") if a.viavel else None,
            "dp_casco": max((x for x in (r.derivados_v2 or {}).get("dp_casco_por_caso", []) if x == x),
                            default=None) if a.viavel else None,
            "governante": r.driver_case if a.viavel else None}


def estado_p001(sel):
    """Edições do estado do P-001 que reproduzem o candidato selecionado (geometria congelada)."""
    e = dict(sel["especificacao"])
    e.update(n_min=sel["tubos_por_passe"], n_max=sel["tubos_por_passe"], n_step=1.0,
             l_instalado=sel["comprimento_por_casco"], cascos_serie=sel["cascos_serie"],
             trens_reserva=float(sel["servico"]["standby"]))
    e.update(layout.edicoes_de_estudo(_contexto(), "P-001"))
    return e


def estagio_residual(processos, p001):
    eixos = layout.eixos_residual()
    serie, l_max = max(eixos["cascos_serie"]), max(eixos["l_tubo_max"])
    out = {}
    with Pool(processos, initializer=_abrir_residual, initargs=(p001,)) as pool:
        for ident in layout.cfg()["residual"]["tags"]:
            pares = [(ident, e) for e in layout.especificacoes_residual(serie, l_max)]
            print(f"{ident}: estágio 1, {len(pares)} geometrias térmicas (empacotamento permissivo)", flush=True)
            e1 = list(pool.imap(_residual, pares, chunksize=4))
            # estágio 2: o empacotamento mínimo de cada geometria viável, por comprimento máximo
            chaves = list(eixos)
            pares2 = []
            for r in e1:
                if not r["viavel"]:
                    continue
                for lm in eixos["l_tubo_max"]:
                    s = math.ceil(r["caminho"] / lm - 1e-9)
                    if 1 <= s <= max(eixos["cascos_serie"]):
                        d = {**r["especificacao"], "cascos_serie": float(s), "l_tubo_max": float(lm)}
                        pares2.append((ident, layout.Especificacao(tuple((k, d[k]) for k in chaves))))
            print(f"{ident}: estágio 2, {len(pares2)} empacotamentos", flush=True)
            e2 = list(pool.imap(_residual, pares2, chunksize=4))
            out[ident] = {"estagio1": e1, "estagio2": e2}
    return out


def selecionar_residual(rs, so_com_fonte=True):
    lim = layout.cfg()["selecao"]["l_tubo_max_com_fonte"]
    v = [r for r in rs if r["viavel"] and (not so_com_fonte or r["especificacao"]["l_tubo_max"] <= lim)]
    return min(v, key=lambda r: (r["area_instalada"], r["cascos_instalados"])) if v else None


# ------------------------------------------------------------------ estágio: comparativo
def _n(x, c=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _estado(ident, edicoes):
    est = servico.estado_inicial(ident)
    for k_, v in edicoes.items():
        est.editar(k_, float(v))
    return est


def planta_com(edicoes_por_tag, **kw):
    """Contexto com os estados dados (geometria de cada TAG) e a planta dimensionada nele."""
    from fpso_siz.pfd.planta import dimensionar
    ctx = _contexto(**kw)
    for ident, ed in edicoes_por_tag.items():
        ctx.fixar_estado(_estado(ident, ed))
    return ctx, dimensionar(contexto=ctx)


def metricas_trocador(rt):
    r = rt.resultado
    if rt.status != servico.DIMENSIONADO or r is None:
        return {"status": rt.status, "motivo": r.message if r is not None else ""}
    v2 = r.derivados_v2 or {}
    dps = [x for x in v2.get("dp_casco_por_caso", []) if x == x]
    from fpso_siz.core import memoria
    op = memoria.operacao(r) or []
    dpt = [o["dp"] for _, o in op if o.get("dp") == o.get("dp")]
    return {"status": rt.status, "x": r.x, "y": r.y, "cascos_serie": v2.get("cascos_serie"),
            "trens": v2.get("cascos_paralelo"), "reserva": v2.get("trens_reserva", 0.0),
            "area_operacional": v2.get("area_total"), "area_instalada": v2.get("area_instalada", v2.get("area_total")),
            "dp_tubo_max": max(dpt) if dpt else None, "dp_casco_max": max(dps) if dps else None,
            "governante": r.driver_case,
            "violacoes": sorted({nat for vs in v2.get("violacoes_por_caso", []) for nat, _ in vs})}


def verificar_geometria_fixa(ctx, rt):
    """O TAG de utilidade com a geometria escolhida CONGELADA e classificado em todos os casos:
    cada caso tem de realizar a sua carga (fração 1); o caso que governa a ÁREA é o de maior
    U·A exigido sobre U·A instalado, e não necessariamente o de maior carga."""
    r = rt.resultado
    if rt.status != servico.DIMENSIONADO:
        return None
    est = copy.deepcopy(ctx.estado_tag(rt.tag.tag))
    for k_, v in (("n_min", r.x), ("n_max", r.x), ("n_step", 1.0), ("l_instalado", r.y)):
        est.editar(k_, float(v))
    rc = servico.dimensionar(servico.preparar(ctx, est), est).resultado
    v2 = rc.derivados_v2
    nomes = rc.case_names
    razao = [e / i if i and i == i else float("nan") for e, i in zip(v2["ua_exigido_por_caso"], v2["ua_instalado_por_caso"])]
    i_area = max(range(len(razao)), key=lambda i: razao[i] if razao[i] == razao[i] else -1)
    i_carga = max(range(len(nomes)), key=lambda i: v2["q_alvo_por_caso"][i])
    return {"casos": [{"caso": n, "q_kW": q / 1000, "fracao": f, "ua_exigido_sobre_instalado": z,
                       "estado": e} for n, q, f, z, e in zip(nomes, v2["q_alvo_por_caso"],
                                                             v2["fracao_realizada_por_caso"], razao,
                                                             v2["estado_rating_por_caso"])],
            "caso_area": nomes[i_area], "caso_maior_carga": nomes[i_carga],
            "todos_realizam": all(f >= 1 - 1e-6 for f in v2["fracao_realizada_por_caso"])}


def comparativo():
    dados = json.loads((SAIDA / "residual.json").read_text(encoding="utf-8"))
    cls = json.loads((SAIDA / "classificada.json").read_text(encoding="utf-8"))
    sel, res = dados["p001"], dados["selecionado"]
    ed_p001 = estado_p001(sel)
    edicoes = {"P-001": ed_p001}
    for t, r in res.items():
        if r is not None:
            edicoes[t] = {**r["especificacao"], **layout.edicoes_de_estudo(_contexto(), t)}
    ctx_v, planta_v = planta_com({})
    ctx_n, planta_n = planta_com(edicoes)
    out = {"vigente": {}, "nova": {}}
    for nome, ctx, planta in (("vigente", ctx_v, planta_v), ("nova", ctx_n, planta_n)):
        i = ctx.integracao
        out[nome] = {"completa": planta.completa, "cenario": i.cenario,
                     "recuperacao": i.q_realizado_total if i.aplicavel else None,
                     "carga_balanco": i.q_alvo_total if i.aplicavel else None,
                     "q_h": i.residual_total("Q_H") if i.aplicavel else None,
                     "q_c": i.residual_total("Q_C") if i.aplicavel else None,
                     "tags": {t: metricas_trocador(planta.tag(t)) for t in ("P-001", "P-002", "P-003")},
                     "casos": [{"num": c.num, "ativo": c.ativo, "q_alvo": c.q_alvo, "q_real": c.q_realizado,
                                "estado": c.estado_rating,
                                "q_h": next((l.q_residual for l in c.lados if l.aquece), None),
                                "q_c": next((l.q_residual for l in c.lados if not l.aquece), None)}
                               for c in i.casos] if i.aplicavel else []}
    out["verificacao_fixa"] = {t: verificar_geometria_fixa(ctx_n, planta_n.tag(t)) for t in ("P-002", "P-003")}
    lim = layout.cfg()["selecao"]["l_tubo_max_com_fonte"]
    out["p001_alternativas"] = [r for r in cls["candidatos"]
                                if r["viavel"] and (r in cls["frente"] or r["especificacao"]["l_tubo_max"] > lim)]
    out["p001_selecionado"], out["p001_estudo"] = cls["selecionado"]["acervo"], cls["selecionado"]["estudo"]
    out["residual_estudo"] = dados["selecionado_estudo"]
    out["contagem"] = {"classificada_total": len(cls["candidatos"]),
                       "classificada_viaveis": sum(1 for r in cls["candidatos"] if r["viavel"]),
                       "residual": {t: {"total": len(d["estagio1"]) + len(d["estagio2"]),
                                        "viaveis": sum(1 for r in d["estagio1"] + d["estagio2"] if r["viavel"])}
                                    for t, d in dados["busca"].items()}}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--estagio", choices=["classificada", "selecao", "residual", "comparativo"], required=True)
    ap.add_argument("--processos", type=int, default=4)
    args = ap.parse_args()
    if args.estagio == "selecao":   # refaz só a seleção e o refino sobre a busca já gravada
        dados = json.loads((SAIDA / "classificada.json").read_text(encoding="utf-8"))
        # regra da nota 46: com limite declarado, ΔP do casco em faixa não validada não aprova —
        # aplicada aos resultados já gravados (o aviso de cada candidato traz a informação)
        for r in dados["candidatos"]:
            pendentes = [a for a in r["avisos"] if "não validada" in a]
            if r["viavel"] and pendentes:
                r["viavel"], r["motivo"] = False, "verificação pendente: " + "; ".join(pendentes)
        dados["frente"] = frente(dados["candidatos"])
        ctx, lim = _contexto(), layout.cfg()["selecao"]["l_tubo_max_com_fonte"]
        sel = {}
        for nome, so in (("acervo", True), ("estudo", False)):
            base = [r for r in dados["candidatos"] if not so or r["especificacao"]["l_tubo_max"] <= lim]
            s_ = selecionar(base)
            sel[nome] = refinar(ctx, s_) if s_ else None
            print(nome, s_ and (s_["especificacao"], s_["tubos_por_passe"], round(s_["fracao_realizada"], 4)),
                  "→ refinado", sel[nome] and (sel[nome]["tubos_por_passe"], round(sel[nome]["fracao_realizada"], 4),
                                                round(sel[nome]["area_instalada"], 1)))
        dados["selecionado"] = sel
        print(_gravar(dados, "classificada.json"))
        return
    if args.estagio == "comparativo":
        print(_gravar(comparativo(), "comparativo.json"))
        return
    if args.estagio == "classificada":
        # o empacotamento só divide o caminho total: a varredura térmica usa cascos de até 6 m (com
        # fonte) e a FRENTE é reavaliada com 7, 8 e 9 m, as alternativas de estudo
        lim = layout.cfg()["selecao"]["l_tubo_max_com_fonte"]
        todos = estagio_classificada(args.processos, lim)
        ctx = _contexto()
        for r in frente(todos):
            for lm in layout.cfg()["eixo"]["l_tubo_max"]["valores"]:
                if lm > lim:
                    todos.append(_reavaliar(ctx, r, l_max=lm))
        sel = {}
        for nome, so in (("acervo", True), ("estudo", False)):
            base = [r for r in todos if not so or r["especificacao"]["l_tubo_max"] <= lim]
            s = selecionar(base)
            sel[nome] = refinar(ctx, s) if s else None
        print(_gravar({"candidatos": todos, "frente": frente(todos), "selecionado": sel}, "classificada.json"))
        for nome, s in sel.items():
            if s:
                print(nome, s["especificacao"], "n", s["tubos_por_passe"], "caminho %.2f" % s["caminho"],
                      "fração %.4f" % s["fracao_realizada"], "A_inst %.0f" % s["area_instalada"])
    else:
        dados = json.loads((SAIDA / "classificada.json").read_text(encoding="utf-8"))
        sel = dados["selecionado"]["acervo"]
        if sel is None:
            sys.exit("nenhum pré-aquecedor viável na busca classificada")
        out = estagio_residual(args.processos, estado_p001(sel))
        escolha = {t: selecionar_residual(d["estagio1"] + d["estagio2"]) for t, d in out.items()}
        estudo = {t: selecionar_residual(d["estagio1"] + d["estagio2"], False) for t, d in out.items()}
        print(_gravar({"p001": sel, "busca": out, "selecionado": escolha, "selecionado_estudo": estudo},
                      "residual.json"))
        for t, s in escolha.items():
            print(t, s and (s["especificacao"], s["x"], round(s["y"], 3), round(s["area_instalada"], 1),
                            round(s["dp_casco"], 1)))


if __name__ == "__main__":
    main()
