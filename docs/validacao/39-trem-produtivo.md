# 39 — Trem produtivo: recombinação da Nota 4 e flash nos casos avaliáveis

**Mudança física deliberada**, aprovada pelo usuário em 2026-09-28 (premissa de modelagem da
nota 38). Esta nota é a justificativa escrita exigida antes de rever as regressões
(`CLAUDE.md`, "Refatoração não muda número"). Números gerados pela API pública
(`resolver_todos`, `EstadoProcesso.trem`, planta pelo serviço por TAG) e por
`tools/relatorio_trem.py`; o "antes" é o `main` em `593f7d9`.

## 1. O que mudou

- **Composição do caso** (12 casos sem gás de lift): `z_caso` pela Nota 4 do BOT, com a
  referência do FWKO (P_FWKO = 2.500 kPa(a), T do caso). **Premissa de modelagem sustentada
  pelo conjunto de evidências do BOT, não prescrita pelo texto** (nota 38). `z_base` (BOT) não
  é alterado e fica no estado ao lado de `z_caso`.
- **Trem produtivo**: `z_caso → SG-001 → x_F → V-001 → x₁ → V-002 → x₂`, nas condições do
  próprio balanço, com quantidade molar propagada. O balanço e o dimensionamento consomem de
  cada estágio: β, y, x, MW_v, Z_v e ρ_v. **Standing sai desses 12 casos** (continua nos 4 com
  lift).
- **Não ativado**: h e cp dos pseudo-componentes, ρ líquida da PR, μ líquida da EOS, k líquida,
  Péneloux, correlação nova. μ do gás continua pelo corte leve (não há método de transporte
  validado para a composição y, que tem pseudo-componentes). As propriedades de líquido seguem
  nas fontes validadas (API, BOT + Beggs & Robinson + Zanker, IAPWS/Laliberté).
- **Casos 9, 11, 15 e 16**: "não avaliável termodinamicamente para integração completa" — o
  gás de lift não tem composição na fonte. Nenhuma composição suposta; continuam no envelope
  do BOT por Standing, e o estado de cada caso diz isso. **Bit a bit iguais ao antes.**

### Como o balanço (O, W, D, G) acompanha o flash

Cada líquido do trem é levado à condição padrão (15,6 °C; 101,3 kPa): o que fica líquido é o
**óleo de tanque** (componente O) e o que vaporiza é **gás dissolvido** (G). O vapor de um
estágio leva como O a parte do óleo de tanque da alimentação que vaporizou a 90 °C (componentes
que condensariam na condição padrão) e como G o resto. Assim O e G se conservam cada um e a
energia sensível (P-14, cp constante por componente) fecha sem calor latente, que o modelo não
tem. Uma primeira versão convertia O em G dentro do líquido e deixou 145 kW de resíduo no
balanço de energia global — a auditoria independente pegou, e a versão final fecha em 3·10⁻⁸ kW.
A vazão de gás do estágio é o vapor inteiro, ṅ_V·V_M (Sm³ como medida molar).

Na condição padrão o PR com pseudo-componentes divide o líquido final dos casos Mid Life em
**duas fases líquidas**; óleo de tanque é a soma das fases líquidas.

**Acoplamento com o reciclo**: o trem fica congelado enquanto o laço de reciclo converge e é
refeito nas temperaturas convergidas até elas não mudarem mais que 10⁻⁹ °C (mesmo ponto fixo,
~3 vezes mais rápido que refazer o trem a cada iteração). Resolver os 16 casos: ~7 s na primeira vez por processo, ~0,05 s depois
(flash memorizado pela condição exata).

## 2. Fórmula e algoritmo da recombinação

```
1. flash de z_base a (P_FWKO, T_caso)            → β_ref, y_ref, x_ref
2. flash de x_ref a (15,6 °C; 101,3 kPa)         → β_std, MW_std (média de TODAS as fases líquidas)
3. ṅ_g = Q_G / V_M                                (Produced Gas = gás na saída do FWKO)
4. ṅ_L = Q_O · ρ_O / [(1 − β_std) · MW_std]       (Q_O = óleo morto na condição padrão, Nota 2)
5. z_caso,i = (ṅ_g · y_ref,i + ṅ_L · x_ref,i) / (ṅ_g + ṅ_L)
6. verificação: re-flash de z_caso em (P_FWKO, T_caso) → Q_G = β·ṅ·V_M;
                o líquido levado à condição padrão → Q_O de óleo morto
```

Nenhum componente é ajustado: z_caso está sobre a linha de amarração do flash de referência
(re-flashado, devolve as mesmas y e x; teste `test_a_recombinacao_e_so_a_mistura_das_duas_fases`).
Critérios: reprodução ≤ 10⁻⁸ relativo (re-convergência do flash); Σz, mol, massa e componente
≤ 10⁻¹² (`config/trem.toml [recombinacao]`).

## 3. Os 12 casos: fechamento de Q_G e Q_O, Σz, mol, massa e componente

