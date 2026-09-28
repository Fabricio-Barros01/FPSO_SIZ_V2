# Fase 3 — serviço termodinâmico ativo, exercitado na planta

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): o serviço foi fundido em `termo/servico.py` (uma API; o flash de água, salmoura e hidrocarboneto sem pseudo-componentes, que duplicava as propriedades, saiu). O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Gerado por `tools/servico_termodinamico.py`. O serviço é `pfd/estado_termodinamico.py`: `flash_tp(T, P, z, fluido) → EstadoTermodinamico`.

> **O serviço ainda NÃO alimenta o balanço nem o dimensionamento.** Esta fase o disponibiliza; integrar ao processo é a Fase 5, e a fração pesada (surrogate n-C40/n-C33) é a Fase 4. Nenhum número do programa mudou — há paridade bit a bit.

Unidades do serviço: T [K], P [Pa], rho [kg/m³], h [J/kg], cp [J/(kg·K)], mu [Pa·s], k [W/(m·K)], MW [g/mol].

## Fluidos atendidos

| id | modelo | base de `z` | fases | referência de entalpia |
|---|---|---|---|---|
| `hidrocarboneto` | peng_robinson | fracao_molar | vapor, liquido | gás ideal a 298,15 K, sem entalpia de formação (convenção do thermo) |
| `agua` | iapws95 | fracao_molar | liquido | convenção IAPWS-95: u = s = 0 no líquido saturado do ponto triplo |
| `salmoura` | laliberte | fracao_massica_de_sal | aquosa | não aplicável: o modelo de Laliberté dá cp, não entalpia |
| `poco` | peng_robinson_pseudo | fracao_molar | vapor, liquido | não aplicável: sem Cp_ig dos pseudo-componentes, h e cp não são calculados (bloqueio declarado em caracterizacao_scn.toml) |

As fontes de cada modelo estão no TOML do serviço e em `fluidos.toml`. **As bases de composição não são iguais**: hidrocarboneto e água recebem fração molar; salmoura recebe a fração mássica de sal. **As referências de entalpia também não são comuns** — só diferenças do mesmo fluido têm significado.

## Gás dos vasos (Peng-Robinson)

Composição do balanço (corte N2–nC4, P-03), caso 1. `VF` é a fração molar de vapor que a EOS prevê na condição — abaixo de 1 a EOS já condensa parte do gás.

| corrente | T (°C) | P (kPa) | VF | Z | ρ (kg/m³) | cp (J/kg·K) | μ (µPa·s) | k (W/m·K) |
|---|---|---|---|---|---|---|---|---|
| C-04 | 65,0 | 2.500 | 1,0000 | 0,9324 | 25,617 | 1.786,2 | 13,190 | 0,03540 |
| C-09 | 90,0 | 700 | 1,0000 | 0,9849 | 6,323 | 1.748,6 | 14,061 | 0,03721 |
| C-17 | 90,0 | 200 | 1,0000 | 0,9957 | 1,787 | 1.728,5 | 14,061 | 0,03666 |

## Fase aquosa (Laliberté)

Caso 2 — o caso 1 é seco (BSW = 0) e não tem fase aquosa a avaliar.

`k` e `h` saem **NaN**: são lacunas declaradas do modelo, não zeros nem valores supostos.

| corrente | T (°C) | w sal | ρ (kg/m³) | cp (J/kg·K) | μ (mPa·s) | k | h |
|---|---|---|---|---|---|---|---|
| C-05 | 52,7 | 0,17009 | 1.107,965 | 3.510,1 | 0,7654 | — | — |
| C-12 | 90,0 | 0,17009 | 1.085,980 | 3.530,1 | 0,4728 | — | — |
| C-19 | 90,0 | 0,04409 | 994,832 | 3.999,9 | 0,3465 | — | — |
| C-10 | 90,0 | 0,17009 | 1.085,980 | 3.530,1 | 0,4728 | — | — |
| C-18 | 90,0 | 0,04409 | 994,832 | 3.999,9 | 0,3465 | — | — |

## Água de utilidade (IAPWS-95)

