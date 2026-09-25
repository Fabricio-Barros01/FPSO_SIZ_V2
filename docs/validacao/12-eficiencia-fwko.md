# F10w — eficiência de água livre do SG-001 (P-43)

Pedido do usuário (2026-09-25): a eficiência média do separador é uma premissa que costuma
ficar entre 80 % e 90 %; usar 85 %, editável pelo usuário, e redimensionar os cálculos.

As decisões do usuário, tomadas antes da implementação:
- **Onde vale:** a eficiência é a de remoção de água livre do SG-001 (FWKO). Os tratadores
  seguem pelas especificações de BSW.
- **Regra adotada:** η_A = máx(η_padrão; η_req), com η_padrão = 0,85 no `premissas.toml`
  (P-43, **premissa do autor**, sem referência bibliográfica, editável).
- **η_req:** 1 − [BSW_lim/(1 − BSW_lim)]·Q_O / Q_A,e, com BSW_lim = 0,40 (F-06, BOT 2.7.1.2).
  É calculado dentro do laço de reciclo, e Q_A,e inclui o reciclo e a diluição.
- **Limite do BOT:** quando η_req > η_padrão, o resultado e o memorial registram que o SG-001
  é exigido acima do padrão. É um estado, sem exceção.
- **Modo de paridade:** a regra mín(40 %; BSW) do oráculo continua disponível.
- **Confirmação:** a tabela dos 16 casos convergidos foi confirmada pelo usuário antes da
  atualização dos testes e do oráculo.

## Uso

```sh
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/                         # regra padrão (eficiência)
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/ --premissa eta_F=0.80   # outra eficiência padrão
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/ --regra-fwko referencia # paridade com o oráculo
uv run fpso-siz memorial --casos design_cases_bot.json --saida saida/mc --layout senai        # memorial com a P-43
```

No modo interativo, a P-43 aparece em "Premissas do balanço" e pode ser editada como as
demais.

## Regra

- **Base de Q_O:** é o óleo que efetivamente sai em C-06, descontados o óleo disperso na
  água e o arraste no gás. É a mesma base do BSW em todo o modelo (`split_water`).
- **Onde η_req é calculado:** a cada iteração do laço de reciclo (`split_eficiencia`, em
  `balanco/propriedades.py`).
- **Unicidade:** como 1 − η_A < 1, cada passagem remove uma fração fixa da água que retorna,
  e o estado estacionário é único. A regra mínima do script de referência existia
  justamente para garantir essa unicidade.
- **Diagnóstico:** η_req < η_padrão é apenas diagnóstico; o limite do BOT não restringe e
  vale o padrão.

A regra de referência, BSW_C06 = mín(F-06; BSW de chegada), continua disponível:
- `resolver_todos(..., regra_fwko="referencia")` ou `--regra-fwko referencia`;
- o memorial `original`, que continua byte a byte igual ao script de referência;
- os testes de paridade com o oráculo.

A regra em uso fica em `config/constantes.toml [modelo] regra_fwko`.

## Tabela dos 16 casos convergidos (confirmada pelo usuário)

| Caso | BSW de chegada (C-01) | BSW de entrada no SG-001 (C-03) | η_req | η adotado | Exigido acima do padrão | BSW de saída do SG-001 (C-06) | BSW de saída do TO-002 (C-21) | Iterações |
|---|---|---|---|---|---|---|---|---|
| 1, 4, 5, 6, 7 | 0,0 % | 0,0 % | — | — (sem água) | não | 0,00 % | 0,00 % | 5 |
| 2, 3 | 10,0 % | 14,0 % | −308,9 % | 85,0 % | não | 2,39 % | 0,50 % | 15 |
| 8 | 40,0 % | 44,9 % | 18,5 % | 85,0 % | não | 10,92 % | 0,50 % | 15 |
| 9 | 52,8 % | 57,4 % | 50,7 % | 85,0 % | não | 16,87 % | 0,50 % | 15 |
| 10 | 59,8 % | 64,1 % | 62,7 % | 85,0 % | não | 21,15 % | 0,50 % | 16 |
| 11 | 75,0 % | 78,1 % | 81,4 % | 85,0 % | não | 34,95 % | 0,50 % | 16 |
| 12 | 74,7 % | 77,8 % | 81,1 % | 85,0 % | não | 34,56 % | 0,50 % | 16 |
| 13, 14 | 69,6 % | 73,2 % | 75,7 % | 85,0 % | não | 29,15 % | 0,50 % | 16 |
| 15 | 88,9 % | 89,6 % | 92,4 % | **92,4 %** | **sim** | 40,00 % | 0,50 % | 11 |
| 16 | 87,6 % | 88,6 % | 91,5 % | **91,5 %** | **sim** | 40,00 % | 0,50 % | 11 |

