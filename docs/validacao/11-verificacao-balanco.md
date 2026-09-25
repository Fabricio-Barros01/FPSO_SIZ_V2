# F10v — verificação física do balanço e premissa "sem fase aquosa" (P-42)

Pedido do usuário (2026-09-25): verificação rigorosa dos balanços e dos cálculos, porque o
FPSO "parecia não ter água saindo nas correntes". O plano aprovado tem dois escopos:
- **Balanço:** só verificação. **Nenhum número muda**; a paridade bit a bit com o oráculo
  se mantém.
- **Dimensionamento:** implementa a premissa da fase aquosa que o usuário fixou.

> **Premissa P-42 (usuário, 2026-09-25).** Nenhuma água fictícia. O BOT 2.3.1.1 é limite
> superior: BSW_saída(TO-002) = min(BSW_entrada; 0,5 %). Nos casos 1 e 4–7 as correntes
> aquosas do FWKO, do TO-001 e do TO-002 são nulas, e o reciclo (Nota 11 da Tab. 2.2.2.3)
> é de óleo. Os critérios de dimensionamento que dependem da fase aquosa retornam "não
> aplicável — sem fase aquosa", sem exceção e sem governar o envelope; a fase aquosa é
> dimensionada pelos casos com água. Nos casos com água, o FWKO sempre deixa água na saída
> de óleo; só o TO-002, último separador, chega à especificação.

## Uso

```sh
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/   # imprime a verificação física
uv run fpso-siz                                                        # Balanço: linhas de água e alertas
uv run pytest tests/balanco/test_verificacao_fisica.py tests/sizing/test_sem_fase_aquosa.py
```

## 1. Por que "não saía água"

A água sai. Nos 11 casos com água ela deixa a planta por **C-05** (água livre do FWKO) e
pelo BSW do óleo tratado em **C-25**. A água dos tratadores (C-12, C-19) volta ao M-01 por
C-02 (BOT 2.7.1.6); o gás sai seco (água vaporizada não modelada, §6).

Os casos 1, 4, 5, 6 e 7 têm **BSW nulo no próprio BOT**: Tab. 2.2.2.3, `liquid_sm3d` =
`oil_sm3d`; a Nota 5 diz que o water cut vai de 0 a 95 %. Neles não entra água nenhuma.

O terminal abria "Ver correntes de um caso" no caso 1, e o resumo do balanço não tinha
nenhuma linha sobre a água. Corrigido:
- o resumo (interativo e `fpso-siz balanco`) mostra o fechamento de água, as saídas e os
  casos sem fase aquosa;
- "Ver correntes" abre no primeiro caso com água e identifica o caso sem água quando ele é
  escolhido.

**Água (W + D) por caso, kg/s** (`indicadores.balanco_agua`; fronteiras lidas de
`topologia_db.toml`):

| Caso | BSW C-01 | Entra W (C-01) | Entra D (C-14) | Sai C-05 | Sai C-25 | Reciclo C-02 | entra − sai |
|---|---|---|---|---|---|---|---|
| 1, 4, 5, 6, 7 | 0,0 % | 0,00 | 0,00 | 0,00 | 0,000 | 0,00 | 0 |
| 2, 3 | 10,0 % | 42,49 | 10,73 | 51,51 | 1,711 | 50,34 | −1,3e-11 |
| 8 | 40,0 % | 169,91 | 7,14 | 175,91 | 1,146 | 174,96 | −1,3e-11 |
| 9 | 52,8 % | 224,42 | 5,61 | 229,13 | 0,901 | 137,69 | −9,6e-12 |
| 10 | 59,8 % | 228,68 | 4,30 | 232,28 | 0,690 | 105,56 | −8,4e-12 |
| 11 | 75,0 % | 318,58 | 2,96 | 321,06 | 0,476 | 72,81 | −2,6e-12 |
| 12 | 74,7 % | 317,22 | 3,00 | 319,73 | 0,482 | 73,75 | −3,2e-12 |
| 13, 14 | 69,6 % | 295,81 | 3,60 | 298,83 | 0,578 | 88,54 | −3,9e-12 |
| 15 | 88,9 % | 377,47 | 1,30 | 378,56 | 0,209 | 32,09 | −1,1e-12 |
| 16 | 87,6 % | 372,22 | 1,45 | 373,44 | 0,233 | 35,72 | −3,6e-12 |

## 2. Validade numérica

- **Paridade:** bit a bit com o oráculo (`tests/balanco/test_paridade.py`, inalterado). O
  caso 1 é conferido de novo em `test_verificacao_fisica.py`.
