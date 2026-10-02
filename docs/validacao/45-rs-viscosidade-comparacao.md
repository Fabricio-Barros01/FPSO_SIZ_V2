# 45 — Fase B: μ do óleo vivo com o Rs do trem × com o Rs da rota anterior (Standing)

> **Estado: ENCERRADA como sensibilidade documentada (decisão do usuário, 2026-10-02).** A rota
> vigente fica: Rs do trem → Beggs & Robinson nos casos avaliáveis e Standing, identificado, nos
> casos sem flash avaliável (9, 11, 15, 16). **Justificativa: consistência das bases e do modelo** —
> o Rs é o gás que o líquido do próprio trem libera até o tanque, na condição padrão da correlação,
> pela mesma composição que o balanço usa (§2). **Não** é justificativa o fato de essa rota
> viabilizar o P-001. A rota de Standing fica como sensibilidade. A §6 usa a comparação do
> dimensionamento; o rating com a geometria congelada, que separa insuficiência para a carga de
> incapacidade de operar, está na nota 46 (Fase C).

## 1. Como foi comparado

`tools/comparar_rs_viscosidade.py`. A rota anterior é reconstruída como ESTUDO e aplicada **só à
viscosidade**: o Rs de cada corrente vem do balanço de Standing — o mesmo caminho que o balanço usa
hoje nos casos com gás de lift, ligado nos 16 casos — e todo o resto (correntes, cargas, gás por
estágio, temperaturas) continua sendo o do trem nas duas colunas. A μ é calculada pela mesma função
do serviço (`termo.oleo`) na temperatura que cada TAG pede, inclusive no ponto fixo da integração
realizada do P-001. Nos casos **9, 11, 15 e 16** (gás de lift sem composição, sem flash avaliável)
as duas rotas são Standing e coincidem bit a bit.

## 2. Bases conferidas

| item | situação |
|---|---|
| condição padrão | arquivo de casos: 15,6 °C e 101,3 kPa; Beggs & Robinson: 60 °F (15,56 °C) e 14,696 psia (101,325 kPa). Mesma base (0,02 % em P) |
| definição do Rs | gás que o líquido da corrente libera num flash único até a condição padrão (Sm³), dividido pelo volume padrão do óleo de tanque da corrente (m³; ρ padrão pelo API do BOT). É a razão gás-óleo em solução até o tanque, a grandeza que a correlação recebe |
| unidades | Sm³/Sm³ → scf/STB pelos fatores exatos (barril, pé cúbico) de `core/unidades.py` |
| faixa | Rs 20–2.070 scf/STB, API 16–58, T 70–295 °F (`termo/fluidos.toml`). Abaixo de 20 scf/STB a μ do óleo morto do BOT é mantida (conservador para decantação) |
| natureza do gás | a correlação recebe só o volume de gás dissolvido; o gás aqui é rico em CO2 e a fonte (fora do acervo) não demonstra aplicabilidade a ele — limitação já declarada na nota 40 |

Consequências das bases que a tabela 3 mostra: a jusante do V-002 (C-18, C-21, C-22, C-23) o óleo
tem TVP abaixo da pressão padrão, não libera gás no tanque e o Rs é **zero** nas duas rotas; no
C-10 (saída do V-001) o Rs do trem é 11–13 scf/STB, **abaixo** da faixa da correlação, e a μ é a
do óleo morto nas duas rotas. A diferença de rota só age onde há gás dissolvido de fato: C-06 e
C-07 (saída do FWKO), onde o trem dá 1,9 a 4,1 vezes o Rs de Standing.

## 3. Rs por corrente (scf/STB): trem → Standing