- **Casos 15 e 16:** o limite do BOT 2.7.1.2 governa, e o resultado é idêntico ao da regra
  de referência, que já os deixava em 40 %.
- **Substituição do caso 15:** η_req = 1 − (0,40/0,60) × (3.483 m³/d)/(30.678 m³/d) = 0,924.
  As duas vazões são volumétricas, na condição padrão (F-01: 15,6 °C e 101,3 kPa):
  - Q_O,C06 = 3.483 m³/d é o óleo que sai do SG-001 em C-06, descontados o óleo na água e o
    arraste;
  - Q_A+D,C03 = 30.678 m³/d é a água que chega ao vaso em C-03 (produzida + reciclo +
    diluição).

  É a mesma conta mostrada no memorial `senai`.

## Comparação com a regra de referência (casos 2, 8, 9 e 11)

As cargas são separadas pela origem do calor, sem somar as quatro:
- **Calor recuperado:** o do P-001 (pré-aquecedor óleo/óleo), trocado entre correntes de
  processo.
- **Q_H (aquecimento por utilidade):** Q_P-002 + Q_DWH-001, o aquecedor de óleo mais o
  aquecedor da água de diluição, supridos pelo meio de aquecimento.
- **Q_C (resfriamento por utilidade):** Q_P-003, o resfriador de óleo.

O `balanco.json` usa os mesmos termos desde o esquema 2:
- `cargas.Q_H` = P-002 + DWH-001;
- `cargas.Q_C` = P-003;
- um campo por trocador pelo TAG (`P-001` = calor recuperado, `P-002`, `DWH-001`, `P-003`).

No esquema 1, `cargas.Q_H` era só o P-002.

| Caso | Regra | η_A | BSW C-06 | Água no óleo C-06 (kg/s) | Reciclo C-02 (kg/s) | Calor recuperado P-001 (kW) | Q P-002 (kW) | Q DWH-001 (kW) | **Q_H** (kW) | **Q_C** = P-003 (kW) | T C-03 (°C) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | referência | 55,5 % | 10,00 % | 41,32 | 50,34 | 14.329 | 10.526 | 2.915 | 13.441 | 15.741 | 56,4 |
| 2 | eficiência | 85,0 % | 2,39 % | 9,09 | 18,11 | 16.532 | 6.855 | 2.915 | 9.770 | 13.537 | 52,7 |
| 8 | referência | 51,0 % | 40,00 % | 168,96 | 174,96 | 3.987 | 14.959 | 1.941 | 16.900 | 16.033 | 70,4 |
| 8 | eficiência | 85,0 % | 10,92 % | 31,04 | 37,04 | 6.892 | 6.596 | 1.941 | 8.537 | 13.129 | 63,1 |
| 9 | referência | 63,3 % | 40,00 % | 132,98 | 137,69 | 2.652 | 11.046 | 1.524 | 12.570 | 13.071 | 72,0 |
| 9 | eficiência | 85,0 % | 16,87 % | 40,43 | 45,14 | 3.937 | 5.982 | 1.524 | 7.506 | 11.785 | 67,8 |
| 11 | referência | 82,0 % | 40,00 % | 70,33 | 72,81 | 3.312 | 8.577 | 804 | 9.382 | 4.986 | 60,3 |
| 11 | eficiência | 85,0 % | 34,95 % | 56,66 | 59,14 | 3.455 | 7.380 | 804 | 8.185 | 4.843 | 59,5 |

