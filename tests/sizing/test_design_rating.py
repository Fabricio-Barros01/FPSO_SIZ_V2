"""DESIGN × RATING no método do trocador (ADR 0005; docs/validacao/43).

Com o default (`rating_fora_do_projeto = 0`) a física é a do Julia e nada aqui muda: TODO caso
exige da geometria o comprimento que realiza a sua carga inteira. Com 1, só o caso de PROJETO
dimensiona; os demais são CLASSIFICADOS na geometria escolhida, e o que ela entrega neles sai
do rating. O que estes testes cobram é exatamente a fronteira entre as duas coisas.
"""
import math
import tomllib
from pathlib import Path

import pytest

from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.motor import size_envelope
from fpso_siz.core.parametros import with_defaults
from fpso_siz.sizing import SaariLMTD, ShellTubeExchanger
from fpso_siz.sizing.trocador import (comprimento_do_caso, perda_carga_tubo, rating_do_caso)

FJ = Path(__file__).resolve().parents[1] / "fixtures" / "julia"
M, EQ = SaariLMTD(), ShellTubeExchanger()


def casos(**ajustes):
    """Os casos do exemplo do trocador (fixture do Julia), com os ajustes pedidos em todos."""
    cfg = tomllib.loads((FJ / "casos" / "exemplo_trocador.toml").read_text(encoding="utf-8"))
    for caso in cfg["case"]:
        caso.update(ajustes)
    return case_set_from_config(cfg)


def restricoes(cs, **ajustes):
    """(nomes, restrições, p_env) preparados como o motor prepara."""
    specs, k = M.parameters(), M.constants()
    nomes, conss, params = [], [], []
    for nome, vals in cs.expand():
        p = with_defaults(specs, {**vals, **ajustes})
        ok, c, _ = M.sizing_constraints(M.case_input(vals), p, k)
        assert ok, c
        nomes.append(nome)
        conss.append(c)
        params.append(p)
    ok_p, p_env = M.envelope_params(params)
    assert ok_p, p_env
    return nomes, conss, p_env


# ------------------------------------------------------------------ o default é o Julia
def test_sem_o_parametro_todo_caso_dimensiona():
    _, conss, p_env = restricoes(casos())
    assert p_env["rating_fora_do_projeto"] == 0.0
    marcadas = M.envelope_constraints(conss, p_env)
    assert all(not c.rating_apenas and not c.dimensionantes for c in marcadas)
    assert [M.requirement(50, c) for c in marcadas] == [M.requirement(50, c) for c in conss]


def test_envelope_do_julia_nao_muda_com_o_parametro_em_zero():
    r0 = size_envelope(EQ, M, casos())
    r1 = size_envelope(EQ, M, casos(rating_fora_do_projeto=0.0))
    assert (r0.feasible, r0.x, r0.y) == (r1.feasible, r1.x, r1.y)
    assert r0.derivados_v2 == r1.derivados_v2 == {}


# ------------------------------------------------------------------ com o rating fora do projeto
def test_so_o_caso_de_projeto_exige_comprimento():
    _, conss, p_env = restricoes(casos(rating_fora_do_projeto=1.0), rating_fora_do_projeto=1.0)
    marcadas = M.envelope_constraints(conss, p_env)
    projeto = M.caso_projeto(conss)
    assert sum(not c.rating_apenas for c in marcadas) == 1
    assert not marcadas[projeto].rating_apenas
    for i, c in enumerate(marcadas):
        if i == projeto:
            assert M.requirement(50, c) == M.requirement(50, conss[i])
        else:
            assert M.requirement(50, c) == 0.0           # não exige
            assert c.dimensionantes == (conss[projeto],)  # mas sabe onde opera


def test_caso_classificado_opera_no_comprimento_do_caso_de_projeto():
    _, conss, p_env = restricoes(casos(rating_fora_do_projeto=1.0), rating_fora_do_projeto=1.0)
    marcadas = M.envelope_constraints(conss, p_env)
    projeto = M.caso_projeto(conss)
    l_projeto = comprimento_do_caso(marcadas[projeto], 50)
    assert all(comprimento_do_caso(c, 50) == l_projeto for c in marcadas)
    assert M.comprimento_instalado(marcadas, 50) == l_projeto


