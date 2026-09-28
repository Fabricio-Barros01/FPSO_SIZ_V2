# Fase 5.1 — cascata composicional do trem, em modo sombra

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): a cascata saiu do modo sombra e é o trem do `EstadoProcesso` (`balanco/trem.py`); o relatório vigente é `tools/relatorio_trem.py`. O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Gerado por `tools/cascata_composicional.py`.

> **Modo sombra, integral.** O balanço produtivo, o dimensionamento, os equipamentos e os memoriais continuam intocados; `y`, `β`, `x`, `h`, `cp`, `ρ_líquido`, `μ` e `k` seguem NÃO liberados no mapa de proveniência, e o guarda `exigir_liberada` continua recusando consumo. O que muda em relação à F5 é a ANÁLISE: os três pontos deixam de ser flashes independentes e viram um trem.

## 0. O que a F5.1 muda em relação à F5

| | F5 | F5.1 |
|---|---|---|
| alimentação do V-001 | z₀ (fluido de poço) | x do SG-001 |
| alimentação do V-002 | z₀ (fluido de poço) | x do V-001 |
| quantidade absoluta | não havia | ṅ_V = β·ṅ_F, ṅ_L = (1−β)·ṅ_F |
| fechamento | por flash | por flash **e** do trem inteiro, global e por componente |
| gás de lift | não tratado | lacuna declarada |

## 1. `oil_sm3d`, `produced_gas_sm3d` e `fluid_compositions` são compatíveis?

**Não são, e a incompatibilidade é estrutural.** `fluid_compositions` é por TIPO DE
FLUIDO (sete tipos), e o mesmo tipo aparece em casos com GOR bem diferentes — o flash
de uma composição só não pode reproduzir os dois volumes de todos os casos. A medida
abaixo usa o equilíbrio na condição padrão (15,6 °C, 101,3 kPa, V_M = 23,6999 sm³/kmol) e a ρ do óleo pela API do poço:

| caso | fluido | GOR do BOT | GOR do flash | razão | base pelo gás (kmol/d) | base pelo óleo (kmol/d) | discordância |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | Early Life | 419,3 | 258,9 | 0,62 | 652.485 | 402.971 | 61,9 % |
| 2 | Early Life | 419,3 | 258,9 | 0,62 | 652.485 | 402.971 | 61,9 % |
| 3 | Early Life Blend | 324,9 | 371,4 | 1,14 | 482.649 | 551.739 | 14,3 % |
| 4 | Early Life | 241,9 | 258,9 | 1,07 | 48.936 | 52.376 | 7,0 % |
| 5 | Low CO2 | 185,0 | 194,6 | 1,05 | 53.567 | 56.331 | 5,2 % |
| 6 | Mid Life | 720,0 | 755,3 | 1,05 | 41.888 | 43.943 | 4,9 % |
| 7 | Mid Life | 349,4 | 755,3 | 2,16 | 465.424 | 1.006.146 | 116,2 % |
| 8 | Mid Life | 524,1 | 755,3 | 1,44 | 465.424 | 670.776 | 44,1 % |
| 9 | Mid Life | 533,3 | 755,3 | 1,42 | 372.339 | 527.312 | 41,6 % |
| 10 | Late Life | 652,2 | 1.109,9 | 1,70 | 335.673 | 571.279 | 70,2 % |
| 11 | Late Life | 880,5 | 1.109,9 | 1,26 | 313.295 | 394.928 | 26,1 % |
| 12 | Late Life | 1.117,7 | 1.109,9 | 0,99 | 402.808 | 399.995 | 0,7 % |
| 13 | High CO2 | 963,2 | 944,4 | 0,98 | 420.328 | 412.128 | 2,0 % |
| 14 | High CO2 | 1.242,9 | 944,4 | 0,76 | 542.358 | 412.128 | 31,6 % |
| 15 | Highest CO2 | 1.270,8 | 1.332,7 | 1,05 | 200.854 | 210.634 | 4,9 % |
| 16 | Highest CO2 | 1.271,0 | 1.332,7 | 1,05 | 223.171 | 234.011 | 4,9 % |

