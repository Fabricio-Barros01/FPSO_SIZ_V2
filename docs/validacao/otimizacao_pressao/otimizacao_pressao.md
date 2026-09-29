# Subproblema de pressão — grade-oráculo, NSGA-II e frente (tabelas geradas)

Gerado por `tools/otimizar.py --sub pressao`. subproblema de pressão e separação (docs/validacao/42): P_D1, P_D2 → balanço (resolver_todos, recombinação da Nota 4, trem) → SG-001, V-001, V-002 → objetivos e restrições. Não é a otimização da planta inteira.

## Declaração

| Variável | Domínio | Natureza dos extremos | Origem |
|---|---|---|---|
| pressão do V-001 (P_D1) | 200,0 – 2.000,0 kPa | dominio_estudo / dominio_estudo | domínio de estudo da Nota 41 (grade do mapa determinístico); o máximo fica abaixo do limite com fonte da sucção do compressor principal, 2.200 kPa (BOT §2.7.3.9.20.1, valor ESTIMADO pelo BOT), que por isso nunca fica ativo |
| pressão do V-002 (P_D2) | 110,0 – 250,0 kPa | dominio_estudo / dominio_estudo | domínio de estudo da Nota 41; o piso físico de P_D2 (sucção do 1º estágio da VRU) não tem fonte, e 110 kPa é só o extremo explorado; o teto efetivo vem da restrição de TVP, não de bound |

| Objetivo | Unidade | Sentido | Definição |
|---|---|---|---|
| perda de óleo estabilizado (1 − recuperação mássica) (`perda_oleo`) | – | minimizar | recuperação = Σ ṁ_O(C-25, óleo à estocagem) / Σ ṁ_O(C-01, alimentação) nos 12 casos avaliáveis; O é o teor de óleo de tanque (flash à condição padrão), conservado pelo trem (docs/validacao/39), e o que falta sai pelas outras saídas globais: como O nos vapores do SG-001, V-001 e V-002 e no óleo da água do FWKO (C-05, fixado pela premissa de teor de óleo na água, não pela pressão). Adimensional; por caso, massa e volume padrão dão a mesma razão (mesma ρ_O). Maximizar a recuperação = minimizar 1 − recuperação |
| carga de vapor da VRU (V-001 + V-002) (`carga_vru`) | Sm³/d | minimizar | vazão de vapor que chega à VRU (V-001 + V-002, Sm³/d) já calculada pelo balanço; o máximo entre os 16 casos, como o envelope com que os vasos são dimensionados. Não é potência de compressor (sem modelo de compressor) |

| Restrição | Natureza | Definição |
|---|---|---|
| P_D2 < P_D1 (`p_d2_menor_que_p_d1`) | processo | topologia do BOT (Fig. 2.7.1.17): o líquido do V-001 segue ao V-002 sem bomba; o ΔP mínimo de transferência não tem fonte |
| TVP do óleo tratado na estocagem ≤ limite do BOT (`tvp`) | fonte | BOT I-ET-3010.2K-1200-941-P4X-001 rev. C, §2.3.1.1 (TVP ≤ 70 kPa) e §2.7.1.10 (na estocagem). Verificada só nos 12 casos avaliáveis: nos 4 com gás de lift (9, 11, 15, 16) não há composição e a TVP NÃO é verificada. É restrição, não bound de P_D2 |
| viabilidade de SG-001 | contrato | mesmo serviço por TAG; violação = medida de distância (`_violacao`) |
| viabilidade de V-001 | contrato | mesmo serviço por TAG; violação = medida de distância (`_violacao`) |
| viabilidade de V-002 | contrato | mesmo serviço por TAG; violação = medida de distância (`_violacao`) |

## Grade-oráculo

Eixos da grade (passos declarados em `grade_passo`): P_D1 = 200,0 a 2.000,0 kPa, 13 valores; P_D2 = 110,0 a 250,0 kPa, 15 valores. 195 pontos: 163 inviável, 32 viável.

Restrições que barram os pontos inviáveis da grade: `p_d2_menor_que_p_d1` em 6, `tvp` em 157.

Resolução da grade no espaço dos objetivos (maior diferença entre vizinhos viáveis): ε(`perda_oleo`) = 0,7133 p.p., ε(`carga_vru`) = 61.949 Sm³/d.