| caso | fluido | T_ref (°C) | ṅ_g (kmol/d) | ṅ_L (kmol/d) | Q_G BOT (Sm³/d) | Q_G do z_caso no FWKO | erro rel. | Q_O BOT (m³/d) | Q_O de óleo morto | erro rel. | Σz−1 | molar | mássico | componente (pior) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Early Life | 65 | 506.331,0 | 130.070,3 | 12.000.000 | 12.000.000,00 | 3.7e-11 | 28.621 | 28.621,0000 | 1.3e-10 | 0.0e+00 | 0.0e+00 | 1.9e-16 | 1.4e-17 (C1) |
| 2 | Early Life | 50 | 506.331,0 | 137.967,9 | 12.000.000 | 12.000.000,00 | 1.1e-11 | 28.621 | 28.621,0000 | 5.4e-11 | 2.2e-16 | 1.8e-16 | 0.0e+00 | 1.7e-17 (C1) |
| 3 | Early Life Blend | 50 | 392.406,5 | 155.496,6 | 9.300.000 | 9.300.000,00 | 5.9e-13 | 28.621 | 28.621,0000 | 2.3e-12 | 1.1e-16 | 0.0e+00 | 0.0e+00 | 6.6e-18 (C1) |
| 4 | Early Life | 45 | 37.974,8 | 18.325,7 | 900.000 | 900.000,00 | 4.7e-13 | 3.720 | 3.720,0000 | 3.4e-12 | 2.2e-16 | 1.3e-16 | 2.1e-16 | 2.0e-17 (C1) |
| 5 | Low CO2 | 35 | 37.974,8 | 25.502,3 | 900.000 | 900.000,00 | 8.1e-12 | 4.864 | 4.864,0000 | 3.9e-12 | 1.1e-16 | 1.1e-16 | 1.7e-16 | 2.9e-17 (C1) |
| 6 | Mid Life | 35 | 37.974,8 | 7.543,7 | 900.000 | 900.000,00 | 4.0e-12 | 1.250 | 1.250,0000 | 1.0e-10 | 2.9e-15 | 2.9e-15 | 2.0e-16 | 4.5e-17 (CO2) |
| 7 | Mid Life | 75 | 421.942,5 | 135.349,5 | 10.000.000 | 10.000.000,00 | 8.0e-11 | 28.621 | 28.621,0000 | 7.9e-11 | 1.1e-16 | 0.0e+00 | 1.9e-16 | 2.6e-17 (C1) |
| 8 | Mid Life | 60 | 421.942,5 | 97.629,4 | 10.000.000 | 10.000.000,00 | 9.5e-11 | 19.081 | 19.081,0000 | 2.7e-10 | 0.0e+00 | 1.1e-16 | 1.2e-16 | 2.1e-17 (CO2) |
| 9 | Mid Life | — | — | — | 8.000.000 | não avaliável | | 15.000 | | | | | | |
| 10 | Late Life | 90 | 316.456,9 | 44.088,5 | 7.500.000 | 7.500.000,00 | 4.8e-12 | 11.500 | 11.500,0000 | 1.6e-10 | 1.9e-14 | 1.9e-14 | 0.0e+00 | 1.4e-17 (C1) |
| 11 | Late Life | — | — | — | 7.000.000 | não avaliável | | 7.950 | | | | | | |
| 12 | Late Life | 90 | 379.748,2 | 30.869,6 | 9.000.000 | 9.000.000,00 | 1.7e-11 | 8.052 | 8.052,0000 | 1.7e-10 | 1.1e-15 | 1.1e-15 | 0.0e+00 | 1.1e-17 (CO2) |
| 13 | High CO2 | 90 | 392.406,5 | 36.786,6 | 9.300.000 | 9.300.000,00 | 1.3e-10 | 9.655 | 9.655,0000 | 1.2e-09 | 2.2e-15 | 2.2e-15 | 0.0e+00 | 1.9e-17 (C1) |
| 14 | High CO2 | 90 | 506.331,0 | 36.786,6 | 12.000.000 | 12.000.000,00 | 1.9e-12 | 9.655 | 9.655,0000 | 1.9e-10 | 1.1e-14 | 1.1e-14 | 1.5e-16 | 1.5e-17 (C1) |
| 15 | Highest CO2 | — | — | — | 4.500.000 | não avaliável | | 3.541 | | | | | | |
| 16 | Highest CO2 | — | — | — | 5.000.000 | não avaliável | | 3.934 | | | | | | |

## 4. z_base → z_caso (principais componentes)

| caso | CO2 | C1 | C2 | C3 | nC4 | C7 | C10 | C20+ / C20++ |
|---:|---|---|---|---|---|---|---|---|
| 1 | 0,1757 → 0,1943 | 0,4442 → 0,5096 | 0,0659 → 0,0713 | 0,0449 → 0,0444 | 0,0181 → 0,0158 | 0,0103 → 0,0069 | 0,0143 → 0,0089 | 0,0705 → 0,0437 |
| 2 | 0,1757 → 0,1945 | 0,4442 → 0,5163 | 0,0659 → 0,0709 | 0,0449 → 0,0431 | 0,0181 → 0,0149 | 0,0103 → 0,0066 | 0,0143 → 0,0088 | 0,0705 → 0,0430 |
| 3 | 0,1596 → 0,1606 | 0,4900 → 0,4944 | 0,0693 → 0,0696 | 0,0472 → 0,0471 | 0,0190 → 0,0188 | 0,0090 → 0,0088 | 0,0125 → 0,0122 | 0,0573 → 0,0558 |
| 4 | 0,1757 → 0,1801 | 0,4442 → 0,4619 | 0,0659 → 0,0670 | 0,0449 → 0,0443 | 0,0181 → 0,0173 | 0,0103 → 0,0094 | 0,0143 → 0,0130 | 0,0705 → 0,0639 |
| 5 | 0,0226 → 0,0237 | 0,4846 → 0,5264 | 0,0901 → 0,0927 | 0,0618 → 0,0597 | 0,0267 → 0,0244 | 0,0123 → 0,0107 | 0,0162 → 0,0140 | 0,1062 → 0,0918 |
| 6 | 0,2713 → 0,2739 | 0,4813 → 0,4888 | 0,0627 → 0,0631 | 0,0427 → 0,0423 | 0,0172 → 0,0166 | 0,0052 → 0,0048 | 0,0072 → 0,0066 | 0,0266 → 0,0243 |
| 7 | 0,2713 → 0,2497 | 0,4813 → 0,4327 | 0,0627 → 0,0586 | 0,0427 → 0,0425 | 0,0172 → 0,0190 | 0,0052 → 0,0078 | 0,0072 → 0,0124 | 0,0266 → 0,0467 |
| 8 | 0,2713 → 0,2642 | 0,4813 → 0,4645 | 0,0627 → 0,0614 | 0,0427 → 0,0430 | 0,0172 → 0,0181 | 0,0052 → 0,0062 | 0,0072 → 0,0089 | 0,0266 → 0,0329 |
| 10 | 0,3661 → 0,3538 | 0,4445 → 0,4264 | 0,0564 → 0,0548 | 0,0362 → 0,0359 | 0,0130 → 0,0134 | 0,0042 → 0,0052 | 0,0037 → 0,0056 | 0,0216 → 0,0339 |
| 12 | 0,3661 → 0,3669 | 0,4445 → 0,4456 | 0,0564 → 0,0565 | 0,0362 → 0,0362 | 0,0130 → 0,0130 | 0,0042 → 0,0041 | 0,0037 → 0,0036 | 0,0216 → 0,0209 |
| 13 | 0,4175 → 0,4189 | 0,3986 → 0,4001 | 0,0520 → 0,0521 | 0,0310 → 0,0310 | 0,0113 → 0,0113 | 0,0040 → 0,0039 | 0,0042 → 0,0040 | 0,0252 → 0,0240 |
| 14 | 0,4175 → 0,4247 | 0,3986 → 0,4067 | 0,0520 → 0,0527 | 0,0310 → 0,0311 | 0,0113 → 0,0111 | 0,0040 → 0,0035 | 0,0042 → 0,0033 | 0,0252 → 0,0190 |

