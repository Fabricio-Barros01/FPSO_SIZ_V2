"""Gravação de JSON e CSV. Genérica: não conhece nenhuma grandeza pelo nome."""
import csv
import json
from pathlib import Path


def escrever_json(obj, caminho):
    """JSON UTF-8, floats em repr exato (ida e volta sem perda), sem NaN/Inf."""
    texto = json.dumps(obj, ensure_ascii=False, indent=1, allow_nan=False) + "\n"
    Path(caminho).write_text(texto, encoding="utf-8")


def escrever_csv(colunas, linhas, caminho):
    """CSV UTF-8 com cabeçalho = ids das colunas, na ordem dos descritores."""
    ids = [c["id"] for c in colunas]
    with Path(caminho).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ids, extrasaction="raise")
        w.writeheader()
        w.writerows(linhas)