| Caso | Δ calor recuperado (P-001) | Δ Q_H (P-002 + DWH-001) | Δ Q_C (P-003) |
|---|---|---|---|
| 2 | +2.204 kW (+15,4 %) | −3.671 kW (−27,3 %) | −2.204 kW (−14,0 %) |
| 8 | +2.905 kW (+72,9 %) | −8.363 kW (−49,5 %) | −2.905 kW (−18,1 %) |
| 9 | +1.286 kW (+48,5 %) | −5.064 kW (−40,3 %) | −1.286 kW (−9,8 %) |
| 11 | +143 kW (+4,3 %) | −1.197 kW (−12,8 %) | −143 kW (−2,9 %) |

Leitura:
- **Menos água no aquecedor:** o FWKO passa a remover 85 % da água que chega, então passa
  menos água pelo aquecedor, pelo TO-001 e pelo reciclo. O Q_H cai todo pelo P-002.
- **Calor recuperado e Q_C:** a entrada do FWKO fica mais fria, porque volta menos água
  quente dos tratadores. O P-001 recupera mais calor do óleo tratado, e o Q_C cai na mesma
  quantidade.
- **Diluição e água produzida:** a diluição (DWH-001) não muda, pois depende do BSW do
  TO-001. A água produzida que sai pela C-05 também não muda: em regime, toda ela sai pelo
  FWKO nas duas regras.

No memorial `senai`, a tabela de energia (Seção de balanço de energia) passou a mostrar o
P-001 como calor recuperado e as colunas Q_H e Q_C. Os envelopes usam os mesmos termos. O
`original` mantém a apresentação do script de referência.

## Efeito nos equipamentos (PFD)

- **V-001:** 4850 mm (BOT 08) → **4700 mm (BOT 03)**, porque o líquido do desgaseificador
  tem menos água.
- **SG-001:** continua inviável; o teto de decantação cai de 4434 mm para **3612 mm**, ainda
  no caso 2. Com menos reciclo quente, a entrada do FWKO fica mais fria (caso 2: 56,4 →
  52,7 °C), o óleo mais viscoso e a decantação mais lenta. O caso 3 também fica inviável
  sozinho (teto de 4877 mm).
- **Os outros 9 TAGs:** mesmos estados; as lacunas não mudam.
- **V-002:** 4700 mm (BOT 03), igual.

## Rev. 0 do MC-SEN-SEP-COO-001 (memorial do balanço)

A Rev. 0 **não cita dimensões** do V-001 nem de nenhum outro TAG: não aparecem diâmetro,
comprimento, esbeltez, DN nem número de tubos em nenhum dos dois layouts. As dimensões só
existem nas saídas do PFD e do `dimensionar`.

A Rev. 0 cita, por equipamento, os **critérios de dimensionamento e o caso que os maximiza**
(tabela de casos críticos) e os **envelopes** (tabela de envelopes).
- **Layout `original`:** não muda nada, porque é gerado sempre na regra de referência e
  segue idêntico à Rev. 0.
- **Layout `senai`:** muda o seguinte na regra padrão.

