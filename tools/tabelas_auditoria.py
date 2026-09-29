"""Tabelas da auditoria da release do TCC (docs/auditoria/), só orquestração da API pública.

Gera, a partir do caminho produtivo (Contexto → resolver_todos → serviço por TAG), sem física
própria:
  - TABELA_PROCESSO.md: resumo do processo por caso (cenário-base);
  - resultados_equipamentos.json: estado e resultado principal dos 11 TAGs;
  - golden_case_01.json: os números do caso de referência (BOT 02) de ponta a ponta.

    uv run python tools/tabelas_auditoria.py [--casos ARQ] [--saida docs/auditoria]
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.core.unidades import SEGUNDOS_POR_DIA
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas
from fpso_siz.pfd.planta import dimensionar

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
GOLDEN = 2
CORRENTES_GOLDEN = ["C-01", "C-03", "C-04", "C-05", "C-06", "C-09", "C-10", "C-12", "C-14", "C-16", "C-17",
                    "C-18", "C-19", "C-21", "C-25"]


def n(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(x):
    return None if isinstance(x, float) and not math.isfinite(x) else x


def identidade(casos):
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    suja = bool(subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=RAIZ, capture_output=True,
                               text=True).stdout.strip())
    return {"commit": commit, "src_modificado": suja, "casos": str(casos.relative_to(RAIZ)),
            "sha256_casos": hashlib.sha256(casos.read_bytes()).hexdigest()}


def tabela_processo(b, prem):
    out = ["# Tabela resumida do processo — cenário-base", "",
           f"Gerado por `tools/tabelas_auditoria.py`. **CENÁRIO-BASE**: P_D1 = {n(prem['P_D1'], 0)} kPa (P-18), "
           f"P_D2 = {n(prem['P_D2'], 0)} kPa (P-19). Vazões padrão (m³/d; gás em Sm³/d). Gás por estágio pelo trem nos "
           "12 casos avaliáveis e por Standing nos 4 com gás de lift. TVP a 40 °C só nos avaliáveis; **no cenário-base "
           "ela não atende o limite de 70 kPa do BOT em nenhum dos 12**.", "",
           "| caso | fluido | classe | óleo BOT | água | gás BOT | lift | T (°C) | Q_G SG-001 | Q_G V-001 | Q_G V-002 | "
           "óleo à estocagem (C-25) | Q_pre (kW) | Q_H (kW) | Q_C (kW) | W bombas (kW) | TVP (kPa) |",
           "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in b:
        c = r.caso
        w = r.duties["W_Bo"] + r.duties["W_B1"] + r.duties["W_B2"]
        out.append(f"| {r.num} | {r.fluid} | {'avaliável' if r.avaliavel else 'lift (Standing)'} | {n(c['oil_sm3d'], 0)} | "
                   f"{n(r.Wv, 0)} | {n(c['produced_gas_sm3d'], 0)} | {n(c['lift_gas_sm3d'], 0)} | {n(c['T_C'], 0)} | "
                   f"{n(r.gas['G_F'], 0)} | {n(r.gas['G_D1'], 0)} | {n(r.gas['G_D2'], 0)} | {n(r.q('C-25', 'O'), 0)} | "
                   f"{n(r.duties['Q_pre'], 0)} | {n(r.duties['Q_H'], 0)} | {n(r.duties['Q_C'], 0)} | {n(w, 1)} | "
                   f"{n(r.tvp_kPa, 1) if r.avaliavel else 'não verificada'} |")
    return "\n".join(out) + "\n"


def equipamentos(planta):
    out = {}
    for rt in planta.tags:
        r = rt.resultado
        campos = {}
        if r is not None:
            for f in rt.entradas.metodo.result_fields(r):
                campos[f.label] = {"valor": num(float(f.value)) if isinstance(f.value, (int, float)) else f.value,
                                   "unidade": f.unit, "principal": bool(f.highlight)}
        out[rt.tag.tag] = {"nome": rt.tag.nome, "metodo": rt.tag.metodo, "status": rt.status,
                           "x": num(r.x) if r else None, "y": num(r.y) if r else None,
                           "governante": r.governing if r else None, "caso_governante": r.driver_case if r else None,
                           "mensagem": r.message if r else rt.mensagem if hasattr(rt, "mensagem") else None,
                           "derivados": {k: num(v) for k, v in (r.derivados.items() if r else [])
                                         if isinstance(v, (int, float))},
                           "cartao": campos}
    return out


def golden(b, planta):
    r = next(x for x in b if x.num == GOLDEN)
    rec = r.recombinacao
    est = [{"estagio": e.ponto, "T_C": e.T_C, "P_kPa": e.P_kPa, "beta": e.beta, "Q_G_Sm3_d": e.q_vapor_sm3d,
            "MW_v": e.vapor.MW, "Z_v": e.vapor.Z, "rho_v": e.vapor.rho} for e in r.trem.estagios]
    f = r.trem.fechamento
    k = SEGUNDOS_POR_DIA
    streams = {s: {"T_C": r.T[s], "P_kPa": r.P[s], **{c: r.streams[s][c] * k for c in r.streams[s]}}
               for s in CORRENTES_GOLDEN}
    entradas = {}
    for rt in planta.tags:
        caso = next((c for c in rt.entradas.casos if c.num == GOLDEN), None) if rt.entradas else None
        if caso is None:
            continue
        entradas[rt.tag.tag] = {ch: {"valor": num(v.valor), "origem": v.origem, "fonte": v.fonte}
                                for ch, v in caso.valores.items() if isinstance(v.valor, (int, float))}
    perca = {}
    for rt in planta.tags:
        if rt.resultado is None:
            continue
        pc = next((p for p, nome in zip(rt.resultado.per_case, rt.resultado.case_names) if nome.startswith(f"BOT {GOLDEN:02d}")),
                  None)
        if pc is not None:
            perca[rt.tag.tag] = {"x_isolado": num(pc.x), "viavel_isolado": pc.feasible}
    return {"caso": GOLDEN, "fluido": r.fluid, "avaliavel": r.avaliavel, "entrada_BOT": {
                k: r.caso[k] for k in ("oil_sm3d", "liquid_sm3d", "produced_gas_sm3d", "lift_gas_sm3d", "T_C")},
            "recombinacao": {"n_gas_kmol_d": rec.n_gas_kmol_d, "n_liquido_kmol_d": rec.n_liquido_kmol_d,
                             "Q_G_reproduzido_Sm3_d": rec.reproducao.q_gas_fwko_sm3d,
                             "Q_O_reproduzido_m3_d": rec.reproducao.q_oleo_tanque_m3d,
                             "erro_gas_rel": rec.reproducao.erro_gas_rel, "erro_oleo_rel": rec.reproducao.erro_oleo_rel},
            "trem": est, "fechamento_trem": {"molar": f.erro_molar_relativo, "massico": f.erro_massico_relativo,
                                             "componente": f.erro_componente_max, "ok": f.ok},
            "correntes_kg_d": streams, "gas_Sm3_d": {k: num(v) for k, v in r.gas.items()}, "cargas_kW": r.duties,
            "BSW_FWKO": r.BSW_F, "FWKO": {k: v for k, v in r.fwko.items() if k != "estado"},
            "TVP_kPa": r.tvp_kPa, "T_TVP_C": r.T_tvp_C, "iteracoes_reciclo": r.iters, "residuo_reciclo": r.residuo_reciclo,
            "entradas_TAG": entradas, "x_isolado_por_TAG": perca}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS)
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "auditoria")
    a = ap.parse_args()
    dados = carregar_casos(a.casos)
    ctx = servico.Contexto(dados, propostas=propostas.padrao())
    b = ctx.balanco
    planta = dimensionar(contexto=ctx)
    a.saida.mkdir(parents=True, exist_ok=True)
    ident = identidade(a.casos.resolve())
    (a.saida / "TABELA_PROCESSO.md").write_text(tabela_processo(b, ctx.prem), encoding="utf-8")
    for nome, dado in (("resultados_equipamentos.json", equipamentos(planta)), ("golden_case_01.json", golden(b, planta))):
        (a.saida / nome).write_text(json.dumps({"identidade": ident, "dados": dado}, indent=2, ensure_ascii=False,
                                               default=str) + "\n", encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