Nos casos de GOR do BOT maior que o da composição de base (1, 2, 14) a recombinação acrescenta
gás (C1 e CO2 sobem, C20+ desce); nos de GOR menor (7, 8, 10) acrescenta líquido.

## 5. Standing × flash por estágio

| caso | estágio | Q_G antes (Sm³/d) | Q_G depois | Δ | ṅ antes (kmol/d) | ṅ depois | ṁ antes (t/d) | ṁ depois (t/d) | Δṁ | β | MW_v antes → depois | Z_v antes → depois | ρ_v antes → depois (kg/m³) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | SG-001 | 11.691.313 | 12.000.000 | +2,6 % | 493.306,2 | 506.331,0 | 13.250,8 | 13.366,9 | +0,9 % | 0,79562 | 26,86 → 26,40 | 0,9324 → 0,9346 | 25,617 → 25,116 |
| 1 | V-001 | 257.955 | 679.386 | +163,4 % | 10.884,2 | 28.666,2 | 292,4 | 1.021,9 | +249,5 % | 0,22039 | 26,86 → 35,65 | 0,9849 → 0,9711 | 6,323 → 8,511 |
| 1 | V-002 | 50.733 | 218.928 | +331,5 % | 2.140,6 | 9.237,5 | 57,5 | 451,4 | +685,0 % | 0,09110 | 26,86 → 48,86 | 0,9957 → 0,9818 | 1,787 → 3,297 |
| 2 | SG-001 | 11.672.036 | 12.046.580 | +3,2 % | 492.492,8 | 508.296,4 | 13.229,0 | 13.172,6 | -0,4 % | 0,78891 | 26,86 → 25,92 | 0,9231 → 0,9289 | 26,850 → 25,747 |
| 2 | V-001 | 277.231 | 808.445 | +191,6 % | 11.697,6 | 34.111,7 | 314,2 | 1.232,5 | +292,2 % | 0,25082 | 26,86 → 36,13 | 0,9849 → 0,9702 | 6,323 → 8,633 |
| 2 | V-002 | 50.733 | 227.513 | +348,5 % | 2.140,6 | 9.599,8 | 57,5 | 473,7 | +723,8 % | 0,09422 | 26,86 → 49,35 | 0,9957 → 0,9813 | 1,787 → 3,331 |
| 3 | SG-001 | 8.974.930 | 9.349.397 | +4,2 % | 378.690,5 | 394.490,8 | 9.848,2 | 9.971,3 | +1,2 % | 0,72000 | 26,01 → 25,28 | 0,9249 → 0,9294 | 25,932 → 25,087 |
| 3 | V-001 | 274.745 | 861.091 | +213,4 % | 11.592,7 | 36.333,1 | 301,5 | 1.315,6 | +336,4 % | 0,23683 | 26,01 → 36,21 | 0,9852 → 0,9688 | 6,120 → 8,664 |
| 3 | V-002 | 50.324 | 265.189 | +427,0 % | 2.123,4 | 11.189,5 | 55,2 | 559,5 | +913,3 % | 0,09557 | 26,01 → 50,01 | 0,9957 → 0,9802 | 1,730 → 3,379 |
| 4 | SG-001 | 855.723 | 900.000 | +5,2 % | 36.106,6 | 37.974,8 | 969,9 | 974,0 | +0,4 % | 0,67450 | 26,86 → 25,65 | 0,9165 → 0,9246 | 27,700 → 26,216 |
| 4 | V-001 | 37.683 | 118.803 | +215,3 % | 1.590,0 | 5.012,8 | 42,7 | 182,8 | +328,0 % | 0,27354 | 26,86 → 36,47 | 0,9849 → 0,9696 | 6,323 → 8,719 |
| 4 | V-002 | 6.594 | 30.454 | +361,9 % | 278,2 | 1.285,0 | 7,5 | 63,9 | +754,4 % | 0,09652 | 26,86 → 49,69 | 0,9957 → 0,9810 | 1,787 → 3,355 |
| 5 | SG-001 | 845.524 | 900.000 | +6,4 % | 35.676,3 | 37.974,8 | 838,0 | 786,9 | -6,1 % | 0,59824 | 23,49 → 20,72 | 0,8986 → 0,9227 | 25,506 → 21,914 |
| 5 | V-001 | 46.751 | 163.734 | +250,2 % | 1.972,6 | 6.908,7 | 46,3 | 230,5 | +397,4 % | 0,27090 | 23,49 → 33,36 | 0,9834 → 0,9654 | 5,538 → 8,012 |
| 5 | V-002 | 7.725 | 46.898 | +507,1 % | 325,9 | 1.978,8 | 7,7 | 97,0 | +1166,4 % | 0,10643 | 23,49 → 49,00 | 0,9952 → 0,9782 | 1,563 → 3,318 |
| 6 | SG-001 | 883.620 | 900.000 | +1,9 % | 37.283,7 | 37.974,8 | 1.049,9 | 1.051,1 | +0,1 % | 0,83427 | 28,16 → 27,68 | 0,9085 → 0,9118 | 30,246 → 29,621 |
| 6 | V-001 | 14.058 | 61.767 | +339,4 % | 593,2 | 2.606,2 | 16,7 | 104,3 | +524,3 % | 0,34548 | 28,16 → 40,01 | 0,9852 → 0,9652 | 6,626 → 9,610 |
| 6 | V-002 | 2.323 | 13.528 | +482,4 % | 98,0 | 570,8 | 2,8 | 30,5 | +1005,6 % | 0,11561 | 28,16 → 53,46 | 0,9957 → 0,9780 | 1,873 → 3,620 |
| 7 | SG-001 | 9.692.043 | 10.000.000 | +3,2 % | 408.948,5 | 421.942,5 | 11.515,8 | 12.145,7 | +5,5 % | 0,75713 | 28,16 → 28,79 | 0,9402 → 0,9358 | 25,868 → 26,565 |
| 7 | V-001 | 254.772 | 668.038 | +162,2 % | 10.749,9 | 28.187,3 | 302,7 | 1.050,4 | +247,0 % | 0,20826 | 28,16 → 37,27 | 0,9852 → 0,9709 | 6,626 → 8,898 |
| 7 | V-002 | 53.185 | 233.563 | +339,2 % | 2.244,1 | 9.855,0 | 63,2 | 493,0 | +680,1 % | 0,09196 | 28,16 → 50,02 | 0,9957 → 0,9817 | 1,873 → 3,375 |
| 8 | SG-001 | 9.782.224 | 10.040.998 | +2,6 % | 412.753,6 | 423.672,4 | 11.622,9 | 12.064,4 | +3,8 % | 0,81543 | 28,16 → 28,48 | 0,9323 → 0,9296 | 27,009 → 27,396 |
| 8 | V-001 | 182.319 | 546.411 | +199,7 % | 7.692,8 | 23.055,4 | 216,6 | 880,7 | +306,6 % | 0,24041 | 28,16 → 38,20 | 0,9852 → 0,9690 | 6,626 → 9,140 |
| 8 | V-002 | 35.457 | 171.694 | +384,2 % | 1.496,1 | 7.244,5 | 42,1 | 372,0 | +782,9 % | 0,09945 | 28,16 → 51,34 | 0,9957 → 0,9804 | 1,873 → 3,469 |
| 10 | SG-001 | 7.377.928 | 7.500.477 | +1,7 % | 311.306,1 | 316.477,0 | 9.323,9 | 9.769,7 | +4,8 % | 0,87777 | 29,95 → 30,87 | 0,9483 → 0,9429 | 26,143 → 27,101 |
| 10 | V-001 | 99.358 | 190.052 | +91,3 % | 4.192,3 | 8.019,1 | 125,6 | 295,6 | +135,4 % | 0,18197 | 29,95 → 36,86 | 0,9852 → 0,9752 | 7,046 → 8,760 |
| 10 | V-002 | 22.714 | 66.729 | +193,8 % | 958,4 | 2.815,6 | 28,7 | 131,9 | +359,4 % | 0,07810 | 29,95 → 46,83 | 0,9957 → 0,9861 | 1,992 → 3,145 |
| 12 | SG-001 | 8.914.531 | 9.000.429 | +1,0 % | 376.141,9 | 379.766,4 | 11.265,8 | 11.723,4 | +4,1 % | 0,92487 | 29,95 → 30,87 | 0,9483 → 0,9429 | 26,142 → 27,100 |
| 12 | V-001 | 69.566 | 133.046 | +91,3 % | 2.935,3 | 5.613,8 | 87,9 | 206,9 | +135,4 % | 0,18196 | 29,95 → 36,86 | 0,9852 → 0,9752 | 7,046 → 8,759 |
| 12 | V-002 | 15.903 | 46.711 | +193,7 % | 671,0 | 1.970,9 | 20,1 | 92,3 | +359,3 % | 0,07809 | 29,95 → 46,83 | 0,9957 → 0,9861 | 1,992 → 3,145 |
| 13 | SG-001 | 9.192.961 | 9.300.457 | +1,2 % | 387.890,1 | 392.425,8 | 12.133,9 | 12.594,0 | +3,8 % | 0,91433 | 31,28 → 32,09 | 0,9471 → 0,9421 | 27,339 → 28,196 |
| 13 | V-001 | 87.122 | 160.777 | +84,5 % | 3.676,1 | 6.783,9 | 115,0 | 255,2 | +121,9 % | 0,18451 | 31,28 → 37,61 | 0,9849 → 0,9760 | 7,362 → 8,933 |
| 13 | V-002 | 19.917 | 53.755 | +169,9 % | 840,4 | 2.268,2 | 26,3 | 105,7 | +301,9 % | 0,07565 | 31,28 → 46,58 | 0,9956 → 0,9871 | 2,081 → 3,125 |
| 14 | SG-001 | 11.892.959 | 12.000.482 | +0,9 % | 501.814,5 | 506.351,3 | 15.697,6 | 16.250,1 | +3,5 % | 0,93231 | 31,28 → 32,09 | 0,9471 → 0,9421 | 27,340 → 28,197 |
| 14 | V-001 | 87.124 | 160.775 | +84,5 % | 3.676,1 | 6.783,8 | 115,0 | 255,2 | +121,9 % | 0,18451 | 31,28 → 37,61 | 0,9849 → 0,9760 | 7,362 → 8,933 |
| 14 | V-002 | 19.917 | 53.754 | +169,9 % | 840,4 | 2.268,1 | 26,3 | 105,6 | +301,9 % | 0,07565 | 31,28 → 46,58 | 0,9956 → 0,9871 | 2,081 → 3,125 |