A discordância entre as duas bases possíveis vai de **0,7 %** (caso 12) a **116,2 %** (caso 7). Escolher uma delas seria inventar quantidade molar para fechar o flash — que é exatamente o que não se faz aqui.

## 2. A base molar absoluta, declarada

```
    n_F = m_HC,in / MW_z
```

- **massa**: m_HC,in = oil_sm3d·ρ_óleo(API) + produced_gas_sm3d·ρ_gás,padrão — os MESMOS dois termos, com as MESMAS duas massas específicas, que o balanço produtivo põe em C-01
- **MW**: MW_z = Σ_fases (fração molar · MW da fase) do flash do primeiro estágio: o MW da mistura pelos MW ADOTADOS nas entradas e na caracterização (F4), não o MW verdadeiro do petróleo real
- **ρ do óleo**: ρ = (141,5/(131,5 + API))·ρ_água,15,6 °C — API do poço, dado do BOT (o mesmo do balanço)
- **ρ do gás**: ρ = MW_corte_leve / V_M, com V_M = R·T_padrão/P_padrão — a definição de sm³ (o mesmo V_M e o mesmo corte leve do balanço)
- **por que não pelo split**: usar o split de fases na condição padrão para fixar a base exigiria escolher entre a base do gás (n_gás/β) e a base do óleo (n_óleo/(1−β)), que discordam entre 0,7 % e 116 % nos 16 casos. Escolher uma delas seria inventar quantidade molar para fechar o flash.
- **o que isso conserva**: a massa total de hidrocarboneto é a mesma do balanço produtivo (menos o gás de lift, ver a lacuna), então a cascata e o modelo legado partem dos mesmos quilogramas

| caso | fluido | óleo (sm³/d) | gás produzido (sm³/d) | ṁ óleo (kg/d) | ṁ gás (kg/d) | ṁ HC (kg/d) | MW_z (g/mol) | ṅ_F (kmol/d) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Early Life | 28.621 | 12.000.000 | 25.445.419 | 13.600.664 | 39.046.083 | 85,23 | 458.111,7 |
| 2 | Early Life | 28.621 | 12.000.000 | 25.445.419 | 13.600.664 | 39.046.083 | 85,23 | 458.111,7 |
| 3 | Early Life Blend | 28.621 | 9.300.000 | 25.333.886 | 10.204.947 | 35.538.833 | 68,26 | 520.669,8 |
| 4 | Early Life | 3.720 | 900.000 | 3.307.255 | 1.020.050 | 4.327.305 | 85,23 | 50.770,5 |
| 5 | Low CO2 | 4.864 | 900.000 | 4.305.371 | 892.017 | 5.197.388 | 94,24 | 55.152,8 |
| 6 | Mid Life | 1.250 | 900.000 | 1.111.309 | 1.069.351 | 2.180.660 | 52,10 | 41.854,9 |
| 7 | Mid Life | 28.621 | 10.000.000 | 25.445.419 | 11.881.683 | 37.327.102 | 52,10 | 716.444,3 |
| 8 | Mid Life | 19.081 | 10.000.000 | 16.963.909 | 11.881.683 | 28.845.592 | 52,10 | 553.653,0 |
| 9 | Mid Life | 15.000 | 8.000.000 | 13.335.708 | 9.505.346 | 22.841.054 | 52,10 | 438.403,8 |
| 10 | Late Life | 11.500 | 7.500.000 | 10.224.042 | 9.478.190 | 19.702.233 | 47,16 | 417.741,1 |
| 11 | Late Life | 7.950 | 7.000.000 | 7.067.925 | 8.846.311 | 15.914.236 | 47,16 | 337.425,2 |
| 12 | Late Life | 8.052 | 9.000.000 | 7.158.608 | 11.373.828 | 18.532.436 | 47,16 | 392.938,2 |
| 13 | High CO2 | 9.655 | 9.300.000 | 8.583.750 | 12.275.137 | 20.858.887 | 50,95 | 409.394,2 |
| 14 | High CO2 | 9.655 | 12.000.000 | 8.583.750 | 15.838.886 | 24.422.637 | 50,95 | 479.339,3 |
| 15 | Highest CO2 | 3.541 | 4.500.000 | 3.148.116 | 6.722.362 | 9.870.478 | 49,31 | 200.177,0 |
| 16 | Highest CO2 | 3.934 | 5.000.000 | 3.497.512 | 7.469.291 | 10.966.803 | 49,31 | 222.410,9 |