| Tabela | Item | Rev. 0 | Agora (eficiência) |
|---|---|---|---|
| Casos críticos | SG-001 — Líquido total em C-03 | 45.075 m³/d (caso 8) | 36.276 m³/d (caso 11) |
| Casos críticos | SG-001 — Carga de gás real | 25.263 m³/h (caso 14) | 25.260 m³/h (caso 14) |
| Casos críticos | P-001 — calor recuperado | 14,33 MW (caso 2) | 16,53 MW (caso 2) |
| Casos críticos | P-002 — Q | 14,96 MW (caso 8) | 7,38 MW (caso 11) |
| Casos críticos | **V-001 — Gás real** | 2.057 m³/h (caso 2) | 2.102 m³/h (caso 2) |
| Casos críticos | **V-001 — Líquido C-10** | 31.802 m³/d (caso 3) | 29.315 m³/d (caso 3) |
| Casos críticos | TO-001 — Água removida C-12 | 12.528 m³/d (caso 8) | 4.168 m³/d (caso 11) |
| Casos críticos | TO-001 — Óleo C-10 | 28.621 m³/d (caso 3) | 28.621 m³/d (caso 7; empate) |
| Casos críticos | B-002 — Vazão C-12 | 12.528 m³/d (caso 8) | 4.168 m³/d (caso 11) |
| Envelopes | Líquido na entrada do FWKO (C-03) | 45.075 m³/d (caso 8) | 36.276 m³/d (caso 11) |
| Envelopes | Carga/calor recuperado do pré-aquecedor | 14,33 MW (caso 2) | 16,53 MW (caso 2) |
| Envelopes | Carga do aquecedor de óleo (P-002) | 14,96 MW (caso 8) | 7,38 MW (caso 11) |
| Envelopes | Q_H = P-002 + DWH-001 | 16,90 MW (caso 8) | 9,77 MW (caso 2) |
| Envelopes | Potência total de bombas | 612,8 kW (caso 8) | 340,9 kW (caso 3) |
| Envelopes | Reciclo de água (C-02) | 13.243 m³/d (caso 8) | 4.464 m³/d (caso 11) |

Os envelopes que não aparecem na tabela não mudam: vazões do BOT, gás, Q_C máximo (26,51 MW,
caso 7), temperaturas, viscosidade, BSW de chegada, diluição e CO₂. Nos TAGs governados pelo
envelope, o que mudou de dimensão foi o **V-001: 4850 mm (BOT 08) → 4700 mm (BOT 03)**,
consequência da queda do líquido em C-10. O V-002 continua com 4700 mm. O SG-001 segue
inviável (teto de 3612 mm), e os demais TAGs aguardam entradas.

Ao reemitir o memorial `senai` com estes números, a revisão deve subir: hoje ele sai com a
Rev. 0 de `memorial_balanco.toml`. A decisão é do usuário.

## Pendência — η_A do SG-001 não é sustentada pela geometria nos casos 2 e 3

A P-43 fixa a eficiência de remoção de água livre do SG-001, mas o dimensionamento do
próprio SG-001 não sustenta essa separação nos casos 2 e 3.
- **SG-001 inviável:** nenhum diâmetro da grade atende à esbeltez 3–5 abaixo do teto de
  decantação de 3612 mm, imposto pelo caso 2.
- **Caso 3 sozinho:** também inviável, com teto de 4877 mm.
- **Causa:** a regra de eficiência reduz o reciclo quente dos tratadores e esfria a entrada
  do FWKO, de 56,4 para 52,7 °C no caso 2 e de 56,8 para 52,9 °C no caso 3. O óleo fica
  mais viscoso e a decantação da água mais lenta.

A eficiência adotada no balanço e a geometria do vaso ficam, assim, inconsistentes nesses
casos. A pendência fica aberta até uma decisão de projeto com fonte, por exemplo:
- manter a entrada do FWKO mais quente (reciclo de óleo ou de água, BOT 2.7.1.6);
- rever a gotícula ou a retenção;
- usar trens em paralelo;
- reduzir η_padrão nesses casos.

Enquanto isso, os resultados dos casos 2 e 3 dependentes do SG-001 são preliminares.

## Validade numérica

