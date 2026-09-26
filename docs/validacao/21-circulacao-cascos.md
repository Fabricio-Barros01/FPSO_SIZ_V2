# F13/Etapa 2 — circulação fixa da utilidade e cascos em série (estudos)

Gerado por `tools/estudo_circulacao.py`; todos os números saem do motor e do rastro.

Os dois estudos foram autorizados pelo usuário em 2026-09-26 **como estudo**. O cálculo padrão não muda: a vazão da utilidade continua proporcional à carga (ṁ = q/(cp·ΔT), com o ΔT fixo pelos insumos `t_agua_in`/`t_agua_out`), a política de divisão em cascos do P-003 continua a de cascos em paralelo, e as recomendações dos TAGs continuam as da reotimização F10x.7 (`docs/validacao/18-trocadores.md`). Nada aqui é promovido a premissa ou a padrão.

**Circulação fixa:** a bomba da utilidade mantém a vazão do caso de projeto (critério da P-45: maior vazão volumétrica no tubo) em todos os casos, e o ΔT varia com a carga. A temperatura de saída de cada caso é **resolvida** por bisseção sobre o mesmo fechamento de energia do cálculo padrão (ṁ_fixa = q/(cp(T̄)·|ΔT|)), com cp, ρ, μ e k da água reavaliados na temperatura média resultante (IAPWS); a saída resolvida entra no próprio insumo `t_agua_out`, e a grade de tubos por passe é preparada outra vez com a vazão fixa e a densidade reavaliada. Critérios numéricos em `config/pfd/circulacao.toml`; nenhum valor físico é suposto.

**Condição do estudo (P-32):** as duas aproximações terminais de cada caso ativo são conferidas contra o ΔT de aproximação do balanço (P-32 = 10,0 K). É exigência destes estudos, registrada por caso; a regra padrão do método continua sem impô-la.

**Casos inativos continuam inativos** (motivo do TAG, carga nula). Lacuna continua lacuna: falha física ou de convergência volta como inviabilidade com mensagem, nunca número suposto.

## P-002

Busca completa na grade de `config/pfd/reotimizacao.toml` (96 candidatos por etapa), com `divisao = "cascos_serie"`, gatilho `comprimento` e até 3 cascos. Os limites `l_tubo_max` (6 m) e `d_casco_max` (2.500 mm) não foram alterados.

| Configuração | Estado | Cascos | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|---|
| circulação original, um casco | inviável | 1 | 308 | 17,98 | 331,5 | comprimento de tubo > l_tubo_max; fora da faixa de Dittus-Boelter (BOT 06) |
| circulação original, busca em série | inviável | 2 | 308 | 5,29 | 389,9 | fora da faixa de Dittus-Boelter (BOT 06) |
| circulação fixa, um casco | viável | 1 | 1.529 | 5,99 | 365,5 | — |
| circulação fixa, busca em série | viável | 1 | 1.529 | 5,99 | 365,5 | — |

### P-002 — circulação original: operação por caso no feixe escolhido

| Caso | Papel | Carga (kW) | ṁ utilidade (kg/s) | T saída utilidade (°C) | v (m/s) | Re | Dittus-Boelter | ΔT₁ (K) | ΔT₂ (K) | P-32 | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 5.764 | — | — | 1,79 | 92.540 | sim | 20,00 | 14,68 | atende | 4,69 |
| BOT 02 — Early Life | turndown | 6.855 | — | — | 2,13 | 110.053 | sim | 20,00 | 15,92 | atende | 5,29 |
| BOT 03 — Early Life Blend | turndown | 6.821 | — | — | 2,12 | 109.519 | sim | 20,00 | 15,92 | atende | 5,21 |
| BOT 04 — Early Life | turndown | 769 | — | — | 0,24 | 12.352 | sim | 20,00 | 14,93 | atende | 1,26 |
| BOT 05 — Low CO2 | turndown | 1.014 | — | — | 0,31 | 16.274 | sim | 20,00 | 15,05 | atende | 1,39 |
| BOT 06 — Mid Life | turndown | 263 | — | — | 0,08 | 4.220 | NÃO | 20,00 | 15,09 | atende | 0,79 |
| BOT 07 — Mid Life | turndown | 5.698 | — | — | 1,77 | 91.490 | sim | 20,00 | 14,57 | atende | 4,66 |
| BOT 08 — Mid Life | turndown | 6.596 | — | — | 2,05 | 105.906 | sim | 20,00 | 18,15 | atende | 5,03 |
| BOT 09 — Mid Life | turndown | 5.982 | — | — | 1,86 | 96.042 | sim | 20,00 | 18,37 | atende | 4,70 |
| BOT 11 — Late Life | projeto | 7.380 | — | — | 2,29 | 118.494 | sim | 20,00 | 25,80 | atende | 5,22 |