## 3. Gás de lift: lacuna declarada

**Situação: ausente.** Fonte procurada: BOT I-ET-3010.2K-1200-941-P4X-001 rev. C, §2.3.3 (Service and Lift Gas).

- O que a fonte dá: apenas ESPECIFICAÇÃO de envelope — máximo 5 ppmv de H2S, máximo 3 % mol de CO2, máximo 1 ppmv de H2O —, que são limites superiores, não uma composição.
- O que existe na fonte: a composição do gás TRANSFERIDO (GT30/GT40/GT50) está na Tabela 2.3.5.1; ela é de outra corrente, que não entra em C-01, e não pode ser usada como se fosse a do gás de lift.
- Efeito: nos casos com lift_gas_sm3d > 0 o balanço produtivo soma o lift ao gás de entrada (Gin = produced + lift) e converte a massa com a ρ_padrão do CORTE LEVE DO FLUIDO DE POÇO, isto é, atribui ao gás de lift a composição do poço. A cascata em sombra NÃO faz isso: ela exclui o lift da base molar e declara a lacuna.
- Decisão: **não supor composição. A base molar da cascata usa só o gás produzido; a diferença em relação ao balanço é reportada caso a caso.**

Casos afetados (4 de 16):

| caso | fluido | gás produzido (sm³/d) | gás de lift (sm³/d) | lift / gás de entrada | ṅ_F da cascata cobre |
|---:|---|---:|---:|---:|---|
| 9 | Mid Life | 8.000.000 | 2.000.000 | 20,0 % | só o gás produzido |
| 11 | Late Life | 7.000.000 | 2.000.000 | 22,2 % | só o gás produzido |
| 15 | Highest CO2 | 4.500.000 | 2.000.000 | 30,8 % | só o gás produzido |
| 16 | Highest CO2 | 5.000.000 | 2.000.000 | 28,6 % | só o gás produzido |

Nesses casos a cascata em sombra e o balanço produtivo **não partem da mesma massa**: a diferença é exatamente a massa de gás de lift, à qual o balanço atribui a composição do poço por falta de outra. Isso não é corrigido aqui — é registrado.

## 4. A sequência dos três estágios (caso 1 — Early Life)

| estágio | corrente | T (°C) | P (kPa) | β | ṅ_V (kmol/d) | ṁ_V (kg/d) | ṅ_L (kmol/d) | ṁ_L (kg/d) | MW_V | Z_V | ρ_V (kg/m³) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SG-001 | C-04 | 65,00 | 2.500,0 | 0,670207 | 307.029,6 | 8.105.422 | 151.082,1 | 30.940.661 | 26,399 | 0,93462 | 25,1164 |
| V-001 | C-09 | 90,00 | 700,0 | 0,220390 | 33.296,9 | 1.187.016 | 117.785,2 | 29.753.645 | 35,649 | 0,97106 | 8,5110 |
| V-002 | C-17 | 90,00 | 200,0 | 0,091096 | 10.729,8 | 524.269 | 107.055,4 | 29.229.377 | 48,861 | 0,98176 | 3,2966 |

