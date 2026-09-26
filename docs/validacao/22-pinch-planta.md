# F8 — alvos de energia do pré-aquecedor (Análise Pinch na planta do BOT)

Gerado por `tools/pinch_planta.py`; todos os números saem do balanço e do núcleo da Análise Pinch (`analysis/pinch.py`, Kemp §3.9.1).

## A rede e por que é esta

Pedido do usuário (2026-09-26): a F8 aplicada ao **pré-aquecedor depois do SG**, com as correntes de **óleo tratado antes de ir para o cargo tank** e **óleo vivo que sai do SG**. São as duas correntes que o balanço já cruza no P-001:

- **óleo vivo do SG-001 (fria)**: C-06 → premissa `T_trat` (aquecer); CP = C(C-06) do balanço. saída de óleo do FWKO (C-06) até a temperatura de tratamento (P-11, T_trat); CP = C(C-06) do balanço
- **óleo tratado antes do cargo tank (quente)**: C-22 → premissa `T_store` (resfriar); CP = C(C-21) do balanço. recalque do óleo tratado (C-22) até a temperatura de estocagem (P-13, T_store); CP = C(C-21) do balanço, a mesma capacidade que o modelo usa no lado quente do P-001

**ΔTmin = a própria premissa `dT_app`** — P-32 (dT_app): aproximação de temperatura do pré-aquecedor, premissa do balanço — a mesma que balanco/modelo.py usa em Q_pre. Não há ΔTmin novo suposto: com outro valor as duas coisas comparadas seriam redes diferentes.

O **destino** de cada corrente é a premissa, não a temperatura que o balanço realizou: usar a realizada embutiria o arranjo na resposta. Quando a exigência já está atendida no caso (o destino é piso para quem aquece e teto para quem resfria), a corrente **não entra na rede** e o motivo é registrado — inverter o seu sentido inventaria uma carga que o processo não pede.

## Alvos por caso, contra o que o balanço realizou

| Caso | ΔTmin (°C) | QHmin alvo (kW) | Q_H do balanço (kW) | QCmin alvo (kW) | Q_C do balanço (kW) | Recuperação alvo (kW) | Q_pre do balanço (kW) | T de pinch deslocada (°C) |
|---|---|---|---|---|---|---|---|---|
| BOT 01 — Early Life | 10,0 | 5.763,8 | 5.763,8 | 20.615,4 | 20.615,4 | 9.119,1 | 9.119,1 | 70,0 |
| BOT 02 — Early Life | 10,0 | 6.854,5 | 6.854,5 | 13.536,8 | 13.536,8 | 16.532,4 | 16.532,4 | 57,7 |
| BOT 03 — Early Life Blend | 10,0 | 6.821,3 | 6.821,3 | 13.572,8 | 13.572,8 | 16.367,4 | 16.367,4 | 57,9 |
| BOT 04 — Early Life | 10,0 | 769,3 | 769,3 | 1.148,3 | 1.148,3 | 2.716,4 | 2.716,4 | 50,0 |
| BOT 05 — Low CO2 | 10,0 | 1.013,6 | 1.013,6 | 498,3 | 498,3 | 4.533,0 | 4.533,0 | 40,0 |
| BOT 06 — Mid Life | 10,0 | 262,8 | 262,8 | 128,6 | 128,6 | 1.170,0 | 1.170,0 | 40,0 |
| BOT 07 — Mid Life | 10,0 | 5.698,3 | 5.698,3 | 26.505,5 | 26.505,5 | 3.229,0 | 3.229,0 | 80,0 |
| BOT 08 — Mid Life | 10,0 | 6.596,2 | 6.596,2 | 13.128,7 | 13.128,7 | 6.892,0 | 6.892,0 | 68,1 |
| BOT 09 — Mid Life | 10,0 | 5.981,9 | 5.981,9 | 11.785,2 | 11.785,2 | 3.937,4 | 3.937,4 | 72,8 |
| BOT 10 — Late Life | 10,0 | — | 0,0 | — | 12.065,2 | — | 0,0 | rede incompleta |
| BOT 11 — Late Life | 10,0 | 7.380,2 | 7.380,2 | 4.843,0 | 4.843,0 | 3.454,6 | 3.454,6 | 64,5 |
| BOT 12 — Late Life | 10,0 | — | 0,0 | — | 8.420,7 | — | 0,0 | rede incompleta |
| BOT 13 — High CO2 | 10,0 | — | 0,0 | — | 10.111,7 | — | 0,0 | rede incompleta |
| BOT 14 — High CO2 | 10,0 | — | 0,0 | — | 10.111,0 | — | 0,0 | rede incompleta |
| BOT 15 — Highest CO2 | 10,0 | — | 0,0 | — | 3.657,6 | — | 0,0 | rede incompleta |
| BOT 16 — Highest CO2 | 10,0 | — | 0,0 | — | 4.072,4 | — | 0,0 | rede incompleta |