O que o serviço acrescenta ao caminho de hoje: **cp e h**. ρ, μ e k saem idênticos aos de `fluidos.agua` — é a mesma norma, e há teste que prende isso.

| T (°C) | P (kPa) | ρ (kg/m³) | cp (J/kg·K) | μ (mPa·s) | k (W/m·K) | h (kJ/kg) |
|---|---|---|---|---|---|---|
| 25,0 | 2.500 | 998,127 | 4.174,4 | 0,8897 | 0,60787 | 107,14 |
| 40,0 | 2.500 | 993,266 | 4.173,5 | 0,6530 | 0,62976 | 169,74 |
| 60,0 | 2.500 | 984,242 | 4.179,7 | 0,4666 | 0,65225 | 253,26 |
| 90,0 | 2.500 | 966,404 | 4.199,9 | 0,3148 | 0,67411 | 378,92 |

## O que o serviço recusa hoje

Recusar é resultado: o serviço não inventa caracterização que não tem.

| fluido | grandeza | motivo | quando |
|---|---|---|---|
| `hidrocarboneto` | fluido de poço completo (com a fração pesada C20+/C20++) | o BOT dá só MW e densidade do C20+; Tc, Pc e ω exigiriam o ponto de ebulição normal. O serviço flasheia a composição que tem caracterização (o corte N2–nC4 do balanço), e recusa a fração pesada | Fase 4: surrogate n-C40 / n-C33 por proximidade de MW |
| `hidrocarboneto` | condutividade térmica da fase líquida | o backend a estima por DIPPR_9H sobre ajustes REFPROP_FIT dos puros; numa sondagem a 250 K a mistura leve deu 2,5e-4 W/(m·K), valor fora do que se espera de hidrocarboneto líquido (~0,1). É extrapolação dos ajustes para muito abaixo da faixa dos componentes leves | validar antes de a Fase 5 consumir k da fase líquida; o serviço entrega o valor do backend COM o método na mão, e avisa |
| `salmoura` | condutividade térmica | o banco de Magomedov (thermo.electrochem) não tem NaCl | sem previsão; hoje k da fase aquosa é entrada proposta |
| `salmoura` | entalpia | Laliberté (2009) correlaciona rho, mu e cp; não há entalpia no modelo | sem previsão; diferenças de entalpia da fase aquosa podem ser obtidas do cp |

O caso mais importante é o primeiro: **o fluido de poço completo não é flasheável hoje**. Pedir o flash de uma composição que inclua a fração pesada levanta erro com a lacuna nomeada, em vez de devolver um número. A Fase 4 resolve isso com o surrogate.

## Equilíbrio de duas fases

Para mostrar que o contrato entrega o equilíbrio inteiro, e não só a fase vapor, uma condição em que a EOS prevê as duas fases:

T = 250,00 K, P = 5.000 kPa, VF molar = 0,7654, VF mássica = 0,6940.

| fase | β molar | β mássica | Z | ρ (kg/m³) | MW | cp (J/kg·K) |
|---|---|---|---|---|---|---|
| vapor | 0,7654 | 0,6940 | 0,6783 | 86,377 | 24,357 | 2.609,7 |
| liquido | 0,2346 | 0,3060 | 0,1526 | 552,054 | 35,027 | 2.761,9 |

| componente | z | y (vapor) | x (líquido) |
|---|---|---|---|
| N2 | 0,00316 | 0,00390 | 0,00075 |
| CO2 | 0,23151 | 0,22036 | 0,26791 |
| H2S | 0,00016 | 0,00012 | 0,00029 |
| C1 | 0,58531 | 0,66944 | 0,31086 |
| C2 | 0,08683 | 0,07037 | 0,14053 |
| C3 | 0,05916 | 0,02788 | 0,16119 |
| iC4 | 0,01001 | 0,00269 | 0,03389 |
| nC4 | 0,02385 | 0,00523 | 0,08457 |

O balanço por componente fecha: z = β·y + (1 − β)·x, conferido por teste.

> **Aviso do serviço:** condutividade da fase líquida por DIPPR_9H, extrapolada dos ajustes dos componentes leves: lacuna declarada, a validar antes de ser consumida