Composições (fração molar; os 8 componentes de maior fração na alimentação):

| componente | y SG-001 | x SG-001 | y V-001 | x V-001 | y V-002 | x V-002 |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 0,616315 | 0,094400 | 0,373053 | 0,015628 | 0,152961 | 0,001863 |
| CO2 | 0,224747 | 0,076016 | 0,264618 | 0,022700 | 0,199071 | 0,005023 |
| C20+ | 0,000000 | 0,213766 | 0,000000 | 0,274196 | 0,000000 | 0,301678 |
| C2 | 0,080083 | 0,037074 | 0,118187 | 0,014143 | 0,114632 | 0,004072 |
| C3 | 0,043660 | 0,047416 | 0,110018 | 0,029720 | 0,179812 | 0,014676 |
| C8 | 0,001197 | 0,056088 | 0,007025 | 0,069958 | 0,022849 | 0,074679 |
| nC4 | 0,011997 | 0,030501 | 0,043888 | 0,026717 | 0,102260 | 0,019146 |
| C10 | 0,000176 | 0,043001 | 0,001127 | 0,054839 | 0,003606 | 0,059974 |

A alimentação de cada estágio é o **líquido** do anterior: z₀ → x(SG-001) → x(V-001).

## 5. Fechamento do trem

```
    ṅ_HC,in = ṅ_V,F + ṅ_V,1 + ṅ_V,2 + ṅ_L,final          (global)
    ṅ_F·z_i = Σ_e ṅ_V,e·y_i,e + ṅ_L,final·x_i,final       (componente a componente)
```

| caso | estágios | completa | erro molar rel. | erro mássico rel. | erro por componente | pior componente | pior fechamento de flash |
|---:|---:|:--:|---:|---:|---:|---|---:|
| 1 | 3 | sim | 0.00e+00 | 0.00e+00 | 6.35e-17 | C1 | 5.55e-17 |
| 2 | 3 | sim | 1.27e-16 | 1.91e-16 | 1.27e-16 | C1 | 1.11e-16 |
| 3 | 3 | sim | 0.00e+00 | 2.10e-16 | 2.79e-17 | CO2 | 5.55e-17 |
| 4 | 3 | sim | 0.00e+00 | 2.15e-16 | 3.58e-17 | CO2 | 2.78e-17 |
| 5 | 3 | sim | 0.00e+00 | 1.79e-16 | 6.60e-17 | C1 | 5.55e-17 |
| 6 | 3 | sim | 1.74e-16 | 0.00e+00 | 1.09e-17 | C20+ | 1.39e-17 |
| 7 | 3 | sim | 0.00e+00 | 0.00e+00 | 1.02e-17 | C20+ | 5.55e-17 |
| 8 | 3 | sim | 0.00e+00 | 1.29e-16 | 1.05e-16 | C1 | 1.11e-16 |
| 9 | 3 | sim | 0.00e+00 | 0.00e+00 | 6.64e-17 | C1 | 6.94e-18 |
| 10 | 3 | sim | 0.00e+00 | 1.89e-16 | 8.71e-18 | C2 | 5.55e-17 |
| 11 | 3 | sim | 1.73e-16 | 1.17e-16 | 8.63e-17 | C1 | 5.55e-17 |
| 12 | 3 | sim | 0.00e+00 | 0.00e+00 | 7.41e-17 | CO2 | 5.55e-17 |
| 13 | 3 | sim | 1.42e-16 | 1.79e-16 | 1.78e-17 | C2 | 5.55e-17 |
| 14 | 3 | sim | 0.00e+00 | 0.00e+00 | 6.07e-17 | CO2 | 5.55e-17 |
| 15 | 3 | sim | 0.00e+00 | 0.00e+00 | 3.63e-17 | C1 | 2.78e-17 |
| 16 | 3 | sim | 0.00e+00 | 1.70e-16 | 6.54e-17 | CO2 | 1.11e-16 |