Z_v e ρ_v "antes" são os do gás de composição fixa (corte N2–nC4) na condição do vaso, como o
dimensionamento os recebia; MW_v "antes" é o do corte leve.

**Caso 2** — y do corte leve (Standing, igual nos três estágios) × y e x do trem

| componente | z_base | z_caso | y corte leve | y SG-001 | x SG-001 | y V-001 | x V-001 | y V-002 | x V-002 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| C1 | 0,4442 | 0,5163 | 0,5853 | 0,6274 | 0,1009 | 0,3577 | 0,0150 | 0,1424 | 0,0017 |
| CO2 | 0,1757 | 0,1945 | 0,2315 | 0,2239 | 0,0845 | 0,2682 | 0,0230 | 0,1965 | 0,0050 |
| C2 | 0,0659 | 0,0709 | 0,0868 | 0,0789 | 0,0411 | 0,1206 | 0,0144 | 0,1142 | 0,0041 |
| C3 | 0,0449 | 0,0431 | 0,0592 | 0,0406 | 0,0522 | 0,1152 | 0,0311 | 0,1849 | 0,0151 |
| C20+ | 0,0705 | 0,0430 | — | 0,0000 | 0,2037 | 0,0000 | 0,2720 | 0,0000 | 0,3002 |
| nC4 | 0,0181 | 0,0149 | 0,0238 | 0,0102 | 0,0324 | 0,0459 | 0,0279 | 0,1058 | 0,0198 |
| C8 | 0,0193 | 0,0120 | — | 0,0008 | 0,0542 | 0,0070 | 0,0700 | 0,0229 | 0,0748 |
| C10 | 0,0143 | 0,0088 | — | 0,0001 | 0,0411 | 0,0011 | 0,0545 | 0,0036 | 0,0598 |
| C6 | 0,0125 | 0,0086 | — | 0,0026 | 0,0310 | 0,0175 | 0,0355 | 0,0526 | 0,0337 |
| C9 | 0,0122 | 0,0075 | — | 0,0002 | 0,0348 | 0,0021 | 0,0458 | 0,0068 | 0,0498 |

