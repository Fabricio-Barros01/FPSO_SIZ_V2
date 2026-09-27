"""Caso-ouro e validação da película do lado tubo nos três regimes (`sizing/pelicula.py`).

O oráculo é `tests/fixtures/python_ref/golden_pelicula_tubo.json`, gerado por
`tools/gerar_golden_pelicula.py` — um script **independente**, que digita as equações e os
coeficientes da própria página do Branan e não importa nada de `fpso_siz.sizing`. Por isso ele é
caso-ouro e não espelho: se o módulo e o script discordarem, um dos dois está errado, e o valor
publicado na fonte decide.

Cobre, na ordem do aceite: caso-ouro ponto a ponto, conta à mão, verificação dimensional, limites
de validade, comportamento nos três regimes, continuidade nas fronteiras, regressão do
turbulento, verificação cruzada com a segunda referência do acervo e a errata arbitrada.
"""
import json
import math
from pathlib import Path

import pytest

from fpso_siz.sizing import pelicula as pel
from fpso_siz.sizing.trocador import SaariLMTD, nusselt_dittus_boelter

OURO = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "python_ref"
                   / "golden_pelicula_tubo.json").read_text(encoding="utf-8"))
K = SaariLMTD().constants()
RTOL = 1e-12


def filme(p):
    return pel.filme_tubo(p["re"], p["pr"], p["k"], p["d_i"], p["l"], p["aquecendo"], K,
                          razao_visc=p.get("razao_visc", 1.0))


@pytest.mark.parametrize("p", OURO["pontos"], ids=lambda p: p["nome"])
def test_caso_ouro_ponto_a_ponto(p):
    """h, Nu, regime e peso da interpolação iguais aos do script independente."""
    f = filme(p)
    assert f.regime == p["regime"] and f.valido, f.motivo
    assert f.h == pytest.approx(p["h"], rel=RTOL)
    assert f.nu == pytest.approx(p["nu"], rel=RTOL)
    assert f.fator_parede == pytest.approx(p["fator_parede"], rel=RTOL)
    if p["peso_transicao"] is None:
        assert math.isnan(f.peso)
    else:
        assert f.peso == pytest.approx(p["peso_transicao"], rel=RTOL)


def test_conta_a_mao_do_primeiro_ponto():
    """A conta passo a passo do oráculo, refeita com as mesmas parcelas: Gz, o denominador, o
    termo de entrada, Nu e h. É a linha que uma pessoa confere contra a p. 40 com uma calculadora."""
    m = OURO["conta_a_mao"]
    p = next(x for x in OURO["pontos"] if x["nome"] == m["ponto"])
    kf = pel.cfg()
    gz = pel.graetz(p["re"], p["pr"], p["d_i"], p["l"])
    assert gz == pytest.approx(m["gz"], rel=RTOL)
    coef = float(kf["hausen"]["coef_denominador"])
    denom = 1 + coef * gz ** float(kf["hausen"]["expoente_denominador"])
    assert denom == pytest.approx(m["denominador"], rel=RTOL)
    termo = float(kf["hausen"]["coef_entrada"]) * gz / denom
    assert termo == pytest.approx(m["termo_entrada"], rel=RTOL)
    nu = float(kf["hausen"]["nu_desenvolvido"]) + termo
    assert nu == pytest.approx(m["nu"], rel=RTOL)
    assert nu * p["k"] / p["d_i"] == pytest.approx(m["h"], rel=RTOL)
    assert pel.nusselt_hausen(p["re"], p["pr"], p["d_i"], p["l"]) == pytest.approx(nu, rel=RTOL)


def test_verificacao_dimensional():
    """Nu é adimensional e h = Nu·k/d_i. Duas consequências que um erro de dimensão quebraria:
    escalar d_i e L pelo MESMO fator preserva Gz e Nu (e h cai com 1/d_i), e h é proporcional a k."""
    base = dict(re=800.0, pr=30.0, k=0.13, d_i=0.02, l=6.0, aquecendo=True)
    f = pel.filme_tubo(base["re"], base["pr"], base["k"], base["d_i"], base["l"], True, K)
    assert f.h * base["d_i"] / base["k"] == pytest.approx(f.nu, rel=RTOL)
    f2 = pel.filme_tubo(base["re"], base["pr"], base["k"], 2 * base["d_i"], 2 * base["l"], True, K)
    assert f2.nu == pytest.approx(f.nu, rel=RTOL)            # Gz inalterado
    assert f2.h == pytest.approx(f.h / 2, rel=RTOL)           # h ∝ 1/d_i
    f3 = pel.filme_tubo(base["re"], base["pr"], 2 * base["k"], base["d_i"], base["l"], True, K)
    assert f3.h == pytest.approx(2 * f.h, rel=RTOL)           # h ∝ k