- **Auditoria independente:** 16 verificações, maior |desvio| nos 16 casos:

| Verificação | Desvio | Verificação | Desvio |
|---|---|---|---|
| massa global | 1,3e-11 kg/s | resíduo por componente | 9,9e-11 kg/s |
| energia global | 2,0e-9 kW | cargas térmicas | 3,6e-12 kW |
| gás por estágio | 1,9e-9 Sm³/d | molar CO₂/H₂S | 1,8e-12 kmol/h |
| BSW de saída | 1,1e-16 | salinidade do óleo | 5,1e-13 mg/L |
| demais (8) | ≤ 1,8e-12 | | |

- **Reciclo:** converge em 4–35 iterações (tolerância 1e-10).
- **Vazões:** nenhuma é negativa além do arredondamento. O gás de C-18 em diante sai de
  ṁ_G,C16 − ṁ_G,C17, que é zero na física e dá até −2,2e-16 kg/s no ponto flutuante
  (≈ 1 ulp) nos casos 3, 6, 10 e 11.
- **Temperaturas:** T08 ≥ 90 °C em todos os casos (BOT 2.7.1.4). Com Q_pre > 0, as duas
  aproximações do pré-aquecedor são ≥ dT_app (P-32).

## 3. Premissa P-42 no balanço (confere, sem mudança)

O modelo de referência já cumpre a premissa:
- **TO-001 e TO-002:** `split_water` impõe `w_óleo = min(BSW/(1−BSW)·Q_O, w_entrada)`, que
  dá **BSW_saída = min(BSW_entrada; especificação)**.
- **FWKO:** a especificação é imposta sobre o BSW da chegada C-01: min(40 %; BSW₀₁), BOT
  2.7.1.2.
- **Casos sem água:** todas as correntes aquosas são zero exato.

| Caso | BSW C-06 (FWKO) | BSW C-11 (TO-001) | BSW C-21 (TO-002) | Sal emulsão | Sal só óleo | Diluição a mais | γ gás | T C-03 |
|---|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | 0 | — | — | — | 0,927 | 65,0 °C |
| 2 | 10,0 % | 1,00 % | 0,50 % | 226,7 | 227,8 | 36,7 % | 0,927 | 56,4 °C |
| 3 | 10,0 % | 1,00 % | 0,50 % | 226,7 | 227,8 | 36,7 % | 0,898 | 56,8 °C |
| 4 | 0 | 0 | 0 | — | — | — | 0,927 | 45,0 °C |
| 5 | 0 | 0 | 0 | — | — | — | 0,811 | **35,0 °C** |
| 6 | 0 | 0 | 0 | — | — | — | 0,972 | **35,0 °C** |
| 7 | 0 | 0 | 0 | — | — | — | 0,972 | 75,0 °C |
| 8 | 40,0 % | 1,00 % | 0,50 % | 273,3 | 274,7 | 5,7 % | 0,972 | 70,4 °C |
| 9 | 40,0 % | 1,00 % | 0,50 % | 277,9 | 279,3 | 3,4 % | 0,972 | 72,0 °C |
| 10 | 40,0 % | 1,00 % | 0,50 % | 279,6 | 281,1 | 2,5 % | 1,034 | 90,2 °C |
| 11 | 40,0 % | 1,00 % | 0,50 % | 282,3 | 283,7 | 1,2 % | 1,034 | 60,3 °C |
| 12 | 40,0 % | 1,00 % | 0,50 % | 282,3 | 283,7 | 1,3 % | 1,034 | 90,1 °C |
| 13, 14 | 40,0 % | 1,00 % | 0,50 % | 281,5 | 282,9 | 1,6 % | 1,080 | 90,2 °C |
| 15 | 40,0 % | 1,00 % | 0,50 % | 284,0 | 285,4 | 0,5 % | 1,222 | 90,1 °C |
| 16 | 40,0 % | 1,00 % | 0,50 % | 283,9 | 285,3 | 0,5 % | 1,222 | 90,1 °C |

Sal em mg/L. "Sal emulsão" e "sal só óleo" usam o sal real de cada água (S_W = 240.000 e
S_D = 0 mg/L) no volume padrão.

- **Sal (A5):** o limite de 285 mg/L (BOT 2.3.1.1) vale **no volume da emulsão**, por
  decisão do usuário (2026-09-25). Todos os casos atendem; o máximo é 284,0 mg/L. Na base
  só do óleo, os casos 15 e 16 dariam 285,4 e 285,3 mg/L (informativo).
