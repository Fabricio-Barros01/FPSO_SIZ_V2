#!/usr/bin/env python3
"""Gera a fixture de regressão do balanço na regra de eficiência do FWKO (F10w).

O oráculo `oraculo_balanco.json` vem do script de referência e cobre só a regra de
referência (modo de paridade). A regra padrão desde a F10w — η_A do SG-001 = máx(η_padrão;
η_req) — não tem oráculo externo: esta fixture congela o resultado que o usuário conferiu
em 2026-09-25 (tabela dos 16 casos em docs/validacao/12-eficiencia-fwko.md), para que uma
refatoração não mude número sem ser notada. Saída determinística (sem data nem caminho).

Uso:
    uv run python tools/gerar_regressao_eficiencia.py [--saida tests/fixtures/python_ref]
"""
import argparse
import hashlib
import json
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import EFICIENCIA, resolver_todos

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
NOME = "regressao_eficiencia.json"
ESQUEMA = 1


def gerar():
    dados = carregar_casos(ENTRADA)
    prem = premissas(dados)
    casos = [dict(num=r.num, fwko=r.fwko, BSW01=r.BSW01, BSW_F=r.BSW_F, iters=r.iters,
                  residuo_reciclo=r.residuo_reciclo, streams=r.streams, T=r.T, duties=r.duties, gas=r.gas)
             for r in resolver_todos(dados, prem, EFICIENCIA)]
    return dict(esquema=ESQUEMA, regra_fwko=EFICIENCIA,
                proveniencia=dict(entrada_sha256=hashlib.sha256(ENTRADA.read_bytes()).hexdigest(),
                                  gerador="tools/gerar_regressao_eficiencia.py",
                                  conferencia="tabela dos 16 casos confirmada pelo usuário em 2026-09-25"),
                premissas=prem, casos=casos)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", type=Path, default=ENTRADA.parent)
    a = ap.parse_args()
    destino = a.saida / NOME
    destino.write_text(json.dumps(gerar(), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(destino)


if __name__ == "__main__":
    main()