## Folga do arranjo do BOT

Utilidade acima do alvo é utilidade desperdiçada; recuperação abaixo do alvo é calor que o pré-aquecedor poderia trocar e não troca.

| Caso | Utilidade quente acima do alvo (kW) | Utilidade fria acima do alvo (kW) | Recuperação abaixo do alvo (kW) |
|---|---|---|---|
| BOT 01 — Early Life | -0,000 | 0,000 | 0,000 |
| BOT 02 — Early Life | 0,000 | 0,000 | -0,000 |
| BOT 03 — Early Life Blend | 0,000 | 0,000 | 0,000 |
| BOT 04 — Early Life | -0,000 | 0,000 | 0,000 |
| BOT 05 — Low CO2 | 0,000 | 0,000 | 0,000 |
| BOT 06 — Mid Life | 0,000 | 0,000 | 0,000 |
| BOT 07 — Mid Life | 0,000 | 0,000 | 0,000 |
| BOT 08 — Mid Life | -0,000 | 0,000 | 0,000 |
| BOT 09 — Mid Life | 0,000 | 0,000 | 0,000 |
| BOT 10 — Late Life | — | — | — |
| BOT 11 — Late Life | -0,000 | 0,000 | 0,000 |
| BOT 12 — Late Life | — | — | — |
| BOT 13 — High CO2 | — | — | — |
| BOT 14 — High CO2 | — | — | — |
| BOT 15 — Highest CO2 | — | — | — |
| BOT 16 — Highest CO2 | — | — | — |

**Resultado:** nos casos em que a rede se aplica, o arranjo do BOT **alcança o alvo termodinâmico** — a maior folga em módulo é 0,000000 kW, ruído de ponto flutuante. É uma validação cruzada genuína: o alvo vem da cascata de calor da Problem Table, e as cargas do balanço vêm da regra Q_pre = min(C_frio, C_quente)·(ΔT − ΔT_app) de `balanco/modelo.py`. Dois caminhos independentes, o mesmo número.

Com duas correntes e um ΔTmin, o ótimo de recuperação é o encosto das duas na aproximação — e é exatamente o que aquela regra calcula. O alvo NÃO promete mais recuperação do que o único trocador já entrega; ele prova que não há mais a recuperar nesta rede. Ganho adicional exigiria outra rede (mais correntes, outras utilidades ou outro ΔTmin), que é decisão de projeto do usuário.

## As correntes de cada caso

