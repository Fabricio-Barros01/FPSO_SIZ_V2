# 44 — Premissa de pressão dos degaseificadores: TVP do BOT (Fase A)

> **Estado: CONSOLIDADA (aprovação do usuário, 2026-10-02).** P-18/P-19 = 500/130 kPa
> (pressões ABSOLUTAS) são premissas PRELIMINARES do autor em `config/premissas.toml`, com esta
> nota como fonte. Avisos que permanecem: TVP **não verificada** nos casos 9, 11, 15 e 16 (gás de
> lift sem composição na fonte; a composição não foi substituída) e compatibilidade de P_D2 com a
> sucção da VRU **não verificada**. A rota de viscosidade é a vigente; a comparação Rs → μ é da
> Fase B. As tabelas abaixo comparam as premissas anteriores (700/200 kPa) com as vigentes.

## 1. Por que mudar

Com as premissas vigentes a TVP do óleo tratado na estocagem (40 °C) é **110,8 kPa** no caso 14,
contra o limite de **70 kPa** do BOT (§2.3.1.1, §2.7.1.10): g_TVP = +0,583 nos 12 casos avaliáveis
(nota 42, §6). A planta fecha e os 11 TAGs são dimensionados, mas isso **não** é atendimento à ET:
é uma não conformidade de processo. A Fase A trocou P-18/P-19 por um ponto que atende a TVP.

## 2. O ponto adotado

| premissa | anterior | vigente (preliminar do autor) |
|---|---:|---:|
| P-18 — P_D1 absoluta (desgaseificador 1 e desidratador) | 700 kPa | **500 kPa** |
| P-19 — P_D2 absoluta (desgaseificador 2 e dessalinizador) | 200 kPa | **130 kPa** |

- **Origem:** a grade-oráculo da nota 42 (§5) — P_D1 de 200 a 2.000 kPa a cada 150 kPa × P_D2 de
  110 a 250 kPa a cada 10 kPa, avaliada pelo mesmo serviço.
- **Critério de seleção (decisão do usuário, 2026-10-02):** o ponto EXATO da grade que forma a sua
  frente de Pareto (perda de óleo × carga da VRU) com a TVP atendida no máximo entre os 12 casos
  avaliáveis — g_TVP = −0,034, TVP máxima de 67,6 kPa (caso 14). Foi escolhido no lugar do ótimo do
  NSGA-II (≈ 510–540 kPa; 134 kPa), que fica sobre a fronteira (g_TVP ≈ −0,002).
- **Ressalvas:** a folga de 3,4 % é consequência da resolução da grade, **não** margem de segurança
  validada. Nos casos 9, 11, 15 e 16 (gás de lift sem composição na fonte) a TVP **não é
  verificada** — a composição do lift não foi substituída. A compatibilidade de P_D2 = 130 kPa com
  a sucção da VRU e com a hidráulica a jusante não foi verificada (não há fonte para o piso de P_D2,
  SPRINTS item 7). A cascata de pressões vale em todos os casos: P_FWKO = 2.500 > 500 > 130 kPa.

## 3. Como foi avaliado

Pelo caminho produtivo inteiro, sem segundo modelo: `tools/comparar_premissas.py --base P_D1=700
--base P_D2=200 --premissa P_D1=500 --premissa P_D2=130` monta dois contextos do mesmo serviço
(ambos com as propostas do pacote) e lê de cada um o balanço, o trem, a TVP, os 11 TAGs, a
operação das bombas e a integração térmica realizada do P-001 (ADR 0005). Antes de consolidar, a
mesma comparação rodou com a premissa como candidata (`premissas_candidatas.toml`); depois de
consolidada ela é idêntica bit a bit. O gate de sanidade (`tools/auditar_saida_pfd.py`) aprova a
planta. Testes: `tests/pfd/test_premissa_pressao.py`.

## 4. Resultado

TVP máxima nos 12 avaliáveis: **110,8 → 67,6 kPa** (caso 14 nos dois). Planta completa nos dois
estados. Carga da VRU no caso governante (3): 1.126.280 → 1.221.882 Sm³/d — o mesmo valor que a
nota 42 registra para (500; 130).

