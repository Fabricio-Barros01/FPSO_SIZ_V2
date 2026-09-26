# F13 — alarmes de inviabilidade: anotação e investigação

Gerado por `tools/investigar_alarmes.py`; todos os números saem do motor e do rastro.

A unidade do BOT (I-ET-3010.2K-1200-941-P4X-001, rev. C, em `docs/bot/`) é um projeto básico real:
um TAG sem equipamento que atenda aos casos é **alarme** de erro de premissa, numérico ou de modelo,
nunca conclusão de projeto. Nenhuma variante altera o cálculo padrão; a decisão é do usuário.

## Planta com óleo morto (--oleo-morto), sem propostas

| TAG | Estado | Casos com solução isolados | Casos sem solução isolados | Motivo do motor |
|---|---|---|---|---|
| SG-001 | inviável (alarme) | BOT 01 (5.450), BOT 04 (2.750), BOT 05 (3.050), BOT 06 (2.000), BOT 07 (5.450), BOT 08 (5.900), BOT 09 (5.900), BOT 10 (5.750), BOT 11 (6.050), BOT 12 (6.050), BOT 13 (6.050), BOT 14 (6.050), BOT 15 (5.900), BOT 16 (5.900) | BOT 02, BOT 03 | Não há equipamento que atenda simultaneamente aos 16 casos. Nenhum diâmetro admissível tem esbeltez na banda 3.0–5.0: abaixo do teto de decantação (3612.0 mm) o SR varia de 20.34 a 6975.66. Amplie a grade de diâmetros ou… |

### Variantes executadas (mesmo motor)

| TAG | Variante | Origem do valor | Resultado |
|---|---|---|---|
| SG-001 | η_padrão = 0,80 (P-43) | limite inferior da faixa de 80–90 % declarada pelo usuário para a P-43 (F10w) | segue inviável (teto 3.708 mm, BOT 02 — Early Life): Não há equipamento que atenda simultaneamente aos 16 casos. Nenhum diâmetro admissível tem esbeltez na banda 3.0–5.0: abaixo do teto de decantação (3708.0 mm) o… |
| SG-001 | η_padrão = 0,90 (P-43) | limite superior da faixa de 80–90 % declarada pelo usuário para a P-43 (F10w) | segue inviável (teto 3.527 mm, BOT 02 — Early Life): Não há equipamento que atenda simultaneamente aos 16 casos. Nenhum diâmetro admissível tem esbeltez na banda 3.0–5.0: abaixo do teto de decantação (3527.0 mm) o… |
| SG-001 | 2 trens em paralelo (2 × 50 %) | divisão da vazão por um número inteiro de vasos iguais; não há valor suposto | segue inviável (teto 3.612 mm, BOT 02 — Early Life): Não há equipamento que atenda simultaneamente aos 16 casos. Nenhum diâmetro admissível tem esbeltez na banda 3.0–5.0: abaixo do teto de decantação (3612.0 mm) o… |
| SG-001 | 3 trens em paralelo (3 × 33 %) | divisão da vazão por um número inteiro de vasos iguais; não há valor suposto | segue inviável (teto 3.612 mm, BOT 02 — Early Life): Não há equipamento que atenda simultaneamente aos 16 casos. Nenhum diâmetro admissível tem esbeltez na banda 3.0–5.0: abaixo do teto de decantação (3612.0 mm) o… |

## Planta sem propostas (catálogo com fonte; óleo vivo)

Nenhum TAG inviável: não há alarme a investigar.

## Planta com as propostas (pendencias_propostas.toml, status proposto; óleo vivo)

