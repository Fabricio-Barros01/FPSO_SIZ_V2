"""F10x.6 — P-44: banda de velocidade da linha pelo caso de projeto (maior vazão) e P-44b:
zona de transição nos casos de turndown com o f de Colebrook-White como limite superior.
Com os defaults do método (0) o envelope é exatamente o do Julia."""
import math

from fpso_siz.core.casos import Case, CaseSet
from fpso_siz.core.motor import size_envelope
from fpso_siz.sizing import CentrifugalPump, MoranPumpSizing
from fpso_siz.sizing.bomba import _hidraulica, _limite_superior
from fpso_siz.sizing.hidraulica import darcy_friction

M, EQ = MoranPumpSizing(), CentrifugalPump()
K = M.constants()

# Linha de óleo com duas vazões de faixa 23× (a razão do B-001 no BOT): valores de ensaio,
# não dados do projeto.
BASE = {"rho_oil": 889.0, "mu_oil": 7.9, "pressure": 1000.0, "temperature": 70.0, "p_recalque": 2500.0,
        "pv_informada": 1000.0, "h_sucao": 5.0, "dn_max": 1000.0}   # grade do descritor, como no PFD


def _envelope(vazoes, **extra):
    casos = CaseSet([Case(f"Q = {q}", BASE | {"q_oil": q} | extra) for q in vazoes])
    return size_envelope(EQ, M, casos)


def test_default_e_a_regra_do_julia():
    """Sem a P-44 a banda vale em todos os casos: as faixas isoladas não se cruzam."""
    r = _envelope((1198.4, 52.1))
    assert not r.feasible and "não se cruzam" in r.message


def test_piso_so_no_caso_de_projeto():
    r = _envelope((1198.4, 400.0), piso_caso_projeto=1.0)
    assert r.feasible
    projeto = _hidraulica(M.sizing_constraints(M.case_input(BASE | {"q_oil": 1198.4}),
                                               _p(piso_caso_projeto=1.0), K)[1], r.x)
    assert 1.0 <= projeto["v"] <= 1.5    # a banda inteira no caso de projeto
    # o menor DN com a banda no caso de maior vazão: o DN anterior da série passa do teto
    serie = [d for d in K["nominal_diameters"] if d < r.x]
    c = M.sizing_constraints(M.case_input(BASE | {"q_oil": 1198.4}), _p(), K)[1]
    assert _hidraulica(c, serie[-1])["v"] > 1.5


def _p(**extra):
    from fpso_siz.core.parametros import with_defaults
    return with_defaults(M.parameters(), BASE | extra)


def test_parametros_por_caso_so_relaxam_o_piso_fora_do_projeto():
    conss = [M.sizing_constraints(M.case_input(BASE | {"q_oil": q}), _p(), K)[1] for q in (100.0, 900.0, 300.0)]
    ok, p_env = M.envelope_params([_p(piso_caso_projeto=1.0, transicao_turndown=1.0)] * 3)
    pcs = M.envelope_case_params(conss, p_env)
    assert M.caso_projeto(conss) == 1 and pcs[1] is p_env
    assert all(pc["v_min"] == 0.0 and pc["v_max"] == p_env["v_max"] and pc["aceita_transicao"] for pc in (pcs[0], pcs[2]))
    ok, p_julia = M.envelope_params([_p()] * 3)
    assert M.envelope_case_params(conss, p_julia) == [p_julia] * 3


def test_colebrook_e_limite_superior_na_transicao():
    """Em toda a zona de transição o f de Colebrook-White (tubo liso e rugoso) é maior que 64/Re."""
    lam, turb = float(K["reynolds_laminar_max"]), float(K["reynolds_turbulent_min"])
    n = 10
    for i in range(1, n):
        re = lam + (turb - lam) * i / n
        for rel in (0.0, 1e-4, 1e-2):
            f, regime, confiavel = darcy_friction(re, rel, K)
            assert regime == "transicao" and not confiavel and f >= K["laminar_coefficient"] / re
            assert _limite_superior(dict(regime=regime, f=f, re=re), K)
    assert not _limite_superior(dict(regime="laminar", f=0.03, re=2000.0), K)


def test_turndown_na_transicao_so_com_p44b():
    """Caso de turndown com Re na transição na linha do caso de projeto: rejeitado sem a
    P-44b, aceito com ela; o caso de projeto continua exigindo correlação válida."""
    vazoes = (1198.4, 52.1)
    sem = _envelope(vazoes, piso_caso_projeto=1.0)
    com = _envelope(vazoes, piso_caso_projeto=1.0, transicao_turndown=1.0)
    assert not sem.feasible and com.feasible
    c = M.sizing_constraints(M.case_input(BASE | {"q_oil": 52.1}), _p(), K)[1]
    h = _hidraulica(c, com.x)
    assert h["regime"] == "transicao" and not h["confiavel"]
    # o caso de projeto não relaxa: sozinho e na transição, segue rejeitado
    assert not _envelope((52.1,), piso_caso_projeto=1.0, transicao_turndown=1.0, v_min=0.0, dn_min=600.0).feasible


def test_operacao_por_caso():
    vazoes = (1198.4, 400.0, 52.1)
    r = _envelope(vazoes, piso_caso_projeto=1.0, transicao_turndown=1.0)
    conss = [M.sizing_constraints(M.case_input(BASE | {"q_oil": q}), _p(), K)[1] for q in vazoes]
    ok, p_env = M.envelope_params([_p(piso_caso_projeto=1.0, transicao_turndown=1.0)] * 3)
    op = M.operacao_por_caso(conss, r.x, M.envelope_case_params(conss, p_env))
    assert [o["papel"] for o in op] == ["projeto", "turndown", "turndown"]
    assert [o["limite_superior"] for o in op] == [False, False, True]
    assert all(math.isclose(o["h"], _hidraulica(c, r.x)["h_total"]) for o, c in zip(op, conss))
    assert max(o["potencia"] for o in op) == op[0]["potencia"]
