import math

import pytest

from fpso_siz.sizing import rating as rating_mod
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


@pytest.mark.parametrize("campo", CasoRating.__dataclass_fields__)
def test_nan_em_qualquer_entrada_torna_caso_nao_avaliavel(campo):
    valores = {nome: getattr(CASO, nome) for nome in CasoRating.__dataclass_fields__}
    valores[campo] = math.nan
    r = rating(CasoRating(**valores), constante(10.0))
    assert r.estado == "nao_avaliavel"
    assert not r.avaliavel and not r.convergiu
    assert math.isnan(r.q_real)
    assert "não finita" in r.mensagem


@pytest.mark.parametrize("callback", ("ua", "fator"))
def test_nan_retornado_por_callback_nao_vira_transferencia_zero(callback):
    funcoes = {"ua": constante(10.0), "fator": constante(1.0)}
    funcoes[callback] = constante(math.nan)
    r = rating(CASO, funcoes["ua"], funcoes["fator"])
    assert r.estado == "nao_avaliavel" and math.isnan(r.q_real)
    assert callback.upper() in r.mensagem.upper()


def test_lmtd_invalido_torna_caso_nao_avaliavel():
    caso = CasoRating(100.0, 100.0, 10.0, 20.0, 1.0)
    r = rating(caso, constante(10.0))
    assert r.estado == "nao_avaliavel"
    assert "LMTD" in r.mensagem


def test_sem_carga_tem_estado_e_diagnostico():
    r = rating(CasoRating(20.0, 100.0, 10.0, 20.0, 0.0), constante(10.0))
    assert r.estado == "sem_carga" and r.convergiu
    assert "sem carga" in r.mensagem


def test_convergencia_exatamente_na_ultima_iteracao(monkeypatch):
    monkeypatch.setattr(rating_mod, "carregar", lambda _: {
        "rating": {"tolerancia_relativa": 1e-9, "max_iteracoes": 1,
                   "margem_temperatura_K": 1e-9}})
    # No primeiro (e último) ponto médio, escolhe-se UA para o resíduo ser zero.
    dt_meio = rating_mod.lmtd(55.0, 67.5)
    r = rating(CASO, constante(250.0 / dt_meio))
    assert r.iteracoes == 1 and r.estado == "convergido" and r.convergiu


def test_esgotamento_real_das_iteracoes(monkeypatch):
    monkeypatch.setattr(rating_mod, "carregar", lambda _: {
        "rating": {"tolerancia_relativa": 1e-16, "max_iteracoes": 1,
                   "margem_temperatura_K": 1e-9}})
    r = rating(CASO, constante(1.0))
    assert r.iteracoes == 1 and r.estado == "nao_convergido" and not r.convergiu
    assert "1 iterações" in r.mensagem