| caso | C-06 | C-07 | C-10 | C-18 | C-21 | C-22 | C-23 |
|---:|---|---|---|---|---|---|---|
| 1 | 157,9 → 60,6 | 157,9 → 60,6 | 11,8 → 5,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 2 | 183,7 → 64,3 | 183,7 → 64,3 | 11,9 → 5,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 3 | 194,7 → 63,8 | 194,7 → 63,8 | 11,8 → 5,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 4 | 204,3 → 66,8 | 204,3 → 66,8 | 12,0 → 5,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 5 | 214,8 → 62,9 | 214,8 → 62,9 | 10,9 → 5,2 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 6 | 303,9 → 73,6 | 303,9 → 73,6 | 13,0 → 6,1 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 7 | 156,7 → 60,4 | 156,7 → 60,4 | 12,4 → 6,1 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 8 | 187,6 → 64,2 | 187,6 → 64,2 | 12,6 → 6,1 | 0,0 → -0,0 | 0,0 → -0,0 | 0,0 → -0,0 | 0,0 → -0,0 |
| 9 (Standing) | 62,7 → 62,7 | 62,7 → 62,7 | 6,1 → 6,1 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 10 | 115,4 → 59,8 | 115,4 → 59,8 | 11,4 → 6,5 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 11 (Standing) | 69,8 → 69,8 | 69,8 → 69,8 | 6,6 → 6,6 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 12 | 115,7 → 59,9 | 115,7 → 59,9 | 11,4 → 6,5 | 0,0 → -0,0 | 0,0 → -0,0 | 0,0 → -0,0 | 0,0 → -0,0 |
| 13 | 116,2 → 62,5 | 116,2 → 62,5 | 11,6 → 6,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 14 | 116,2 → 62,5 | 116,2 → 62,5 | 11,6 → 6,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 15 (Standing) | 71,6 → 71,6 | 71,6 → 71,6 | 7,8 → 7,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |
| 16 (Standing) | 71,5 → 71,5 | 71,5 → 71,5 | 7,8 → 7,8 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 |

## 4. μ do óleo nas entradas dos TAGs (cP): Rs do trem → Rs de Standing

**B-001 `mu_oil`** (μ de C-21, Rs de C-21)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 7,900 | 7,900 | 0,0 % |
| 2 | 7,944 | 7,944 | 0,0 % |
| 3 | 6,335 | 6,335 | 0,0 % |
| 4 | 7,900 | 7,900 | 0,0 % |
| 5 | 6,300 | 6,300 | 0,0 % |
| 6 | 7,900 | 7,900 | 0,0 % |
| 7 | 7,900 | 7,900 | 0,0 % |
| 8 | 7,944 | 7,944 | 0,0 % |
| 9 | 7,944 | 7,944 | 0,0 % |
| 10 | 7,944 | 7,944 | 0,0 % |
| 11 | 7,944 | 7,944 | 0,0 % |
| 12 | 7,944 | 7,944 | 0,0 % |
| 13 | 7,944 | 7,944 | 0,0 % |
| 14 | 7,944 | 7,944 | 0,0 % |
| 15 | 7,944 | 7,944 | 0,0 % |
| 16 | 7,944 | 7,944 | 0,0 % |

**P-001 `mu_tubo`** (μ de C-06, Rs de C-06)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 3,106 | 4,951 | 59,4 % |
| 2 | 3,313 | 5,610 | 69,3 % |
| 3 | 2,601 | 4,549 | 74,9 % |
| 4 | 3,269 | 5,889 | 80,1 % |
| 5 | 3,158 | 5,551 | 75,8 % |
| 6 | 2,715 | 6,674 | 145,8 % |
| 7 | 3,120 | 4,955 | 58,8 % |
| 8 | 3,271 | 5,612 | 71,6 % |
| 9 | 6,078 | 6,078 | 0,0 % |
| 11 | 8,875 | 8,875 | 0,0 % |

**P-001 `mu_casco`** (μ de C-22, Rs de C-22)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 7,900 | 7,900 | 0,0 % |
| 2 | 7,944 | 7,944 | 0,0 % |
| 3 | 6,335 | 6,335 | 0,0 % |
| 4 | 7,900 | 7,900 | 0,0 % |
| 5 | 6,300 | 6,663 | 5,8 % |
| 6 | 8,418 | 8,418 | 0,0 % |
| 7 | 7,900 | 7,900 | 0,0 % |
| 8 | 7,944 | 7,944 | 0,0 % |
| 9 | 7,944 | 7,944 | 0,0 % |
| 11 | 7,944 | 7,944 | 0,0 % |