### Frente da grade

| P_D1 | P_D2 | perda de óleo (%) | carga VRU (Sm³/d) | g_TVP |
|---:|---:|---:|---:|---:|
| 500,0 | 130,0 | 2,1579 | 1.221.881 | -0,0340 |

## NSGA-II

Algoritmo **NSGA-II** (pymoo 0.6.2), população 40, 20 gerações, semente 1 (os valores declarados em `[algoritmo]`), 800 avaliações, 800 pontos distintos: 561 viável, 235 inviável, 4 não avaliável (lacuna de entrada ou grandeza sem solução).

| P_D1 | P_D2 | perda de óleo (%) | carga VRU (Sm³/d) | g_TVP |
|---:|---:|---:|---:|---:|
| 510,5 | 133,7 | 2,1030 | 1.215.765 | -0,0020 |
| 537,6 | 133,9 | 2,1033 | 1.215.717 | -0,0003 |
| 538,2 | 133,9 | 2,1033 | 1.215.716 | -0,0003 |

## Conferência contra a grade

- pontos da frente do NSGA-II que a grade supera por mais que ε em todo objetivo: **0**;
- pontos da frente da grade que a do NSGA-II não cobre dentro de ε: **0**;
- veredito: **a frente do NSGA-II reproduz a da grade na resolução declarada**.

Reavaliação de cada ponto da frente fora do otimizador (`ot.avaliar`): **idêntica** (objetivos, restrições e estados bit a bit).

Pontos **não avaliáveis** do NSGA-II (4): a grandeza de uma restrição não existe (para a TVP: flash sem equilíbrio num passo da bisseção). Não entram na frente — falta de dado não é viabilidade. A última coluna diz se a frente os domina mesmo que fossem viáveis.

| P_D1 | P_D2 | sem grandeza | perda de óleo (%) | carga VRU (Sm³/d) | dominado pela frente |
|---:|---:|---|---:|---:|---|
| 1.556,3 | 185,3 | tvp | 2,0948 | 1.198.407 | não |
| 539,8 | 127,8 | tvp | 2,1989 | 1.226.242 | sim |
| 365,3 | 132,6 | tvp | 2,2256 | 1.226.977 | sim |
| 508,5 | 126,5 | tvp | 2,2124 | 1.227.886 | sim |

Segunda rodada com a mesma semente: **mesma sequência de pontos e mesma frente**.

## Ficha de cada ponto da frente do NSGA-II

Máximos entre os 16 casos (TVP: 12 avaliáveis), com o caso que governa. Potências das bombas: métrica auxiliar, não objetivo.

| P_D1 | P_D2 | recuperação (%) | Q_G V-001 (Sm³/d) | Q_G V-002 (Sm³/d) | VRU máx. (Sm³/d) / caso | TVP máx. (kPa) / caso | SG-001 vol. (m³) / d / gov. / caso | V-001 | V-002 | W B-001 / B-002 / B-003 (kW) | estado |
|---:|---:|---:|---:|---:|---|---|---|---|---|---|---|
| 510,5 | 133,7 | 97,897 | 975.490 | 240.274 | 1.215.765 / BOT 03 | 69,86 / BOT 14 | 684,8 / 6.050 / liquid / BOT 12 | 283,9 / 4.700 / liquid / BOT 02 | 284,7 / 4.700 / liquid / BOT 02 | 310,1 / 144,3 / 43,6 | viável |
| 537,6 | 133,9 | 97,897 | 957.455 | 258.262 | 1.215.717 / BOT 03 | 69,98 / BOT 14 | 684,8 / 6.050 / liquid / BOT 12 | 284,1 / 4.700 / liquid / BOT 02 | 284,8 / 4.700 / liquid / BOT 02 | 310,1 / 142,4 / 43,7 | viável |
| 538,2 | 133,9 | 97,897 | 957.086 | 258.630 | 1.215.716 / BOT 03 | 69,98 / BOT 14 | 684,8 / 6.050 / liquid / BOT 12 | 284,1 / 4.700 / liquid / BOT 02 | 284,8 / 4.700 / liquid / BOT 02 | 310,1 / 142,4 / 43,7 | viável |
