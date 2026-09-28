# F10x.7 — trocadores P-002 e P-003: reotimização discreta

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): a reotimização discreta (`pfd/reotimizacao.py`) saiu; a geometria que ela escolheu está nas recomendações dos TAGs. O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Gerado por `tools/reotimizar_trocadores.py` (grade e regras em `config/pfd/reotimizacao.toml`); todos os números saem do serviço por TAG. Topologia P-46 (óleo no casco), P-45 ativa, limites l_tubo_max = 6 m e d_casco_max = 2.500 mm mantidos.

## P-002

Divisão permitida: `cascos_serie` quando o melhor candidato tem o bloqueio `comprimento` (até 3 cascos, limite da busca).

| Cascos | Candidatos | Viáveis | Melhor candidato: bloqueios |
|---|---|---|---|
| 1 | 96 | 21 | — |

**Escolhido** (viável): `banda_caso_projeto` = 1, `cascos_serie` = 1, `d_externo` = 12.7, `passes_tubo` = 1, `razao_passo` = 1.25, `layout_tubos` = 90, `espacamento_chicana` = 0.2.

Tubos por passe 1.605; comprimento por casco 5,99 m; área total 383,8 m²; bloqueios: —.

| Caso | Papel | Carga (kW) | v (m/s) | Re | Dittus-Boelter | h_i (W/m²K) | h_o (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 5.764 | 1,05 | 31.056 | válida | 9.578 | 5.172 | 5,37 |
| BOT 02 — Early Life | turndown | 6.855 | 1,25 | 36.934 | válida | 11.002 | 5.300 | 5,99 |
| BOT 03 — Early Life Blend | turndown | 6.821 | 1,24 | 36.755 | válida | 10.959 | 5.572 | 5,91 |
| BOT 04 — Early Life | turndown | 769 | 0,14 | 4.145 | válida | 803 | 1.301 | 2,29 |
| BOT 05 — Low CO2 | turndown | 1.014 | 0,18 | 5.461 | válida | 1.273 | 1.690 | 2,22 |
| BOT 06 — Mid Life | turndown | 263 | 0,05 | 1.416 | válida | 350 | 598 | 1,56 |
| BOT 07 — Mid Life | turndown | 5.698 | 1,04 | 30.704 | válida | 9.491 | 5.172 | 5,33 |
| BOT 08 — Mid Life | turndown | 6.596 | 1,20 | 35.542 | válida | 10.669 | 4.418 | 5,64 |
| BOT 09 — Mid Life | turndown | 5.982 | 1,09 | 32.232 | válida | 9.867 | 3.983 | 5,26 |
| BOT 11 — Late Life | projeto | 7.380 | 1,35 | 39.766 | válida | 11.672 | 2.963 | 5,78 |

## P-003

Divisão permitida: `cascos_paralelo` quando o melhor candidato tem o bloqueio `casco` (até 3 cascos, limite da busca).

| Cascos | Candidatos | Viáveis | Melhor candidato: bloqueios |
|---|---|---|---|
| 1 | 96 | 32 | — |

**Escolhido** (viável): `banda_caso_projeto` = 1, `cascos_paralelo` = 1, `d_externo` = 12.7, `passes_tubo` = 1, `razao_passo` = 1.25, `layout_tubos` = 30, `espacamento_chicana` = 0.2.

Tubos por passe 7.526; comprimento por casco 4,91 m; área total 1.473,4 m²; bloqueios: —.

| Caso | Papel | Carga (kW) | v (m/s) | Re | Dittus-Boelter | h_i (W/m²K) | h_o (W/m²K) | L exigido (m) |
|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 20.615 | 2,33 | 26.013 | válida | 11.444 | 1.604 | 4,54 |
| BOT 02 — Early Life | turndown | 13.537 | 1,53 | 17.081 | válida | 8.174 | 1.525 | 3,93 |
| BOT 03 — Early Life Blend | turndown | 13.573 | 1,54 | 17.127 | válida | 8.191 | 1.644 | 3,80 |
| BOT 04 — Early Life | turndown | 1.148 | 0,13 | 1.449 | válida | 388 | 469 | 1,77 |
| BOT 05 — Low CO2 | turndown | 498 | 0,06 | 629 | válida | 356 | 550 | 1,11 |
| BOT 06 — Mid Life | turndown | 129 | 0,01 | 162 | válida | 336 | 256 | 0,39 |
| BOT 07 — Mid Life | projeto | 26.506 | 3,00 | 33.446 | válida | 13.993 | 1.672 | 4,91 |
| BOT 08 — Mid Life | turndown | 13.129 | 1,49 | 16.566 | válida | 7.976 | 1.247 | 3,47 |
| BOT 09 — Mid Life | turndown | 11.785 | 1,33 | 14.871 | válida | 7.316 | 1.100 | 3,11 |
| BOT 10 — Late Life | turndown | 12.065 | 1,37 | 15.224 | válida | 7.455 | 984 | 2,86 |
| BOT 11 — Late Life | turndown | 4.843 | 0,55 | 6.111 | válida | 2.117 | 725 | 2,25 |
| BOT 12 — Late Life | turndown | 8.421 | 0,95 | 10.626 | válida | 5.591 | 791 | 2,33 |
| BOT 13 — High CO2 | turndown | 10.112 | 1,14 | 12.759 | válida | 6.473 | 884 | 2,58 |
| BOT 14 — High CO2 | turndown | 10.111 | 1,14 | 12.758 | válida | 6.472 | 884 | 2,58 |
| BOT 15 — Highest CO2 | turndown | 3.658 | 0,41 | 4.615 | válida | 1.311 | 504 | 1,75 |
| BOT 16 — Highest CO2 | turndown | 4.072 | 0,46 | 5.139 | válida | 1.573 | 532 | 1,79 |