| TAG | Estado | Casos com solução isolados | Casos sem solução isolados | Motivo do motor |
|---|---|---|---|---|
| B-001 | inviável (alarme) | BOT 01 (600), BOT 02 (600), BOT 03 (600), BOT 04 (200), BOT 05 (250), BOT 06 (125), BOT 07 (600), BOT 08 (450), BOT 09 (400), BOT 10 (350), BOT 11 (300), BOT 12 (300), BOT 13 (350), BOT 14 (350), BOT 15 (200), BOT 16 (200) | — | Não há equipamento que atenda simultaneamente aos 16 casos. Há diâmetros na banda de velocidade 1.0–1.5 m/s, e neles o NPSH tem folga (a maior é 0.84 m). A recusa não veio deste caso. Isolado, cada caso tem diâmetro nomi… |
| B-002 | inviável (alarme) | BOT 02 (65), BOT 03 (65), BOT 08 (150), BOT 09 (200), BOT 10 (200), BOT 11 (250), BOT 12 (250), BOT 13 (200), BOT 14 (200) | BOT 15, BOT 16 | Não há equipamento que atenda simultaneamente aos 11 casos. Nenhum diâmetro da grade mantém a velocidade na banda 1.0–1.5 m/s: na grade oferecida ela varia de 0.01 a 282.98 m/s. Amplie a grade de DN, ou reveja a banda.… |
| B-003 | inviável (alarme) | BOT 02 (125), BOT 03 (125), BOT 08 (100), BOT 09 (80), BOT 10 (80), BOT 11 (65), BOT 12 (65), BOT 13 (65), BOT 14 (65), BOT 15 (40), BOT 16 (40) | — | Não há equipamento que atenda simultaneamente aos 11 casos. Há diâmetros na banda de velocidade 1.0–1.5 m/s, e neles o NPSH tem folga (a maior é 0.81 m). A recusa não veio deste caso. Isolado, cada caso tem diâmetro nomi… |
| P-001 | inviável (alarme) | — | — | Caso 'BOT 01 — Early Life': O arranjo 1-2 não fecha com estas temperaturas: o fator de correção F sai do domínio da Fig. 4.3. Em contracorrente puro (1 passe) o caso é viável — o cruzamento interno de um segundo passe é … |
| P-002 | inviável (alarme) | — | BOT 01, BOT 02, BOT 03, BOT 04, BOT 05, BOT 06, BOT 07, BOT 08, BOT 09, BOT 11 | Não há equipamento que atenda simultaneamente aos 10 casos. Na banda de velocidade 1.0–3.0 m/s todos os feixes caem fora da faixa em que Saari declara a correlação de Dittus-Boelter (Eq. 6.23): o Reynolds no tubo vai de … |
| P-003 | inviável (alarme) | — | BOT 01, BOT 02, BOT 03, BOT 04, BOT 05, BOT 06, BOT 07, BOT 08, BOT 09, BOT 10, BOT 11, BOT 12, BOT 13, BOT 14, BOT 15, BOT 16 | Não há equipamento que atenda simultaneamente aos 16 casos. Na banda de velocidade 1.0–3.0 m/s todos os feixes caem fora da faixa em que Saari declara a correlação de Dittus-Boelter (Eq. 6.23): o Reynolds no tubo vai de … |

### Variantes executadas (mesmo motor)

| TAG | Variante | Origem do valor | Resultado |
|---|---|---|---|
| B-001 | sem piso de velocidade (líquido limpo) | nota do descritor v_min em equipment/pump/moran.toml (Moran 2016: piso só para líquido com sólidos decantáveis) | segue inviável: Não há equipamento que atenda simultaneamente aos 16 casos. Há diâmetros na banda de velocidade 0.0–1.5 m/s, e neles o NPSH tem folga (a maior é 0.95 m). A recu… |
| P-001 | 1 passe no tubo (contracorrente pura) | limite inferior do descritor passes_tubo (Saari §4.2.1: contracorrente puro, F = 1), sugerido pela própria mensagem do motor | segue inviável: Não há equipamento que atenda simultaneamente aos 10 casos. Na banda de velocidade 1.0–3.0 m/s todos os feixes caem fora da faixa em que Saari declara a correla… |

## Conferência numérica do teto do SG-001

- Óleo morto (inviavel): caso BOT 02 — Early Life: (h_o)max = 0.033 · 10.0 min · ΔSG 0,2189 · (500 µm)² / 13,28 cP = 1.360,1 mm; β = 0,3766; d_max = 3.612,0 mm. Rastro: 3.612,0 mm (diferença 0.0e+00 mm).
- Óleo vivo (dimensionado, D = 6.050 mm): caso BOT 02 — Early Life: (h_o)max = 0.033 · 10.0 min · ΔSG 0,2189 · (500 µm)² / 7,67 cP = 2.356,0 mm; β = 0,3766; d_max = 6.256,8 mm. Rastro: 6.256,8 mm (diferença 0.0e+00 mm).

A cadeia não tem erro numérico: o teto decorre das entradas. A única diferença entre as duas linhas é µ_o (óleo morto do BOT × óleo vivo por Beggs & Robinson com o Rs da saída de óleo C-06): a hipótese de premissa da viscosidade explica o alarme (docs/validacao/16-oleo-vivo.md).

## Hipóteses registradas (config/pfd/alarmes.toml)

### SG-001 — investigação explicada

Só no modo --oleo-morto: os casos 2 e 3 (Early Life, com água) são inviáveis isolados, porque o teto de decantação (água em óleo) fica abaixo do menor diâmetro com a esbeltez na banda. Com a viscosidade de óleo vivo (padrão) o vaso é viável (docs/validacao/16-oleo-vivo.md).