**Somas entre casos.** As somas de carga entre os 16 casos (P-001: 67.163,5 → 66.780,4 kW de carga
do balanço, 64.542,6 → 64.155,1 kW recuperados, 96,1 % nos dois) são **indicador comparativo**
entre premissas e geometrias. Os casos do BOT não operam simultaneamente: a soma não é demanda
simultânea nem energia anual.

### 4.1 Por caso (TVP na estocagem, P-001 e utilidades)

Q_H e Q_C são as cargas RESIDUAIS do P-002 e do P-003 (depois do que o P-001 recuperou de fato).

| caso | TVP antes (kPa) | TVP depois (kPa) | Q P-001 balanço antes → depois (kW) | Q P-001 realizado antes → depois (kW) | Q_H P-002 (kW) | Q_C P-003 (kW) | Q DWH-001 (kW) | W bombas (kW) |
|---:|---:|---:|---|---|---|---|---|---|
| 1 | 101,6 | 60,5 | 9.018,3 → 8.977,9 | 9.018,3 → 8.977,9 | 6.243,9 → 6.284,4 | 20.387,6 → 20.222,6 | 0,0 → 0,0 | 280,8 → 311,0 |
| 2 | 100,6 | 60,0 | 16.342,9 → 16.235,4 | 14.950,0 → 14.837,4 | 9.133,9 → 9.248,5 | 14.727,5 → 14.613,5 | 2.909,0 → 2.894,3 | 337,2 → 369,7 |
| 3 | 95,3 | 56,6 | 16.137,5 → 16.002,3 | 16.137,5 → 16.002,3 | 7.851,3 → 7.989,5 | 13.313,1 → 13.168,1 | 2.908,5 → 2.890,7 | 336,2 → 368,0 |
| 4 | 99,8 | 59,7 | 2.681,7 → 2.661,2 | 2.439,6 → 2.415,6 | 1.171,2 → 1.195,2 | 1.375,8 → 1.368,8 | 0,0 → 0,0 | 36,4 → 40,3 |
| 5 | 93,6 | 56,0 | 4.459,8 → 4.416,2 | 3.473,9 → 3.434,5 | 2.319,1 → 2.358,5 | 1.476,2 → 1.466,6 | 0,0 → 0,0 | 47,5 → 52,4 |
| 6 | 93,1 | 55,7 | 1.145,5 → 1.130,9 | 1.145,5 → 1.130,9 | 372,3 → 386,9 | 125,9 → 124,2 | 0,0 → 0,0 | 12,1 → 13,4 |
| 7 | 100,4 | 59,7 | 3.190,0 → 3.194,9 | 3.190,0 → 3.194,9 | 5.956,5 → 5.951,5 | 26.185,2 → 25.959,7 | 0,0 → 0,0 | 280,5 → 310,5 |
| 8 | 97,7 | 58,0 | 6.795,8 → 6.746,8 | 6.795,8 → 6.746,8 | 7.032,5 → 7.079,5 | 12.892,8 → 12.762,0 | 1.934,6 → 1.923,5 | 282,7 → 310,2 |
| 9 | não verificada | não verificada | 3.937,4 → 3.952,5 | 3.937,4 → 3.952,5 | 5.981,9 → 5.963,5 | 11.785,2 → 11.787,5 | 1.524,3 → 1.524,3 | 262,4 → 290,0 |
| 10 | 109,1 | 66,1 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 11.989,0 → 11.947,0 | 1.167,2 → 1.164,5 | 223,9 → 246,8 |
| 11 | não verificada | não verificada | 3.454,6 → 3.462,3 | 3.454,6 → 3.462,3 | 7.380,2 → 7.369,4 | 4.843,0 → 4.844,4 | 804,5 → 804,5 | 221,7 → 245,1 |
| 12 | 109,1 | 66,1 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 8.367,0 → 8.337,7 | 814,5 → 812,6 | 221,8 → 244,7 |
| 13 | 110,8 | 67,6 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 10.054,1 → 10.023,7 | 978,1 → 976,0 | 231,0 → 254,8 |
| 14 | 110,8 | 67,6 | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 10.053,2 → 10.022,8 | 978,0 → 976,0 | 231,0 → 254,8 |
| 15 | não verificada | não verificada | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 3.657,6 → 3.662,0 | 354,3 → 354,3 | 111,9 → 123,6 |
| 16 | não verificada | não verificada | 0,0 → 0,0 | 0,0 → 0,0 | 0,0 → 0,0 | 4.072,4 → 4.077,3 | 394,4 → 394,4 | 124,5 → 137,6 |

