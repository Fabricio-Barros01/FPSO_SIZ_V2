# F10x.7 — trocadores P-002 e P-003: reotimização discreta

Gerado por `tools/reotimizar_trocadores.py` (grade e regras em `config/pfd/reotimizacao.toml`); todos os números saem do serviço por TAG. Topologia P-46 (óleo no casco), P-45 ativa, limites l_tubo_max = 6 m e d_casco_max = 2.500 mm mantidos.

## P-002

Divisão permitida: `cascos_serie` quando o melhor candidato tem o bloqueio `comprimento` (até 3 cascos, limite da busca).

| Cascos | Candidatos | Viáveis | Melhor candidato: bloqueios |
|---|---|---|---|
| 1 | 96 | 0 | comprimento de tubo > l_tubo_max; fora da faixa de Dittus-Boelter (BOT 06) |
| 2 | 96 | 0 | fora da faixa de Dittus-Boelter (BOT 06) |

**Escolhido** (inviável: melhor feixe encontrado): `banda_caso_projeto` = 1, `cascos_serie` = 2, `d_externo` = 19.05, `passes_tubo` = 2, `razao_passo` = 1.25, `layout_tubos` = 90, `espacamento_chicana` = 0.2.

Tubos por passe 308; comprimento por casco 5,29 m; área total 389,9 m²; bloqueios: fora da faixa de Dittus-Boelter (BOT 06).

| Caso | Papel | Carga (kW) | v (m/s) | Re | Dittus-Boelter | h_i (W/m²K) | h_o (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 5.764 | 1,79 | 92.540 | válida | 13.118 | 4.790 | 4,69 |
| BOT 02 — Early Life | turndown | 6.855 | 2,13 | 110.053 | válida | 15.069 | 4.908 | 5,29 |
| BOT 03 — Early Life Blend | turndown | 6.821 | 2,12 | 109.519 | válida | 15.010 | 5.160 | 5,21 |
| BOT 04 — Early Life | turndown | 769 | 0,24 | 12.352 | válida | 2.619 | 1.276 | 1,26 |
| BOT 05 — Low CO2 | turndown | 1.014 | 0,31 | 16.274 | válida | 3.266 | 1.743 | 1,39 |
| BOT 06 — Mid Life | turndown | 263 | 0,08 | 4.220 | FORA | 1.109 | 586 | 0,79 |
| BOT 07 — Mid Life | turndown | 5.698 | 1,77 | 91.490 | válida | 12.999 | 4.789 | 4,66 |
| BOT 08 — Mid Life | turndown | 6.596 | 2,05 | 105.906 | válida | 14.613 | 4.090 | 5,03 |
| BOT 09 — Mid Life | turndown | 5.982 | 1,86 | 96.042 | válida | 13.513 | 3.687 | 4,70 |
| BOT 11 — Late Life | projeto | 7.380 | 2,29 | 118.494 | válida | 15.986 | 2.918 | 5,22 |

## P-003

Divisão permitida: `cascos_paralelo` quando o melhor candidato tem o bloqueio `casco` (até 3 cascos, limite da busca).

| Cascos | Candidatos | Viáveis | Melhor candidato: bloqueios |
|---|---|---|---|
| 1 | 96 | 0 | comprimento de tubo > l_tubo_max; fora da faixa de Dittus-Boelter (BOT 04, BOT 05, BOT 06) |

**Escolhido** (inviável: melhor feixe encontrado): `banda_caso_projeto` = 1, `cascos_paralelo` = 1, `d_externo` = 25.4, `passes_tubo` = 1, `razao_passo` = 1.25, `layout_tubos` = 90, `espacamento_chicana` = 0.2.

Tubos por passe 1.210; comprimento por casco 14,10 m; área total 1.361,3 m²; bloqueios: comprimento de tubo > l_tubo_max; fora da faixa de Dittus-Boelter (BOT 04, BOT 05, BOT 06).

| Caso | Papel | Carga (kW) | v (m/s) | Re | Dittus-Boelter | h_i (W/m²K) | h_o (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 20.615 | 2,33 | 64.780 | válida | 9.507 | 1.693 | 13,16 |
| BOT 02 — Early Life | turndown | 13.537 | 1,53 | 42.537 | válida | 6.791 | 1.571 | 11,54 |
| BOT 03 — Early Life Blend | turndown | 13.573 | 1,53 | 42.650 | válida | 6.805 | 1.753 | 10,99 |
| BOT 04 — Early Life | turndown | 1.148 | 0,13 | 3.608 | FORA | 944 | 350 | 3,91 |
| BOT 05 — Low CO2 | turndown | 498 | 0,06 | 1.566 | FORA | 484 | 428 | 2,80 |
| BOT 06 — Mid Life | turndown | 129 | 0,01 | 404 | FORA | 164 | 188 | 1,76 |
| BOT 07 — Mid Life | projeto | 26.506 | 2,99 | 83.289 | válida | 11.624 | 1.798 | 14,10 |
| BOT 08 — Mid Life | turndown | 13.129 | 1,48 | 41.255 | válida | 6.626 | 1.248 | 10,35 |
| BOT 09 — Mid Life | turndown | 11.785 | 1,33 | 37.033 | válida | 6.078 | 1.079 | 9,42 |
| BOT 10 — Late Life | turndown | 12.065 | 1,36 | 37.913 | válida | 6.193 | 956 | 8,73 |
| BOT 11 — Late Life | turndown | 4.843 | 0,55 | 15.218 | válida | 2.984 | 642 | 6,54 |
| BOT 12 — Late Life | turndown | 8.421 | 0,95 | 26.461 | válida | 4.645 | 735 | 7,34 |
| BOT 13 — High CO2 | turndown | 10.112 | 1,14 | 31.774 | válida | 5.377 | 840 | 8,00 |
| BOT 14 — High CO2 | turndown | 10.111 | 1,14 | 31.772 | válida | 5.377 | 840 | 8,00 |
| BOT 15 — Highest CO2 | turndown | 3.658 | 0,41 | 11.493 | válida | 2.384 | 401 | 5,16 |
| BOT 16 — Highest CO2 | turndown | 4.072 | 0,46 | 12.797 | válida | 2.598 | 433 | 5,38 |

