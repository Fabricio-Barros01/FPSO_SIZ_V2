# Fase 5 — integração do serviço termodinâmico, em modo sombra

Gerado por `tools/integracao_termodinamica.py`.

> **O processo continua consumindo o caminho legado.** O flash roda em paralelo nos 3 pontos de equilíbrio e é comparado; nenhum resultado da planta mudou — há paridade bit a bit. Trocar a origem de uma propriedade exige mudar o `status` dela no mapa, e o guarda recusa consumo de propriedade não liberada.

## 1. Onde o flash foi integrado

| ponto | corrente de gás | pressão | o que o legado faz |
|---|---|---|---|
| SG-001 | C-04 | `P_FWKO` | ΔRs de Standing entre (P_FWKO, T03) e a condição padrão, multiplicado pela vazão de óleo |
| V-001 | C-09 | `P_D1` | ΔRs de Standing entre (P_D1, T_D1) e a condição padrão |
| V-002 | C-17 | `P_D2` | derivado do mesmo ΔRs do V-001 (regra do script de referência) |

## 2. Mapa de proveniência

A regra é a invariante 5 do `CLAUDE.md`: backend devolver número não é o mesmo que propriedade validada para engenharia.

| propriedade | origem atual | origem proposta | consumidores | status |
|---|---|---|---|---|
| `beta` — fração de fase (vapor/líquido) | não existe como fração: o gás liberado sai de ΔRs de Standing × vazão de óleo (P-39/P-40) | flash_tp(fluido='poco'): fração molar e mássica de vapor | balanco/modelo.py: vazão de gás de C-04, C-09 e C-17; todas as correntes a jusante; cargas térmicas (via vazões); dimensionamento de todos os TAGs | sombra |
| `y` — composição da fase vapor | corte N2–nC4 da composição de alimentação, renormalizado e CONSTANTE em toda a planta (P-03) | flash_tp: composição da fase vapor em cada estágio, que muda de estágio para estágio | pfd/fluidos.gas → Z, μ, k do gás; balanco/propriedades.gas_props → MW, cp, γ, ρ_std; balanco/indicadores → CO2 e H2S molares; entradas do PFD: capacidade de gás dos vasos | sombra |
| `x` — composição da fase líquida | não existe: o líquido é tratado por pseudo-componentes O/W/D/G com propriedades fixas | flash_tp: composição da fase líquida | nenhum hoje | sombra |
| `Z` — fator de compressibilidade do gás | balanço: Z = 1 (gás ideal, P-39). PFD: Z pela EOS de Peng-Robinson sobre a composição FIXA (pfd/fluidos.gas) | flash_tp: Z da fase vapor com a composição de equilíbrio do estágio | pfd/fluidos.gas → ρ_g = P·MW/(Z·R·T); capacidade de gás dos vasos (SG-001, V-001, V-002) | **liberada** |
| `MW` — massa molar das fases | MW do corte leve, constante (balanco/propriedades.gas_props) | flash_tp: MW de cada fase, dentro da caracterização adotada | ρ_std do gás; densidade relativa γ (Standing); indicadores molares; ρ_g no PFD | **liberada** |
| `rho_vapor` — densidade da fase vapor | P·MW/(Z·R·T) com MW e R do balanço (S&A eq. 1.8) | flash_tp: ρ da fase vapor pela EOS | capacidade de gás dos vasos; velocidade do gás; arraste de gotas | **liberada** |
| `rho_liquido` — densidade da fase líquida | óleo: correlação de API (P-07); água: premissa; sem correção por T nem Bo | flash_tp: ρ da fase líquida pela EOS | velocidades; holdup; tempo de residência; perda de carga; hidráulica de bombas; dimensionamento de vasos e tratadores; otimização | **BLOQUEADA** |
| `h` — entalpia | cp constante por pseudo-componente (P-10 a P-12), gás ideal a 25 °C, sem calor de flash | flash_tp: entalpia das fases | cargas térmicas Q_H, Q_C, Q_D; P-001, P-002, P-003; temperaturas de mistura | **BLOQUEADA** |
| `cp` — calor específico | constante por pseudo-componente (P-10 a P-12) | flash_tp: cp das fases | cargas térmicas; temperatura de mistura; LMTD dos trocadores | **BLOQUEADA** |
| `mu` — viscosidade | óleo: tabela do BOT + Beggs & Robinson (óleo vivo); água: Laliberté; gás: thermo sobre a composição fixa | flash_tp: μ das fases | película dos trocadores; decantação de gotas; hidráulica | **BLOQUEADA** |
| `k` — condutividade térmica | óleo: entrada proposta; água: lacuna; gás: thermo | flash_tp: k das fases | película dos trocadores | **BLOQUEADA** |

