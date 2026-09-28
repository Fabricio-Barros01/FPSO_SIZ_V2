# 40 — μ do óleo vivo com o Rs do trem: limitação de aplicabilidade e sensibilidade

**Decisão do usuário (2026-09-28):** aprovado Rs do trem → Beggs & Robinson; **proibido** voltar a
Standing só para a viscosidade. Esta nota registra a limitação de aplicabilidade e mede a
sensibilidade. Não há segundo caminho produtivo: o estudo usa a mesma função do serviço
(`termo.oleo`) e o mesmo serviço por TAG, com a μ sobreposta como ajuste do usuário
(`tools/sensibilidade_viscosidade.py`, fatores em `config/pfd/sensibilidade_viscosidade.toml`).

## 1. Limitação de aplicabilidade

| aspecto | situação |
|---|---|
| faixas numéricas da correlação (`termo/fluidos.toml [oleo_vivo]`) | Rs 20–2.070 scf/STB, API 16–58, T 70–295 °F. Os Rs do trem (116–304 scf/STB no SG-001, 22–28 scf/STB no TO-001), a API (27,5; 28,2) e as T (35–90 °C = 95–194 °F) estão **dentro** |
| natureza do gás dissolvido | a correlação recebe só o **volume** de gás dissolvido (Rs); não tem variável de composição do gás. Aqui o gás dissolvido é rico em CO2 (17–56 % no fluido), e a fonte — fora do acervo local — **não demonstra** aplicabilidade a esse gás |
| fonte | Beggs & Robinson (1975), *JPT* 27(9), fora do acervo local, a conferir (já declarado) |
| consequência | a μ é número de modelo, não de PVT; o seu uso em projeto vale enquanto o dimensionamento não depender dela (§3) |

A limitação está no contrato (`proveniencia.toml`, `viscosidade_fase`) e em `fluidos.toml`
(`limitacao`).

## 2. Sensibilidade

Rs do trem multiplicado por 0,5–1,5 (cobre o Rs de Standing, 60–75 % menor, pela metade), mais
dois extremos: óleo morto (limite conservador) e o Rs de Standing (referência, não produtivo).

### SG-001 — `mu_oil` (Rs de C-06, T de C-04)

| caso | Rs do trem (Sm³/Sm³) | Rs Standing (ref.) | μ óleo morto (cP) | μ ×0,50 Rs | μ ×0,75 Rs | μ ×1,00 Rs | μ ×1,25 Rs | μ ×1,50 Rs | μ com Rs Standing |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 28,1 | 10,8 | 9,108 | 5,031 | 4,107 | 3,473 | 3,011 | 2,661 | 5,620 |
| 2 | 32,7 | 11,5 | 13,298 | 6,467 | 5,107 | 4,213 | 3,585 | 3,121 | 7,675 |
| 3 | 34,7 | 11,4 | 10,025 | 4,937 | 3,930 | 3,267 | 2,799 | 2,451 | 5,996 |
| 4 | 36,4 | 11,9 | 17,450 | 7,667 | 5,905 | 4,786 | 4,017 | 3,459 | 9,596 |
| 5 | 38,3 | 11,2 | 18,452 | 7,796 | 5,956 | 4,800 | 4,013 | 3,446 | 10,371 |
| 6 | 54,1 | 13,1 | 26,004 | 8,139 | 5,889 | 4,584 | 3,742 | 3,157 | 12,982 |
| 7 | 27,9 | 10,8 | 7,900 | 4,462 | 3,669 | 3,120 | 2,718 | 2,412 | 4,955 |
| 8 | 33,4 | 11,4 | 9,626 | 4,861 | 3,891 | 3,247 | 2,789 | 2,448 | 5,773 |
| 10 | 20,6 | 10,6 | 7,900 | 5,039 | 4,267 | 3,704 | 3,274 | 2,937 | 4,980 |
| 12 | 20,6 | 10,6 | 7,900 | 5,034 | 4,262 | 3,699 | 3,270 | 2,932 | 4,980 |
| 13 | 20,7 | 11,1 | 7,900 | 5,027 | 4,255 | 3,691 | 3,262 | 2,925 | 4,900 |
| 14 | 20,7 | 11,1 | 7,900 | 5,027 | 4,254 | 3,691 | 3,262 | 2,925 | 4,900 |

#### Efeito no dimensionamento de SG-001

