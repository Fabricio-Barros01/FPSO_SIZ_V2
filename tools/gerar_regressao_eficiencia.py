#!/usr/bin/env python3
"""Gera a fixture de regressão do balanço produtivo (regra de eficiência do FWKO, P-43).

O balanço não tem oráculo externo: esta fixture congela o resultado que o usuário conferiu em
2026-09-25 (tabela dos 16 casos em docs/validacao/12-eficiencia-fwko.md), para que uma
refatoração não mude número sem ser notada. Revista em 2026-09-28 pela mudança física
deliberada do trem produtivo (docs/validacao/39): os 12 casos avaliáveis mudam, os 4 com gás de
lift ficam idênticos. Saída determinística (sem data nem caminho).

Uso:
    uv run python tools/gerar_regressao_eficiencia.py [--saida tests/fixtures/python_ref]
"""
import argparse
import hashlib
import json
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, premissas
from fpso_siz.balanco.modelo import resolver_todos

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
NOME = "regressao_eficiencia.json"
ESQUEMA = 2


def gerar():
    dados = carregar_casos(ENTRADA)
    prem = premissas(dados)
    casos = [dict(num=r.num, fwko=r.fwko, BSW01=r.BSW01, BSW_F=r.BSW_F, iters=r.iters,
                  residuo_reciclo=r.residuo_reciclo, streams=r.streams, T=r.T, duties=r.duties, gas=r.gas)
             for r in resolver_todos(dados, prem)]
    return dict(esquema=ESQUEMA, regra_fwko="eficiencia",
                proveniencia=dict(entrada_sha256=hashlib.sha256(ENTRADA.read_bytes()).hexdigest(),
                                  gerador="tools/gerar_regressao_eficiencia.py",
                                  conferencia="tabela dos 16 casos confirmada pelo usuário em 2026-09-25",
                                  revisao="2026-09-28: trem produtivo nos casos avaliáveis (docs/validacao/39)"),
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