**Caso 13** — y do corte leve (Standing, igual nos três estágios) × y e x do trem

| componente | z_base | z_caso | y corte leve | y SG-001 | x SG-001 | y V-001 | x V-001 | y V-002 | x V-002 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CO2 | 0,4175 | 0,4189 | 0,4550 | 0,4464 | 0,1256 | 0,4925 | 0,0425 | 0,4293 | 0,0109 |
| C1 | 0,3986 | 0,4001 | 0,4343 | 0,4318 | 0,0621 | 0,2835 | 0,0121 | 0,1386 | 0,0017 |
| C2 | 0,0520 | 0,0521 | 0,0566 | 0,0550 | 0,0210 | 0,0741 | 0,0089 | 0,0823 | 0,0029 |
| C3 | 0,0310 | 0,0310 | 0,0338 | 0,0315 | 0,0255 | 0,0629 | 0,0170 | 0,1128 | 0,0092 |
| C20+ | 0,0252 | 0,0240 | — | 0,0000 | 0,2803 | 0,0000 | 0,3438 | 0,0000 | 0,3719 |
| nC4 | 0,0113 | 0,0113 | 0,0123 | 0,0106 | 0,0182 | 0,0268 | 0,0163 | 0,0656 | 0,0122 |
| C8 | 0,0060 | 0,0058 | — | 0,0021 | 0,0458 | 0,0056 | 0,0549 | 0,0182 | 0,0579 |
| iC4 | 0,0048 | 0,0048 | 0,0052 | 0,0046 | 0,0066 | 0,0111 | 0,0056 | 0,0257 | 0,0040 |
| nC5 | 0,0048 | 0,0048 | — | 0,0039 | 0,0138 | 0,0109 | 0,0145 | 0,0316 | 0,0131 |
| C6 | 0,0046 | 0,0045 | — | 0,0034 | 0,0172 | 0,0095 | 0,0190 | 0,0289 | 0,0182 |

**Por que as diferenças são grandes nos desgaseificadores:**

1. **Standing não vê o CO2.** A correlação é de óleo negro com gás hidrocarboneto; os fluidos
   têm 17–56 % de CO2, muito mais solúvel no óleo. O flash deixa no líquido do FWKO 21–54
   Sm³/Sm³ de gás dissolvido (Standing: 11–13), e esse gás sai nos desgaseificadores: V-001 de
   +84 a +339 % e V-002 de +170 a +507 % em Sm³/d.
2. **O vapor dos desgaseificadores é pesado.** A 90 °C e 700/200 kPa ele leva C3–C8: MW_v de
   33–40 (V-001) e 47–53 (V-002), contra 23–31 do corte leve fixo. A massa cresce mais que o
   volume (V-002: até +1.166 %), e ρ_v sobe (V-002: de ~1,8 para ~3,3 kg/m³).
3. **SG-001 muda pouco** (Q_G de +0,9 a +6,4 %): pela recombinação o gás do FWKO é o do BOT na
   T do caso; a diferença vem da T real do FWKO (reciclo quente: casos 2, 3, 8, 10, 12–14) e,
   nos casos de Standing, de Q_G,F ter sido o resto (Q_G,in − Q_G,D1 − Q_G,D2). MW_v e ρ_v
   caem nos fluidos com pouco CO2 (caso 5: 23,5 → 20,7) e sobem nos de muito CO2.
4. **Z_v** diminui 1–2 % nos desgaseificadores (vapor mais pesado, menos ideal) e sobe no SG-001
   dos casos de baixa T (menos pesados no vapor).

## 6. Massa de C-01