### 4.2 Gás por estágio (G_F = SG-001, G_D1 = V-001, G_D2 = V-002)

| caso | G_F antes → depois (Sm³/d) | G_D1 antes → depois (Sm³/d) | G_D2 antes → depois (Sm³/d) |
|---:|---|---|---|
| 1 | 12.000.000 → 12.000.000 | 679.386 → 777.760 | 218.928 → 194.215 |
| 2 | 12.046.580 → 12.046.501 | 808.445 → 914.320 | 227.513 → 200.162 |
| 3 | 9.349.397 → 9.349.287 | 861.091 → 982.694 | 265.189 → 239.188 |
| 4 | 900.000 → 900.000 | 118.803 → 133.315 | 30.454 → 26.631 |
| 5 | 900.000 → 900.000 | 163.734 → 185.743 | 46.898 → 41.958 |
| 6 | 900.000 → 900.000 | 61.767 → 68.616 | 13.528 → 11.815 |
| 7 | 10.000.000 → 10.000.000 | 668.038 → 771.058 | 233.563 → 208.300 |
| 8 | 10.040.998 → 10.041.036 | 546.411 → 624.578 | 171.694 → 153.446 |
| 9 | 9.832.766 → 9.832.772 | 139.360 → 150.867 | 27.874 → 16.361 |
| 10 | 7.500.477 → 7.500.521 | 190.052 → 218.870 | 66.729 → 56.322 |
| 11 | 8.901.742 → 8.901.746 | 82.545 → 89.031 | 15.713 → 9.223 |
| 12 | 9.000.429 → 9.000.471 | 133.046 → 153.215 | 46.711 → 39.424 |
| 13 | 9.300.457 → 9.300.501 | 160.777 → 184.048 | 53.755 → 44.504 |
| 14 | 12.000.482 → 12.000.529 | 160.775 → 184.044 | 53.754 → 44.502 |
| 15 | 6.455.559 → 6.455.560 | 36.171 → 39.586 | 8.270 → 4.854 |
| 16 | 6.950.628 → 6.950.630 | 40.184 → 43.978 | 9.187 → 5.392 |

### 4.3 Equipamentos (resultado principal e caso governante)

`area_total` é a área de OPERAÇÃO (cascos em série × trens em serviço × área por casco);
`area_instalada` soma os trens de reserva (P-001: 1 trem, BOT 2.7.1.11). No P-001: 4.392,5 m² de
operação + 1.098,1 m² do trem de reserva = **5.490,7 m² instalados** (eram 5.672,0 m² com 700/200
kPa). O cartão do memorial mostra os dois valores com esses nomes.

