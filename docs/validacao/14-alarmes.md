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
| P-001 | inviável (alarme) | — | — | Caso 'BOT 01 — Early Life': O arranjo 1-2 não fecha com estas temperaturas: o fator de correção F sai do domínio da Fig. 4.3. Em contracorrente puro (1 passe) o caso é viável — o cruzamento interno de um segundo passe é … |
| P-002 | inviável (alarme) | BOT 01 (238), BOT 02 (283), BOT 03 (282), BOT 04 (34), BOT 05 (42), BOT 06 (13), BOT 07 (236), BOT 08 (275), BOT 09 (250), BOT 11 (305) | — | Não há equipamento que atenda simultaneamente aos 10 casos. Há feixes na banda de velocidade 1.0–3.0 m/s, dentro da faixa de Dittus-Boelter, com tubo até 6.0 m e casco até 2500.0 mm (o menor casco dá 677.0 mm). A recusa … |
| P-003 | inviável (alarme) | — | BOT 01, BOT 02, BOT 03, BOT 04, BOT 05, BOT 06, BOT 07, BOT 08, BOT 09, BOT 10, BOT 11, BOT 12, BOT 13, BOT 14, BOT 15, BOT 16 | Não há equipamento que atenda simultaneamente aos 16 casos. Na banda de velocidade 1.0–3.0 m/s todos os feixes pedem tubo mais longo que o limite de 6.0 m — o mais curto dá 7.33 m. Amplie a grade para mais tubos, aceite … |

### Variantes executadas (mesmo motor)

| TAG | Variante | Origem do valor | Resultado |
|---|---|---|---|
| P-001 | 1 passe no tubo (contracorrente pura) | limite inferior do descritor passes_tubo (Saari §4.2.1: contracorrente puro, F = 1), sugerido pela própria mensagem do motor | segue inviável: Não há equipamento que atenda simultaneamente aos 10 casos. Na banda de velocidade 1.0–3.0 m/s todos os feixes caem fora da faixa em que Saari declara a correla… |
| P-001 | emulsão fria no casco, óleo tratado quente nos tubos | prática de alocar o fluido mais viscoso no casco (hipótese do alarme); k e incrustações do P-001 são as mesmas propostas nos dois lados | segue inviável: Caso 'BOT 01 — Early Life': O arranjo 1-2 não fecha com estas temperaturas: o fator de correção F sai do domínio da Fig. 4.3. Em contracorrente puro (1 passe) o… |

## Estudo da P-44 (banda de velocidade pelo caso de projeto)

| TAG | Com a P-44 (padrão) | Sem a P-44 (variante `sem_p44`) |
|---|---|---|
| B-001 | DN 600 mm, H 75,1 m | inviável: Não há equipamento que atenda simultaneamente aos 16 casos. Há diâmetros na banda de velocidade 1.0–1.5 m/s, e neles o NPSH tem folga (a maior é 0.84 m). A recu… |
| B-002 | DN 250 mm, H 183,4 m | inviável: Não há equipamento que atenda simultaneamente aos 11 casos. Nenhum diâmetro da grade mantém a velocidade na banda 1.0–1.5 m/s: na grade oferecida ela varia de 0… |
| B-003 | DN 125 mm, H 252,2 m | inviável: Não há equipamento que atenda simultaneamente aos 11 casos. Há diâmetros na banda de velocidade 1.0–1.5 m/s, e neles o NPSH tem folga (a maior é 0.81 m). A recu… |

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

### P-001 — investigação lacuna metodológica

Óleo/óleo: o lado tubo fica laminar ou de transição, fora de Dittus-Boelter. FONTE LOCALIZADA (2026-09-26): Branan pp. 40-41 (eq. 2-9 parede, 2-10 Hausen laminar Re <= 2000, 2-11 Sieder-Tate turbulento, 2-12 interpolação de transição 2000 < Re < 10^4) e Saari §6.3, pp. 68-72 (eq. 6.28 laminar desenvolvido, 6.31 Sieder-Tate laminar com µ/µ_s, 6.32 Bhatti & Shah). Falta o EXEMPLO NUMÉRICO resolvido que o aceite do projeto exige para o caso-ouro: o Branan remete à planilha 'Tubes htc' do livro e Saari não fecha exemplo. O TAG continua lacuna metodológica até a correlação ser implementada e validada, como ramo próprio do método, sem extrapolar Dittus-Boelter (docs/validacao/20-correlacao-tubo-laminar.md).

- **premissa**: Arranjo de 2 passes no tubo (default 'escolha' de Saari Tab. 3.1): com a aproximação de P-32 a troca óleo/óleo é quase simétrica (R ≈ 1) e P alto, fora do alcance de um casco 1-2. Contracorrente pura (1 passe) ou cascos em série resolvem o domínio de F.
- **modelo**: LACUNA METODOLÓGICA: resolvido o domínio de F (1 passe), o óleo no tubo tem Re de 1.661 a 4.947, fora de Dittus-Boelter (Re ≥ 10⁴). Os dois lados são óleo, e trocar os lados não resolve: com a emulsão no casco e o óleo tratado quente nos tubos, o F segue fora do domínio com 2 passes, e com 1 passe o tubo continua laminar/de transição. A correlação do lado tubo laminar e de transição EXISTE no acervo (Branan pp. 40-41, eq. 2-10 e 2-12; Saari pp. 70-72, eq. 6.28 e 6.31); falta o exemplo numérico do caso-ouro e a implementação. O P-001 é o único TAG que atravessa Re = 2000 (Re de 1.661 a 4.947) e precisa dos dois ramos.

### P-002 — investigação aberta