- **Diluição (A3):** o modelo calcula a água de diluição supondo S_W para toda a água
  residual de C-11 (`Q_D = Q_A,C11·(S_W/S_res − 1)`). Parte dessa água, porém, é diluição
  reciclada, sem sal. A diluição sai de 0,5 % a 36,7 % maior que a necessária. É
  conservador para a especificação, mas superestima Q_D, a carga do DWH-001 e a vazão do
  TO-002.
- **FWKO a 35 °C (A4):** nos casos 5 e 6 a entrada do FWKO fica abaixo de 40 °C. O BOT
  2.7.1.6 pede 40 °C por recirculação, e a Nota 11 manda recircular óleo nos casos com BSW
  nulo. O reciclo de óleo **não é modelado** (P-41, "A VALIDAR"); o caso 1 (65 °C) não
  precisa dele.

## 4. Premissas conferidas

| Id | Premissa | Valor | Origem | Conferência |
|---|---|---|---|---|
| F-02 | P do FWKO | 2500 kPa | BOT 2.7.1.2 | confere ("operating at 2,500 kPa(a)") |
| F-05 | T mínima nos tratadores | 90 °C | BOT 2.7.1.4 | confere ("at least 90°C") |
| F-06 | água no óleo do FWKO | até 40 % | BOT 2.7.1.2 | confere ("up to 40% of water") |
| F-07 | T de entrada do FWKO | 40 °C | BOT 2.7.1.6 | confere; violada nos casos 5 e 6 (A4) |
| F-08 | T de armazenamento | 40 °C | BOT 2.7.1.10 | confere |
| F-09 | óleo tratado: BSW; sal | < 0,5 %; < 285 mg/L | BOT 2.3.1.1 | confere; tratados como limite superior (P-42) |
| F-10 | salinidade da água produzida | 240.000 mg/L | BOT 2.2.5.1 | confere ("up to 240,000 mg/L") |
| P-08 | ρ da água produzida | 1154 kg/m³ | autor | Laliberté (2009) a 15,6 °C: 1156,7 (−0,2 %) |
| P-09 | ρ da água de diluição | 999 kg/m³ | autor | IAPWS a 15,6 °C: 999,0 |
| P-11 | c_p da água produzida | 3,35 kJ/(kg·K) | autor | Laliberté 15,6–90 °C: 3,39–3,42 (−1,1 a −2,1 %) |
| P-12 | c_p da água de diluição | 4,18 kJ/(kg·K) | autor | IAPWS 25–90 °C: 4,182–4,205 (0 a −0,6 %) |
| P-10 | c_p do óleo | 2,0 kJ/(kg·K) | autor | sem fonte no acervo |
| P-17 a P-21 | pressões e ΔP | 100/700/200/800/2600 kPa | autor | sem fonte no acervo (documentadas no memorial) |
| P-22 | η das bombas | 0,70 | autor | sem fonte no acervo |
| P-23 | Standing (Rs) | — | Standing (1947) | **fonte fora do acervo**: faixa de validade não conferível; γ do gás de 0,811 a 1,222 e até 56 % de CO₂ |
| P-25 | óleo na água | 2000 mg/L | S&A §4.7 | citada no TOML; não reconferida nesta fase |
| P-26 | arraste no gás | 0,1 gal/MMscf | autor | sem fonte no acervo |
| P-28 | BSW do desidratador | 1 % | autor | coerente com P-42 (> 0,5 %: só o TO-002 chega à especificação) |
| P-31, P-32 | T da diluição; aproximação | 25→90 °C; 10 °C | autor | sem fonte no acervo |

As premissas "autor" vêm do script de referência (`references/Balanço_Preliminar.py`) e
estão na tabela do memorial. Pela regra das fontes, só mudam com fonte nova e com a
revisão do oráculo.

## 5. Premissa P-42 no dimensionamento (muda o diagnóstico)

**Implementação:**
- **Métodos** (`sizing/vasos.sem_fase_aquosa`, `separador.py`, `tratador.py`): com
  `q_w == 0` (zero exato) e `q_o > 0`, o bloco de decantação líquido-líquido não é
  avaliado. O rastro registra "P-42 … não aplicável — sem fase aquosa", e o caso devolve
  teto infinito com o mecanismo `sem_fase_aquosa`.
  - A capacidade de gás e de líquido e o β são **os mesmos números** da forma geral:
    (tr)w·Qw = 0 (teste).
  - Com óleo e água nulos seguem as inviabilidades de antes.
- **PFD** (`pfd/entradas._fase_aquosa`, lista em `config/pfd/metodos.toml
  [<método>.fase_aquosa]`): nesses casos, `dm_water`, `dm_oil`, `tr_water` (e
  `rho_water`/`mu_water`, se não vierem do balanço) deixam de ser lacuna ou revisão.
  - A origem passa a ser `nao_aplicavel`, com a fonte P-42.
  - Valores do balanço, das propriedades e do usuário permanecem.
