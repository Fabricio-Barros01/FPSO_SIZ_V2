# Película do lado tubo nos três regimes — fechamento dos alarmes dos trocadores

Gerado por `tools/pelicula_baixo_re.py`; os números saem do motor e do caso-ouro.

## O que faltava, e o que não faltava

Até aqui o programa só tinha o regime **turbulento** no lado tubo (Dittus-Boelter na forma de Saari, eq. 6.23): fora de 10⁴ ≤ Re ≤ 1,2·10⁵ o caso era **recusado**. Era essa recusa — e não um limite físico — que mantinha abertos os alarmes do P-001, do P-002 e do P-003 em baixa carga. A fonte primária do acervo já traz o procedimento completo, com equações, variáveis, propriedades, unidades, hipóteses e domínio de cada correlação, e é isso que está implementado.

| Regime | Correlação | Domínio declarado pela fonte | Fonte |
|---|---|---|---|
| laminar | Hausen, Nu = 3,66 + 0.0668·Gz/(1 + 0.04·Gz^(2/3)) | Re ≤ 2.000; propriedades na temperatura média do fluido; sem faixa de Prandtl declarada | Branan, cap. 2, p. 40, eq. 2-10 |
| transição | interpolação linear entre as duas, h = h_lam + (h_turb − h_lam)·(Re − 2.000)/8.000 | 2.000 < Re < 10.000; a fonte a chama de "plausible equation" e recomenda EVITAR a região | Branan, cap. 2, p. 41, eq. 2-12 |
| turbulento | Dittus-Boelter na forma de Saari (o ramo já validado) | 10.000 ≤ Re ≤ 120.000 e 0.7 ≤ Pr ≤ 120.0 | Saari, eq. 6.23 |
| parede | fator (µ/µ_parede)^0.14, com a temperatura de parede da eq. 2-9 | razão declarada (padrão 1,0: fator omitido, conservador ao aquecer líquido) | Branan, eq. 2-9/2-10/2-11 |

A ponta turbulenta da interpolação de transição é a **própria eq. 6.23**, e não a eq. 2-11 do Branan: assim a interpolação encosta exatamente no ramo que já estava validado contra o Julia e contra o caso-ouro de Saari, em Re = 10⁴, e o comportamento turbulento não muda em nada (há teste de regressão). A continuidade nas duas fronteiras é verificada por teste, com salto relativo abaixo de 1e-6.

**O que continua não coberto continua recusado.** Prandtl fora da faixa declarada por Dittus-Boelter recusa o caso no turbulento e na transição (onde a ponta superior da interpolação é ela), e a mensagem diz que correlação de baixo Reynolds não resolve isso. No laminar a fonte não declara faixa de Prandtl, e o programa não inventa uma.

## A errata do denominador de Hausen, e como ela foi arbitrada

A página imprime `1 + 0,40·Gz^(2/3)` no denominador da eq. 2-10; a forma clássica de Hausen tem **0,04**. Um fator de dez no denominador não é detalhe, então a escolha foi arbitrada contra a segunda via do acervo — Saari eq. 6.31 (Sieder-Tate laminar, atribuída a Incropera 2002, p. 490), que é metodologia diferente: correlação de comprimento de entrada, sem o valor plenamente desenvolvido somado.

A assíntota do termo de entrada de Hausen quando Gz cresce é (0,0668/C)·Gz^(1/3):

| C | assíntota | Sieder-Tate (6.31) | razão |
|---|---|---|---|
| 0,04 (adotado) | 1,670·Gz^(1/3) | 1,860·Gz^(1/3) | 1,11× |
| 0,40 (impresso) | 0,167·Gz^(1/3) | 1,860·Gz^(1/3) | 11,14× |

Com 0,04 as duas fontes concordam em 11 %; com 0,40 a divergência é de mais de onze vezes. Adotou-se 0,04, e o valor impresso está registrado no TOML (`coef_denominador_impresso`) para quem conferir contra a página. Ponto a ponto:

| Gz | Hausen (0,04) | Hausen (0,40) | Sieder-Tate 6.31 |
|---|---|---|---|
| 1 | 3,72 | 3,71 | 1,86 |
| 10 | 4,22 | 3,89 | 4,01 |
| 100 | 7,25 | 4,35 | 8,63 |
| 1.000 | 17,02 | 5,29 | 18,60 |
| 10.000 | 37,80 | 7,24 | 40,07 |
| 100.000 | 80,29 | 11,40 | 86,33 |
| 1.000.000 | 170,24 | 20,36 | 186,00 |

**A segunda fonte tem errata própria, também registrada:** o texto de Saari define Gz = (x/d_h)·Re·Pr, que cresce com a distância e faria o Nusselt crescer ao longo do tubo; a forma consistente, e a usada aqui, é Gz = Re·Pr·(d/L). A verificação cruzada vale onde as duas descrevem a mesma coisa — o regime dominado pela entrada (Gz grande). Com Gz → 0 elas divergem por construção: só Hausen tem o piso de 3,66, e é justamente o que a 6.31 não modela.

## Caso-ouro independente

`tests/fixtures/python_ref/golden_pelicula_tubo.json`, gerado por `tools/gerar_golden_pelicula.py` — um script que **digita as equações e os coeficientes da página** e não importa nada de `fpso_siz.sizing`. Traz, para sete pontos (os três regimes, as duas fronteiras, um ponto de controle turbulento e um com fator de parede): entradas, Gz, fator de parede, Nusselt de cada correlação, h, regime e peso da interpolação; a conta passo a passo de um ponto, para conferência manual; e a temperatura de parede da eq. 2-9. `tests/sizing/test_golden_pelicula.py` cobre o caso-ouro ponto a ponto, a conta à mão, a verificação dimensional (Nu = h·d_i/k; escalar d_i e L preserva Nu e h cai com 1/d_i; h ∝ k), os limites de validade, o comportamento nos três regimes, a continuidade nas fronteiras, a regressão do turbulento, a arbitragem da errata e a verificação cruzada com a 6.31.

## Caso a caso, antes e depois

"Antes" é o programa com `pelicula_baixo_re = 0` (só Dittus-Boelter, a regra do Julia); "depois" é com os três regimes. Mesmas entradas, mesmos limites, mesma geometria recomendada.

### P-001 — recomendado (2 passes no tubo)

| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|
| antes (só Dittus-Boelter) | inviável | — | — | — | preparacao |
| depois (três regimes) | inviável | — | — | — | preparacao |

A operação por caso não está disponível neste arranjo: algum caso não chega ao lado tubo (o fator F do arranjo 1-2 sai do domínio antes disso).

### P-001 — 1 passe (contracorrente pura)

| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|
| antes (só Dittus-Boelter) | inviável | 668 | 81,34 | 3.251,8 | comprimento de tubo acima de l_tubo_max; fora da faixa de validade de Dittus-Boelter (BOT 01, BOT 02, BOT 03, BOT 04, BOT 05, BOT 06, BOT 07, BOT 08, BOT 09, BOT 11) |
| depois (três regimes) | inviável | 678 | 434,38 | 17.625,5 | comprimento de tubo acima de l_tubo_max |