- **Convergência:** os 16 casos convergem em 5 a 16 iterações (tolerância 1e-10).
- **Auditoria independente:** 17 verificações. A nova, `eficiencia_fwko`, recalcula η_A =
  Q_A+D,C05/Q_A+D,C03 e η_req pelas correntes e confere η_A = máx(η_padrão; η_req) e
  BSW_C06 ≤ F-06; o maior desvio é 3,3e-16. Nas demais:
  - massa global 1,1e-10 kg/s;
  - energia global 2,9e-8 kW;
  - resíduo por componente 9,9e-11 kg/s;
  - BSW 1,3e-16;
  - sal 2,8e-13 mg/L.
- **Verificação física:**
  - a água fecha em 1,1e-10 kg/s;
  - o BSW de cada separador bate com a sua regra;
  - o FWKO sempre deixa água no óleo;
  - o sal no óleo tratado chega a no máximo 284,0 mg/L (base da emulsão);
  - o FWKO segue abaixo de 40 °C nos casos 5–6 (reciclo de óleo não modelado, P-41).
- **Oráculo:** a paridade bit a bit com o script de referência continua, no modo de
  paridade. A regra de eficiência não tem oráculo externo. A fixture
  `tests/fixtures/python_ref/regressao_eficiencia.json` (gerada por
  `tools/gerar_regressao_eficiencia.py`, determinística) congela o resultado conferido pelo
  usuário, e `tests/balanco/test_eficiencia_fwko.py` fixa a tabela acima.

## Memorial

- **Layout `senai`:**
  - a seção do SG-001 traz a equação de η_A e η_req (`eq:etaF`), a substituição numérica do
    caso 15 (vazões volumétricas na condição padrão F-01, em m³/d) e a nota de que
    η_req < η_padrão é diagnóstico;
  - a tabela de energia mostra o P-001 como calor recuperado e as colunas
    Q_H = P-002 + DWH-001 e Q_C = P-003; os rótulos dos envelopes usam os mesmos termos;
  - a tabela de η por caso (`tab:etaF`) dá η_req, η_A e o estado; nos casos 1 e 4–7, η e
    η_req aparecem como "—" e o estado como "não aplicável — sem fase aquosa" (no JSON, η e
    η_req são `null`);
  - lista os casos exigidos acima do padrão (15 e 16);
  - a tabela de premissas traz a P-43 ("premissa do autor"), e a P-24 aparece como resultado
    (BSW ≤ 40 %);
  - as seções de eficiências, M-03, sensibilidade, fechamento e informações recomendadas
    citam a P-43;
  - a sensibilidade ganha as variações η_padrão = 80 % e 90 %.
- **Layout `original`:** é gerado sempre com a regra de referência e segue idêntico ao
  script.

## Arquivos

- **Núcleo:**
  - `balanco/propriedades.split_eficiencia`;
  - `balanco/modelo` (`REFERENCIA`/`EFICIENCIA`, `regra_fwko_padrao`, `ResultadoCaso.fwko`);
  - `balanco/auditoria` (`eficiencia_fwko`);
  - `balanco/indicadores` (sensibilidade na regra dos resultados; verificação física por
    regra);
  - `balanco/exportacao` (campo `FWKO` por caso; `cargas` do esquema 2 por TAG, com Q_H e
    Q_C de utilidade).
- **Configuração:**
  - `premissas.toml` (`eta_F`, P-43);
  - `saida_balanco.toml` (cargas do `balanco.json`);
  - `constantes.toml [modelo]`;
  - `equacoes_balanco.toml` (`eficiencia_fwko`, `regra`, `memorial_regra`);
  - `auditoria.toml`, `sensibilidade_balanco.toml`, `verificacao_balanco.toml`,
    `memorial_balanco.toml` (`caso_eta_req`).
- **Saída:**
  - `cli.py` (`--regra-fwko`);
  - `output/latex/balanco/memorial.py` (regra por layout; linhas de premissa com `regra`;
    terminologia do layout);
  - templates `11b`, `11m`, `13`, `15`, `16`, `17` e `18`;
  - `envelopes_memorial.toml` (`nome_senai`);
  - `premissas_memorial.toml`;
  - `docs/esquemas/balanco.schema.json`.
