# Golden Case 01 — BOT 02 (Early Life), cenário-base, de ponta a ponta

Um caso seguido por todo o caminho produtivo: entrada do BOT → recombinação da Nota 4 → trem de
flashes → balanço → entradas dos TAGs → dimensionamento. Serve para conferir à mão o que o
software faz e para defender a cadeia no TCC.

- **Cenário:** CENÁRIO-BASE (P-18 = 700 kPa, P-19 = 200 kPa) — o dos resultados produtivos. **Não
  é** o ponto do subproblema otimizado da nota 42 (P_D1 ≈ 510–540 kPa, P_D2 ≈ 134 kPa).
- **Entrada auditada:** `tests/fixtures/python_ref/design_cases_bot.json`, sha256
  `ca3dfe559b32926c9d9ca4d9e75e2cec711f00f7fdfd2247242bbf3a754dac60`.
- **Baseline físico:** `b638c19`. Números gerados por `tools/tabelas_auditoria.py` (arquivo
  completo: [`golden_case_01.json`](golden_case_01.json)).
- **Por que o BOT 02:** é avaliável (sem gás de lift), está entre os de maior vazão de óleo (28.621 m³/d) e é o
  caso governante de cinco TAGs (V-001, V-002, TO-001, TO-002, P-002).

## 1. Entrada (BOT Tab. 2.2.2.3)

| grandeza | valor |
|---|---|
| fluido | Early Life |
| óleo (morto, padrão) | 28.621 m³/d |
| líquido | 31.802 m³/d (água 3.181 m³/d) |
| gás produzido | 12.000.000 Sm³/d |
| gás de lift | 0 → **avaliável** |
| T a jusante do choke | 50 °C |

## 2. Recombinação da Nota 4 (referência do FWKO: 2.500 kPa(a), 50 °C)

| grandeza | valor |
|---|---|
| ṅ gás | 506.331,0 kmol/d |
| ṅ líquido | 137.967,9 kmol/d |
| Q_G reproduzido no FWKO | 12.000.000,0001 Sm³/d (erro relativo 1,1·10⁻¹¹) |
| Q_O de óleo morto reproduzido | 28.620,99999 m³/d (erro relativo 5,4·10⁻¹¹) |

Nenhum componente ajustado: z_caso é a mistura das duas fases do mesmo flash (nota 39 §2).

## 3. Trem SG-001 → V-001 → V-002 (Peng-Robinson com pseudo-componentes)

| estágio | T (°C) | P (kPa) | β | Q_G (Sm³/d) | MW_v | Z_v | ρ_v (kg/m³) |
|---|---:|---:|---:|---:|---:|---:|---:|
| SG-001 | 52,68 | 2.500 | 0,78891 | 12.046.580 | 25,92 | 0,9289 | 25,747 |
| V-001 | 90,00 | 700 | 0,25082 | 808.445 | 36,13 | 0,9702 | 8,633 |
| V-002 | 90,00 | 200 | 0,09422 | 227.513 | 49,35 | 0,9813 | 3,331 |

Fechamento do trem: molar 0, mássico 0, por componente 9·10⁻¹⁷ (`ok`). A T do SG-001 (52,68 °C)
é a da mistura com o reciclo de água quente, não os 50 °C da referência — por isso o gás do FWKO
sai 0,39 % acima dos 12 MSm³/d do BOT.

## 4. Balanço (kg/d; T em °C; P em kPa)