A coluna de vazão e de temperatura de saída da utilidade fica vazia: na circulação original elas são as do cálculo padrão (ΔT fixo pelos insumos).

### P-002 — circulação fixa: operação por caso no feixe escolhido

Caso de projeto pela P-45 na **configuração-base**: **BOT 11 — Late Life**; circulação fixada em 116,63 kg/s — a vazão desse caso, com origem no rastro.

Achado do estudo: com a circulação fixa a vazão volumétrica no tubo fica praticamente igual em todos os casos, e o critério da P-45 **degenera** dentro do método — a coluna "Papel" passa a rotular como projeto o caso de maior temperatura de retorno (menor densidade), não o de maior carga. Como a velocidade é a mesma em todos os casos, a escolha não muda o feixe; mas é mais uma razão para a variante não ser promovida a padrão sem decisão: a P-45 foi escrita para a circulação proporcional à carga.

| Caso | Papel | Carga (kW) | ṁ utilidade (kg/s) | T saída utilidade (°C) | v (m/s) | Re | Dittus-Boelter | ΔT₁ (K) | ΔT₂ (K) | P-32 | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 5.764 | 116,63 | 98,29 | 1,41 | 42.450 | sim | 20,00 | 17,97 | atende | 4,92 |
| BOT 02 — Early Life | turndown | 6.855 | 116,63 | 96,07 | 1,41 | 41.973 | sim | 20,00 | 17,00 | atende | 5,99 |
| BOT 03 — Early Life Blend | turndown | 6.821 | 116,63 | 96,14 | 1,41 | 41.987 | sim | 20,00 | 17,06 | atende | 5,90 |
| BOT 04 — Early Life | turndown | 769 | 116,63 | 108,44 | 1,42 | 44.643 | sim | 20,00 | 28,37 | atende | 0,81 |
| BOT 05 — Low CO2 | turndown | 1.014 | 116,63 | 107,94 | 1,42 | 44.535 | sim | 20,00 | 27,99 | atende | 0,96 |
| BOT 06 — Mid Life | projeto | 263 | 116,63 | 109,47 | 1,42 | 44.866 | sim | 20,00 | 29,56 | atende | 0,43 |
| BOT 07 — Mid Life | turndown | 5.698 | 116,63 | 98,42 | 1,41 | 42.478 | sim | 20,00 | 18,00 | atende | 4,86 |
| BOT 08 — Mid Life | turndown | 6.596 | 116,63 | 96,60 | 1,41 | 42.086 | sim | 20,00 | 19,75 | atende | 5,55 |
| BOT 09 — Mid Life | turndown | 5.982 | 116,63 | 97,85 | 1,41 | 42.354 | sim | 20,00 | 21,21 | atende | 4,97 |
| BOT 11 — Late Life | turndown | 7.380 | 116,63 | 95,00 | 1,41 | 41.743 | sim | 20,00 | 25,80 | atende | 5,99 |

## P-003