| μ usada | diâmetro (mm) | Leff (m) | governante | caso governante | teto (mm) | mecanismo do teto |
|---|---:|---:|---|---|---:|---|
| regra do TAG (Rs do trem) | 6.050 | 17,867 | liquid | BOT 12 — Late Life | 10.021 | oil_in_water |
| Rs do trem ×0,50 | 6.050 | 17,867 | liquid | BOT 12 — Late Life | 7.418 | water_in_oil |
| Rs do trem ×0,75 | 6.050 | 17,867 | liquid | BOT 12 — Late Life | 9.394 | water_in_oil |
| Rs do trem ×1,25 | 6.050 | 17,867 | liquid | BOT 12 — Late Life | 10.021 | oil_in_water |
| Rs do trem ×1,50 | 6.050 | 17,867 | liquid | BOT 12 — Late Life | 10.021 | oil_in_water |
| óleo morto (limite conservador) | — | — | none |  | 3.607 | water_in_oil |
| Rs de Standing (referência, não produtivo) | 6.050 | 17,867 | liquid | BOT 12 — Late Life | 6.250 | water_in_oil |

### TO-001 — `mu_oil` (Rs de C-10, T de C-10)

| caso | Rs do trem (Sm³/Sm³) | Rs Standing (ref.) | μ óleo morto (cP) | μ ×0,50 Rs | μ ×0,75 Rs | μ ×1,00 Rs | μ ×1,25 Rs | μ ×1,50 Rs | μ com Rs Standing |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4,2 | — | 7,900 | 7,900 | 7,900 | 6,404 | 6,114 | 5,848 | — |
| 2 | 4,3 | — | 7,900 | 7,900 | 7,900 | 6,378 | 6,083 | 5,815 | — |
| 3 | 4,5 | — | 6,300 | 6,300 | 6,300 | 5,110 | 4,880 | 4,671 | — |
| 4 | 4,4 | — | 7,900 | 7,900 | 7,900 | 6,359 | 6,062 | 5,792 | — |
| 5 | 4,3 | — | 6,300 | 6,300 | 6,300 | 5,157 | 4,934 | 4,729 | — |
| 6 | 5,0 | — | 7,900 | 7,900 | 6,537 | 6,180 | 5,860 | 5,572 | — |
| 7 | 4,5 | — | 7,900 | 7,900 | 7,900 | 6,337 | 6,038 | 5,765 | — |
| 8 | 4,7 | — | 7,900 | 7,900 | 7,900 | 6,284 | 5,977 | 5,699 | — |
| 10 | 3,9 | — | 7,900 | 7,900 | 7,900 | 6,512 | 6,237 | 5,984 | — |
| 12 | 3,9 | — | 7,900 | 7,900 | 7,900 | 6,509 | 6,234 | 5,980 | — |
| 13 | 3,9 | — | 7,900 | 7,900 | 7,900 | 6,504 | 6,228 | 5,975 | — |
| 14 | 3,9 | — | 7,900 | 7,900 | 7,900 | 6,504 | 6,228 | 5,975 | — |

#### Efeito no dimensionamento de TO-001

| μ usada | diâmetro (mm) | Leff (m) | governante | caso governante | teto (mm) | mecanismo do teto |
|---|---:|---:|---|---|---:|---|
| regra do TAG (Rs do trem) | 5.550 | 16,428 | liquid | BOT 02 — Early Life | 18.725 | oil_in_water |
| Rs do trem ×0,50 | 5.550 | 16,428 | liquid | BOT 02 — Early Life | 17.107 | water_in_oil |
| Rs do trem ×0,75 | 5.550 | 16,428 | liquid | BOT 02 — Early Life | 17.107 | water_in_oil |
| Rs do trem ×1,25 | 5.550 | 16,428 | liquid | BOT 02 — Early Life | 18.725 | oil_in_water |
| Rs do trem ×1,50 | 5.550 | 16,428 | liquid | BOT 02 — Early Life | 18.725 | oil_in_water |
| óleo morto (limite conservador) | 5.550 | 16,428 | liquid | BOT 02 — Early Life | 17.107 | water_in_oil |


## 3. Leitura

- **SG-001**: o vaso (6.050 mm, 17,87 m, governado pelo líquido no BOT 12) **não muda** para Rs
  entre ×0,5 e ×1,5 do trem, nem com o Rs de Standing. Só o teto de decantação muda: com Rs ≤ ×0,75
  o mecanismo volta a água-em-óleo (7.418–9.394 mm), sempre acima do diâmetro escolhido. Com óleo
  morto o teto cai a 3.607 mm e o vaso fica inviável — é o alarme histórico do SG-001
  (`14-alarmes.md`), que a correção de óleo vivo resolveu; nada novo.
- **TO-001**: não muda em nenhum cenário. Com Rs baixo (≤ ×0,75) a correlação fica abaixo da faixa e
  a regra mantém o óleo morto (conservador).
- **Conclusão**: o dimensionamento dos vasos não depende da μ do óleo vivo na faixa de incerteza
  estudada; a limitação de aplicabilidade não afeta o resultado. P-001 e P-002 também recebem a
  μ (lado óleo) e ela entra no coeficiente de película; o P-001 está fora do subproblema e o P-002
  não foi estudado aqui — a sensibilidade deles fica pendente.
