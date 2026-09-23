#!/usr/bin/env python3
"""Gera o oráculo numérico do balanço preliminar a partir do script original congelado.

O script `references/Balanço_Preliminar.py` (cabeçalho: `gerar_memorial.py`) NÃO é
editado. Ele é executado como módulo, numa pasta temporária com uma cópia do JSON de
casos, e as grandezas são lidas das suas globais. A saída é determinística: não há
carimbo de tempo nem caminho absoluto.

Uso:
    uv run python tools/gerar_oraculo_balanco.py [--referencias references]
                                                 [--saida tests/fixtures/python_ref]
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = "Balanço_Preliminar.py"
ENTRADA = "design_cases_bot.json"
NOME_MODULO = "balanco_preliminar_ref"
ESQUEMA = 1


def sha256(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


def executar_script(referencias):
    """Executa o script original num diretório temporário; devolve (módulo, stdout, main.tex)."""
    script = referencias / SCRIPT
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(referencias / ENTRADA, Path(tmp) / ENTRADA)
        spec = importlib.util.spec_from_file_location(NOME_MODULO, script)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[NOME_MODULO] = mod  # o script faz M = sys.modules[__name__]
        cwd = os.getcwd()
        saida = io.StringIO()
        try:
            os.chdir(tmp)
            with warnings.catch_warnings(), contextlib.redirect_stdout(saida):
                warnings.simplefilter("ignore", SyntaxWarning)  # escapes inválidos do original
                spec.loader.exec_module(mod)
            main_tex = (Path(tmp) / "main.tex").read_bytes()
        finally:
            os.chdir(cwd)
    return mod, saida.getvalue().strip(), main_tex


def resultado_caso(r):
    """Tudo o que solve_case devolve, menos as funções (H, C, vol)."""
    mu_valor, mu_flag = r["mu"]
    return {
        "num": r["case"]["num"],
        "fluid": r["fluid"],
        "well": r["well"],
        "api": r["api"],
        "rho": r["rho"],
        "cp": r["cp"],
        "gp": r["gp"],
        "Wv": r["Wv"],
        "BSW01": r["BSW01"],
        "BSW_F": r["BSW_F"],
        "streams": r["streams"],
        "T": r["T"],
        "P": r["P"],
        "duties": r["duties"],
        "gas": r["gas"],
        "reciclo": {"iters": r["iters"], "convergiu": r["iters"] < 499},
        "mu": {"valor": mu_valor, "flag": mu_flag},
    }


def montar_oraculo(mod, stdout, main_tex, referencias):
    casos = []
    for r in mod.R:
        c = resultado_caso(r)
        c["block_balance"] = {b[0]: mod.block_balance(r, b) for b in mod.BLOCKS}
        c["global_balance"] = mod.global_balance(r)
        casos.append(c)

    sensibilidade = []
    for n in mod.SC:
        caso = mod.CASES[mod.NUM.index(n)]
        for rotulo, kw in mod.SENS:
            r = mod.run(caso, **kw)
            sensibilidade.append({
                "num": n,
                "rotulo": rotulo,
                "premissas_alteradas": kw,
                "resultado": resultado_caso(r),
                "global_balance": mod.global_balance(r),
            })

    return {
        "esquema": ESQUEMA,
        "proveniencia": {
            "script": SCRIPT,
            "script_sha256": sha256(referencias / SCRIPT),
            "entrada": ENTRADA,
            "entrada_sha256": sha256(referencias / ENTRADA),
            "main_tex_sha256": hashlib.sha256(main_tex).hexdigest(),
            "main_tex_bytes": len(main_tex),
            "stdout": stdout,
            "gerador": "tools/gerar_oraculo_balanco.py",
            "python": "%d.%d" % sys.version_info[:2],
            "limitacoes": [
                "resíduo do laço de reciclo não é exposto pelo script; registra-se iters "
                "e convergiu = iters < 499 (critério original: diff < 1e-10 após it > 3)",
                "envelopes: o script guarda só texto formatado; os valores numéricos "
                "estão em 'criticos' e derivam dos resultados por caso",
            ],
        },
        "constantes": {
            "R_GAS": mod.R_GAS, "T_STD": mod.T_STD, "P_STD": mod.P_STD, "VM": mod.VM,
            "RHO_W15": mod.RHO_W15, "MW": mod.MW, "CP0": mod.CP0,
            "API_WELL": mod.API_WELL, "MU_WELL": mod.MU_WELL, "COMP": mod.COMP,
        },
        "premissas": mod.PREM,
        "topologia": {
            "blocos": [
                {"id": b[0], "nome": b[1], "entradas": b[2], "saidas": b[3],
                 "Q_in": b[4], "Q_out": b[5], "W": b[6]}
                for b in mod.BLOCKS
            ],
            "global_in": mod.GLOBAL_IN,
            "global_out": mod.GLOBAL_OUT,
            "correntes": [{"id": a, "nome": b, "fase": c} for a, b, c in mod.STREAMS],
        },
        "casos": casos,
        "auditoria": [
            {"verificacao": nome, "base": base, "max_desvio_abs": val, "unidade": un}
            for nome, base, val, un in mod.AUD
        ],
        "envelopes": [
            {"variavel": nome, "valor_fmt": val, "unidade": un, "casos_fmt": casos_, "origem": orig}
            for nome, val, un, casos_, orig in mod.env
        ],
        "criticos": [
            {"equipamento": e, "criterio": cr, "valor": mx, "casos": idx}
            for e, cr, (mx, idx) in mod.crit
        ],
        "caso_demo": mod.DEMO,
        "casos_sensibilidade": mod.SC,
        "sensibilidade": sensibilidade,
    }


def serializar(oraculo):
    return (json.dumps(oraculo, ensure_ascii=False, indent=1, allow_nan=False) + "\n").encode()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--referencias", default=RAIZ / "references", type=Path)
    ap.add_argument("--saida", default=RAIZ / "tests" / "fixtures" / "python_ref", type=Path)
    a = ap.parse_args(argv)

    mod, stdout, main_tex = executar_script(a.referencias)
    dados = serializar(montar_oraculo(mod, stdout, main_tex, a.referencias))
    a.saida.mkdir(parents=True, exist_ok=True)
    (a.saida / "oraculo_balanco.json").write_bytes(dados)
    (a.saida / "main_ref.tex").write_bytes(main_tex)
    print(f"oraculo_balanco.json  {hashlib.sha256(dados).hexdigest()}  ({len(dados)} bytes)")
    print(f"main_ref.tex          {hashlib.sha256(main_tex).hexdigest()}  ({len(main_tex)} bytes)")


if __name__ == "__main__":
    main()
