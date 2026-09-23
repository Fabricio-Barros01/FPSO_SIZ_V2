"""F3 — auditoria independente: paridade com o original, independência e sensibilidade."""
import ast
import dataclasses
from pathlib import Path

from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import premissas

FONTE = Path(__file__).resolve().parents[2] / "src" / "fpso_siz" / "balanco" / "auditoria.py"


def como_original(aud):
    return [[a["verificacao"], a["base"], a["max_desvio_abs"], a["unidade"]] for a in aud]


def test_identica_ao_oraculo(resultados, dados, oraculo):
    esperado = [[a["verificacao"], a["base"], a["max_desvio_abs"], a["unidade"]] for a in oraculo["auditoria"]]
    assert como_original(auditar(resultados, dados, premissas(dados))) == esperado


def test_nao_importa_o_motor():
    for n in ast.walk(ast.parse(FONTE.read_text(encoding="utf-8"))):
        if isinstance(n, ast.ImportFrom):
            assert n.module not in ("fpso_siz.balanco.modelo", "fpso_siz.balanco.balancos",
                                    "fpso_siz.balanco.propriedades"), n.module


def test_detecta_erro_injetado_no_resultado(resultados, dados):
    p = premissas(dados)
    base = {a["id"]: a["max_desvio_abs"] for a in auditar(resultados, dados, p)}
    r = resultados[7]
    errado = dataclasses.replace(r, duties=dict(r.duties, Q_H=r.duties["Q_H"] + 1.0))
    aud = {a["id"]: a["max_desvio_abs"] for a in auditar([*resultados[:7], errado, *resultados[8:]], dados, p)}
    assert base["cargas_termicas"] < 1e-9 < 0.99 < aud["cargas_termicas"]
    assert aud["energia_global"] > 0.99
    assert aud["massa_global"] == base["massa_global"]


def test_salinidade_omitida_sem_agua_no_desidratador(resultados, dados):
    sem_agua = [r for r in resultados if r.gas["Dv"] == 0.0]
    assert sem_agua
    ids = [a["id"] for a in auditar(sem_agua, dados, premissas(dados))]
    assert "salinidade_oleo" not in ids and ids[0] == "identidade_liquido"