**P-002 `mu_casco`** (μ de C-07, Rs de C-07)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 3,106 | 4,951 | 59,4 % |
| 2 | 2,919 | 4,977 | 70,5 % |
| 3 | 2,374 | 4,088 | 72,2 % |
| 4 | 2,646 | 4,766 | 80,2 % |
| 5 | 2,166 | 3,992 | 84,3 % |
| 6 | 2,020 | 4,583 | 126,9 % |
| 7 | 3,120 | 4,955 | 58,8 % |
| 8 | 3,236 | 5,551 | 71,5 % |
| 9 | 6,064 | 6,064 | 0,0 % |
| 11 | 7,707 | 7,707 | 0,0 % |

**P-003 `mu_casco`** (μ de C-23, Rs de C-23)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 11,382 | 11,382 | 0,0 % |
| 2 | 13,432 | 13,962 | 3,9 % |
| 3 | 10,511 | 10,511 | 0,0 % |
| 4 | 14,970 | 15,907 | 6,3 % |
| 5 | 11,821 | 13,987 | 18,3 % |
| 6 | 19,143 | 19,143 | 0,0 % |
| 7 | 9,779 | 9,779 | 0,0 % |
| 8 | 11,809 | 11,809 | 0,0 % |
| 9 | 10,931 | 10,931 | 0,0 % |
| 10 | 9,076 | 9,076 | 0,0 % |
| 11 | 12,512 | 12,512 | 0,0 % |
| 12 | 9,075 | 9,075 | 0,0 % |
| 13 | 9,075 | 9,075 | 0,0 % |
| 14 | 9,076 | 9,076 | 0,0 % |
| 15 | 9,081 | 9,081 | 0,0 % |
| 16 | 9,081 | 9,081 | 0,0 % |

**SG-001 `mu_oil`** (μ de C-03, Rs de C-06)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 3,473 | 5,620 | 61,8 % |
| 2 | 4,214 | 7,677 | 82,2 % |
| 3 | 3,267 | 5,997 | 83,6 % |
| 4 | 4,786 | 9,596 | 100,5 % |
| 5 | 4,800 | 10,371 | 116,1 % |
| 6 | 4,584 | 12,982 | 183,2 % |
| 7 | 3,120 | 4,955 | 58,8 % |
| 8 | 3,247 | 5,770 | 77,7 % |
| 9 | 5,159 | 5,159 | 0,0 % |
| 10 | 3,704 | 4,975 | 34,3 % |
| 11 | 6,106 | 6,106 | 0,0 % |
| 12 | 3,699 | 4,970 | 34,4 % |
| 13 | 3,691 | 4,892 | 32,5 % |
| 14 | 3,691 | 4,892 | 32,5 % |
| 15 | 4,634 | 4,634 | 0,0 % |
| 16 | 4,638 | 4,638 | 0,0 % |

**TO-001 `mu_oil`** (μ de C-10, Rs de C-10)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 7,900 | 7,900 | 0,0 % |
| 2 | 7,900 | 7,900 | 0,0 % |
| 3 | 6,300 | 6,300 | 0,0 % |
| 4 | 7,900 | 7,900 | 0,0 % |
| 5 | 6,300 | 6,300 | 0,0 % |
| 6 | 7,900 | 7,900 | 0,0 % |
| 7 | 7,900 | 7,900 | 0,0 % |
| 8 | 7,900 | 7,900 | 0,0 % |
| 9 | 7,900 | 7,900 | 0,0 % |
| 10 | 7,900 | 7,900 | 0,0 % |
| 11 | 7,900 | 7,900 | 0,0 % |
| 12 | 7,900 | 7,900 | 0,0 % |
| 13 | 7,900 | 7,900 | 0,0 % |
| 14 | 7,900 | 7,900 | 0,0 % |
| 15 | 7,900 | 7,900 | 0,0 % |
| 16 | 7,900 | 7,900 | 0,0 % |