**Pior caso do conjunto:** molar 1.74e-16, mássico 2.15e-16, componente a componente 1.27e-16, fechamento de flash isolado 1.11e-16 — tudo na precisão da máquina.

## 6. F5 (flashes independentes) × F5.1 (cascata) × Standing legado

Os três não medem a mesma coisa, e é isso que a tabela mostra:

- **F5**: flash de z₀ em cada (T, P), como se cada vaso recebesse o fluido de poço;
- **F5.1**: flash da alimentação REAL de cada vaso (o líquido do anterior);
- **Standing**: ΔRs sobre a vazão de óleo — gás que sai de solução, não fração de fase.

| caso | estágio | β (F5) | β (F5.1) | ṅ_V F5 (kmol/d) | ṅ_V F5.1 (kmol/d) | ṅ_V Standing (kmol/d) | ṁ_V F5.1 (kg/d) | ṁ_V Standing (kg/d) | MW_V F5.1 | Z_V F5.1 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | SG-001 | 0,670207 | 0,670207 | 307.029,6 | 307.029,6 | 493.306,2 | 8.105.422 | 13.250.801 | 26,399 | 0,93462 |
| 1 | V-001 | 0,774943 | 0,220390 | 355.010,3 | 33.296,9 | 10.884,2 | 1.187.016 | 292.363 | 35,649 | 0,97106 |
| 1 | V-002 | 0,813876 | 0,091096 | 372.846,1 | 10.729,8 | 2.140,6 | 524.269 | 57.500 | 48,861 | 0,98176 |
| 2 | SG-001 | 0,653125 | 0,653125 | 299.204,1 | 299.204,1 | 492.492,8 | 7.761.644 | 13.228.953 | 25,941 | 0,92874 |
| 2 | V-001 | 0,774943 | 0,251342 | 355.010,3 | 39.940,1 | 11.697,6 | 1.445.184 | 314.211 | 36,184 | 0,97012 |
| 2 | V-002 | 0,813876 | 0,094678 | 372.846,1 | 11.263,6 | 2.140,6 | 556.756 | 57.500 | 49,430 | 0,98122 |
| 3 | SG-001 | 0,712345 | 0,712345 | 370.896,4 | 370.896,4 | 378.690,5 | 9.376.359 | 9.848.246 | 25,280 | 0,92941 |
| 3 | V-001 | 0,815344 | 0,236692 | 424.525,2 | 35.450,1 | 11.592,7 | 1.283.598 | 301.480 | 36,209 | 0,96883 |
| 3 | V-002 | 0,848013 | 0,095579 | 441.534,8 | 10.926,9 | 2.123,4 | 546.430 | 55.221 | 50,008 | 0,98017 |
| 4 | SG-001 | 0,641009 | 0,641009 | 32.544,4 | 32.544,4 | 36.106,6 | 834.713 | 969.867 | 25,648 | 0,92464 |
| 4 | V-001 | 0,774943 | 0,273538 | 39.344,2 | 4.985,5 | 1.590,0 | 181.811 | 42.709 | 36,468 | 0,96964 |
| 4 | V-002 | 0,813876 | 0,096522 | 41.320,9 | 1.278,0 | 278,2 | 63.504 | 7.474 | 49,690 | 0,98098 |
| 5 | SG-001 | 0,535349 | 0,535349 | 29.526,0 | 29.526,0 | 35.676,3 | 611.807 | 838.025 | 20,721 | 0,92266 |
| 5 | V-001 | 0,705381 | 0,270903 | 38.903,7 | 6.942,4 | 1.972,6 | 231.621 | 46.336 | 33,363 | 0,96543 |
| 5 | V-002 | 0,752559 | 0,106425 | 41.505,8 | 1.988,5 | 325,9 | 97.431 | 7.656 | 48,997 | 0,97821 |
| 6 | SG-001 | 0,818315 | 0,818315 | 34.250,5 | 34.250,5 | 37.283,7 | 948.033 | 1.049.889 | 27,679 | 0,91180 |
| 6 | V-001 | 0,910787 | 0,345480 | 38.120,9 | 2.627,2 | 593,2 | 105.108 | 16.703 | 40,008 | 0,96518 |
| 6 | V-002 | 0,929507 | 0,115607 | 38.904,4 | 575,4 | 98,0 | 30.759 | 2.760 | 53,456 | 0,97800 |
| 7 | SG-001 | 0,861501 | 0,861501 | 617.217,9 | 617.217,9 | 408.948,5 | 17.766.698 | 11.515.779 | 28,785 | 0,93584 |
| 7 | V-001 | 0,910787 | 0,208256 | 652.528,5 | 20.664,5 | 10.749,9 | 770.075 | 302.712 | 37,266 | 0,97090 |
| 7 | V-002 | 0,929507 | 0,091964 | 665.940,1 | 7.224,8 | 2.244,1 | 361.399 | 63.193 | 50,022 | 0,98173 |
| 8 | SG-001 | 0,851166 | 0,851166 | 471.250,6 | 471.250,6 | 412.753,6 | 13.415.601 | 11.622.928 | 28,468 | 0,92967 |
| 8 | V-001 | 0,910787 | 0,240052 | 504.260,1 | 19.780,8 | 7.692,8 | 755.113 | 216.626 | 38,174 | 0,96906 |
| 8 | V-002 | 0,929507 | 0,099191 | 514.624,4 | 6.211,5 | 1.496,1 | 318.612 | 42.129 | 51,294 | 0,98041 |
| 9 | SG-001 | 0,855469 | 0,855469 | 375.040,8 | 375.040,8 | 414.886,2 | 10.724.140 | 11.682.981 | 28,595 | 0,93221 |
| 9 | V-001 | 0,910787 | 0,226600 | 399.292,7 | 14.358,0 | 5.880,2 | 542.964 | 165.584 | 37,816 | 0,96979 |
| 9 | V-002 | 0,929507 | 0,096258 | 407.499,4 | 4.717,1 | 1.176,1 | 239.651 | 33.119 | 50,804 | 0,98093 |
| 10 | SG-001 | 0,922184 | 0,922184 | 385.234,3 | 385.234,3 | 311.306,1 | 11.892.152 | 9.323.921 | 30,870 | 0,94289 |
| 10 | V-001 | 0,945480 | 0,181965 | 394.965,8 | 5.915,1 | 4.192,3 | 218.020 | 125.564 | 36,858 | 0,97524 |
| 10 | V-002 | 0,955627 | 0,078098 | 399.204,6 | 2.076,8 | 958,4 | 97.260 | 28.705 | 46,833 | 0,98607 |
| 11 | SG-001 | 0,905213 | 0,905213 | 305.441,6 | 305.441,6 | 375.602,3 | 9.264.167 | 11.249.654 | 30,330 | 0,92588 |
| 11 | V-001 | 0,945456 | 0,258813 | 319.020,7 | 8.277,8 | 3.482,9 | 324.173 | 104.318 | 39,162 | 0,97080 |
| 11 | V-002 | 0,955609 | 0,093646 | 322.446,6 | 2.220,0 | 663,0 | 112.166 | 19.857 | 50,526 | 0,98250 |
| 12 | SG-001 | 0,922187 | 0,922187 | 362.362,4 | 362.362,4 | 376.141,9 | 11.186.135 | 11.265.816 | 30,870 | 0,94290 |
| 12 | V-001 | 0,945481 | 0,181960 | 371.515,8 | 5.563,6 | 2.935,3 | 205.064 | 87.915 | 36,858 | 0,97524 |
| 12 | V-002 | 0,955628 | 0,078095 | 375.502,7 | 1.953,3 | 671,0 | 91.480 | 20.098 | 46,833 | 0,98607 |
| 13 | SG-001 | 0,910141 | 0,910141 | 372.606,5 | 372.606,5 | 387.890,1 | 11.957.964 | 12.133.855 | 32,093 | 0,94214 |
| 13 | V-001 | 0,936048 | 0,184508 | 383.212,6 | 6.787,6 | 3.676,1 | 255.315 | 114.993 | 37,615 | 0,97596 |
| 13 | V-002 | 0,947546 | 0,075647 | 387.919,8 | 2.269,4 | 840,4 | 105.713 | 26.288 | 46,581 | 0,98711 |
| 14 | SG-001 | 0,910140 | 0,910140 | 436.265,7 | 436.265,7 | 501.814,5 | 14.000.934 | 15.697.602 | 32,093 | 0,94213 |
| 14 | V-001 | 0,936047 | 0,184511 | 448.684,1 | 7.947,6 | 3.676,1 | 298.947 | 114.995 | 37,615 | 0,97596 |
| 14 | V-002 | 0,947545 | 0,075649 | 454.195,7 | 2.657,3 | 840,4 | 123.778 | 26.289 | 46,581 | 0,98711 |
| 15 | SG-001 | 0,924858 | 0,924858 | 185.135,3 | 185.135,3 | 272.387,5 | 6.714.568 | 9.643.690 | 36,268 | 0,93384 |
| 15 | V-001 | 0,949050 | 0,201292 | 189.977,9 | 3.027,8 | 1.526,2 | 124.453 | 54.034 | 41,104 | 0,97371 |
| 15 | V-002 | 0,960067 | 0,081443 | 192.183,3 | 978,5 | 348,9 | 48.058 | 12.354 | 49,117 | 0,98632 |
| 16 | SG-001 | 0,924861 | 0,924861 | 205.699,1 | 205.699,1 | 293.276,5 | 7.460.407 | 10.383.254 | 36,269 | 0,93384 |
| 16 | V-001 | 0,949051 | 0,201285 | 211.079,4 | 3.363,8 | 1.695,5 | 138.266 | 60.030 | 41,104 | 0,97371 |
| 16 | V-002 | 0,960068 | 0,081440 | 213.529,6 | 1.087,1 | 387,7 | 53.393 | 13.725 | 49,117 | 0,98632 |

