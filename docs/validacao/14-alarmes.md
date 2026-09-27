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

### Variantes executadas (mesmo motor)

| TAG | Variante | Origem do valor | Resultado |
|---|---|---|---|
| P-001 | 1 passe no tubo (contracorrente pura) | limite inferior do descritor passes_tubo (Saari §4.2.1: contracorrente puro, F = 1), sugerido pela própria mensagem do motor | segue inviável: Não há equipamento que atenda simultaneamente aos 10 casos. Na banda de velocidade 1.0–3.0 m/s todos os feixes pedem tubo mais longo que o limite de 6.0 m — o m… |
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

### P-001 — investigação aberta

Óleo/óleo. A LACUNA METODOLÓGICA FOI FECHADA: a película do lado tubo passou a ter correlação nos três regimes (Hausen em Re ≤ 2000, interpolação em 2000 < Re < 10⁴, Dittus-Boelter acima — Branan pp. 40-41), e todos os dez casos ativos agora CALCULAM. O que restou é físico e construtivo, não metodológico: com 2 passes o fator F do arranjo 1-2 sai do domínio da Fig. 4.3 (cruzamento interno); com 1 passe (contracorrente) o impedimento é a ÁREA. No platô laminar o h_i do óleo satura em cerca de 34 W/(m²·K) e o U em cerca de 25 W/(m²·K), contra um U·A exigido de 1,55 MW/K no caso de projeto: o feixe mais curto de toda a grade pede 186,4 m de tubo (o escolhido, 434,4 m) contra o limite de 6 m. No topo da banda de velocidade (3 m/s, teto de erosão de Saari) o óleo ainda está em transição, com U de cerca de 388 W/(m²·K) e área de cerca de 4.000 m². Nenhuma correlação resolve isto: é a troca óleo/óleo com aproximação de 10 K (P-32) que exige essa área. Ver docs/validacao/24-pelicula-baixo-reynolds.md.

- **premissa**: Arranjo de 2 passes no tubo (default 'escolha' de Saari Tab. 3.1): com a aproximação de P-32 a troca óleo/óleo é quase simétrica (R ≈ 1) e P alto, fora do alcance de um casco 1-2. Contracorrente pura (1 passe) resolve o domínio de F — e aí o impedimento passa a ser a área.
- **modelo**: RESOLVIDA: faltava correlação do lado tubo fora da faixa de Dittus-Boelter. A fonte existia (Branan pp. 40-41) e está implementada e validada (caso-ouro independente em tests/fixtures/python_ref/golden_pelicula_tubo.json). Os dez casos calculam; o alarme deixou de ser metodológico.
- **premissa**: A área exigida vem da APROXIMAÇÃO de 10 K da P-32 entre duas correntes de óleo. O teto de velocidade de 3 m/s (erosão, Saari Tab. 3.1) impede o óleo de chegar ao turbulento: a 3 m/s o Reynolds é de cerca de 7.000. Aumentar o ΔT de aproximação reduz a recuperação do pré-aquecedor e a área na mesma direção — é decisão de projeto, com efeito no balanço, e não foi tomada aqui.
- **modelo**: No platô laminar o Nusselt é constante (3,66 mais o termo de entrada), então acrescentar tubos reduz o comprimento sem piorar o coeficiente: de 1.994 tubos/passe (piso de 1 m/s) a 50.000 tubos/passe o comprimento exigido cai de 266 m para 21 m, e a área fica em cerca de 60.000 m². Ou seja: nem relaxando o piso de velocidade o equipamento cabe no limite de 6 m — o impedimento é a área, não a banda.

### P-002 — investigação fechada pela física

FECHADO em 2026-09-26, sem premissa nova e sem mudar arquitetura. O único bloqueio era a faixa de Dittus-Boelter no caso de menor carga (BOT 06, 3,6 % da carga de projeto), e ele existia porque o programa não tinha correlação fora do turbulento. Com os três regimes (Branan pp. 40-41) o BOT 06 passa a ser calculado e o TAG fica VIÁVEL: na geometria que a reotimização escolhe ele cai no LAMINAR (Re = 1.416, Hausen), e quem cai na interpolação de transição são os BOT 04 (Re = 4.145) e BOT 05 (Re = 5.461). A reotimização reexecutada com a física correta escolhe UM CASCO: tubo de 12,7 mm, 1 passe, passo 1,25, arranjo 90°, chicana 0,2·Ds, 1.605 tubos/passe, L = 5,99 m, 383,8 m² — 21 dos 96 candidatos da grade são viáveis. Nem cascos em série nem circulação fixa foram necessários.

- **premissa**: CONFIRMADA e adotada (P-46): a alocação com o óleo viscoso no tubo foi trocada; com a água nos tubos, só o turndown profundo saía da faixa turbulenta.
- **modelo**: RESOLVIDA: a correlação do lado tubo fora do turbulento existia no acervo e está implementada (Hausen eq. 2-10, interpolação eq. 2-12), com caso-ouro independente. Era o que faltava — não uma premissa de operação.
- **premissa**: Vazão da utilidade proporcional à carga (ṁ = q/(cp·ΔT), com o ΔT fixo pelos insumos): com a física completa ela NÃO precisa mais ser revista para o TAG ter solução. A circulação fixa continua estudo em docs/validacao/21-circulacao-cascos.md, e agora é escolha de operação, não remédio de viabilidade.

### P-003 — investigação fechada pela física

FECHADO em 2026-09-26, junto com o P-002 e pelo mesmo motivo. Os casos de baixa carga (BOT 04, BOT 05 e BOT 06) eram recusados por falta de correlação, não por limite físico: na geometria escolhida os três ficam no LAMINAR (Re = 1.449, 629 e 162; Hausen), e a interpolação de transição aparece nos BOT 11, 15 e 16 (Re = 6.111, 4.615 e 5.139). Com os três regimes eles calculam, e a reotimização reexecutada encontra UM CASCO viável: tubo de 12,7 mm, 1 passe, passo 1,25, arranjo 30°, chicana 0,2·Ds, 7.526 tubos/passe, L = 4,91 m, 1.473,4 m² — 32 dos 96 candidatos são viáveis. O bloqueio de comprimento que restava com tubo de 25,4 mm (7,33 m contra o limite de 6 m) desaparece com o tubo menor, que acomoda mais tubos no mesmo casco. NÃO foi preciso estender a série de cascos ao P-003, nem fixar a circulação: a premissa original (série só no P-002) segue intacta e o P-002 também não precisa mais dela.

- **premissa**: CONFIRMADA e adotada (P-46): a alocação com o óleo viscoso no tubo foi trocada.
- **modelo**: RESOLVIDA: os casos de baixa carga eram recusados por falta de correlação. Implementados os três regimes, com caso-ouro independente, nenhum caso ativo é mais recusado por correlação.
- **modelo**: RESOLVIDA sem mudar arquitetura: o comprimento excedia o limite de estoque de 6 m com tubo de 25,4 mm; com 12,7 mm o melhor feixe cabe em 4,91 m num casco só. Os limites de 6 m e de 2.500 mm não foram alterados, e cascos em série/paralelo não foram acionados.
- **premissa**: Vazão da utilidade proporcional à carga: não é mais necessária para o TAG ter solução. A circulação fixa segue como estudo, e a decisão é de operação.

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