| TAG | grandeza | antes | depois | variação | governante antes → depois |
|---|---|---:|---:|---:|---|
| B-001 | Diâmetro nominal DN [mm] | 600,000 | 600,000 | 0,0 % | carga estática (BOT 03 — Early Life Blend) → carga estática (BOT 03 — Early Life Blend) |
| B-001 | Carga do sistema H [m] | 75,021 | 83,058 | 10,7 % |  |
| B-001 | Potência nominal requerida [kW] | 307,295 | 337,241 | 9,7 % |  |
| B-002 | Diâmetro nominal DN [mm] | 250,000 | 250,000 | 0,0 % | carga estática (BOT 03 — Early Life Blend) → carga estática (BOT 02 — Early Life) |
| B-002 | Carga do sistema H [m] | 183,425 | 202,183 | 10,2 % |  |
| B-002 | Potência nominal requerida [kW] | 143,261 | 157,911 | 10,2 % |  |
| B-003 | Diâmetro nominal DN [mm] | 125,000 | 125,000 | 0,0 % | carga estática (BOT 03 — Early Life Blend) → carga estática (BOT 02 — Early Life) |
| B-003 | Carga do sistema H [m] | 252,185 | 259,338 | 2,8 % |  |
| B-003 | Potência nominal requerida [kW] | 45,545 | 46,609 | 2,3 % |  |
| P-001 | Tubos por passe | 397,000 | 392,000 | -1,3 % | área de troca térmica (BOT 03 — Early Life Blend) → área de troca térmica (BOT 03 — Early Life Blend) |
| P-001 | Comprimento do tubo L [m] | 5,968 | 5,851 | -2,0 % |  |
| P-001 | Fração da carga do balanço realizada | 0,961 | 0,961 | -0,0 % |  |
| P-001 | area_total | 4.537,636 | 4.392,549 | -3,2 % |  |
| P-001 | area_instalada | 5.672,046 | 5.490,687 | -3,2 % |  |
| P-002 | Tubos por passe | 1.901,000 | 1.917,000 | 0,8 % | área de troca térmica (BOT 02 — Early Life) → área de troca térmica (BOT 02 — Early Life) |
| P-002 | Comprimento do tubo L [m] | 5,995 | 5,994 | -0,0 % |  |
| P-002 | area_total | 454,710 | 458,446 | 0,8 % |  |
| P-002 | area_instalada | 454,710 | 458,446 | 0,8 % |  |
| P-003 | Tubos por passe | 7.435,000 | 7.370,000 | -0,9 % | área de troca térmica (BOT 07 — Mid Life) → área de troca térmica (BOT 07 — Mid Life) |
| P-003 | Comprimento do tubo L [m] | 4,910 | 4,912 | 0,0 % |  |
| P-003 | area_total | 1.456,401 | 1.444,355 | -0,8 % |  |
| P-003 | area_instalada | 1.456,401 | 1.444,355 | -0,8 % |  |
| SG-001 | Diâmetro d [mm] | 6.050,000 | 6.050,000 | 0,0 % | capacidade de líquido (BOT 12 — Late Life) → capacidade de líquido (BOT 12 — Late Life) |
| SG-001 | volume | 684,837 | 684,830 | -0,0 % |  |
| TO-001 | Diâmetro d [mm] | 5.550,000 | 5.550,000 | 0,0 % | capacidade de líquido (retenção) (BOT 02 — Early Life) → capacidade de líquido (retenção) (BOT 02 — Early Life) |
| TO-001 | volume | 531,702 | 529,710 | -0,4 % |  |
| TO-002 | Diâmetro d [mm] | 5.550,000 | 5.550,000 | 0,0 % | capacidade de líquido (retenção) (BOT 02 — Early Life) → capacidade de líquido (retenção) (BOT 02 — Early Life) |
| TO-002 | volume | 531,059 | 527,626 | -0,6 % |  |
| V-001 | Diâmetro d [mm] | 4.700,000 | 4.700,000 | 0,0 % | capacidade de líquido (BOT 02 — Early Life) → capacidade de líquido (BOT 02 — Early Life) |
| V-001 | volume | 284,857 | 283,849 | -0,4 % |  |
| V-002 | Diâmetro d [mm] | 4.700,000 | 4.700,000 | 0,0 % | capacidade de líquido (BOT 02 — Early Life) → capacidade de líquido (BOT 02 — Early Life) |
| V-002 | volume | 286,380 | 284,623 | -0,6 % |  |

### 4.4 NPSH disponível das bombas

O líquido sai do vaso no ponto de bolha (Pv = P do vaso), então
NPSHd = (P₀ − Pv)/(ρg) + h₀ − h_atrito,suc ≈ h₀ − h_atrito,suc: a pressão do vaso se cancela, e
baixar P-18/P-19 não tira NPSH. O NPSHd fica entre 4,81 e 5,00 m em todos os casos, antes e
depois (diferença ≤ 0,004 m, de ρ e do atrito). A folga é contra **NPSHr + margem = 3 + 1 m
PROPOSTOS** (`pendencias_propostas.toml`): a comparação com o NPSHr do fabricante está
**PENDENTE** — não há curva de bomba no acervo.