def test_limites_de_validade_de_cada_correlacao():
    """O que a fonte não cobre continua não coberto, e o motivo distingue as recusas."""
    re_max = float(K["dittus_boelter_re_max"])
    pr_max = float(K["dittus_boelter_pr_max"])
    # Reynolds acima do teto de Dittus-Boelter: recusa por Reynolds
    f = pel.filme_tubo(2 * re_max, 5.0, 0.6, 0.02, 6.0, True, K)
    assert not f.valido and "acima do teto" in f.motivo and f.regime == pel.TURBULENTO
    # Prandtl fora da faixa, no turbulento: recusa por Prandtl, e a mensagem diz que baixo
    # Reynolds não resolve
    f = pel.filme_tubo(5e4, 2 * pr_max, 0.13, 0.02, 6.0, True, K)
    assert not f.valido and "Prandtl" in f.motivo and "baixo Reynolds" in f.motivo
    # Prandtl fora da faixa, na transição: a ponta turbulenta da interpolação não é válida
    f = pel.filme_tubo(5000.0, 2 * pr_max, 0.13, 0.02, 6.0, True, K)
    assert not f.valido and f.regime == pel.TRANSICAO and "interpolação" in f.motivo
    # No LAMINAR a fonte não declara faixa de Prandtl: Pr alto é calculável, e isso está no TOML
    assert pel.cfg()["hausen"]["faixa_prandtl_declarada"] is False
    f = pel.filme_tubo(500.0, 2 * pr_max, 0.13, 0.02, 6.0, True, K)
    assert f.valido and f.regime == pel.LAMINAR
    # entrada sem sentido físico não vira número
    for re, pr in ((0.0, 5.0), (-10.0, 5.0), (500.0, 0.0), (math.nan, 5.0)):
        assert not pel.filme_tubo(re, pr, 0.6, 0.02, 6.0, True, K).valido


def test_comportamento_nos_tres_regimes():
    """Regime pelo Reynolds, h crescente com Re em cada ramo, e o piso laminar da fonte."""
    arg = dict(pr=5.0, k=0.6, d_i=0.02, l=6.0, aquecendo=True)
    regimes = [pel.filme_tubo(re, arg["pr"], arg["k"], arg["d_i"], arg["l"], True, K).regime
               for re in (10.0, 1999.0, 2001.0, 9999.0, 10001.0, 1e5)]
    assert regimes == [pel.LAMINAR, pel.LAMINAR, pel.TRANSICAO, pel.TRANSICAO, pel.TURBULENTO, pel.TURBULENTO]
    for re_a, re_b in ((100.0, 1000.0), (2500.0, 9000.0), (2e4, 1e5)):
        a = pel.filme_tubo(re_a, arg["pr"], arg["k"], arg["d_i"], arg["l"], True, K)
        b = pel.filme_tubo(re_b, arg["pr"], arg["k"], arg["d_i"], arg["l"], True, K)
        assert b.h > a.h, (re_a, re_b)
    # tubo longo: Nu tende ao valor plenamente desenvolvido da fonte (3,66)
    longo = pel.nusselt_hausen(500.0, 5.0, 0.02, 1e9)
    assert longo == pytest.approx(float(pel.cfg()["hausen"]["nu_desenvolvido"]), rel=1e-6)
    # o peso da interpolação vai de 0 a 1 entre as fronteiras
    assert pel.filme_tubo(2000.0 + 1e-9, 5.0, 0.6, 0.02, 6.0, True, K).peso == pytest.approx(0.0, abs=1e-12)
    assert pel.filme_tubo(1e4 - 1e-9, 5.0, 0.6, 0.02, 6.0, True, K).peso == pytest.approx(1.0, abs=1e-12)


def test_continuidade_nas_duas_fronteiras():
    """A política de fronteira é declarada e verificável: a interpolação da eq. 2-12 usa as DUAS
    correlações no mesmo Reynolds, então encosta em Hausen a 2000 e em Dittus-Boelter a 10⁴. O
    salto relativo nas duas fronteiras é numérico, não físico."""
    arg = (5.0, 0.6, 0.02, 6.0, True, K)
    for re_fronteira in (2000.0, 1e4):
        eps = re_fronteira * 1e-9
        esq = pel.filme_tubo(re_fronteira - eps, *arg)
        dir_ = pel.filme_tubo(re_fronteira + eps, *arg)
        assert esq.regime != dir_.regime
        assert abs(dir_.h - esq.h) / esq.h < 1e-6, re_fronteira