| Caso | Corrente | T entrada (°C) | T destino (°C) | CP (kW/°C) | Carga (kW) |
|---|---|---|---|---|---|
| BOT 01 — Early Life | óleo vivo do SG-001 (fria) | 65,00 | 90,00 | 595,315 | 14.882,9 |
| BOT 01 — Early Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 589,011 | 29.734,5 |
| BOT 02 — Early Life | óleo vivo do SG-001 (fria) | 52,73 | 90,00 | 627,416 | 23.386,9 |
| BOT 02 — Early Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 595,679 | 30.069,2 |
| BOT 03 — Early Life Blend | óleo vivo do SG-001 (fria) | 52,88 | 90,00 | 624,771 | 23.188,7 |
| BOT 03 — Early Life Blend | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 593,098 | 29.940,2 |
| BOT 04 — Early Life | óleo vivo do SG-001 (fria) | 45,00 | 90,00 | 77,461 | 3.485,7 |
| BOT 04 — Early Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 76,557 | 3.864,7 |
| BOT 05 — Low CO2 | óleo vivo do SG-001 (fria) | 35,00 | 90,00 | 100,847 | 5.546,6 |
| BOT 05 — Low CO2 | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 99,661 | 5.031,3 |
| BOT 06 — Mid Life | óleo vivo do SG-001 (fria) | 35,00 | 90,00 | 26,051 | 1.432,8 |
| BOT 06 — Mid Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 25,724 | 1.298,6 |
| BOT 07 — Mid Life | óleo vivo do SG-001 (fria) | 75,00 | 90,00 | 595,156 | 8.927,3 |
| BOT 07 — Mid Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 589,012 | 29.734,5 |
| BOT 08 — Mid Life | óleo vivo do SG-001 (fria) | 63,10 | 90,00 | 501,457 | 13.488,3 |
| BOT 08 — Mid Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 396,616 | 20.020,7 |
| BOT 09 — Mid Life | óleo vivo do SG-001 (fria) | 67,84 | 90,00 | 447,571 | 9.919,2 |
| BOT 09 — Mid Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 311,468 | 15.722,6 |
| BOT 10 — Late Life | óleo tratado antes do cargo tank (quente) | 90,57 | 40,00 | 238,594 | 12.065,2 |
| BOT 10 — Late Life | óleo vivo do SG-001 (fria) | — | — | — | omitida: o óleo já sai do SG-001 acima da temperatura de tratamento (T_trat é piso, P-11: o balanço usa T08 = max(T_trat, T07)); não há exigência de aquecimento nem de resfriamento desta corrente |
| BOT 11 — Late Life | óleo vivo do SG-001 (fria) | 59,46 | 90,00 | 354,806 | 10.834,8 |
| BOT 11 — Late Life | óleo tratado antes do cargo tank (quente) | 90,48 | 40,00 | 164,377 | 8.297,6 |
| BOT 12 — Late Life | óleo tratado antes do cargo tank (quente) | 90,57 | 40,00 | 166,505 | 8.420,7 |
| BOT 12 — Late Life | óleo vivo do SG-001 (fria) | — | — | — | omitida: o óleo já sai do SG-001 acima da temperatura de tratamento (T_trat é piso, P-11: o balanço usa T08 = max(T_trat, T07)); não há exigência de aquecimento nem de resfriamento desta corrente |
| BOT 13 — High CO2 | óleo tratado antes do cargo tank (quente) | 90,57 | 40,00 | 199,950 | 10.111,7 |
| BOT 13 — High CO2 | óleo vivo do SG-001 (fria) | — | — | — | omitida: o óleo já sai do SG-001 acima da temperatura de tratamento (T_trat é piso, P-11: o balanço usa T08 = max(T_trat, T07)); não há exigência de aquecimento nem de resfriamento desta corrente |
| BOT 14 — High CO2 | óleo tratado antes do cargo tank (quente) | 90,57 | 40,00 | 199,949 | 10.111,0 |
| BOT 14 — High CO2 | óleo vivo do SG-001 (fria) | — | — | — | omitida: o óleo já sai do SG-001 acima da temperatura de tratamento (T_trat é piso, P-11: o balanço usa T08 = max(T_trat, T07)); não há exigência de aquecimento nem de resfriamento desta corrente |
| BOT 15 — Highest CO2 | óleo tratado antes do cargo tank (quente) | 90,53 | 40,00 | 72,388 | 3.657,6 |
| BOT 15 — Highest CO2 | óleo vivo do SG-001 (fria) | — | — | — | omitida: o óleo já sai do SG-001 acima da temperatura de tratamento (T_trat é piso, P-11: o balanço usa T08 = max(T_trat, T07)); não há exigência de aquecimento nem de resfriamento desta corrente |
| BOT 16 — Highest CO2 | óleo tratado antes do cargo tank (quente) | 90,53 | 40,00 | 80,588 | 4.072,4 |
| BOT 16 — Highest CO2 | óleo vivo do SG-001 (fria) | — | — | — | omitida: o óleo já sai do SG-001 acima da temperatura de tratamento (T_trat é piso, P-11: o balanço usa T08 = max(T_trat, T07)); não há exigência de aquecimento nem de resfriamento desta corrente |

## O que este documento NÃO afirma

- Não sintetiza rede de trocadores, não dá alvo de área nem número mínimo de unidades (fora do escopo declarado do método, `config/equipment/pinch/kemp.toml`).

- Não propõe mudar o ΔTmin do projeto: o ΔTmin usado é a premissa P-32 do próprio balanço.

- Não altera o balanço, o PFD nem as recomendações de nenhum TAG: é leitura sobre o balanço já resolvido.