| bomba | caso | P sucção antes → depois (kPa) | NPSHd antes → depois (m) | NPSHr + margem (m) | folga antes → depois (m) |
|---|---|---|---|---:|---|
| B-001 | BOT 01 — Early Life | 200,0 → 130,0 | 4,841 → 4,844 | 4,0 | 0,841 → 0,844 |
| B-001 | BOT 02 — Early Life | 200,0 → 130,0 | 4,840 → 4,843 | 4,0 | 0,840 → 0,843 |
| B-001 | BOT 03 — Early Life Blend | 200,0 → 130,0 | 4,842 → 4,846 | 4,0 | 0,842 → 0,846 |
| B-001 | BOT 04 — Early Life | 200,0 → 130,0 | 4,997 → 4,997 | 4,0 | 0,997 → 0,997 |
| B-001 | BOT 05 — Low CO2 | 200,0 → 130,0 | 4,995 → 4,995 | 4,0 | 0,995 → 0,995 |
| B-001 | BOT 06 — Mid Life | 200,0 → 130,0 | 5,000 → 5,000 | 4,0 | 1,000 → 1,000 |
| B-001 | BOT 07 — Mid Life | 200,0 → 130,0 | 4,841 → 4,844 | 4,0 | 0,841 → 0,844 |
| B-001 | BOT 08 — Mid Life | 200,0 → 130,0 | 4,929 → 4,930 | 4,0 | 0,929 → 0,930 |
| B-001 | BOT 09 — Mid Life | 200,0 → 130,0 | 4,954 → 4,954 | 4,0 | 0,954 → 0,954 |
| B-001 | BOT 10 — Late Life | 200,0 → 130,0 | 4,973 → 4,973 | 4,0 | 0,973 → 0,973 |
| B-001 | BOT 11 — Late Life | 200,0 → 130,0 | 4,987 → 4,987 | 4,0 | 0,987 → 0,987 |
| B-001 | BOT 12 — Late Life | 200,0 → 130,0 | 4,987 → 4,987 | 4,0 | 0,987 → 0,987 |
| B-001 | BOT 13 — High CO2 | 200,0 → 130,0 | 4,981 → 4,981 | 4,0 | 0,981 → 0,981 |
| B-001 | BOT 14 — High CO2 | 200,0 → 130,0 | 4,981 → 4,981 | 4,0 | 0,981 → 0,981 |
| B-001 | BOT 15 — Highest CO2 | 200,0 → 130,0 | 4,997 → 4,997 | 4,0 | 0,997 → 0,997 |
| B-001 | BOT 16 — Highest CO2 | 200,0 → 130,0 | 4,997 → 4,997 | 4,0 | 0,997 → 0,997 |
| B-002 | BOT 02 — Early Life | 700,0 → 500,0 | 4,999 → 4,999 | 4,0 | 0,999 → 0,999 |
| B-002 | BOT 03 — Early Life Blend | 700,0 → 500,0 | 4,999 → 4,999 | 4,0 | 0,999 → 0,999 |
| B-002 | BOT 08 — Mid Life | 700,0 → 500,0 | 4,963 → 4,963 | 4,0 | 0,963 → 0,963 |
| B-002 | BOT 09 — Mid Life | 700,0 → 500,0 | 4,933 → 4,933 | 4,0 | 0,933 → 0,933 |
| B-002 | BOT 10 — Late Life | 700,0 → 500,0 | 4,930 → 4,930 | 4,0 | 0,930 → 0,930 |
| B-002 | BOT 11 — Late Life | 700,0 → 500,0 | 4,862 → 4,862 | 4,0 | 0,862 → 0,862 |
| B-002 | BOT 12 — Late Life | 700,0 → 500,0 | 4,863 → 4,863 | 4,0 | 0,863 → 0,863 |
| B-002 | BOT 13 — High CO2 | 700,0 → 500,0 | 4,882 → 4,882 | 4,0 | 0,882 → 0,882 |
| B-002 | BOT 14 — High CO2 | 700,0 → 500,0 | 4,882 → 4,882 | 4,0 | 0,882 → 0,882 |
| B-002 | BOT 15 — Highest CO2 | 700,0 → 500,0 | 4,958 → 4,958 | 4,0 | 0,958 → 0,958 |
| B-002 | BOT 16 — Highest CO2 | 700,0 → 500,0 | 4,948 → 4,948 | 4,0 | 0,948 → 0,948 |
| B-003 | BOT 02 — Early Life | 200,0 → 130,0 | 4,812 → 4,813 | 4,0 | 0,812 → 0,813 |
| B-003 | BOT 03 — Early Life Blend | 200,0 → 130,0 | 4,812 → 4,814 | 4,0 | 0,812 → 0,814 |
| B-003 | BOT 08 — Mid Life | 200,0 → 130,0 | 4,915 → 4,916 | 4,0 | 0,915 → 0,916 |
| B-003 | BOT 09 — Mid Life | 200,0 → 130,0 | 4,947 → 4,947 | 4,0 | 0,947 → 0,947 |
| B-003 | BOT 10 — Late Life | 200,0 → 130,0 | 4,969 → 4,969 | 4,0 | 0,969 → 0,969 |
| B-003 | BOT 11 — Late Life | 200,0 → 130,0 | 4,985 → 4,985 | 4,0 | 0,985 → 0,985 |
| B-003 | BOT 12 — Late Life | 200,0 → 130,0 | 4,984 → 4,984 | 4,0 | 0,984 → 0,984 |
| B-003 | BOT 13 — High CO2 | 200,0 → 130,0 | 4,978 → 4,978 | 4,0 | 0,978 → 0,978 |
| B-003 | BOT 14 — High CO2 | 200,0 → 130,0 | 4,978 → 4,978 | 4,0 | 0,978 → 0,978 |
| B-003 | BOT 15 — Highest CO2 | 200,0 → 130,0 | 4,997 → 4,997 | 4,0 | 0,997 → 0,997 |
| B-003 | BOT 16 — Highest CO2 | 200,0 → 130,0 | 4,996 → 4,996 | 4,0 | 0,996 → 0,996 |