- **Memorial:** a P-42 entra na tabela de premissas e no apêndice de rastreabilidade do
  layout `senai`. O `original` segue byte a byte igual ao script de referência (campo
  `layouts` em `premissas_memorial.toml`).

**Efeito** (planta sem ajustes; `test_efeito_da_p42_restrito_a_fase_aquosa` prova que nada
mais muda):
- Só **SG-001, TO-001 e TO-002** mudam, e só nas chaves `dm_water`, `dm_oil` e `tr_water`
  dos casos 1 e 4–7. Os outros 8 TAGs ficam idênticos.
- **TO-001/002:** a lacuna `dm_water` passa de "casos 1–16" a "casos 2–3, 8–16". Os
  envelopes com ajustes são idênticos.
- **SG-001:** continua **inviável**, mas pela razão certa:

| Caso sozinho | Antes (F10b/F10c) | Com a P-42 |
|---|---|---|
| 1, 4, 5, 6, 7 (sem água) | inviável | viável: 5450, 2750, 3050, 2000, 5450 mm |
| 2 (BSW 10 %, FWKO a 56 °C) | inviável | **inviável** (teto de 4434 mm, água em óleo) |
| 3 e 8–16 | viável | viável (sem mudança) |
| Envelope | teto de 1635 mm, caso 6 | teto de **4434 mm, caso 2**; o SR abaixo do teto vai de 12,6 a 8559 |

Antes, o teto de decantação "água em óleo" era calculado em casos sem água (β = 0,5) e
tornava inviáveis os cinco casos sem fase aquosa. Agora o conflito que resta é real e está
num caso com água:
- o caso 2 (Early Life, μ do óleo alta a 56 °C) limita o diâmetro a 4434 mm;
- abaixo desse teto, a capacidade exigida pelos 16 casos leva a esbeltez a 12,6 ou mais,
  fora da banda 3–5.

Resolver isso exige premissa nova com fonte, fora do escopo desta fase. Opções: gotícula,
retenção, temperatura, trens em paralelo ou internos de coalescência.

Com os ajustes sintéticos dos testes, o SG-001 mantém d = 6500 mm, governado pelo BOT 08;
só o caso do teto passa do 6 para o 2.

**Oráculos:**
- **Fixtures do Julia:** intactas; nenhum caso delas tem `q_water = 0`.
- **Fixture da F10b** (`tests/fixtures/pfd/f10b_resultados.json`): **não foi reescrita**.
  O teste de regressão roda com a P-42 desligada e reproduz a F10b exatamente; o efeito da
  P-42 é conferido à parte, em `test_efeito_da_p42_restrito_a_fase_aquosa`. Isso é um
  desvio do plano, que previa revisar a fixture.

## 6. Limitações declaradas e propostas (sem implementação)

**Limitações:**
- gás seco (sem água vaporizada no gás);
- c_p constantes;
- sem calor de flash nem Joule-Thomson;
- C-26 (óleo fora de especificação) é zero por projeto;
- a gotícula de água após a coalescência dos tratadores continua lacuna (sem fonte no
  acervo).

**Propostas**, cada uma exigindo aprovação, justificativa e revisão do oráculo:
- **M1:** diluição com o sal real da água residual (A3).
- **M2:** reciclo de óleo para manter T_FWKO ≥ 40 °C nos casos 5–6 (Nota 11; P-41).
- **M3:** fração de reciclo da água dos tratadores como premissa. O default 1 é o
  comportamento atual.
- **Fonte:** incluir a fonte de Standing (1947) no acervo, para conferir a faixa de validade
  com gás de γ > 0,95 e alto CO₂.

## Verificação

- `uv run pytest --cov=fpso_siz --cov-fail-under=90`: ver os números finais no `SPRINTS.md`.
- `uv run pytest -m latex`: os dois layouts compilam, o `senai` com a P-42.
- `uv run pytest -m julia`: paridade dos métodos com o Julia.
- Novos: `tests/balanco/test_verificacao_fisica.py`, `tests/sizing/test_sem_fase_aquosa.py`,
  `test_efeito_da_p42_restrito_a_fase_aquosa` (em `tests/pfd/test_servico.py`) e
  `test_balanco_mostra_agua_e_padrao_num_caso_com_agua` (em `tests/test_interativo.py`).
- Snapshots de tela regenerados: só mudam o SG-001 (teto e casos) e as pendências e
  revisões aquosas do SG-001, TO-001 e TO-002.