| Caso | Papel | Carga (kW) | Pr | v (m/s) | Re | Regime | Correlação | h_i (W/m²K) | h_o (W/m²K) | U (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 9.119,1 | 75,93 | 2,867 | 7.637 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.092,2 | 2.442,9 | 410,2 | 54,35 |
| BOT 02 — Early Life | projeto | 16.532,4 | 86,53 | 2,940 | 7.063 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 974,1 | 2.452,0 | 387,7 | 98,33 |
| BOT 03 — Early Life Blend | turndown | 16.367,4 | 70,15 | 2,938 | 8.675 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.370,6 | 2.603,5 | 460,0 | 82,07 |
| BOT 04 — Early Life | turndown | 2.716,4 | 88,17 | 0,373 | 856 | laminar | Hausen (Branan eq. 2-10) | 34,4 | 705,5 | 25,2 | 260,11 |
| BOT 05 — Low CO2 | turndown | 4.533,0 | 82,01 | 0,487 | 1.198 | laminar | Hausen (Branan eq. 2-10) | 33,9 | 867,5 | 25,1 | 434,38 |
| BOT 06 — Mid Life | turndown | 1.170,0 | 96,68 | 0,126 | 262 | laminar | Hausen (Branan eq. 2-10) | 33,8 | 372,1 | 24,1 | 116,42 |
| BOT 07 — Mid Life | turndown | 3.229,0 | 75,93 | 2,869 | 7.635 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.102,2 | 2.442,9 | 412,0 | 19,26 |
| BOT 08 — Mid Life | turndown | 6.892,0 | 93,24 | 2,148 | 5.239 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 535,5 | 1.913,5 | 265,0 | 54,68 |
| BOT 09 — Mid Life | turndown | 3.937,4 | 106,34 | 1,808 | 4.100 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 331,1 | 1.651,4 | 187,3 | 43,83 |
| BOT 11 — Late Life | turndown | 3.454,6 | 173,79 | 1,222 | 1.989 | laminar | Hausen (Branan eq. 2-10) | 44,6 | 1.119,1 | 32,7 | 174,30 |

### P-002 — um casco

| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|
| antes (só Dittus-Boelter) | inviável | 720 | 11,67 | 335,3 | comprimento de tubo acima de l_tubo_max; fora da faixa de validade de Dittus-Boelter (BOT 04, BOT 06) |
| depois (três regimes) | viável | 1.605 | 5,99 | 383,8 | — |

| Caso | Papel | Carga (kW) | Pr | v (m/s) | Re | Regime | Correlação | h_i (W/m²K) | h_o (W/m²K) | U (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 5.763,8 | 1,71 | 1,050 | 31.056 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 9.577,7 | 5.172,4 | 974,4 | 5,37 |
| BOT 02 — Early Life | turndown | 6.854,5 | 1,71 | 1,249 | 36.934 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 11.002,2 | 5.299,7 | 998,6 | 5,99 |
| BOT 03 — Early Life Blend | turndown | 6.821,3 | 1,71 | 1,243 | 36.755 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 10.959,5 | 5.572,3 | 1.007,4 | 5,91 |
| BOT 04 — Early Life | turndown | 769,3 | 1,71 | 0,140 | 4.145 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 802,7 | 1.301,2 | 302,0 | 2,29 |
| BOT 05 — Low CO2 | turndown | 1.013,6 | 1,71 | 0,185 | 5.461 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.273,0 | 1.690,2 | 409,0 | 2,22 |
| BOT 06 — Mid Life | turndown | 262,8 | 1,71 | 0,048 | 1.416 | laminar | Hausen (Branan eq. 2-10) | 350,1 | 597,8 | 150,9 | 1,56 |
| BOT 07 — Mid Life | turndown | 5.698,3 | 1,71 | 1,039 | 30.704 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 9.490,6 | 5.171,5 | 973,0 | 5,33 |
| BOT 08 — Mid Life | turndown | 6.596,2 | 1,71 | 1,202 | 35.542 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 10.669,3 | 4.417,9 | 958,5 | 5,64 |
| BOT 09 — Mid Life | turndown | 5.981,9 | 1,71 | 1,090 | 32.232 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 9.866,6 | 3.982,8 | 926,4 | 5,26 |
| BOT 11 — Late Life | projeto | 7.380,2 | 1,71 | 1,345 | 39.766 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 11.672,2 | 2.963,1 | 875,4 | 5,78 |

### P-002 — recomendado

| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|
| antes (só Dittus-Boelter) | inviável | 720 | 11,67 | 335,3 | comprimento de tubo acima de l_tubo_max; fora da faixa de validade de Dittus-Boelter (BOT 04, BOT 06) |
| depois (três regimes) | viável | 1.605 | 5,99 | 383,8 | — |

| Caso | Papel | Carga (kW) | Pr | v (m/s) | Re | Regime | Correlação | h_i (W/m²K) | h_o (W/m²K) | U (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 5.763,8 | 1,71 | 1,050 | 31.056 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 9.577,7 | 5.172,4 | 974,4 | 5,37 |
| BOT 02 — Early Life | turndown | 6.854,5 | 1,71 | 1,249 | 36.934 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 11.002,2 | 5.299,7 | 998,6 | 5,99 |
| BOT 03 — Early Life Blend | turndown | 6.821,3 | 1,71 | 1,243 | 36.755 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 10.959,5 | 5.572,3 | 1.007,4 | 5,91 |
| BOT 04 — Early Life | turndown | 769,3 | 1,71 | 0,140 | 4.145 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 802,7 | 1.301,2 | 302,0 | 2,29 |
| BOT 05 — Low CO2 | turndown | 1.013,6 | 1,71 | 0,185 | 5.461 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.273,0 | 1.690,2 | 409,0 | 2,22 |
| BOT 06 — Mid Life | turndown | 262,8 | 1,71 | 0,048 | 1.416 | laminar | Hausen (Branan eq. 2-10) | 350,1 | 597,8 | 150,9 | 1,56 |
| BOT 07 — Mid Life | turndown | 5.698,3 | 1,71 | 1,039 | 30.704 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 9.490,6 | 5.171,5 | 973,0 | 5,33 |
| BOT 08 — Mid Life | turndown | 6.596,2 | 1,71 | 1,202 | 35.542 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 10.669,3 | 4.417,9 | 958,5 | 5,64 |
| BOT 09 — Mid Life | turndown | 5.981,9 | 1,71 | 1,090 | 32.232 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 9.866,6 | 3.982,8 | 926,4 | 5,26 |
| BOT 11 — Late Life | projeto | 7.380,2 | 1,71 | 1,345 | 39.766 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 11.672,2 | 2.963,1 | 875,4 | 5,78 |

### P-003 — recomendado (um casco)

| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|
| antes (só Dittus-Boelter) | inviável | 7.526 | 4,91 | 1.473,4 | fora da faixa de validade de Dittus-Boelter (BOT 04, BOT 05, BOT 06, BOT 11, BOT 15, BOT 16) |
| depois (três regimes) | viável | 7.526 | 4,91 | 1.473,4 | — |

| Caso | Papel | Carga (kW) | Pr | v (m/s) | Re | Regime | Correlação | h_i (W/m²K) | h_o (W/m²K) | U (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 20.615,4 | 5,12 | 2,333 | 26.013 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 11.444,1 | 1.603,9 | 698,9 | 4,54 |
| BOT 02 — Early Life | turndown | 13.536,8 | 5,12 | 1,532 | 17.081 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 8.174,1 | 1.524,8 | 659,8 | 3,93 |
| BOT 03 — Early Life Blend | turndown | 13.572,8 | 5,12 | 1,536 | 17.127 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 8.191,5 | 1.644,1 | 681,4 | 3,80 |
| BOT 04 — Early Life | turndown | 1.148,3 | 5,12 | 0,130 | 1.449 | laminar | Hausen (Branan eq. 2-10) | 387,5 | 468,8 | 149,8 | 1,77 |
| BOT 05 — Low CO2 | turndown | 498,3 | 5,12 | 0,056 | 629 | laminar | Hausen (Branan eq. 2-10) | 356,0 | 549,5 | 149,2 | 1,11 |
| BOT 06 — Mid Life | turndown | 128,6 | 5,12 | 0,015 | 162 | laminar | Hausen (Branan eq. 2-10) | 336,1 | 255,5 | 110,5 | 0,39 |
| BOT 07 — Mid Life | projeto | 26.505,5 | 5,12 | 2,999 | 33.446 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 13.992,5 | 1.672,3 | 723,8 | 4,91 |
| BOT 08 — Mid Life | turndown | 13.128,7 | 5,12 | 1,486 | 16.566 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 7.976,4 | 1.246,9 | 600,1 | 3,47 |
| BOT 09 — Mid Life | turndown | 11.785,2 | 5,12 | 1,334 | 14.871 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 7.316,4 | 1.099,5 | 558,4 | 3,11 |
| BOT 10 — Late Life | turndown | 12.065,2 | 5,12 | 1,365 | 15.224 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 7.455,2 | 983,9 | 528,0 | 2,86 |
| BOT 11 — Late Life | turndown | 4.843,0 | 5,12 | 0,548 | 6.111 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 2.117,5 | 725,1 | 361,9 | 2,25 |
| BOT 12 — Late Life | turndown | 8.420,7 | 5,12 | 0,953 | 10.626 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 5.591,2 | 791,1 | 452,8 | 2,33 |
| BOT 13 — High CO2 | turndown | 10.111,7 | 5,12 | 1,144 | 12.759 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 6.472,7 | 883,9 | 490,4 | 2,58 |
| BOT 14 — High CO2 | turndown | 10.111,0 | 5,12 | 1,144 | 12.758 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 6.472,4 | 883,9 | 490,4 | 2,58 |
| BOT 15 — Highest CO2 | turndown | 3.657,6 | 5,12 | 0,414 | 4.615 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.311,0 | 503,6 | 262,8 | 1,75 |
| BOT 16 — Highest CO2 | turndown | 4.072,4 | 5,12 | 0,461 | 5.139 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.573,3 | 532,2 | 285,1 | 1,79 |

### P-003 — dois cascos em série

| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|
| antes (só Dittus-Boelter) | inviável | 3.856 | 3,98 | 1.225,8 | fora da faixa de validade de Dittus-Boelter (BOT 04, BOT 05, BOT 06, BOT 15); velocidade no tubo acima de v_max (BOT 01, BOT 07) |
| depois (três regimes) | viável | 7.526 | 2,45 | 1.473,4 | — |

| Caso | Papel | Carga (kW) | Pr | v (m/s) | Re | Regime | Correlação | h_i (W/m²K) | h_o (W/m²K) | U (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 20.615,4 | 5,12 | 2,333 | 26.013 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 11.444,1 | 1.603,9 | 698,9 | 2,27 |
| BOT 02 — Early Life | turndown | 13.536,8 | 5,12 | 1,532 | 17.081 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 8.174,1 | 1.524,8 | 659,8 | 1,97 |
| BOT 03 — Early Life Blend | turndown | 13.572,8 | 5,12 | 1,536 | 17.127 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 8.191,5 | 1.644,1 | 681,4 | 1,90 |
| BOT 04 — Early Life | turndown | 1.148,3 | 5,12 | 0,130 | 1.449 | laminar | Hausen (Branan eq. 2-10) | 492,4 | 468,8 | 170,9 | 0,78 |
| BOT 05 — Low CO2 | turndown | 498,3 | 5,12 | 0,056 | 629 | laminar | Hausen (Branan eq. 2-10) | 437,7 | 549,5 | 169,0 | 0,49 |
| BOT 06 — Mid Life | turndown | 128,6 | 5,12 | 0,015 | 162 | laminar | Hausen (Branan eq. 2-10) | 397,7 | 255,5 | 119,7 | 0,18 |
| BOT 07 — Mid Life | projeto | 26.505,5 | 5,12 | 2,999 | 33.446 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 13.992,5 | 1.672,3 | 723,8 | 2,45 |
| BOT 08 — Mid Life | turndown | 13.128,7 | 5,12 | 1,486 | 16.566 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 7.976,4 | 1.246,9 | 600,1 | 1,73 |
| BOT 09 — Mid Life | turndown | 11.785,2 | 5,12 | 1,334 | 14.871 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 7.316,4 | 1.099,5 | 558,4 | 1,56 |
| BOT 10 — Late Life | turndown | 12.065,2 | 5,12 | 1,365 | 15.224 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 7.455,2 | 983,9 | 528,0 | 1,43 |
| BOT 11 — Late Life | turndown | 4.843,0 | 5,12 | 0,548 | 6.111 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 2.197,3 | 725,1 | 365,3 | 1,12 |
| BOT 12 — Late Life | turndown | 8.420,7 | 5,12 | 0,953 | 10.626 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 5.591,2 | 791,1 | 452,8 | 1,17 |
| BOT 13 — High CO2 | turndown | 10.111,7 | 5,12 | 1,144 | 12.759 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 6.472,7 | 883,9 | 490,4 | 1,29 |
| BOT 14 — High CO2 | turndown | 10.111,0 | 5,12 | 1,144 | 12.758 | turbulento | Dittus-Boelter (Saari eq. 6.23) | 6.472,4 | 883,9 | 490,4 | 1,29 |
| BOT 15 — Highest CO2 | turndown | 3.657,6 | 5,12 | 0,414 | 4.615 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.422,8 | 503,6 | 269,2 | 0,85 |
| BOT 16 — Highest CO2 | turndown | 4.072,4 | 5,12 | 0,461 | 5.139 | transicao | interpolação laminar↔turbulento (Branan eq. 2-12) | 1.676,9 | 532,2 | 290,0 | 0,88 |

## P-001: o que governa, e por que não é a banda de velocidade

A grade que a banda de 1,0–3,0 m/s admite vai de 28 a 1.994 tubos por passe. Varrendo MUITO além dela, no caso que mais exige comprimento (BOT 02 — Early Life, carga de 16.532,4 kW e U·A exigido de 1.547,0 kW/K):

| Tubos/passe | v (m/s) | Re | Regime | h_i (W/m²K) | U (W/m²K) | Área (m²) | L exigido (m) |
|---|---|---|---|---|---|---|---|
| 28 | 71,181 | 171.017 | turbulento | 19.245,0 | 990,9 | 1.561 | 931,68 |
| 1.994 | 1,000 | 2.401 | transicao | 67,6 | 48,7 | 31.793 | 266,41 |
| 5.000 | 0,399 | 958 | laminar | 35,3 | 26,0 | 59.449 | 198,67 |
| 10.000 | 0,199 | 479 | laminar | 35,2 | 25,7 | 60.292 | 100,74 |
| 20.000 | 0,100 | 239 | laminar | 35,2 | 25,2 | 61.416 | 51,31 |
| 50.000 | 0,040 | 96 | laminar | 35,1 | 24,4 | 63.508 | 21,22 |

No platô laminar o Nusselt é constante, então h_i não melhora com mais tubos — mas o comprimento cai com 1/n. Mesmo assim, com 50.000 tubos por passe o comprimento exigido continua muito acima do limite de 6 m, e a área fica na casa de 60.000 m². **O impedimento é a área, não a banda de velocidade:** relaxar o piso de 1 m/s não resolve, e o teto de 3 m/s (erosão, Saari Tab. 3.1) impede o óleo de chegar ao turbulento, onde o coeficiente seria uma ordem de grandeza maior.

## Situação de cada alarme depois da correção

| TAG | Antes | Depois | Restrição que governa agora |
|---|---|---|---|
| P-002 | inviável: faixa de Dittus-Boelter no BOT 06 | **viável** | nenhuma — e sem circulação fixa e sem mudar arquitetura (viável com um casco e com dois em série) |
| P-003 | inviável: faixa de Dittus-Boelter nos BOT 04/05/06 **e** comprimento | inviável | **comprimento de tubo**: o melhor feixe de um casco pede 7,33 m contra o limite de estoque de 6 m (22 % acima); dois cascos em série resolvem |
| P-001 | inviável: domínio do fator F (2 passes) e faixa de Dittus-Boelter (1 passe) | inviável | **área**: no platô laminar U ≈ 25 W/m²K contra U·A exigido de 1,55 MW/K; o melhor feixe da grade pede 186,4 m de tubo. Com 2 passes, o domínio do fator F continua sendo o primeiro impedimento |

Nenhuma premissa de operação foi promovida para obter esses resultados: a circulação da utilidade continua proporcional à carga, a política de divisão em cascos continua a declarada, e os limites de 6 m e 2.500 mm não foram alterados.