- **premissa**: CONFIRMADA: a viscosidade de óleo MORTO (BOT Tab. 2.2.1.2, P-40) usada para o óleo vivo do FWKO. O gás dissolvido na saída de óleo (Rs de C-06) reduz µ_o cerca de 40 % pela correlação de Beggs & Robinson (1975), e (h_o)max ∝ 1/µ_o: o teto dos casos 2 e 3 sobe e o vaso passa a ter solução. A correlação está fora do acervo local (a conferir) e não substitui um PVT medido.
- **premissa**: Critério de decantação de gotículas de água de 500 µm no óleo (S&A §4.7.2) aplicado ao FWKO, cuja saída de óleo pode levar até o BSW de F-06 (BOT 2.7.1.2): o FWKO remove água livre, não especifica o óleo. O critério pode ser mais restritivo que a função do vaso.
- **premissa**: Eficiência de água livre P-43 (premissa do autor, faixa de 80–90 % declarada pelo usuário): muda o reciclo quente e a temperatura de entrada do FWKO, logo µ_o e o teto.
- **modelo**: Um único vaso para todos os casos: com trens em paralelo a vazão por vaso cai e o comprimento exigido também; o teto (razão de vazões, µ, ΔSG) não muda.
- **numérico**: Conferência numérica: (h_o)max, β e d_max refeitos à mão com os operandos do rastro reproduzem o resultado (teste da conta à mão); β por bisseção idêntico ao Julia.

### P-001 — investigação aberta

O motor para no caso 1: com 2 passes no tubo o fator F da Fig. 4.3 sai do domínio (cruzamento interno de temperatura no arranjo 1-2).

- **premissa**: Arranjo de 2 passes no tubo (default 'escolha' de Saari Tab. 3.1): com a aproximação de P-32 a troca óleo/óleo é quase simétrica (R ≈ 1) e P alto, fora do alcance de um casco 1-2. Contracorrente pura (1 passe) ou cascos em série resolvem o domínio de F.
- **modelo**: Resolvido o domínio de F (1 passe), o impedimento seguinte é o mesmo do P-002/P-003: óleo em escoamento laminar/de transição no tubo, fora de Dittus-Boelter. Como os dois lados são óleo, trocar os lados não resolve: falta correlação laminar no acervo.

### P-002 — investigação aberta

Todos os casos: o óleo no lado tubo tem Re de ~1.900 a ~5.600 e Pr ~150 com óleo vivo (~1.100 a ~3.400 e Pr ~250 com --oleo-morto), fora da faixa de Dittus-Boelter (Re ≥ 10⁴, Pr ≤ 120) declarada por Saari: a correção de óleo vivo aproxima, mas não resolve.

- **premissa**: Alocação de fluidos: óleo viscoso no lado tubo. A prática é pôr o fluido mais viscoso no casco, onde Bell-Delaware cobre escoamento laminar (fator Jr); a água quente de utilidade iria nos tubos. A troca de lados é mudança de topologia do TAG (sem variante executável neste modelo).
- **modelo**: Correlação do lado tubo só turbulenta: não há correlação laminar/de transição (ex.: Sieder–Tate) no acervo; o programa não extrapola.

### P-003 — investigação aberta

Todos os casos: o óleo no lado tubo tem Re de ~1.300 a ~4.000 e Pr ~150, fora da faixa de Dittus-Boelter declarada por Saari.

- **premissa**: Alocação de fluidos: óleo viscoso no lado tubo; a água de resfriamento em circuito fechado (BOT 3.3.2) iria nos tubos e o óleo no casco (Bell-Delaware com Jr). Mudança de topologia do TAG, sem variante executável neste modelo.
- **modelo**: Correlação do lado tubo só turbulenta, como no P-002.

### B-001 — investigação aberta

Cada caso tem DN admissível isolado (125 a 600 mm), mas as faixas não se cruzam: a vazão de óleo varia cerca de 23× entre os casos.

- **premissa**: Piso de velocidade de 1 m/s aplicado ao óleo tratado: pela nota do descritor v_min (Moran 2016) o piso é para líquido com sólidos decantáveis; para líquido limpo o artigo só impõe o teto.
- **premissa**: Envelope exige a banda de velocidade em TODOS os casos de uma única linha; no projeto, a linha é dimensionada pelo caso de maior vazão e os de menor vazão operam com velocidade menor (ou com bombas em paralelo/recirculação de mínimo fluxo).
- **modelo**: Na variante sem piso, o caso 6 (baixa vazão, óleo mais frio e viscoso) cai na transição laminar-turbulento nos DN grandes, onde nenhuma correlação de atrito da implementação vale (Colebrook só para Re > 4000; 64/Re só até 2000).

### B-002 — investigação aberta

Casos 15 e 16 inviáveis isolados: entre DN 150 (≈1,7 m/s) e DN 200 (≈1,0 m/s) a banda de 1,0–1,5 m/s cai no vão da série; nos demais a vazão varia cerca de 10×.

- **premissa**: Banda de velocidade 1–1,5 m/s (Moran 2016) mais estreita que o salto de área entre DN consecutivos da série (200/150 → 1,78×): há vazões sem DN na banda. Numérico só na aparência: é a combinação banda × série.
- **premissa**: Banda aplicada a todos os casos de uma única linha, como no B-001.

### B-003 — investigação aberta

Cada caso tem DN admissível isolado (40 a 125 mm), mas as faixas não se cruzam: a vazão de água varia entre os casos.

- **premissa**: Banda de velocidade aplicada a todos os casos de uma única linha (turndown), como no B-001.

