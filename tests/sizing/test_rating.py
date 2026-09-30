import math

import pytest

from fpso_siz.sizing.rating import CasoRating, integrar, rating


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