## 5. Leitura

- **Bombas — a maior mudança.** O recalque não muda (premissas de descarga); a sucção cai com a
  pressão do vaso a montante: B-001 (C-21, de TO-002) 200 → 130 kPa, B-002 (C-12, de TO-001)
  700 → 500 kPa, B-003 (C-19, de TO-002) 200 → 130 kPa. A ΔP sobe 11,7 %, 10,5 % e 2,9 %, e a
  altura e a potência acompanham (+10,7 %, +10,2 %, +2,8 %). DN não muda. O caso governante da
  B-002 e da B-003 passa de BOT 03 para BOT 02.
- **Gás.** Mais vapor no V-001 (+11 a +15 % nos 12 casos sem lift) e menos no V-002; a soma à VRU
  sobe 8,5 % no caso governante. É o custo da TVP que a nota 42 quantificou (0,76 p.p. de
  recuperação e 89 mil Sm³/d).
- **Vasos.** Diâmetros iguais; volumes −0,4 a −0,6 % (V-001, V-002, TO-001, TO-002). Os vasos são
  governados pela capacidade de LÍQUIDO, que quase não muda; a carga de gás maior do V-001 não
  passa a governar.
- **Trocadores.** A carga do P-001 cai 0,6 % na soma entre casos (indicador comparativo) (o óleo chega ao pré-aquecedor um pouco
  diferente depois de mais flash); a fração recuperada fica em 96,1 % e a área de operação e a instalada caem
  3,2 %. P-002 +0,8 %, P-003 −0,8 %. Casos governantes inalterados.

## 6. Consolidação (2026-10-02)

- `config/premissas.toml`: P-18 = 500 kPa e P-19 = 130 kPa, absolutas, "premissa preliminar do
  autor", com esta nota e as ressalvas em `fonte`. A candidata saiu de `premissas_candidatas.toml`.
- Regressões revistas por esta justificativa: `tests/fixtures/python_ref/regressao_eficiencia.json`
  (regenerada por `tools/gerar_regressao_eficiencia.py`; mudam só P_D1/P_D2 nas premissas, e os
  16 casos pela cascata — a montante do V-001 o efeito é o do reciclo de água C-13 + C-20, que
  chega ao FWKO até 0,08 °C mais quente pelo trabalho maior das bombas, e muda C-02…C-06 em no
  máximo 0,01 °C), os snapshots do terminal (V-001 −0,4 %; geometria e área do P-001), o cartão do
  V-001 em `test_memorial_tag` (11,72 → 11,66 m de Leff; 284,9 → 283,8 m³) e o excesso de diluição
  em `test_verificacao_fisica` (0,3665/0,3666 → 0,3647/0,3644).
- Rótulos corrigidos no cartão dos trocadores: "Área de operação (trens em serviço)", "Área
  instalada (operação + reserva)" e "soma dos casos (indicador comparativo)".
- O memorial fica na Rev. 0 (em desenvolvimento e validação).