def test_regressao_do_turbulento_e_o_ramo_ja_validado():
    """No turbulento a película é EXATAMENTE o Dittus-Boelter na forma de Saari que já estava
    validado contra o Julia e contra o caso-ouro de Saari — sem fator de parede por default."""
    for re in (1e4, 3e4, 1.2e5):
        for aquecendo in (True, False):
            f = pel.filme_tubo(re, 5.0, 0.6, 0.02, 6.0, aquecendo, K)
            nu, valida = nusselt_dittus_boelter(re, 5.0, aquecendo, K)
            assert valida and f.nu == nu and f.h == nu * 0.6 / 0.02


def test_errata_do_denominador_de_hausen():
    """A arbitragem que justifica adotar 0,04 onde a página imprime 0,40: a assíntota do termo de
    entrada tem de ficar perto da segunda fonte do acervo (Saari eq. 6.31, 1,86·Gz^(1/3), via
    Incropera), e com 0,40 ela fica uma ordem de grandeza abaixo."""
    a = OURO["arbitragem"]
    kf = pel.cfg()["hausen"]
    assert float(kf["coef_denominador"]) == 0.04 and float(kf["coef_denominador_impresso"]) == 0.40
    assert a["razao_adotada"] == pytest.approx(1.11, abs=0.01)
    assert a["razao_impressa"] == pytest.approx(11.14, abs=0.01)
    # e, ponto a ponto, o adotado acompanha a segunda fonte enquanto o impresso diverge
    for ponto in a["pontos"]:
        if ponto["gz"] >= 1e3:
            assert 0.8 < ponto["hausen_adotado"] / ponto["sieder_tate"] < 1.2
            assert ponto["hausen_impresso"] / ponto["sieder_tate"] < 0.5


def test_verificacao_cruzada_com_saari_sieder_tate_laminar():
    """Segunda referência do acervo, METODOLOGIA DIFERENTE: Saari eq. 6.31 é correlação de
    comprimento de entrada com temperatura de superfície constante; Hausen é a forma combinada que
    já soma o valor plenamente desenvolvido. Por isso elas coincidem no regime dominado pela
    entrada (Gz grande) e divergem quando Gz → 0, onde só Hausen tem o piso de 3,66: a 6.31 tende
    a zero, que é justamente o que ela não modela. A concordância não é oráculo — é confirmação de
    ordem de grandeza e de expoente."""
    for p in OURO["pontos"]:
        st, hausen = p["nu_sieder_tate_laminar"], p["nu_hausen"]
        gz = p["gz"]
        if gz >= 1e3:
            assert 0.8 < hausen / st < 1.2, p["nome"]
        if gz <= 1.0:
            assert hausen > st       # o piso de 3,66 é o que a 6.31 não tem
    # o expoente 1/3 da 6.31 é o mesmo da assíntota de Hausen: dobrar Gz multiplica as duas por 2^(1/3)
    a = pel.nusselt_sieder_tate_laminar(1000.0, 10.0, 0.02, 6.0)
    b = pel.nusselt_sieder_tate_laminar(2000.0, 10.0, 0.02, 6.0)
    assert b / a == pytest.approx(2 ** (1 / 3), rel=1e-12)


def test_temperatura_de_parede_da_eq_2_9():
    """A eq. 2-9 é calculada e sai para o rastro; ela não trava o cálculo quando falta operando."""
    d = OURO["temperatura_parede"]
    t = pel.temperatura_parede(d["t_tubo"], d["t_casco"], d["u_externo"], d["h_i"], d["d_i"], d["d_o"])
    assert t == pytest.approx(d["t_parede"], rel=RTOL)
    # a parede fica entre os dois fluidos, mais perto do de maior coeficiente
    assert d["t_tubo"] < t < d["t_casco"]
    assert math.isnan(pel.temperatura_parede(d["t_tubo"], d["t_casco"], math.nan, d["h_i"], d["d_i"], d["d_o"]))
    assert math.isnan(pel.temperatura_parede(math.nan, d["t_casco"], d["u_externo"], d["h_i"], d["d_i"], d["d_o"]))


def test_fator_de_parede_e_hipotese_declarada():
    """Razão 1,0 omite o fator, e isso é hipótese declarada com sentido de erro conhecido: ao
    aquecer líquido, µ_parede < µ_médio, a razão real é > 1 e o h calculado é conservador."""
    arg = (800.0, 30.0, 0.13, 0.02, 6.0, True, K)
    um = pel.filme_tubo(*arg)
    dois = pel.filme_tubo(*arg, razao_visc=2.0)
    assert um.fator_parede == 1.0
    assert dois.fator_parede == pytest.approx(2 ** float(pel.cfg()["parede"]["expoente"]), rel=RTOL)
    assert dois.h > um.h and dois.h / um.h == pytest.approx(dois.fator_parede, rel=RTOL)
    assert float(pel.cfg()["parede"]["razao_padrao"]) == 1.0
