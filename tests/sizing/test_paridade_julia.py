"""F6/F7/F8 — vasos, bomba, trocador e Análise Pinch reproduzem o FPSO_Siz Julia (tests/fixtures/julia, commit no manifesto):
envelope, varredura, casos individuais com varredura e rastro, cartão, colunas, blocos,
descritores (com reetiquetamentos) e constantes.

Knockout e tratador: igualdade BIT A BIT. Separador, bomba e trocador: ≤ 1e-13 relativo —
funções transcendentais (acos na bisseção de β; log10 no Colebrook; pow/acos/exp/cbrt no
Bell-Delaware) diferem no último ulp entre a libm do Julia e a do sistema. Desvios máximos
medidos: separador 1,25e-15 (11 números), bomba 2,5e-16 (5), trocador 4,8e-16 (846); o ponto
escolhido (x, y) é idêntico nos cinco.
"""
import json
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from comparacao import diferencas, puro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.motor import governing_summary, size_envelope
from fpso_siz.sizing import (ArnoldElectrostatic, CentrifugalPump, ElectrostaticTreater, KnockoutDrum,
                             MoranPumpSizing, PinchKemp, PinchTarget, SaariLMTD, Separator, ShellTubeExchanger,
                             StewartArnold, StewartArnoldTwoPhase)

FJ = Path(__file__).resolve().parents[1] / "fixtures" / "julia"
VASOS = [("separador-3f", Separator(), StewartArnold(), 1e-13),
         ("knockout-2f", KnockoutDrum(), StewartArnoldTwoPhase(), 0.0),
         ("vaso-eletrostatico", ElectrostaticTreater(), ArnoldElectrostatic(), 0.0),
         ("bomba-centrifuga", CentrifugalPump(), MoranPumpSizing(), 1e-13),
         ("trocador-calor", ShellTubeExchanger(), SaariLMTD(), 1e-13),
         # F8: a Problem Table é aritmética sobre os dados, sem correlação empírica no meio —
         # a paridade é bit a bit.
         ("analise-pinch", PinchTarget(), PinchKemp(), 0.0)]


def envelope_puro(r, extensao=()):
    # o que o motor guarda para a memória de cálculo ler (core/memoria.py) não tem par no Julia
    d = puro(replace(r, metodo=None, preparo=(), p_env=None, pcs=()))
    for k in ("derivados_v2", "metodo", "preparo", "p_env", "pcs"):   # extensões do V2
        d.pop(k)

    def sem_extensao(derivados):
        for k in extensao:
            derivados.pop(k, None)

    sem_extensao(d["derivados"])
    for row in d["rows"]:
        row["tem_presentation"] = row.pop("presentation") is not None
        sem_extensao(row["derivados"])
    for pc, orig in zip(d["per_case"], r.per_case):
        pc["trace"] = [puro(e) for e in orig.trace.entries]
        sem_extensao(pc["derivados"])
        for s in pc["sweep"]:
            s["tem_presentation"] = s.pop("presentation") is not None
            sem_extensao(s["derivados"])
    return d


@pytest.fixture(scope="module", params=VASOS, ids=lambda v: v[0])
def vaso(request):
    box, eq, m, rtol = request.param
    fx = json.loads((FJ / f"{box}.json").read_text(encoding="utf-8"))
    cs = case_set_from_config(tomllib.loads((FJ / "casos" / f"{fx['exemplo']}.toml").read_text(encoding="utf-8")))
    return fx, eq, m, rtol, size_envelope(eq, m, cs)


def test_envelope_completo(vaso):
    fx, _, m, rtol, r = vaso
    assert diferencas(envelope_puro(r, m.derivados_extensao), fx["envelope"], rtol) == []
    assert (r.x, r.y, r.driver_case) == (fx["envelope"]["x"], fx["envelope"]["y"], fx["envelope"]["driver_case"])


def test_cartao_resumo_e_colunas(vaso):
    fx, _, m, rtol, r = vaso
    # o cartão do Julia sai quando a extensão do V2 está vazia (ela só acrescenta grandezas)
    assert diferencas([puro(f) for f in m.result_fields(replace(r, derivados_v2={}))], fx["result_fields"],
                      rtol) == []
    assert governing_summary(m, r) == fx["governing_summary"]
    assert diferencas([puro(c) for c in m.sweep_columns()], fx["sweep_columns"], 0) == []
    assert [{"key": k, "title": t} for k, t in m.trace_blocks()] == fx["trace_blocks"]


def test_descritores_e_constantes(vaso):
    fx, eq, m, _, _ = vaso
    extensoes = {s.key for s in m.extensoes()}  # acréscimos do V2, fora do Julia
    assert [puro(s) for s in m.parameters() if s.key not in extensoes] == fx["parameters"]
    assert [puro(s) for s in m.stream_parameters()] == fx["stream_parameters"]
    assert m.constants() == fx["constants"]
    assert (list(m.stream_keys()), m.global_keys(), m.action_label(), list(m.requirement_spec()), m.label,
            eq.label, m.parameter_groups()) == \
        (fx["stream_keys"], fx["global_keys"], fx["action_label"], fx["requirement_spec"], fx["label"],
         fx["equipment_label"], fx["parameter_groups"])


def test_ajustes_globais_sao_descritores_do_metodo(vaso):
    _, _, m, _, _ = vaso
    assert set(m.global_keys()) <= {s.key for s in m.parameters()}