**TO-002 `mu_oil`** (μ de C-18, Rs de C-18)

| caso | trem | Standing | variação |
|---:|---:|---:|---:|
| 1 | 7,900 | 7,900 | 0,0 % |
| 2 | 7,900 | 7,900 | 0,0 % |
| 3 | 6,300 | 6,300 | 0,0 % |
| 4 | 7,900 | 7,900 | 0,0 % |
| 5 | 6,300 | 6,300 | 0,0 % |
| 6 | 7,900 | 7,900 | 0,0 % |
| 7 | 7,900 | 7,900 | 0,0 % |
| 8 | 7,900 | 7,900 | 0,0 % |
| 9 | 7,900 | 7,900 | 0,0 % |
| 10 | 7,900 | 7,900 | 0,0 % |
| 11 | 7,900 | 7,900 | 0,0 % |
| 12 | 7,900 | 7,900 | 0,0 % |
| 13 | 7,900 | 7,900 | 0,0 % |
| 14 | 7,900 | 7,900 | 0,0 % |
| 15 | 7,900 | 7,900 | 0,0 % |
| 16 | 7,900 | 7,900 | 0,0 % |

## 5. Efeito por caso e por equipamento

Somas entre casos são indicador comparativo, não demanda simultânea.

| caso | TVP trem (kPa) | TVP Standing (kPa) | Q P-001 balanço antes → depois (kW) | Q P-001 realizado antes → depois (kW) | Q_H P-002 (kW) | Q_C P-003 (kW) | Q DWH-001 (kW) | W bombas (kW) |
|---:|---:|---:|---|---|---|---|---|---|
| 1 | 60,5 | 60,5 | 8.977,9 → 8.977,9 | 8.977,9 → — | 6.284,4 → 6.284,4 | 20.222,6 → 20.222,6 | 0,0 → 0,0 | 311,0 → 311,0 |
| 2 | 60,0 | 60,0 | 16.235,4 → 16.235,4 | 14.837,4 → — | 9.248,5 → 7.850,5 | 14.613,5 → 13.215,5 | 2.894,3 → 2.894,3 | 369,7 → 369,7 |
| 3 | 56,6 | 56,6 | 16.002,3 → 16.002,3 | 16.002,3 → — | 7.989,5 → 7.989,5 | 13.168,1 → 13.168,1 | 2.890,7 → 2.890,7 | 368,0 → 368,0 |
| 4 | 59,7 | 59,7 | 2.661,2 → 2.661,2 | 2.415,6 → — | 1.195,2 → 949,6 | 1.368,8 → 1.123,2 | 0,0 → 0,0 | 40,3 → 40,3 |
| 5 | 56,0 | 56,0 | 4.416,2 → 4.416,2 | 3.434,5 → — | 2.358,5 → 1.376,8 | 1.466,6 → 484,9 | 0,0 → 0,0 | 52,4 → 52,4 |
| 6 | 55,7 | 55,7 | 1.130,9 → 1.130,9 | 1.130,9 → — | 386,9 → 386,9 | 124,2 → 124,2 | 0,0 → 0,0 | 13,4 → 13,4 |
| 7 | 59,7 | 59,7 | 3.194,9 → 3.194,9 | 3.194,9 → — | 5.951,5 → 5.951,5 | 25.959,7 → 25.959,7 | 0,0 → 0,0 | 310,5 → 310,5 |
| 8 | 58,0 | 58,0 | 6.746,8 → 6.746,8 | 6.746,8 → — | 7.079,5 → 7.079,5 | 12.762,0 → 12.762,0 | 1.923,5 → 1.923,5 | 310,2 → 310,2 |
| 9 | não verificada | não verificada | 3.952,5 → 3.952,5 | 3.952,5 → — | 5.963,5 → 5.963,5 | 11.787,5 → 11.787,5 | 1.524,3 → 1.524,3 | 290,0 → 290,0 |
| 10 | 66,1 | 66,1 | 0,0 → 0,0 | 0,0 → — | 0,0 → 0,0 | 11.947,0 → 11.947,0 | 1.164,5 → 1.164,5 | 246,8 → 246,8 |
| 11 | não verificada | não verificada | 3.462,3 → 3.462,3 | 3.462,3 → — | 7.369,4 → 7.369,4 | 4.844,4 → 4.844,4 | 804,5 → 804,5 | 245,1 → 245,1 |
| 12 | 66,1 | 66,1 | 0,0 → 0,0 | 0,0 → — | 0,0 → 0,0 | 8.337,7 → 8.337,7 | 812,6 → 812,6 | 244,7 → 244,7 |
| 13 | 67,6 | 67,6 | 0,0 → 0,0 | 0,0 → — | 0,0 → 0,0 | 10.023,7 → 10.023,7 | 976,0 → 976,0 | 254,8 → 254,8 |
| 14 | 67,6 | 67,6 | 0,0 → 0,0 | 0,0 → — | 0,0 → 0,0 | 10.022,8 → 10.022,8 | 976,0 → 976,0 | 254,8 → 254,8 |
| 15 | não verificada | não verificada | 0,0 → 0,0 | 0,0 → — | 0,0 → 0,0 | 3.662,0 → 3.662,0 | 354,3 → 354,3 | 123,6 → 123,6 |
| 16 | não verificada | não verificada | 0,0 → 0,0 | 0,0 → — | 0,0 → 0,0 | 4.077,3 → 4.077,3 | 394,4 → 394,4 | 137,6 → 137,6 |