def test_requirement_zero_nao_governa_o_envelope():
    """Exigência nula não pode ser confundida com exigência atendida: o caso classificado
    simplesmente não entra no máximo, e o caso de projeto é o governante."""
    cs = casos(rating_fora_do_projeto=1.0)
    r = size_envelope(EQ, M, cs)
    assert r.feasible
    _, conss, p_env = restricoes(cs, rating_fora_do_projeto=1.0)
    assert r.driver_case == r.case_names[M.caso_projeto(conss)]
    assert r.derivados_v2["rating_fora_do_projeto"] == 1.0


def test_rating_fecha_energia_e_respeita_o_alvo():
    """Em cada caso: ṁ·cp·ΔT dos dois lados = Q realizado, e Q realizado ≤ alvo do Pinch."""
    cs = casos(rating_fora_do_projeto=1.0)
    r = size_envelope(EQ, M, cs)
    _, conss, p_env = restricoes(cs, rating_fora_do_projeto=1.0)
    marcadas = M.envelope_constraints(conss, p_env)
    l = M.comprimento_instalado(marcadas, r.x)
    for c in marcadas:
        rat = rating_do_caso(c, r.x, l)
        assert rat["avaliavel"]
        q = rat["q_realizado"] / c.n_paralelo
        assert q <= c.q * (1 + 1e-9)
        e = c.duty
        assert e.m_tubo * e.cp_tubo * abs(rat["t_tubo_out"] - e.t_tubo_in) == pytest.approx(q, rel=1e-6)
        assert e.m_casco * e.cp_casco * abs(rat["t_casco_out"] - e.t_casco_in) == pytest.approx(q, rel=1e-6)


def test_o_caso_de_projeto_realiza_o_alvo_inteiro():
    """A geometria é dimensionada POR ELE: o rating no caso de projeto não pode ficar abaixo do
    alvo — se ficar, o dimensionamento e a classificação não são a mesma física."""
    cs = casos(rating_fora_do_projeto=1.0)
    r = size_envelope(EQ, M, cs)
    _, conss, p_env = restricoes(cs, rating_fora_do_projeto=1.0)
    marcadas = M.envelope_constraints(conss, p_env)
    projeto = M.caso_projeto(conss)
    rat = rating_do_caso(marcadas[projeto], r.x, M.comprimento_instalado(marcadas, r.x))
    assert rat["fracao_realizada"] == pytest.approx(1.0, rel=1e-6)
    assert rat["estado"] == "limitado_pelo_alvo"


def test_recuperacao_nao_realizada_e_a_diferenca_declarada():
    cs = casos(rating_fora_do_projeto=1.0)
    r = size_envelope(EQ, M, cs)
    v2 = r.derivados_v2
    alvos, reais = v2["q_alvo_por_caso"], v2["q_realizado_por_caso"]
    naos = v2["q_nao_recuperado_por_caso"]
    assert all(a - b == pytest.approx(n) for a, b, n in zip(alvos, reais, naos))
    assert sum(alvos) == pytest.approx(v2["q_alvo_total"])
    assert sum(reais) == pytest.approx(v2["q_realizado_total"])
    assert all(b <= a * (1 + 1e-9) for a, b in zip(alvos, reais))


def test_area_instalada_nao_depende_de_como_o_caminho_e_dividido():
    """Dois cascos em série de metade do comprimento são a MESMA área e o MESMO caminho de
    tubo: é isso que permite a busca de layout separar térmica de empacotamento."""
    um = size_envelope(EQ, M, casos(rating_fora_do_projeto=1.0, cascos_serie=1.0, l_tubo_max=30.0))
    dois = size_envelope(EQ, M, casos(rating_fora_do_projeto=1.0, cascos_serie=2.0, l_tubo_max=30.0))
    assert um.feasible and dois.feasible and um.x == dois.x
    assert dois.y == pytest.approx(um.y / 2)
    assert dois.derivados_v2["area_total"] == pytest.approx(um.derivados_v2["area_total"])
    assert dois.derivados["dp"] == pytest.approx(um.derivados["dp"])