| caso | ṁ C-01 antes (t/d) | ṁ C-01 depois (t/d) | Δ | ṁ óleo (t/d) | ṁ gás antes (t/d) | ṁ gás depois (t/d) | ṅ_g·MW_v (FWKO) | ṅ_L·β_std·MW_v,std (líquido → padrão) | MW gás antes → depois |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 39.046,1 | 40.004,5 | +2,5 % | 25.445,4 | 13.600,7 | 14.559,0 | 13.366,9 | 1.192,2 | 26,86 → 26,95 |
| 2 | 39.046,1 | 39.992,9 | +2,4 % | 25.445,4 | 13.600,7 | 14.547,4 | 13.082,8 | 1.464,7 | 26,86 → 26,57 |
| 3 | 35.538,8 | 36.766,3 | +3,5 % | 25.333,9 | 10.204,9 | 11.432,4 | 9.879,6 | 1.552,8 | 26,01 → 26,22 |
| 4 | 4.327,3 | 4.485,7 | +3,7 % | 3.307,3 | 1.020,0 | 1.178,4 | 974,0 | 204,4 | 26,86 → 26,97 |
| 5 | 5.197,4 | 5.350,2 | +2,9 % | 4.305,4 | 892,0 | 1.044,8 | 786,9 | 257,9 | 23,49 → 22,80 |
| 6 | 2.180,7 | 2.273,9 | +4,3 % | 1.111,3 | 1.069,4 | 1.162,6 | 1.051,1 | 111,5 | 28,16 → 28,47 |
| 7 | 37.327,1 | 38.827,0 | +4,0 % | 25.445,4 | 11.881,7 | 13.381,5 | 12.145,7 | 1.235,9 | 28,16 → 29,37 |
| 8 | 28.845,6 | 30.000,0 | +4,0 % | 16.963,9 | 11.881,7 | 13.036,1 | 11.976,7 | 1.059,4 | 28,16 → 28,96 |
| 9 | 25.217,4 | 25.217,4 | +0,0 % | — | — | — | não avaliável | | |
| 10 | 19.702,2 | 20.357,0 | +3,3 % | 10.224,0 | 9.478,2 | 10.132,9 | 9.768,5 | 364,4 | 29,95 → 31,04 |
| 11 | 18.441,8 | 18.441,8 | +0,0 % | — | — | — | não avaliável | | |
| 12 | 18.532,4 | 19.135,9 | +3,3 % | 7.158,6 | 11.373,8 | 11.977,3 | 11.722,2 | 255,2 | 29,95 → 30,97 |
| 13 | 20.858,9 | 21.490,0 | +3,0 % | 8.583,8 | 12.275,1 | 12.906,3 | 12.592,7 | 313,6 | 31,28 → 32,20 |
| 14 | 24.422,6 | 25.146,0 | +3,0 % | 8.583,8 | 15.838,9 | 16.562,2 | 16.248,7 | 313,6 | 31,28 → 32,18 |
| 15 | 12.858,2 | 12.858,2 | +0,0 % | — | — | — | não avaliável | | |
| 16 | 13.954,5 | 13.954,5 | +0,0 % | — | — | — | não avaliável | | |

A nova massa é **ṁ = Q_O·ρ_O + ṅ_g·MW_v,ref + ṅ_L·β_std·MW_v,std**, com os MW das fases
efetivamente calculadas. Sobe 2,4–4,3 % porque (i) o gás do caso deixa de ter o MW fixo do corte
N2–nC4 (23–31) e passa a ter o do vapor de equilíbrio (de −0,7 a +1,2 no MW: sobe onde o vapor
leva C5+, desce no fluido de pouco CO2); e (ii) o líquido do FWKO ainda libera, até a condição padrão, gás que o BOT
não conta no "Produced Gas" (leitura F da nota 38): 111–1.553 t/d. **Não se forçou paridade**:
é mudança física deliberada.

## 7. SG-001, V-001, V-002 — antes × depois

| TAG | grandeza | antes | depois |
|---|---|---|---|
| SG-001 | Q_G de projeto (máx. dos casos, Sm³/d) | 11.892.959 | 12.046.580 |
| SG-001 | ρ_g (faixa nos casos, kg/m³) | 25,506–31,193 | 21,914–31,193 |
| SG-001 | diâmetro (mm) | 6.050 | 6.050 |
| SG-001 | Leff (m) | 17,867 | 17,867 |
| SG-001 | governante | liquid | liquid |
| SG-001 | caso governante | BOT 12 — Late Life | BOT 12 — Late Life |
| SG-001 | teto (mm) / caso | 6.257 / BOT 02 — Early Life (water_in_oil) | 10.021 / BOT 02 — Early Life (oil_in_water) |
| SG-001 | SR | 3,938 | 3,938 |
| SG-001 | volume (m³) | 684,8 | 684,8 |
| V-001 | Q_G de projeto (máx. dos casos, Sm³/d) | 277.231 | 861.091 |
| V-001 | ρ_g (faixa nos casos, kg/m³) | 5,538–8,350 | 6,626–9,610 |
| V-001 | diâmetro (mm) | 4.700 | 4.700 |
| V-001 | Leff (m) | 11,743 | 11,719 |
| V-001 | governante | liquid | liquid |
| V-001 | caso governante | BOT 03 — Early Life Blend | BOT 02 — Early Life |
| V-001 | teto (mm) / caso | — / BOT 01 — Early Life (none) | — / BOT 01 — Early Life (none) |
| V-001 | SR | 3,499 | 3,493 |
| V-001 | volume (m³) | 285,3 | 284,9 |
| V-002 | Q_G de projeto (máx. dos casos, Sm³/d) | 53.185 | 265.189 |
| V-002 | ρ_g (faixa nos casos, kg/m³) | 1,563–2,356 | 1,873–3,620 |
| V-002 | diâmetro (mm) | 4.700 | 4.700 |
| V-002 | Leff (m) | 11,957 | 11,807 |
| V-002 | governante | liquid | liquid |
| V-002 | caso governante | BOT 03 — Early Life Blend | BOT 02 — Early Life |
| V-002 | teto (mm) / caso | — / BOT 01 — Early Life (none) | — / BOT 01 — Early Life (none) |
| V-002 | SR | 3,544 | 3,512 |
| V-002 | volume (m³) | 289,0 | 286,4 |

