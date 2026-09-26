"""F10x.7 — extensões do V2 no trocador (cascos em série/paralelo, P-45) e nas potências da
bomba. Os casos de ensaio são os exemplos do Julia (tests/fixtures/julia/casos); com os
defaults das extensões o resultado é exatamente o do Julia (test_paridade_julia)."""
import math
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from fpso_siz.core.casos import Case, CaseSet, case_set_from_config
from fpso_siz.core.motor import size_envelope
from fpso_siz.core.parametros import with_defaults
from fpso_siz.core.unidades import potencia_hidraulica_kw
from fpso_siz.sizing import CentrifugalPump, MoranPumpSizing, SaariLMTD, ShellTubeExchanger
from fpso_siz.sizing.trocador import _tubo

CASOS = Path(__file__).resolve().parents[1] / "fixtures" / "julia" / "casos"
S, TX = SaariLMTD(), ShellTubeExchanger()
M, EQ = MoranPumpSizing(), CentrifugalPump()


def _cs(nome, **extra):
    cs = case_set_from_config(tomllib.loads((CASOS / nome).read_text(encoding="utf-8")))
    return CaseSet([replace(c, values={**c.values, **extra}) for c in cs.cases])


def _cons(m, cs):
    out = []
    for _, vals in cs.expand():
        ok, c, _ = m.sizing_constraints(m.case_input(vals), with_defaults(m.parameters(), vals), m.constants())
        assert ok
        out.append(c)
    return out


# ------------------------------------------------------------------ cascos em série e paralelo
def test_defaults_sao_um_casco_e_sem_extensao_no_envelope():
    r = size_envelope(TX, S, _cs("exemplo_trocador.toml"))
    assert r.feasible and r.derivados_v2 == {}
    assert all(c.n_serie == 1 and c.n_paralelo == 1 for c in _cons(S, _cs("exemplo_trocador.toml")))


def test_cascos_em_paralelo_dividem_vazoes_e_carga():
    um, dois = _cons(S, _cs("exemplo_trocador.toml")), _cons(S, _cs("exemplo_trocador.toml", cascos_paralelo=2.0))
    for a, b in zip(um, dois, strict=True):
        assert math.isclose(b.m_tubo, a.m_tubo / 2) and math.isclose(b.m_casco, a.m_casco / 2)
        assert math.isclose(b.q, a.q / 2) and math.isclose(b.ua_exigido, a.ua_exigido / 2)
        assert b.dt_lm == a.dt_lm and b.f == a.f and b.t_casco_out == a.t_casco_out


def test_cascos_em_serie_dividem_o_ua_com_as_vazoes_inteiras():
    um, tres = _cons(S, _cs("exemplo_trocador.toml")), _cons(S, _cs("exemplo_trocador.toml", cascos_serie=3.0))
    for a, b in zip(um, tres, strict=True):
        assert b.m_tubo == a.m_tubo and b.q == a.q and b.f == a.f   # F do conjunto (conservador)
        assert math.isclose(b.ua_exigido, a.ua_exigido / 3)
    r = size_envelope(TX, S, _cs("exemplo_trocador.toml", cascos_serie=3.0))
    assert r.feasible and r.derivados_v2["cascos_serie"] == 3.0
    assert math.isclose(r.derivados_v2["area_total"], 3 * r.derivados_v2["area_por_casco"])


# ------------------------------------------------------------------ P-45
def _dois_casos(fator):
    """O exemplo do Julia e uma cópia com as vazões divididas por `fator` (turndown)."""
    cs = _cs("exemplo_trocador.toml")
    c0 = cs.cases[0]
    baixo = {**c0.values, "m_tubo": c0.values["m_tubo"] / fator, "m_casco": c0.values["m_casco"] / fator}
    return CaseSet([c0, Case("turndown", baixo)])


def test_p45_piso_so_no_caso_de_projeto_com_alerta():
    cs = _dois_casos(2.0)
    julia = size_envelope(TX, S, cs)
    ext = [replace(c, values={**c.values, "banda_caso_projeto": 1.0}) for c in cs.cases]
    p45 = size_envelope(TX, S, CaseSet(ext))
    conss = _cons(S, CaseSet(ext))
    ok, p_env = S.envelope_params([with_defaults(S.parameters(), v) for _, v in CaseSet(ext).expand()])
    pcs = S.envelope_case_params(conss, p_env)
    assert S.caso_projeto(conss) == 0 and pcs[0] is p_env and pcs[1]["v_min"] == 0.0
    assert pcs[1]["v_max"] == p_env["v_max"]
    assert p45.feasible
    v_turndown = _tubo(conss[1], p45.x)["v"]
    alerta = v_turndown < p_env["v_min"]
    assert (1.0 in p45.derivados_v2["casos_abaixo_v_min"]) == alerta
    if not julia.feasible:
        assert alerta   # o que a regra do Julia reprovava vira alerta


def test_p45_nao_relaxa_dittus_boelter():
    """Turndown profundo: sem Re na faixa de Dittus-Boelter, o feixe continua reprovado."""
    cs = _dois_casos(50.0)
    ext = CaseSet([replace(c, values={**c.values, "banda_caso_projeto": 1.0}) for c in cs.cases])
    r = size_envelope(TX, S, ext)
    conss = _cons(S, ext)
    ok, p_env = S.envelope_params([with_defaults(S.parameters(), v) for _, v in ext.expand()])
    pcs = S.envelope_case_params(conss, p_env)
    for row in r.rows:
        if not _tubo(conss[1], row.x)["nu_valido"]:
            assert not row.ok and ("dittus_boelter", 1) in S.bloqueios(row.x, conss, pcs, p_env)


def test_bloqueios_vazio_no_feixe_escolhido():
    cs = _cs("exemplo_trocador.toml")
    r = size_envelope(TX, S, cs)
    conss = _cons(S, cs)
    ok, p_env = S.envelope_params([with_defaults(S.parameters(), v) for _, v in cs.expand()])
    assert S.bloqueios(r.x, conss, S.envelope_case_params(conss, p_env), p_env) == []


# ------------------------------------------------------------------ potências da bomba
def test_tres_potencias_separadas():
    cs = _cs("exemplo_bomba.toml")
    r = size_envelope(EQ, M, cs)
    v2 = r.derivados_v2
    assert v2["potencia_caso_governante"] == r.derivados["potencia"]   # o campo do Julia é o do caso governante
    assert v2["potencia_max_operacional"] >= v2["potencia_caso_governante"]
    conss = _cons(M, cs)
    esperado = potencia_hidraulica_kw(max(c.rho for c in conss), max(c.q_m3h for c in conss), v2["h_nominal"],
                                      min(c.rendimento for c in conss), conss[0].g)
    assert v2["potencia_nominal"] == esperado >= v2["potencia_max_operacional"]
    rotulos = [f.label for f in M.result_fields(r)]
    assert {"Potência no caso governante", "Potência máxima operacional", "Potência nominal requerida"} <= set(rotulos)
    assert "Potência de eixo" not in rotulos
    assert "Potência de eixo" in [f.label for f in M.result_fields(replace(r, derivados_v2={}))]


@pytest.mark.parametrize("nome", ["exemplo_bomba.toml", "exemplo_trocador.toml"])
def test_inviavel_nao_tem_extensao(nome):
    m, eq = (M, EQ) if "bomba" in nome else (S, TX)
    cs = _cs(nome, **({"v_max": 0.1, "v_min": 0.05} if m is M else {"l_tubo_max": 0.5}))
    r = size_envelope(eq, m, cs)
    assert not r.feasible and r.derivados_v2 == {}