# ------------------------------------------------------------------ perda de carga
def test_perda_de_carga_cresce_com_o_caminho_e_e_reportada_sem_limite():
    _, conss, p_env = restricoes(casos())
    c = conss[0]
    assert c.dp_max_pa == 0.0           # sem limite declarado: só reportada
    dp1, f1, regime, confiavel = perda_carga_tubo(c, 50, 3.0)
    dp2, f2, _, _ = perda_carga_tubo(c, 50, 6.0)
    assert dp2 == pytest.approx(2 * dp1) and f1 == f2
    assert math.isfinite(dp1) and dp1 > 0 and regime in ("laminar", "turbulento", "transicao")
    r = size_envelope(EQ, M, casos())
    assert math.isfinite(r.derivados["dp"]) and r.derivados["dp_max"] == 0.0
    assert "ΔP no lado tubo (tubo reto)" not in [f.label for f in M.result_fields(r)]


def test_limite_de_perda_de_carga_reprova_feixe_e_entra_no_cartao():
    folgado = size_envelope(EQ, M, casos())
    apertado = size_envelope(EQ, M, casos(dp_max=folgado.derivados["dp"] / 2))
    assert folgado.feasible
    if apertado.feasible:
        assert apertado.derivados["dp"] <= folgado.derivados["dp"] / 2
        assert "ΔP no lado tubo (tubo reto)" in [f.label for f in M.result_fields(apertado)]
    else:
        assert "perda de carga" in apertado.message


def test_limite_de_perda_de_carga_cobra_todos_os_casos_no_modo_rating():
    """No modo rating o caso classificado opera no comprimento do projeto, e o atrito dele é
    cobrado ALI — o f sobe quando o Reynolds cai, então um caso de turndown pode passar do
    limite com o caso de projeto dentro dele."""
    cs = casos(rating_fora_do_projeto=1.0)
    r = size_envelope(EQ, M, cs)
    _, conss, p_env = restricoes(cs, rating_fora_do_projeto=1.0)
    marcadas = M.envelope_constraints(conss, p_env)
    l = M.comprimento_instalado(marcadas, r.x)
    dps = [perda_carga_tubo(c, r.x, l)[0] for c in marcadas]
    limite = min(dps) / 2
    com_limite = size_envelope(EQ, M, casos(rating_fora_do_projeto=1.0, dp_max=limite / 1000))
    if com_limite.feasible:
        _, c2, p2 = restricoes(casos(rating_fora_do_projeto=1.0, dp_max=limite / 1000),
                               rating_fora_do_projeto=1.0, dp_max=limite / 1000)
        m2 = M.envelope_constraints(c2, p2)
        l2 = M.comprimento_instalado(m2, com_limite.x)
        assert all(perda_carga_tubo(c, com_limite.x, l2)[0] <= limite * (1 + 1e-9) for c in m2)
    else:
        assert com_limite.message


def test_perda_de_carga_entra_no_diagnostico_por_caso():
    cs = casos(rating_fora_do_projeto=1.0, dp_max=1e-6)
    _, conss, p_env = restricoes(cs, rating_fora_do_projeto=1.0, dp_max=1e-6)
    marcadas = M.envelope_constraints(conss, p_env)
    pcs = M.envelope_case_params(marcadas, p_env)
    criterios = {crit for crit, _ in M.bloqueios(50, marcadas, pcs, p_env)}
    assert "perda_carga" in criterios


# ------------------------------------------------------------------ paridade preservada
def test_as_chaves_novas_de_derived_estao_declaradas_como_extensao():
    r = size_envelope(EQ, M, casos())
    julia = set(r.derivados) - set(M.derivados_extensao)
    assert set(M.derivados_extensao) <= set(r.derivados)
    assert "dp" not in julia and "u" in julia