Topologia P-46 (óleo no casco, água quente nos tubos), P-45 e reotimização F10x.7 (docs/validacao/18-trocadores.md). Com 2 cascos em série o comprimento cabe em 6 m. O que ainda governa é a faixa de Dittus-Boelter no caso de menor carga (BOT 06, 3,6 % da carga de projeto: v ≈ 0,08 m/s, Re ≈ 4.200 < 10⁴), que a P-45 manda exigir em todos os casos.

- **premissa**: CONFIRMADA e adotada (P-46): a alocação com o óleo viscoso no tubo foi trocada; com a água nos tubos, a faixa de Dittus-Boelter só falha no turndown profundo.
- **premissa**: Vazão da utilidade proporcional à carga: ṁ = q/(cp·ΔT) com o ΔT da utilidade fixo pelos insumos t_agua_in/t_agua_out em todos os casos. Num turndown de 28× a água de aquecimento fica laminar nos tubos. Manter a circulação da utilidade (ΔT menor no turndown) é outra premissa de operação; sem variante executável, a decidir.
- **modelo**: Correlação do lado tubo só turbulenta (Dittus-Boelter, Re ≥ 10⁴): o caso de turndown (BOT 06, Re ≈ 4.200) cai na faixa de transição coberta pela eq. 2-12 do Branan (p. 41) e pela eq. 6.27 de Saari (p. 69). A fonte existe; falta o exemplo numérico do caso-ouro e a implementação. A própria fonte declara a região de transição imprevisível e recomenda evitá-la (docs/validacao/20-correlacao-tubo-laminar.md).

### P-003 — investigação aberta

Topologia P-46 (óleo no casco, água de resfriamento nos tubos), P-45 e reotimização F10x.7. O casco NÃO passa de 2.500 mm, então os cascos em paralelo não se aplicam (e reduziriam o Re por casco). O que ainda governa: a faixa de Dittus-Boelter nos casos de baixa carga (BOT 04, 05 e 06) e, no melhor feixe, o comprimento de tubo acima de 6 m.

- **premissa**: CONFIRMADA e adotada (P-46): a alocação com o óleo viscoso no tubo foi trocada.
- **premissa**: Vazão da utilidade proporcional à carga (ΔT da utilidade fixo pelos insumos): nos casos de baixa carga a água de resfriamento fica laminar nos tubos, como no P-002. A faixa é coberta pelas eq. 2-10 e 2-12 do Branan (pp. 40-41), pendente de exemplo numérico e implementação.
- **premissa**: Comprimento: a decisão do usuário previu cascos em série só para o P-002. No P-003 o melhor feixe pede tubo acima de 6 m; cascos em série resolveriam esse bloqueio, mas não o de Dittus-Boelter. A decidir.

### B-001 — investigação explicada

Só sem a P-44 (banda em todos os casos): cada caso tem DN admissível isolado (125 a 600 mm), mas as faixas não se cruzam, porque a vazão de óleo varia cerca de 23× entre os casos. Com a P-44 (padrão) a linha é dimensionada pelo caso de maior vazão: DN 600 (docs/validacao/17-banda-bombas.md).

- **premissa**: CONFIRMADA (P-44): piso de velocidade de 1 m/s aplicado ao óleo tratado. Pela nota do descritor v_min (Moran 2016), o piso é para líquido com sólidos decantáveis; para líquido limpo o artigo só impõe o teto.
- **premissa**: CONFIRMADA (P-44): o envelope exigia a banda de velocidade em TODOS os casos de uma única linha. No projeto, a linha é dimensionada pelo caso de maior vazão, e os casos de menor vazão operam com velocidade menor (turndown).
- **modelo**: No turndown (caso 6, 4 % da vazão de projeto) a linha DN 600 fica na zona de transição laminar-turbulento (Re ≈ 3.460), onde nenhuma correlação de atrito da implementação vale. P-44b: o caso é fechado por POLÍTICA conservadora de engenharia (f de Colebrook-White aceito se não for menor que 64/Re), separada das correlações válidas; não é limite superior demonstrado. A confirmar.
- **modelo**: Uma bomba só não opera numa faixa de 23×: a vazão mínima contínua é dado do fabricante (fora do acervo). Bombas em paralelo ou recirculação de mínimo fluxo não são modeladas; a especificação sai do caso de projeto.

### B-002 — investigação explicada

Só sem a P-44: nos casos 15 e 16 a banda de 1,0–1,5 m/s cai no vão da série, entre DN 150 (≈1,7 m/s) e DN 200 (≈1,0 m/s), e nos demais a vazão varia cerca de 10×. Com a P-44 (padrão), a linha é dimensionada pelo caso de maior vazão (caso 11): DN 250.

- **premissa**: Banda de velocidade 1–1,5 m/s (Moran 2016) mais estreita que o salto de área entre DN consecutivos da série (200/150 → 1,78×): há vazões sem DN na banda. É numérico só na aparência: vem da combinação banda × série. Com a P-44 a banda só vale no caso de projeto, e ele tem DN na banda.
- **premissa**: CONFIRMADA (P-44): banda aplicada a todos os casos de uma única linha, como no B-001. O piso é mantido no caso de projeto (água produzida pode levar sólidos decantáveis).

### B-003 — investigação explicada

Só sem a P-44: cada caso tem DN admissível isolado (40 a 125 mm), mas as faixas não se cruzam, porque a vazão de água varia cerca de 8× entre os casos. Com a P-44 (padrão): DN 125, pelo caso 3.

- **premissa**: CONFIRMADA (P-44): banda de velocidade aplicada a todos os casos de uma única linha (turndown), como no B-001.