## 7. Desempenho — medido, não otimizado

Nenhum cache foi implementado nesta fase; o número abaixo é o do custo real.

| grandeza | valor |
|---|---:|
| cascatas rodadas | 16 |
| flashes | 48 |
| condições (T, P, z) distintas | 48 |
| fator de recomputação | 1,000 |
| custo total | 1,165 s |
| custo por flash | 24,28 ms |

Condições repetidas: **0** — casos do mesmo fluido que caem no mesmo (T, P, z). A recomputação é medida e fica registrada; eliminá-la é decisão de outra fase.

## 8. O que ainda impede a ativação

1. **A base molar não reconcilia com o split do BOT.** A regra declarada conserva a massa do balanço produtivo, mas a composição z₀ não reproduz `oil_sm3d` e `produced_gas_sm3d` do caso (§1). Ativar `β`, `y` ou `x` trocaria a vazão de gás por estágio pelo valor da cascata, e o balanço de massa da planta deixaria de fechar contra o BOT enquanto essa incompatibilidade existir.
2. **Gás de lift sem composição** (§3): nos casos 9, 11, 15 e 16 a cascata e o balanço produtivo não partem da mesma massa.
3. **`h` e `cp` continuam ausentes**: sem eles não há balanço de energia pela EOS, e as cargas térmicas seguem no caminho legado.
4. **ρ da fase líquida continua em (c)** da invariante 5 — devolvida pelo backend, não validada, não propagada.

Regra da base molar, como consta no TOML: `n_F = m_HC,in / MW_z` — kmol/d.