| TAG | caso | d·Leff gás antes (mm·m) | d·Leff gás depois | Leff gás depois (m) | Leff líquido depois (m) |
|---|---:|---:|---:|---:|---:|
| V-001 | BOT 01 — Early Life | 1.949,2 | 5.463,2 | 1,162 | 11,447 |
| V-001 | BOT 02 — Early Life | 2.086,1 | 6.493,8 | 1,382 | 11,719 |
| V-001 | BOT 03 — Early Life Blend | 2.045,1 | 6.894,6 | 1,467 | 11,717 |
| V-001 | BOT 14 — High CO2 | 680,6 | 1.307,7 | 0,278 | 5,484 |
| V-002 | BOT 01 — Early Life | 1.044,7 | 4.981,5 | 1,060 | 11,329 |
| V-002 | BOT 02 — Early Life | 1.040,3 | 5.164,6 | 1,099 | 11,807 |
| V-002 | BOT 03 — Early Life Blend | 1.021,6 | 6.007,0 | 1,278 | 11,768 |
| V-002 | BOT 14 — High CO2 | 447,5 | 1.287,1 | 0,274 | 3,992 |
| SG-001 | BOT 01 — Early Life | 46.545,0 | 47.613,6 | 7,870 | 13,734 |
| SG-001 | BOT 02 — Early Life | 44.284,8 | 45.410,3 | 7,506 | 16,002 |
| SG-001 | BOT 03 — Early Life Blend | 33.717,5 | 34.939,2 | 5,775 | 16,003 |
| SG-001 | BOT 14 — High CO2 | 56.840,3 | 57.548,8 | 9,512 | 17,725 |

- **V-001 e V-002 continuam governados pela capacidade de LÍQUIDO** (5 min de retenção): o gás
  pede 1,1–1,5 m de Leff contra 11,7–11,8 m do líquido. O gás triplicou e a folga de gás
  continua ~8×; o diâmetro (4.700 mm) não muda. O Leff cai 0,2–1,3 % porque o líquido que sai
  perdeu o óleo de tanque que vaporizou; o caso governante passa de BOT 03 a BOT 02 (os dois
  estavam praticamente empatados — folga de 5 µm no Leff —, e o 3 perde mais líquido).
- **SG-001**: mesmo diâmetro, comprimento e governante (líquido, BOT 12). O **teto** muda de
  mecanismo: antes água-em-óleo, 6.257 mm (BOT 02); agora óleo-em-água, 10.021 mm. Causa: a μ
  do óleo vivo (Beggs & Robinson) usa o Rs da saída de óleo (C-06), que triplicou (§8).

## 8. Propagação aos demais equipamentos (mostrada, não ajustada)

A planta é um caminho só: os demais TAGs mudam por consequência, sem nenhuma alteração de
método, premissa ou proposta. Três canais:

1. **μ do óleo vivo** (Beggs & Robinson, correlação inalterada) recebe o Rs da corrente, agora
   o gás dissolvido pelo trem: μ de −22 a −65 % (SG-001, P-001 lado tubo, P-002 lado casco,
   TO-001). É a consequência indireta mais forte.
2. **C-06 mais pesada** (mais gás dissolvido) e Q_pre menor → Q_H maior (P-002).
3. **Óleo tratado 1–2 % menor** (óleo de tanque vaporizado) → TO-002, B-001, P-003.

| caso | Q_pre antes → depois (kW) | Q_H antes → depois (kW) | Q_C antes → depois (kW) | óleo tratado C-21 antes → depois (m³/d) | Rs C-06 antes → depois (Sm³/Sm³) |
|---:|---|---|---|---|---|
| 1 | 9.119 → 9.018 | 5.764 → 6.244 | 20.615 → 20.388 | 28.621 → 28.305 | 10.8 → 28.1 |
| 2 | 16.532 → 16.343 | 6.855 → 7.741 | 13.537 → 13.335 | 28.612 → 28.239 | 11.5 → 32.7 |
| 3 | 16.367 → 16.138 | 6.821 → 7.851 | 13.573 → 13.313 | 28.612 → 28.144 | 11.4 → 34.7 |
| 4 | 2.716 → 2.682 | 769 → 929 | 1.148 → 1.134 | 3.720 → 3.672 | 11.9 → 36.4 |
| 5 | 4.533 → 4.460 | 1.014 → 1.333 | 498 → 490 | 4.864 → 4.785 | 11.2 → 38.3 |
| 6 | 1.170 → 1.145 | 263 → 372 | 129 → 126 | 1.250 → 1.224 | 13.1 → 54.1 |
| 7 | 3.229 → 3.190 | 5.698 → 5.956 | 26.506 → 26.185 | 28.621 → 28.275 | 10.8 → 27.9 |
| 8 | 6.892 → 6.796 | 6.596 → 7.033 | 13.129 → 12.893 | 19.051 → 18.735 | 11.4 → 33.4 |
| 10 | 0 → 0 | 0 → 0 | 12.065 → 11.989 | 11.461 → 11.388 | 10.6 → 20.6 |
| 12 | 0 → 0 | 0 → 0 | 8.421 → 8.367 | 7.998 → 7.947 | 10.7 → 20.6 |
| 13 | 0 → 0 | 0 → 0 | 10.112 → 10.054 | 9.604 → 9.550 | 11.1 → 20.7 |
| 14 | 0 → 0 | 0 → 0 | 10.111 → 10.053 | 9.604 → 9.550 | 11.1 → 20.7 |

| TAG | antes | depois | causa |
|---|---|---|---|
| P-001 | inviável (F fora do domínio, 2 passes) | inviável (mesma mensagem) | segue inviável; a variante de 1 passe passa a parar na banda de velocidade da grade (antes: comprimento), por ṁ +8 % e μ −57 % no lado tubo |
| P-002 | 1.605 tubos/passe, 5,993 m | 1.701 tubos/passe, 6,000 m | Q_H +8 a +41 % (canais 1 e 2); x = 1.701 não está em nenhuma grade por caso (pendência 33) |
| P-003 | 7.526 tubos/passe, 4,907 m | 7.435, 4,910 m | canal 3 |
| TO-001 | 5.550 mm, 16,46 m (BOT 03) | 5.550 mm, 16,43 m (BOT 02) | canal 1 (μ) e líquido |
| TO-002 | 5.550 mm, 16,61 m (BOT 03) | 5.550 mm, 16,40 m (BOT 02) | canal 3 |
| B-001/2/3 | DN 600/250/125 | iguais (H −0,03 m) | canal 3 |