| corrente | o que é | T | P | O | W | D | G |
|---|---|---:|---:|---:|---:|---:|---:|
| C-01 | alimentação | 50,0 | 2.500 | 25.445.419 | 3.670.874 | 0 | 14.547.444 |
| C-03 | + reciclo | 52,7 | 2.500 | 25.448.387 | 4.282.277 | 953.026 | 14.547.444 |
| C-04 | gás do SG-001 | 52,7 | 2.500 | 26.216 | 0 | 0 | 13.146.552 |
| C-05 | água do SG-001 | 52,7 | 2.500 | 7.930 | 3.639.935 | 810.072 | 0 |
| C-06 | óleo do SG-001 | 52,7 | 2.500 | 25.414.240 | 642.342 | 142.954 | 1.400.891 |
| C-09 | gás do V-001 | 90,0 | 700 | 27.989 | 0 | 0 | 1.204.493 |
| C-10 | líquido do V-001 | 90,0 | 700 | 25.386.252 | 642.342 | 142.954 | 196.398 |
| C-14 | água de diluição | 25,0 | 700 | 0 | 0 | 925.052 | 0 |
| C-17 | gás do V-002 | 90,0 | 200 | 277.308 | 0 | 0 | 196.398 |
| C-21 | óleo tratado | 90,0 | 200 | 25.105.976 | 30.939 | 114.980 | 0 |
| C-25 | óleo à estocagem | 40,0 | 600 | 25.105.976 | 30.939 | 114.980 | 0 |

O de uma corrente é o seu teor de **óleo de tanque**; o O dos gases é óleo de tanque que
vaporizou (e o arraste). **Fechamento global**: entra C-01 + C-14 = 44.588.788,79 kg/d; saem
C-04 + C-05 + C-09 + C-17 + C-25 = 44.588.788,79 kg/d (resíduo 1,4·10⁻¹³ relativo); por componente
≤ 6,5·10⁻¹² (O, W, D, G). Reciclo: 35 iterações, resíduo 7·10⁻¹¹.

| grandeza | valor |
|---|---|
| BSW na saída do FWKO | 2,39 % (≤ 40 % do BOT; η = η padrão 0,85, sem exigência acima) |
| Q_pre (P-001) / Q_H (P-002) / Q_D (DWH-001) / Q_C (P-003) | 16.343 / 7.741 / 2.909 / 13.335 kW |
| W B-001 / B-002 / B-003 (balanço) | 281,6 / 13,0 / 42,7 kW |
| recuperação de óleo (C-25/C-01, O) | 98,666 % |
| **TVP a 40 °C** | **100,55 kPa — NÃO CONFORME** ao limite de 70 kPa (cenário-base) |

## 5. Do estado aos TAGs (exemplo: V-001, caso 2)

| entrada | valor | origem |
|---|---|---|
| q_oil (líquido de C-10) | 1.219,9 m³/h | propriedade (Σ ṁ/ρ(T)) |
| q_gas (C-09) | 33.685,2 Sm³/h | balanço: ṅ_V·V_M do flash do estágio |
| ρ_gás | 8,633 kg/m³ | vapor de equilíbrio do trem (PR) |
| ρ do líquido | 893,9 kg/m³ | volumes aditivos (API + Laliberté) |
| tempo de retenção | 5 min | recomendada, S&A Tab. 3.2 (alto CO2) |
| gotícula de gás | 140 µm | método, S&A §3.7.1 |

## 6. O que o caso 2 decide no dimensionamento

| TAG | x isolado do caso 2 | x do envelope (16 casos) | o caso 2 governa? |
|---|---:|---:|:--:|
| V-001 | 4.700 mm | 4.700 mm | **sim** (líquido) |
| V-002 | 4.700 mm | 4.700 mm | **sim** (líquido) |
| TO-001 | 5.550 mm | 5.550 mm | **sim** (retenção) |
| TO-002 | 5.550 mm | 5.550 mm | **sim** (retenção) |
| P-002 | 1.704 tubos/passe | 1.701 tubos/passe | **sim** (térmica; grades desalinhadas, nota 33) |
| SG-001 | 5.750 mm | 6.050 mm | não (BOT 12) |
| P-003 | 4.015 tubos/passe | 7.435 tubos/passe | não (BOT 07) |
| B-001 / B-002 / B-003 | DN 600 / 65 / 125 | DN 600 / 250 / 125 | não (BOT 03) |
| P-001 | — | inviável | inviável no envelope (primeiro no BOT 01) |

## 7. Como reproduzir

```
uv run python tools/tabelas_auditoria.py              # regenera golden_case_01.json
uv run fpso-siz dimensionar --tag V-001 --casos tests/fixtures/python_ref/design_cases_bot.json \
    --auto-balanco --saida saida/tag --mc              # MC do V-001 com o caso 2 como governante
```