**Motivo de cada bloqueio:**

- `beta` (sombra): substituir muda a vazão de gás de todos os estágios e, por ela, o balanço de energia — que a Fase 5 não pode ativar (item 9). Fica medido e comparado.
- `y` (sombra): é a diferença física mais visível: hoje o gás tem a mesma composição no FWKO e no segundo desgaseificador, o que o equilíbrio contradiz. Trocar altera Z, ρ_g e o dimensionamento por capacidade de gás.
- `x` (sombra): não há consumidor no caminho atual; é entrada para a fase que reformular o líquido.
- `rho_liquido` (bloqueada): Peng-Robinson sem translação de volume subestima o volume de líquido: razão medida 0,541 contra mistura ideal (474,3 contra 877,3 kg/m³ na condição padrão). NÃO propagar. A fonte validada continua sendo a correlação de API; a proveniência fica marcada.
- `h` (bloqueada): não existe: sem Cp_ig dos pseudo-componentes o pacote não calcula entalpia. A rota energética atual é preservada (item 9).
- `cp` (bloqueada): idem: ausente por falta de Cp_ig com fonte.
- `mu` (bloqueada): o pacote de pseudo-componentes é montado sem correlações de transporte; μ das fases do fluido de poço volta NaN. A fonte validada continua sendo a atual.
- `k` (bloqueada): k da fase líquida de hidrocarboneto é caso (c) da invariante 5 — devolvido pelo backend, extrapolado, não validado. Somado a isso, o pacote de pseudo-componentes não o calcula.

### O estado é híbrido, e isso é declarado

Nenhum resumo deve apresentar o conjunto abaixo como produzido por um modelo termodinâmico único. Origem efetiva de cada propriedade **hoje**:

| propriedade | origem efetiva |
|---|---|
| `beta` | não existe como fração: o gás liberado sai de ΔRs de Standing × vazão de óleo (P-39/P-40) |
| `y` | corte N2–nC4 da composição de alimentação, renormalizado e CONSTANTE em toda a planta (P-03) |
| `x` | não existe: o líquido é tratado por pseudo-componentes O/W/D/G com propriedades fixas |
| `Z` | flash_tp: Z da fase vapor com a composição de equilíbrio do estágio |
| `MW` | flash_tp: MW de cada fase, dentro da caracterização adotada |
| `rho_vapor` | flash_tp: ρ da fase vapor pela EOS |
| `rho_liquido` | óleo: correlação de API (P-07); água: premissa; sem correção por T nem Bo |
| `h` | cp constante por pseudo-componente (P-10 a P-12), gás ideal a 25 °C, sem calor de flash |
| `cp` | constante por pseudo-componente (P-10 a P-12) |
| `mu` | óleo: tabela do BOT + Beggs & Robinson (óleo vivo); água: Laliberté; gás: thermo sobre a composição fixa |
| `k` | óleo: entrada proposta; água: lacuna; gás: thermo |

## 3. Fechamentos

48 de 48 pontos convergiram (16 casos × 3 pontos de equilíbrio). Erros máximos, em número:

| verificação | erro máximo |
|---|---|
| z_i = β·y_i + (1−β)·x_i, componente a componente | 1.11e-16 |
| soma das composições (z, y, x) | 5.73e-13 |
| balanço molar (Σβ = 1) | 0.00e+00 |
| balanço mássico (Σβ_mássica = 1) | 2.22e-16 |
| recomposição da corrente original | 1.11e-16 |
| coerência molar × mássica | 1.11e-16 |
| pontos monofásicos (fase desaparece corretamente) | 0 de 48 |

