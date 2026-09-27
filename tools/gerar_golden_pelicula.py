"""Caso-ouro INDEPENDENTE da película do lado tubo nos três regimes.

Gera `tests/fixtures/python_ref/golden_pelicula_tubo.json`. Este script **não importa nada de
`fpso_siz.sizing`**: as equações estão escritas aqui, literalmente da fonte, com os coeficientes
digitados da página — é essa independência que faz dele oráculo, e não espelho do código testado.

Fonte: Branan, *Rules of Thumb for Chemical Engineers*, cap. 2, pp. 40-41.

    Gz   = N_Re·N_Pr·(d_i/L)
    2-10 h_i = (k/d_i)·[3,66 + 0,0668·Gz/(1 + C·Gz^(2/3))]·(µ/µ_w)^0,14      (Re ≤ 2000)
    2-12 h_T = h_lam + (h_turb − h_lam)·(N_Re − 2000)/8000                   (2000 < Re < 10⁴)
    6.23 h_i = (k/d_i)·a·Re^0,8·Pr^b·(µ/µ_w)^0,14                            (Re ≥ 10⁴, Saari)
    2-9  T_w = t + (U_i/h_i)·(T − t),  U_i = U_o·d_o/d_i

O coeficiente C do denominador da 2-10 é a errata arbitrada: a página imprime 0,40 e a forma
clássica tem 0,04. O arquivo traz os DOIS, e a arbitragem contra a segunda fonte do acervo
(Saari eq. 6.31, Sieder-Tate laminar 1,86·Gz^(1/3), via Incropera 2002 p. 490) também sai aqui.

    uv run python tools/gerar_golden_pelicula.py [--saida <json>]
"""
import argparse
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# coeficientes DIGITADOS da fonte (não lidos do TOML do programa, de propósito)
NU_DESENVOLVIDO = 3.66
COEF_ENTRADA = 0.0668
EXPOENTE_DENOM = 2 / 3
COEF_DENOM_ADOTADO = 0.04
COEF_DENOM_IMPRESSO = 0.40
EXPOENTE_PAREDE = 0.14
RE_LAMINAR_MAX = 2000.0
RE_TURBULENTO_MIN = 10000.0
DIVISOR_TRANSICAO = 8000.0
# Dittus-Boelter na forma de Saari (eq. 6.23), como o programa já usa no turbulento validado
DB_AQUECENDO = (0.024, 0.4)
DB_RESFRIANDO = (0.026, 0.3)
# Sieder-Tate laminar de Saari (eq. 6.31): a segunda via, só para a arbitragem
ST_COEF, ST_EXPOENTE = 1.86, 1 / 3


def gz(re, pr, d_i, l):
    return re * pr * d_i / l


def nu_hausen(re, pr, d_i, l, coef=COEF_DENOM_ADOTADO):
    g = gz(re, pr, d_i, l)
    return NU_DESENVOLVIDO + COEF_ENTRADA * g / (1 + coef * g ** EXPOENTE_DENOM)


def nu_dittus_boelter(re, pr, aquecendo):
    a, b = DB_AQUECENDO if aquecendo else DB_RESFRIANDO
    return a * re ** 0.8 * pr ** b


def nu_sieder_tate_laminar(re, pr, d_i, l):
    return ST_COEF * gz(re, pr, d_i, l) ** ST_EXPOENTE


def filme(re, pr, k, d_i, l, aquecendo, razao_visc=1.0, coef=COEF_DENOM_ADOTADO):
    """(h, Nu, regime, peso) pelas três equações, na fronteira que a fonte declara."""
    fator = razao_visc ** EXPOENTE_PAREDE
    if re <= RE_LAMINAR_MAX:
        nu, regime, peso = nu_hausen(re, pr, d_i, l, coef), "laminar", None
    elif re >= RE_TURBULENTO_MIN:
        nu, regime, peso = nu_dittus_boelter(re, pr, aquecendo), "turbulento", None
    else:
        nu_l = nu_hausen(re, pr, d_i, l, coef)
        nu_t = nu_dittus_boelter(re, pr, aquecendo)
        peso = (re - RE_LAMINAR_MAX) / DIVISOR_TRANSICAO
        nu, regime = nu_l + (nu_t - nu_l) * peso, "transicao"
    return nu * fator * k / d_i, nu * fator, regime, peso


def t_parede(t_tubo, t_casco, u_externo, h_i, d_i, d_o):
    return t_tubo + (u_externo * d_o / d_i) / h_i * (t_casco - t_tubo)