Busca completa na grade de `config/pfd/reotimizacao.toml` (96 candidatos por etapa), com `divisao = "cascos_serie"`, gatilho `comprimento` e até 3 cascos. Os limites `l_tubo_max` (6 m) e `d_casco_max` (2.500 mm) não foram alterados.

| Configuração | Estado | Cascos | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |
|---|---|---|---|---|---|---|
| circulação original, um casco | inviável | 1 | 1.210 | 14,10 | 1.361,3 | comprimento de tubo > l_tubo_max; fora da faixa de Dittus-Boelter (BOT 04, BOT 05, BOT 06) |
| circulação original, busca em série | inviável | 2 | 1.210 | 4,60 | 1.778,2 | fora da faixa de Dittus-Boelter (BOT 04, BOT 05, BOT 06) |
| circulação fixa, um casco | viável | 1 | 7.528 | 4,91 | 1.473,5 | — |
| circulação fixa, busca em série | viável | 1 | 7.528 | 4,91 | 1.473,5 | — |

### P-003 — circulação original: operação por caso no feixe escolhido

| Caso | Papel | Carga (kW) | ṁ utilidade (kg/s) | T saída utilidade (°C) | v (m/s) | Re | Dittus-Boelter | ΔT₁ (K) | ΔT₂ (K) | P-32 | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 20.615 | — | — | 2,33 | 64.780 | sim | 40,00 | 10,00 | atende | 4,26 |
| BOT 02 — Early Life | turndown | 13.537 | — | — | 1,53 | 42.537 | sim | 27,73 | 10,00 | atende | 3,68 |
| BOT 03 — Early Life Blend | turndown | 13.573 | — | — | 1,53 | 42.650 | sim | 27,88 | 10,00 | atende | 3,54 |
| BOT 04 — Early Life | turndown | 1.148 | — | — | 0,13 | 3.608 | NÃO | 20,00 | 10,00 | atende | 1,09 |
| BOT 05 — Low CO2 | turndown | 498 | — | — | 0,06 | 1.566 | NÃO | 10,00 | 10,00 | atende | 0,77 |
| BOT 06 — Mid Life | turndown | 129 | — | — | 0,01 | 404 | NÃO | 10,00 | 10,00 | atende | 0,47 |
| BOT 07 — Mid Life | projeto | 26.506 | — | — | 2,99 | 83.289 | sim | 50,00 | 10,00 | atende | 4,60 |
| BOT 08 — Mid Life | turndown | 13.129 | — | — | 1,48 | 41.255 | sim | 38,10 | 10,00 | atende | 3,32 |
| BOT 09 — Mid Life | turndown | 11.785 | — | — | 1,33 | 37.033 | sim | 42,84 | 10,00 | atende | 3,02 |
| BOT 10 — Late Life | turndown | 12.065 | — | — | 1,36 | 37.913 | sim | 55,57 | 10,00 | atende | 2,81 |
| BOT 11 — Late Life | turndown | 4.843 | — | — | 0,55 | 15.218 | sim | 34,46 | 10,00 | atende | 2,01 |
| BOT 12 — Late Life | turndown | 8.421 | — | — | 0,95 | 26.461 | sim | 55,57 | 10,00 | atende | 2,32 |
| BOT 13 — High CO2 | turndown | 10.112 | — | — | 1,14 | 31.774 | sim | 55,57 | 10,00 | atende | 2,55 |
| BOT 14 — High CO2 | turndown | 10.111 | — | — | 1,14 | 31.772 | sim | 55,57 | 10,00 | atende | 2,55 |
| BOT 15 — Highest CO2 | turndown | 3.658 | — | — | 0,41 | 11.493 | sim | 55,53 | 10,00 | atende | 1,52 |
| BOT 16 — Highest CO2 | turndown | 4.072 | — | — | 0,46 | 12.797 | sim | 55,53 | 10,00 | atende | 1,61 |

A coluna de vazão e de temperatura de saída da utilidade fica vazia: na circulação original elas são as do cálculo padrão (ΔT fixo pelos insumos).

### P-003 — circulação fixa: operação por caso no feixe escolhido