Todos no nível do épsilon de máquina: o flash fecha.

## 4. Antigo × novo, nos 16 casos

A comparação é do **gás liberado**: o legado usa a diferença de Rs de Standing (correlação black-oil calibrada em razão de solubilidade); o novo usa equilíbrio de fases sobre a composição caracterizada. São físicas diferentes respondendo à mesma pergunta, então a diferença é esperada — o que não se admite é diferença **inexplicada**.

| caso | ponto | T (°C) | P (kPa) | gás legado (kg/s) | VF molar (novo) | VF mássica (novo) | Z (novo) |
|---|---|---|---|---|---|---|---|
| 1 | SG-001 | 65,0 | 2.500 | 153,3658 | 0,67021 | 0,20759 | 0,93462 |
| 1 | V-001 | 90,0 | 700 | 3,3838 | 0,77494 | 0,26731 | 0,98080 |
| 1 | V-002 | 90,0 | 200 | 0,6655 | 0,81388 | 0,30371 | 0,99328 |
| 2 | SG-001 | 52,7 | 2.500 | 153,1129 | 0,65312 | 0,19878 | 0,92874 |
| 2 | V-001 | 90,0 | 700 | 3,6367 | 0,77494 | 0,26731 | 0,98080 |
| 2 | V-002 | 90,0 | 200 | 0,6655 | 0,81388 | 0,30371 | 0,99328 |
| 3 | SG-001 | 52,9 | 2.500 | 113,9843 | 0,71234 | 0,26383 | 0,92941 |
| 3 | V-001 | 90,0 | 700 | 3,4893 | 0,81534 | 0,33931 | 0,98144 |
| 3 | V-002 | 90,0 | 200 | 0,6391 | 0,84801 | 0,37846 | 0,99367 |
| 4 | SG-001 | 45,0 | 2.500 | 11,2253 | 0,64101 | 0,19289 | 0,92464 |
| 4 | V-001 | 90,0 | 700 | 0,4943 | 0,77494 | 0,26731 | 0,98080 |
| 4 | V-002 | 90,0 | 200 | 0,0865 | 0,81388 | 0,30371 | 0,99328 |
| 5 | SG-001 | 35,0 | 2.500 | 9,6994 | 0,53535 | 0,11771 | 0,92266 |
| 5 | V-001 | 90,0 | 700 | 0,5363 | 0,70538 | 0,19499 | 0,97949 |
| 5 | V-002 | 90,0 | 200 | 0,0886 | 0,75256 | 0,23133 | 0,99268 |
| 6 | SG-001 | 35,0 | 2.500 | 12,1515 | 0,81832 | 0,43475 | 0,91180 |
| 6 | V-001 | 90,0 | 700 | 0,1933 | 0,91079 | 0,53021 | 0,98171 |
| 6 | V-002 | 90,0 | 200 | 0,0319 | 0,92951 | 0,56324 | 0,99414 |
| 7 | SG-001 | 75,0 | 2.500 | 133,2845 | 0,86150 | 0,47597 | 0,93584 |
| 7 | V-001 | 90,0 | 700 | 3,5036 | 0,91079 | 0,53021 | 0,98171 |
| 7 | V-002 | 90,0 | 200 | 0,7314 | 0,92951 | 0,56324 | 0,99414 |
| 8 | SG-001 | 63,1 | 2.500 | 134,5246 | 0,85117 | 0,46508 | 0,92967 |
| 8 | V-001 | 90,0 | 700 | 2,5072 | 0,91079 | 0,53021 | 0,98171 |
| 8 | V-002 | 90,0 | 200 | 0,4876 | 0,92951 | 0,56324 | 0,99414 |
| 9 | SG-001 | 67,8 | 2.500 | 135,2197 | 0,85547 | 0,46951 | 0,93221 |
| 9 | V-001 | 90,0 | 700 | 1,9165 | 0,91079 | 0,53021 | 0,98171 |
| 9 | V-002 | 90,0 | 200 | 0,3833 | 0,92951 | 0,56324 | 0,99414 |
| 10 | SG-001 | 90,1 | 2.500 | 107,9158 | 0,92218 | 0,60359 | 0,94289 |
| 10 | V-001 | 90,1 | 700 | 1,4533 | 0,94548 | 0,63206 | 0,98259 |
| 10 | V-002 | 90,1 | 200 | 0,3322 | 0,95563 | 0,65208 | 0,99469 |
| 11 | SG-001 | 59,5 | 2.500 | 130,2043 | 0,90521 | 0,58213 | 0,92588 |
| 11 | V-001 | 90,0 | 700 | 1,2074 | 0,94546 | 0,63201 | 0,98258 |
| 11 | V-002 | 90,0 | 200 | 0,2298 | 0,95561 | 0,65203 | 0,99469 |
| 12 | SG-001 | 90,1 | 2.500 | 130,3914 | 0,92219 | 0,60360 | 0,94290 |
| 12 | V-001 | 90,1 | 700 | 1,0175 | 0,94548 | 0,63206 | 0,98259 |
| 12 | V-002 | 90,1 | 200 | 0,2326 | 0,95563 | 0,65209 | 0,99469 |
| 13 | SG-001 | 90,1 | 2.500 | 140,4381 | 0,91014 | 0,57328 | 0,94214 |
| 13 | V-001 | 90,1 | 700 | 1,3309 | 0,93605 | 0,60206 | 0,98237 |
| 13 | V-002 | 90,1 | 200 | 0,3043 | 0,94755 | 0,62283 | 0,99459 |
| 14 | SG-001 | 90,1 | 2.500 | 181,6852 | 0,91014 | 0,57328 | 0,94213 |
| 14 | V-001 | 90,1 | 700 | 1,3310 | 0,93605 | 0,60205 | 0,98237 |
| 14 | V-002 | 90,1 | 200 | 0,3043 | 0,94755 | 0,62283 | 0,99459 |
| 15 | SG-001 | 90,1 | 2.500 | 111,6168 | 0,92486 | 0,68027 | 0,93384 |
| 15 | V-001 | 90,1 | 700 | 0,6254 | 0,94905 | 0,71004 | 0,98014 |
| 15 | V-002 | 90,0 | 200 | 0,1430 | 0,96007 | 0,73195 | 0,99394 |
| 16 | SG-001 | 90,1 | 2.500 | 120,1765 | 0,92486 | 0,68027 | 0,93384 |
| 16 | V-001 | 90,1 | 700 | 0,6948 | 0,94905 | 0,71005 | 0,98014 |
| 16 | V-002 | 90,1 | 200 | 0,1588 | 0,96007 | 0,73196 | 0,99394 |

