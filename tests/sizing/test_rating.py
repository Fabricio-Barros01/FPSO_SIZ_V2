import math

import pytest
import tomllib
from pathlib import Path

from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.parametros import with_defaults
from fpso_siz.sizing.rating import CasoRating, integrar, rating
from fpso_siz.sizing.rating import rating_saari
from fpso_siz.sizing.trocador import GeometriaTrocador, SaariLMTD


CASO = CasoRating(20.0, 100.0, 10.0, 20.0, 500.0)


def constante(ua):
    return lambda q, tc, th: ua


def test_area_zero_implica_carga_zero():
    r = rating(CASO, constante(0.0))
    assert r.q_real == pytest.approx(0.0, abs=1e-6)


def test_ua_infinito_tende_ao_alvo_e_nao_ultrapassa():
    r = rating(CASO, constante(1e12))
    assert r.q_real == CASO.q_rec_max
    assert r.q_rating <= r.q_rec_max


def test_area_nao_reduz_rating_e_fecha_energia():
    cargas = [rating(CASO, constante(ua)).q_real for ua in (1.0, 10.0, 100.0)]
    assert cargas == sorted(cargas)
    r = rating(CASO, constante(10.0))
    assert CASO.c_fria * (r.t_fria_out - CASO.t_fria_in) == pytest.approx(r.q_real)
    assert CASO.c_quente * (CASO.t_quente_in - r.t_quente_out) == pytest.approx(r.q_real)
    assert r.t_fria_out < CASO.t_quente_in
    assert r.t_quente_out > CASO.t_fria_in
    assert r.convergiu and math.isfinite(r.dt_lm)


def test_utilidades_absorvem_recuperacao_nao_realizada():
    r = rating(CASO, constante(1.0))
    b = integrar(CASO, r, 80.0, 40.0)
    assert b.q_p002 == pytest.approx(CASO.c_fria * (80.0 - r.t_fria_out))
    assert b.q_p003 == pytest.approx(CASO.c_quente * (r.t_quente_out - 40.0))


def test_rating_saari_congela_geometria_e_recalcula_ua():
    caminho = Path(__file__).resolve().parents[1] / "fixtures" / "julia" / "casos" / "exemplo_trocador.toml"
    _, valores = case_set_from_config(tomllib.loads(caminho.read_text(encoding="utf-8"))).expand()[0]
    metodo = SaariLMTD()
    entrada = metodo.case_input(valores)
    parametros = with_defaults(metodo.parameters(), {**valores, "passes_tubo": 1.0,
                                                       "pelicula_baixo_re": 1.0})
    geometria = GeometriaTrocador(1000, 6.0)
    q_alvo = entrada.m_tubo * entrada.cp_tubo * (entrada.t_tubo_out - entrada.t_tubo_in)
    r = rating_saari(metodo, entrada, parametros, geometria, q_alvo)
    assert r.convergiu and 0 < r.q_real <= q_alvo
    assert r.ua > 0 and r.t_fria_out < entrada.t_casco_in