| TAG | grandeza | antes | depois | variação | governante antes → depois |
|---|---|---:|---:|---:|---|
| B-001 | Diâmetro nominal DN [mm] | 600,000 | 600,000 | 0,0 % | carga estática (BOT 03 — Early Life Blend) → carga estática (BOT 03 — Early Life Blend) |
| B-001 | Carga do sistema H [m] | 83,058 | 83,058 | 0,0 % |  |
| B-001 | Potência nominal requerida [kW] | 337,241 | 337,241 | 0,0 % |  |
| B-002 | Diâmetro nominal DN [mm] | 250,000 | 250,000 | 0,0 % | carga estática (BOT 02 — Early Life) → carga estática (BOT 02 — Early Life) |
| B-002 | Carga do sistema H [m] | 202,183 | 202,183 | 0,0 % |  |
| B-002 | Potência nominal requerida [kW] | 157,911 | 157,911 | 0,0 % |  |
| B-003 | Diâmetro nominal DN [mm] | 125,000 | 125,000 | 0,0 % | carga estática (BOT 02 — Early Life) → carga estática (BOT 02 — Early Life) |
| B-003 | Carga do sistema H [m] | 259,338 | 259,338 | 0,0 % |  |
| B-003 | Potência nominal requerida [kW] | 46,609 | 46,609 | 0,0 % |  |
| P-001 | estado | dimensionado | inviavel | | área de troca térmica (BOT 03 — Early Life Blend) → none () |
| P-001 | Tubos por passe | 392,000 | — |  | área de troca térmica (BOT 03 — Early Life Blend) → none () |
| P-001 | Comprimento do tubo L [m] | 5,851 | — |  |  |
| P-001 | Fração da carga do balanço realizada | 0,961 | — |  |  |
| P-001 | area_total | 4.392,549 | — |  |  |
| P-001 | area_instalada | 5.490,687 | — |  |  |
| P-002 | Tubos por passe | 1.917,000 | 1.777,000 | -7,3 % | área de troca térmica (BOT 02 — Early Life) → área de troca térmica (BOT 02 — Early Life) |
| P-002 | Comprimento do tubo L [m] | 5,994 | 5,991 | -0,1 % |  |
| P-002 | area_total | 458,446 | 424,728 | -7,4 % |  |
| P-002 | area_instalada | 458,446 | 424,728 | -7,4 % |  |
| P-003 | Tubos por passe | 7.370,000 | 7.370,000 | 0,0 % | área de troca térmica (BOT 07 — Mid Life) → área de troca térmica (BOT 07 — Mid Life) |
| P-003 | Comprimento do tubo L [m] | 4,912 | 4,912 | 0,0 % |  |
| P-003 | area_total | 1.444,355 | 1.444,355 | 0,0 % |  |
| P-003 | area_instalada | 1.444,355 | 1.444,355 | 0,0 % |  |
| SG-001 | Diâmetro d [mm] | 6.050,000 | 6.050,000 | 0,0 % | capacidade de líquido (BOT 12 — Late Life) → capacidade de líquido (BOT 12 — Late Life) |
| SG-001 | volume | 684,830 | 684,830 | 0,0 % |  |
| TO-001 | Diâmetro d [mm] | 5.550,000 | 5.550,000 | 0,0 % | capacidade de líquido (retenção) (BOT 02 — Early Life) → capacidade de líquido (retenção) (BOT 02 — Early Life) |
| TO-001 | volume | 529,710 | 529,710 | 0,0 % |  |
| TO-002 | Diâmetro d [mm] | 5.550,000 | 5.550,000 | 0,0 % | capacidade de líquido (retenção) (BOT 02 — Early Life) → capacidade de líquido (retenção) (BOT 02 — Early Life) |
| TO-002 | volume | 527,626 | 527,626 | 0,0 % |  |
| V-001 | Diâmetro d [mm] | 4.700,000 | 4.700,000 | 0,0 % | capacidade de líquido (BOT 02 — Early Life) → capacidade de líquido (BOT 02 — Early Life) |
| V-001 | volume | 283,849 | 283,849 | 0,0 % |  |
| V-002 | Diâmetro d [mm] | 4.700,000 | 4.700,000 | 0,0 % | capacidade de líquido (BOT 02 — Early Life) → capacidade de líquido (BOT 02 — Early Life) |
| V-002 | volume | 284,623 | 284,623 | 0,0 % |  |