**Razão física da diferença.** O legado não calcula fração de fase: ele calcula quanto gás sai de solução, por ΔRs de Standing, e atribui esse volume ao estágio. O flash calcula a fração de vapor da corrente inteira na condição (T, P). Os dois números não são a mesma grandeza, e por isso nenhuma substituição foi feita: trocar um pelo outro mudaria a vazão de gás de todos os estágios e, por ela, o balanço de energia — que esta fase não pode ativar.

## 5. O que mudou na planta

**Nada.** Nenhum equipamento teve resultado alterado: a paridade bit a bit do instantâneo dos 11 TAGs e das 5.391 linhas de varredura é a mesma de antes do R1. O flash é calculado e descartado; o guarda impede consumo de propriedade não liberada.

## 6. Desempenho

| medida | valor |
|---|---|
| flashes por rodada de sombra | 48 |
| condições (T, P, z) distintas | 38 |
| **fator de recomputação** | **1,263** |
| tempo total em flash | 1,408 s |
| tempo por flash | 29,34 ms |

A recomputação vem de casos do mesmo fluido que caem na mesma condição (V-001 e V-002 operam a T e P fixas). **Não foi otimizada, apenas medida** — a Fase 5 não otimiza.

O caminho produtivo **não** paga nada disso: `resolver_caso` (0,52 ms), `resolver_todos` (19,7 ms) e `avaliar()` seguem sem chamar o flash, porque o modo é sombra. A medida acima é o custo que a integração terá **quando** for ligada.