Caso de projeto pela P-45 na **configuração-base**: **BOT 07 — Mid Life**; circulação fixada em 1.268,30 kg/s — a vazão desse caso, com origem no rastro.

Achado do estudo: com a circulação fixa a vazão volumétrica no tubo fica praticamente igual em todos os casos, e o critério da P-45 **degenera** dentro do método — a coluna "Papel" passa a rotular como projeto o caso de maior temperatura de retorno (menor densidade), não o de maior carga. Como a velocidade é a mesma em todos os casos, a escolha não muda o feixe; mas é mais uma razão para a variante não ser promovida a padrão sem decisão: a P-45 foi escrita para a circulação proporcional à carga.

| Caso | Papel | Carga (kW) | ṁ utilidade (kg/s) | T saída utilidade (°C) | v (m/s) | Re | Dittus-Boelter | ΔT₁ (K) | ΔT₂ (K) | P-32 | L exigido (m) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | turndown | 20.615 | 1.268,30 | 33,89 | 3,00 | 33.055 | sim | 41,11 | 10,00 | atende | 4,39 |
| BOT 02 — Early Life | turndown | 13.537 | 1.268,30 | 32,55 | 3,00 | 32.598 | sim | 30,17 | 10,00 | atende | 3,56 |
| BOT 03 — Early Life Blend | turndown | 13.573 | 1.268,30 | 32,56 | 3,00 | 32.600 | sim | 30,32 | 10,00 | atende | 3,44 |
| BOT 04 — Early Life | turndown | 1.148 | 1.268,30 | 30,22 | 3,00 | 31.804 | sim | 24,78 | 10,00 | atende | 0,69 |
| BOT 05 — Low CO2 | turndown | 498 | 1.268,30 | 30,09 | 3,00 | 31.762 | sim | 14,91 | 10,00 | atende | 0,35 |
| BOT 06 — Mid Life | turndown | 129 | 1.268,30 | 30,02 | 3,00 | 31.739 | sim | 14,98 | 10,00 | atende | 0,16 |
| BOT 07 — Mid Life | projeto | 26.506 | 1.268,30 | 35,00 | 3,00 | 33.437 | sim | 50,00 | 10,00 | atende | 4,91 |
| BOT 08 — Mid Life | turndown | 13.129 | 1.268,30 | 32,48 | 3,00 | 32.571 | sim | 40,63 | 10,00 | atende | 3,18 |
| BOT 09 — Mid Life | turndown | 11.785 | 1.268,30 | 32,22 | 3,00 | 32.485 | sim | 45,61 | 10,00 | atende | 2,83 |
| BOT 10 — Late Life | turndown | 12.065 | 1.268,30 | 32,28 | 3,00 | 32.503 | sim | 58,29 | 10,00 | atende | 2,64 |
| BOT 11 — Late Life | turndown | 4.843 | 1.268,30 | 30,91 | 3,00 | 32.040 | sim | 38,55 | 10,00 | atende | 1,65 |
| BOT 12 — Late Life | turndown | 8.421 | 1.268,30 | 31,59 | 3,00 | 32.269 | sim | 58,98 | 10,00 | atende | 2,08 |
| BOT 13 — High CO2 | turndown | 10.112 | 1.268,30 | 31,91 | 3,00 | 32.377 | sim | 58,66 | 10,00 | atende | 2,35 |
| BOT 14 — High CO2 | turndown | 10.111 | 1.268,30 | 31,91 | 3,00 | 32.377 | sim | 58,66 | 10,00 | atende | 2,35 |
| BOT 15 — Highest CO2 | turndown | 3.658 | 1.268,30 | 30,69 | 3,00 | 31.964 | sim | 59,84 | 10,00 | atende | 1,21 |
| BOT 16 — Highest CO2 | turndown | 4.072 | 1.268,30 | 30,77 | 3,00 | 31.990 | sim | 59,77 | 10,00 | atende | 1,30 |