**Avisos de faixa que mudaram** (não bloqueiam; ficam no JSON e no rastro):

- SG-001, +3: a vazão de gás passa de 500.000 Sm³/h (12 MSm³/d, a faixa do descritor do
  método). Caso 1: por 2·10⁻⁵ m³/h, ruído de re-convergência do flash (a recombinação reproduz
  12.000.000 Sm³/d a 4·10⁻¹¹). Casos 2 (12,05 MSm³/d) e 14 (12,0005 MSm³/d): o FWKO real, mais
  quente que a T do caso pelo reciclo de água, libera um pouco mais que a referência.
- TO-001, −2: o Rs de C-10 estava abaixo da faixa de Beggs & Robinson (9–12 scf/STB, mantido o
  óleo morto); com o trem, fica dentro dela.

A decisão sobre aceitar o canal 1 (μ do óleo vivo com o Rs do trem) é do usuário; a
alternativa coerente seria manter Standing só como entrada de Beggs & Robinson, o que
misturaria dois modelos de gás dissolvido na mesma corrente.

## 9. TVP recalculada com z_caso (diagnóstico)

Líquido final do trem (x₂) na temperatura de estocagem (T_store = 40 °C, BOT §2.7.1.10), limite
do BOT §2.3.1.1 de 70 kPa. O P_D2 do limite foi buscado re-resolvendo o caso inteiro.

| caso | P_D2 atual (kPa) | TVP (kPa) | P_D2 em que TVP = limite (kPa) |
|---:|---:|---:|---:|
| 1 | 200,0 | 101,6 | 146,0 |
| 2 | 200,0 | 100,6 | 147,2 |
| 3 | 200,0 | 95,3 | 154,3 |
| 4 | 200,0 | 99,8 | 148,1 |
| 5 | 200,0 | 93,6 | 156,2 |
| 6 | 200,0 | 93,1 | 157,3 |
| 7 | 200,0 | 100,4 | 147,5 |
| 8 | 200,0 | 97,7 | 151,1 |
| 9 | 200,0 | não avaliável | não avaliável |
| 10 | 200,0 | 109,1 | 135,8 |
| 11 | 200,0 | não avaliável | não avaliável |
| 12 | 200,0 | 109,1 | 135,8 |
| 13 | 200,0 | 110,8 | 133,4 |
| 14 | 200,0 | 110,8 | 133,4 |
| 15 | 200,0 | não avaliável | não avaliável |
| 16 | 200,0 | não avaliável | não avaliável |

Com P-19 = 200 kPa a TVP estimada fica entre 93 e 111 kPa em todos os casos avaliáveis. O P_D2
em que ela atinge 70 kPa vai de **133,4 kPa(a)** (13 e 14) a **157,3 kPa(a)** (6). Continua
**diagnóstico**: não é restrição nem bound da otimização nesta intervenção. Substitui a faixa
137–162 kPa da nota 37, que usava z_base (e 37,8 °C).

## 10. Proveniência antes × depois

| propriedade | antes | depois (avaliáveis) | depois (com lift) |
|---|---|---|---|
| gás por estágio | Standing, consumido | trem (`fracao_vapor_estagio`), consumido pelo balanço | Standing |
| composição do caso | — | `composicao_caso` (BOT + premissa + PR + Riazi), validada | — |
| β, y, x | não validados, sem consumidor | validados (consistência com o BOT), consumidos pelo balanço | — |
| MW_v | validado, sem consumidor | consumido pelo balanço | — |
| Z_v, ρ_v | validados, sem consumidor | consumidos pelo dimensionamento (regras `compressibilidade_gas`, `densidade_gas`) | corte leve (PR) |
| μ_g | corte leve (Brokaw) | corte leve (sem método validado para y) | corte leve |
| ρ_gás padrão do corte leve | consumida pelo balanço | não consumida | consumida |
| ρ, μ, cp líquidos | BOT/Beggs & Robinson/Zanker/IAPWS/Laliberté | iguais; Rs de Beggs & Robinson vem do trem | iguais |
| ρ líquida PR, h, cp, transporte da EOS | não validada / ausente | idem, sem consumidor | idem |

A promoção de β/x/y acontece no mesmo commit em que o processo passa a consumi-los. "Validada"
é no sentido do contrato (fontes citadas, composição que reproduz o BOT, fechamentos): **não há
PVT medido**.

## 11. Números produtivos que mudaram, e a causa

| o quê | casos | causa |
|---|---|---|
| gás por estágio (G_F, G_D1, G_D2), massas de C-04/C-09/C-17 | 12 avaliáveis | trem no lugar de Standing (§5) |
| G_in e massa de C-01 | 12 | recombinação: MW do vapor de equilíbrio e gás que o líquido do FWKO libera (§6) |
| O e G das correntes de líquido | 12 | óleo de tanque × gás dissolvido pelo trem |
| Q_pre, Q_H, Q_C, T de C-07/C-08/C-22/C-23 | 1–8 (Q_pre), 12 (Q_C) | C-06 com mais gás dissolvido; óleo tratado menor |
| BSW de C-06 (8: 10,92 → 10,94 %; 12: 34,56 → 34,57 %) | 8, 12 | óleo que sai do FWKO desconta o óleo de tanque vaporizado |
| iterações do reciclo | 2, 3, 8, 10, 12–14 | ponto fixo em dois níveis |
| excesso de diluição (A3): caso 2 0,3668 → 0,3665 | 2, 3 | idem |
| SG-001: Leff +0,0001 %, teto e mecanismo | — | μ do óleo vivo (§7) |
| V-001, V-002, TO-001, TO-002: Leff e caso governante | — | líquido de saída menor (§7) |
| P-002, P-003, B-001/2/3 | — | propagação (§8) |
| telas do terminal (snapshots) | — | os números acima |

**Não mudou**: os 4 casos com gás de lift (bit a bit), os diâmetros de SG-001, V-001, V-002,
TO-001, TO-002, o DN das bombas, o estado do P-001, as fixtures do Julia e o caso-ouro da
película.
