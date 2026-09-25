"""F2 — paridade do motor modularizado com o oráculo do script original.

O critério do plano é erro relativo ≤ 1e-12; a paridade obtida é BIT A BIT (a ordem das
operações do original foi preservada), então a tolerância é travada em zero: qualquer
mudança numérica, por menor que seja, tem de ser justificada e o oráculo revisto.
"""
import math

import pytest

from fpso_siz.balanco.balancos import balanco_global, balancos_por_bloco
from fpso_siz.balanco.dados import premissas
from fpso_siz.balanco.modelo import REFERENCIA, resolver_caso

TOL_REL = 0.0
CAMPOS = ("fluid", "well", "api", "rho", "cp", "gp", "Wv", "BSW01", "BSW_F",
          "streams", "T", "P", "duties", "gas")


def divergencias(a, b, caminho=""):
    """Lista (caminho, a, b) onde a e b diferem além de TOL_REL (recursivo)."""
    if isinstance(b, dict):
        if not isinstance(a, dict) or set(a) != set(b):
            return [(caminho, a, b)]
        return [d for k in b for d in divergencias(a[k], b[k], f"{caminho}/{k}")]
    if isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return [(caminho, a, b)]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in divergencias(x, y, f"{caminho}[{i}]")]
    if isinstance(b, float) or isinstance(a, float):
        if a == b or math.isclose(a, b, rel_tol=TOL_REL, abs_tol=0.0):
            return []
        return [(caminho, a, b)]
    return [] if a == b else [(caminho, a, b)]


def comparar_resultado(r, esperado):
    difs = []
    for k in CAMPOS:
        difs += divergencias(getattr(r, k), esperado[k], k)
    difs += divergencias(r.iters, esperado["reciclo"]["iters"], "iters")
    difs += divergencias(list(r.mu), [esperado["mu"]["valor"], esperado["mu"]["flag"]], "mu")
    return difs


def test_premissas_iguais_ao_prem_original(dados, oraculo):
    """As premissas do script de referência são as mesmas; a F10w só acrescenta a P-43 (η_A
    padrão do SG-001), que a regra de referência não usa."""
    p = premissas(dados)
    assert set(p) - set(oraculo["premissas"]) == {"eta_F"} and p["eta_F"] == 0.85
    assert divergencias({k: v for k, v in p.items() if k != "eta_F"}, oraculo["premissas"]) == []


@pytest.mark.parametrize("i", range(16), ids=lambda i: f"caso{i + 1}")
def test_caso(i, resultados, oraculo):
    r, esperado = resultados[i], oraculo["casos"][i]
    assert r.num == esperado["num"]
    assert comparar_resultado(r, esperado) == []
    assert divergencias(balancos_por_bloco(r), esperado["block_balance"]) == []
    assert divergencias(balanco_global(r), esperado["global_balance"]) == []


def test_sensibilidade(dados, oraculo):
    for s in oraculo["sensibilidade"]:
        r = resolver_caso(dados.caso(s["num"]), dados, premissas(dados, **s["premissas_alteradas"]), REFERENCIA)
        assert comparar_resultado(r, s["resultado"]) == [], (s["num"], s["rotulo"])
        assert divergencias(balanco_global(r), s["global_balance"]) == [], (s["num"], s["rotulo"])


def test_reciclo_convergiu_abaixo_da_tolerancia(resultados):
    for r in resultados:
        assert r.iters < 499
        assert r.residuo_reciclo < 1e-10


def test_comparador_detecta_diferenca():
    assert divergencias({"a": 1.0}, {"a": 1.0 + 1e-15}) != []
    assert divergencias({"a": [1.0, "x"]}, {"a": [1.0, "y"]}) != []
    assert divergencias({"a": 1.0}, {"b": 1.0}) != []
    assert divergencias([1.0], [1.0, 2.0]) != []


def test_convergiu_explicito(resultados):
    assert all(r.convergiu for r in resultados)


def test_sem_convergencia_e_sinalizado(dados, monkeypatch):
    import dataclasses
    from types import MappingProxyType

    from fpso_siz.balanco import modelo

    const = modelo.constantes()
    curto = dataclasses.replace(const, numerico=MappingProxyType({**const.numerico, "reciclo_max_iter": 2}))
    monkeypatch.setattr(modelo, "constantes", lambda: curto)
    r = modelo.resolver_caso(dados.caso(8), dados)
    assert r.iters == 1
    monkeypatch.undo()
    assert not r.convergiu and r.residuo_reciclo > 1e-10


def test_capacidade_e_volume(resultados):
    r = resultados[7]
    s = r.streams["C-21"]
    assert r.C(s) == sum(s[c] * r.cp[c] for c in "OWDG")
    assert r.vol(s, "O") == s["O"] / r.rho["O"] / (1 / 86400)
    assert r.H(s, r.T_ref) == 0.0