# Pontos do caso-ouro. Os dois primeiros são as condições REAIS dos casos que mantinham os
# alarmes abertos (lidas do diagnóstico do programa, e aqui usadas como entrada); os demais
# fixam as fronteiras e um ponto turbulento de controle.
PONTOS = [
    dict(nome="agua de resfriamento, laminar (ordem do P-003 BOT 06)",
         re=404.0, pr=5.12, k=0.615, d_i=0.02159, l=6.0, aquecendo=True),
    dict(nome="agua quente, transicao (ordem do P-002 BOT 06)",
         re=4220.0, pr=1.71, k=0.673, d_i=0.01509, l=10.58, aquecendo=False),
    dict(nome="oleo, laminar profundo (ordem do P-001 BOT 06)",
         re=266.0, pr=96.68, k=0.13, d_i=0.02159, l=42.05, aquecendo=True),
    dict(nome="fronteira laminar/transicao (Re = 2000, pela esquerda)",
         re=2000.0, pr=5.0, k=0.6, d_i=0.02, l=6.0, aquecendo=True),
    dict(nome="fronteira transicao/turbulento (Re = 10000)",
         re=10000.0, pr=5.0, k=0.6, d_i=0.02, l=6.0, aquecendo=True),
    dict(nome="turbulento de controle (Re = 50000)",
         re=50000.0, pr=5.0, k=0.6, d_i=0.02, l=6.0, aquecendo=True),
    dict(nome="laminar com fator de parede (razao 2,0)",
         re=1500.0, pr=50.0, k=0.13, d_i=0.02, l=6.0, aquecendo=True, razao_visc=2.0),
]


def gerar():
    pontos = []
    for p in PONTOS:
        razao = p.get("razao_visc", 1.0)
        h, nu, regime, peso = filme(p["re"], p["pr"], p["k"], p["d_i"], p["l"], p["aquecendo"], razao)
        h_impresso, _, _, _ = filme(p["re"], p["pr"], p["k"], p["d_i"], p["l"], p["aquecendo"], razao,
                                    COEF_DENOM_IMPRESSO)
        pontos.append(dict(
            **{k: v for k, v in p.items() if k != "razao_visc"},
            razao_visc=razao,
            gz=gz(p["re"], p["pr"], p["d_i"], p["l"]),
            fator_parede=razao ** EXPOENTE_PAREDE,
            nu=nu, h=h, regime=regime, peso_transicao=peso,
            h_com_coeficiente_impresso=h_impresso,
            nu_hausen=nu_hausen(p["re"], p["pr"], p["d_i"], p["l"]),
            nu_dittus_boelter=nu_dittus_boelter(p["re"], p["pr"], p["aquecendo"]),
            nu_sieder_tate_laminar=nu_sieder_tate_laminar(p["re"], p["pr"], p["d_i"], p["l"])))
    # arbitragem do denominador: assíntota do termo de entrada × a segunda fonte
    arbitragem = dict(
        assintota_adotada=COEF_ENTRADA / COEF_DENOM_ADOTADO,
        assintota_impressa=COEF_ENTRADA / COEF_DENOM_IMPRESSO,
        sieder_tate=ST_COEF,
        razao_adotada=ST_COEF / (COEF_ENTRADA / COEF_DENOM_ADOTADO),
        razao_impressa=ST_COEF / (COEF_ENTRADA / COEF_DENOM_IMPRESSO),
        pontos=[dict(gz=g, hausen_adotado=NU_DESENVOLVIDO + COEF_ENTRADA * g / (1 + COEF_DENOM_ADOTADO * g ** EXPOENTE_DENOM),
                     hausen_impresso=NU_DESENVOLVIDO + COEF_ENTRADA * g / (1 + COEF_DENOM_IMPRESSO * g ** EXPOENTE_DENOM),
                     sieder_tate=ST_COEF * g ** ST_EXPOENTE) for g in (1.0, 10.0, 100.0, 1e3, 1e4, 1e5, 1e6)])
    # conta à mão de um ponto, passo a passo, para a conferência humana
    p = PONTOS[0]
    g = gz(p["re"], p["pr"], p["d_i"], p["l"])
    denom = 1 + COEF_DENOM_ADOTADO * g ** EXPOENTE_DENOM
    termo = COEF_ENTRADA * g / denom
    nu = NU_DESENVOLVIDO + termo
    mao = dict(ponto=p["nome"], gz=g, gz_elevado=g ** EXPOENTE_DENOM, denominador=denom, termo_entrada=termo,
               nu=nu, h=nu * p["k"] / p["d_i"])
    # temperatura de parede (eq. 2-9) num ponto com U e h plausíveis
    parede = dict(t_tubo=32.5, t_casco=60.0, u_externo=210.7, h_i=943.5, d_i=0.02159, d_o=0.0254)
    parede["t_parede"] = t_parede(**parede)
    return dict(fonte="Branan (2012), cap. 2, pp. 40-41, eq. 2-9/2-10/2-12; turbulento por Saari eq. 6.23; "
                      "arbitragem do denominador contra Saari eq. 6.31 (Incropera 2002, p. 490)",
                coeficientes=dict(nu_desenvolvido=NU_DESENVOLVIDO, coef_entrada=COEF_ENTRADA,
                                  expoente_denominador=EXPOENTE_DENOM, coef_denominador=COEF_DENOM_ADOTADO,
                                  coef_denominador_impresso=COEF_DENOM_IMPRESSO, expoente_parede=EXPOENTE_PAREDE,
                                  re_laminar_max=RE_LAMINAR_MAX, re_turbulento_min=RE_TURBULENTO_MIN,
                                  divisor_transicao=DIVISOR_TRANSICAO),
                pontos=pontos, arbitragem=arbitragem, conta_a_mao=mao, temperatura_parede=parede)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path,
                    default=RAIZ / "tests" / "fixtures" / "python_ref" / "golden_pelicula_tubo.json")
    a = ap.parse_args()
    a.saida.write_text(json.dumps(gerar(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
