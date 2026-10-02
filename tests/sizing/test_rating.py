import math
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from fpso_siz.sizing import rating as rating_mod
from fpso_siz.sizing.rating import CasoRating, integrar, rating
from fpso_siz.core.parametros import with_defaults
from fpso_siz.core.unidades import cp_para_pas
from fpso_siz.sizing import SaariLMTD
from fpso_siz.sizing.trocador import (AvaliadorGeometriaFixa, GeometriaRating,
                                      PropriedadesRating, propriedades_declaradas)
from fpso_siz.termo import servico as termo


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


def test_geometria_fixa_reconsulta_propriedades_e_nao_congela_u(monkeypatch):
    """Uma curva forte de µ(T) torna observável tanto U(Q) quanto o erro do U congelado."""
    chamadas = []

    def agua_dependente(t, _rastro=None):
        chamadas.append(t)
        return SimpleNamespace(rho=1000.0, mu=4.0 * math.exp(-(t - 20.0) / 20.0),
                               cp=4180.0, k=0.6, avisos=())

    monkeypatch.setattr(termo, "agua_saturada", agua_dependente)

    def agua_saturada_rating(t, rastro=None):
        p_agua = termo.agua_saturada(t, rastro)
        return PropriedadesRating(p_agua.rho, cp_para_pas(p_agua.mu), p_agua.cp,
                                  p_agua.k, p_agua.avisos)
    arquivo = Path(__file__).parents[1] / "fixtures/julia/casos/exemplo_trocador.toml"
    valores = tomllib.loads(arquivo.read_text())["case"][0]
    metodo = SaariLMTD()
    p = with_defaults(metodo.parameters(), {**valores, "passes_tubo": 1.0,
                                            "pelicula_baixo_re": 1.0})
    entrada = metodo.case_input(valores)
    area = 50 * math.pi * 0.01905 * 5.0
    geometria = GeometriaRating(50, 5.0, area)
    avaliador = AvaliadorGeometriaFixa(metodo, geometria, entrada, p, metodo.constants(),
                                       agua_saturada_rating, agua_saturada_rating)
    caso = CasoRating(entrada.t_tubo_in, entrada.t_casco_in,
                      entrada.m_tubo * entrada.cp_tubo,
                      entrada.m_casco * entrada.cp_casco, 2.0e6)
    variavel = rating(caso, avaliador)

    # Rating de referência deliberadamente antigo: propriedades fixadas na condição inicial.
    pt = agua_saturada_rating(entrada.t_tubo_in)
    congelado = AvaliadorGeometriaFixa(metodo, geometria, entrada, p, metodo.constants(),
                                       propriedades_declaradas(pt.rho, pt.mu, pt.cp, pt.k),
                                       propriedades_declaradas(pt.rho, pt.mu, pt.cp, pt.k))
    fixo = rating(caso, congelado)

    assert len(chamadas) > 2 and len({round(t, 6) for t in chamadas}) > 2
    assert max(avaliador.historico_u) - min(avaliador.historico_u) > 1.0
    assert variavel.q_real != pytest.approx(fixo.q_real, rel=1e-4)
    assert variavel.diagnostico["resistencias"]
    assert math.isfinite(variavel.diagnostico["perda_carga_tubo"])
    assert math.isfinite(variavel.diagnostico["perda_carga_casco"])