## 6. Leitura

- **Efeito direto, só onde há gás dissolvido.** SG-001 (μ +33 a +183 %), P-001 lado tubo (+59 a
  +146 %) e P-002 lado casco (+59 a +127 %). TO-001, TO-002 e B-001 não mudam: Rs abaixo da faixa
  ou nulo nas duas rotas.
- **SG-001:** mesmo diâmetro e volume — governa a capacidade de líquido (BOT 12), como a nota 40 já
  mostrava; a μ só move o teto de decantação.
- **P-001 — a mudança que importa.** Com o Rs de Standing a geometria registrada (ADR 0005; 1
  passe, 4 trens + 1 reserva, 8 cascos em série de 6 m) fica **inviável**: "na banda de
  velocidade 1–3 m/s todos os feixes pedem tubo mais longo que o limite de 6 m — o mais curto dá
  8,64 m". O óleo mais viscoso no tubo derruba a película, e o comprimento por casco passa do
  limite do acervo. Ou seja, **a escolha de layout do P-001 depende da rota do Rs**: ela foi feita
  com a rota vigente e só vale com ela.
- **Efeitos em cascata, não de μ:** sem P-001 dimensionado a integração realizada não se aplica, e
  P-002 e P-003 voltam às cargas preliminares (P-002 −7,4 % de área; Q_H e Q_C dos casos 2, 4 e 5
  caem para as preliminares). As variações da μ do casco do P-001 (caso 5) e do P-003 (casos 2, 4,
  5) também vêm daí: as temperaturas em que a μ é avaliada deixam de ser as realizadas. Não são
  efeito do Rs.
- **Bombas e vasos a jusante:** iguais.

## 7. Decisão

Mantida a rota vigente (decisão do usuário, 2026-10-02), pela consistência das bases e do modelo.
O resultado do P-001 com a μ de Standing ("o feixe mais curto pede 8,64 m") mostra que a
geometria é **insuficiente para a carga do balanço** naquela rota, não que ela não opere: o rating
com a geometria congelada (recuperação parcial em 6 m) está na nota 46.
