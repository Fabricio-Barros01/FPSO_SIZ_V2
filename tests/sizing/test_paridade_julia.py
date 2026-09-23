"""F6 — os três vasos reproduzem o FPSO_Siz Julia (tests/fixtures/julia, commit no manifesto):
envelope, varredura, casos individuais com varredura e rastro, cartão, colunas, blocos,
descritores (com reetiquetamentos) e constantes.

Knockout e tratador: igualdade BIT A BIT. Separador: ≤ 1e-13 relativo — a cadeia de β
(bisseção sobre acos) difere no último ulp entre a libm do Julia e a do sistema; o maior
desvio medido é 1,25e-15 (11 números, todos derivados de β).
"""
import json
import tomllib
from pathlib import Path

import pytest

from comparacao import diferencas, puro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.motor import governing_summary, size_envelope
from fpso_siz.sizing import (ArnoldElectrostatic, ElectrostaticTreater, KnockoutDrum, Separator, StewartArnold,
                             StewartArnoldTwoPhase)

FJ = Path(__file__).resolve().parents[1] / "fixtures" / "julia"
VASOS = [("separador-3f", Separator(), StewartArnold(), 1e-13),
         ("knockout-2f", KnockoutDrum(), StewartArnoldTwoPhase(), 0.0),
         ("vaso-eletrostatico", ElectrostaticTreater(), ArnoldElectrostatic(), 0.0)]


def envelope_puro(r):
    d = puro(r)
    for row in d["rows"]:
        row["tem_presentation"] = row.pop("presentation") is not None
    for pc, orig in zip(d["per_case"], r.per_case):
        pc["trace"] = [puro(e) for e in orig.trace.entries]
        for s in pc["sweep"]:
            s["tem_presentation"] = s.pop("presentation") is not None
    return d


@pytest.fixture(scope="module", params=VASOS, ids=lambda v: v[0])
def vaso(request):
    box, eq, m, rtol = request.param
    fx = json.loads((FJ / f"{box}.json").read_text(encoding="utf-8"))
    cs = case_set_from_config(tomllib.loads((FJ / "casos" / f"{fx['exemplo']}.toml").read_text(encoding="utf-8")))
    return fx, eq, m, rtol, size_envelope(eq, m, cs)


def test_envelope_completo(vaso):
    fx, _, _, rtol, r = vaso
    assert diferencas(envelope_puro(r), fx["envelope"], rtol) == []


def test_cartao_resumo_e_colunas(vaso):
    fx, _, m, rtol, r = vaso
    assert diferencas([puro(f) for f in m.result_fields(r)], fx["result_fields"], rtol) == []
    assert governing_summary(m, r) == fx["governing_summary"]
    assert diferencas([puro(c) for c in m.sweep_columns()], fx["sweep_columns"], 0) == []
    assert [{"key": k, "title": t} for k, t in m.trace_blocks()] == fx["trace_blocks"]


def test_descritores_e_constantes(vaso):
    fx, eq, m, _, _ = vaso
    assert [puro(s) for s in m.parameters()] == fx["parameters"]
    assert [puro(s) for s in m.stream_parameters()] == fx["stream_parameters"]
    assert m.constants() == fx["constants"]
    assert (list(m.stream_keys()), m.global_keys(), m.action_label(), list(m.requirement_spec()), m.label,
            eq.label, m.parameter_groups()) == \
        (fx["stream_keys"], fx["global_keys"], fx["action_label"], fx["requirement_spec"], fx["label"],
         fx["equipment_label"], fx["parameter_groups"])


def test_familia_declara_os_seis_descritores(vaso):
    _, _, m, _, _ = vaso
    assert set(m.global_keys()) <= {s.key for s in m.parameters()}
