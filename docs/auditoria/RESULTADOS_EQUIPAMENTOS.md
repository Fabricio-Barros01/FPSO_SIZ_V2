# Resultados dos 11 equipamentos — cenário-base

**CENÁRIO-BASE** (P-18 = 700 kPa, P-19 = 200 kPa), 16 casos do BOT, propostas do pacote
(`pendencias_propostas.toml`, sha256 `a1715287ab3a…`), baseline `b638c19`, entrada
`tests/fixtures/python_ref/design_cases_bot.json` (sha256 `ca3dfe559b32…`). Números do fluxo
produtivo (`pfd/equipamento` → `core/motor`), gerados por `tools/tabelas_auditoria.py`
([`resultados_equipamentos.json`](resultados_equipamentos.json)); conferidos pelo gate
(`tools/auditar_saida_pfd.py`: aprovado). Dimensionamento **preliminar**.

> O subproblema otimizado da nota 42 (P_D1 ≈ 510–540 kPa, P_D2 ≈ 134 kPa) **não** foi usado para
> redimensionar a planta. Nele, SG-001, V-001 e V-002 ficam com os mesmos diâmetros (6.050 /
> 4.700 / 4.700 mm) e volumes de 684,8 / ~284 / ~285 m³ (nota 42 §7); os demais TAGs não foram
> avaliados nesse ponto.

## Resumo

| TAG | equipamento | método | estado | resultado principal | governante | caso governante |
|---|---|---|---|---|---|---|
| SG-001 | separador trifásico de água livre (FWKO) | Stewart & Arnold 3F | dimensionado | d = 6.050 mm; Leff = 17,867 m; Lss = 23,822 m; SR = 3,94; 684,8 m³ | capacidade de líquido | BOT 12 — Late Life |
| V-001 | desgaseificador 1 | Stewart & Arnold 2F | dimensionado | d = 4.700 mm; Leff = 11,719 m; SR = 3,49; 284,9 m³ | capacidade de líquido | BOT 02 — Early Life |
| V-002 | desgaseificador 2 | Stewart & Arnold 2F | dimensionado | d = 4.700 mm; Leff = 11,807 m; SR = 3,51; 286,4 m³ | capacidade de líquido | BOT 02 — Early Life |
| TO-001 | desidratador eletrostático | Arnold | dimensionado | d = 5.550 mm; Leff = 16,428 m; SR = 3,96; 531,7 m³ | retenção de líquido | BOT 02 — Early Life |
| TO-002 | dessalinizador eletrostático | Arnold | dimensionado | d = 5.550 mm; Leff = 16,402 m; SR = 3,96; 531,1 m³ | retenção de líquido | BOT 02 — Early Life |
| P-001 | pré-aquecedor óleo/óleo | Saari + Bell-Delaware | **inviável** | — | — | primeiro impedimento no BOT 01 |
| P-002 | aquecedor de óleo | Saari + Bell-Delaware | dimensionado | 1.701 tubos/passe; L = 6,000 m; A = 407,2 m²; U = 1.030 W/m²K; casco 764 mm | térmica | BOT 02 — Early Life |
| P-003 | resfriador de óleo | Saari + Bell-Delaware | dimensionado | 7.435 tubos/passe; L = 4,910 m; A = 1.456,4 m²; U = 723 W/m²K; casco 1.463 mm | térmica | BOT 07 — Mid Life |
| B-001 | transferência de óleo | Moran | dimensionado | DN 600; H = 75,02 m; 307,3 kW nominal | carga estática | BOT 03 — Early Life Blend |
| B-002 | água do desidratador | Moran | dimensionado | DN 250; H = 183,4 m; 143,3 kW nominal | carga estática | BOT 03 — Early Life Blend |
| B-003 | água do dessalinizador | Moran | dimensionado | DN 125; H = 252,2 m; 45,5 kW nominal | carga estática | BOT 03 — Early Life Blend |

**10 dimensionados, 1 inviável.** Volume dos cinco vasos: 2.318,8 m³.

## Leitura por grupo

**Vasos (SG-001, V-001, V-002, TO-001, TO-002).** Todos governados pelo **líquido** (tempo de
retenção), não pelo gás. Nos desgaseificadores o gás pede 1,1–1,5 m de Leff contra ~11,7 m do
líquido (nota 39 §7) — por isso o diâmetro deles é insensível às pressões (notas 41 e 42). O
SG-001 tem teto de decantação (10.021 mm, óleo em água) acima do diâmetro escolhido; com óleo
morto ele seria inviável (nota 40).

**Trocadores.** P-002 e P-003 fecham em **um casco**, com a película do lado tubo nos três regimes
(Branan pp. 40–41; nota 24) e geometria da reotimização F10x.7 (nota 18). Condutividades,
incrustações e temperaturas das utilidades são **propostas** do autor.

**P-001 — inviável (resultado legítimo).** Mensagem do método: *"Caso 'BOT 01 — Early Life': o
arranjo 1-2 não fecha com estas temperaturas: o fator de correção F sai do domínio da Fig. 4.3.
Em contracorrente puro (1 passe) o caso é viável — o cruzamento interno de um segundo passe é que
não é."* A causa de fundo (nota 36): P-32 = 10 K numa troca quase balanceada (NTU 2,5–4,4), óleo
viscoso laminar no turndown (U ≈ 25 W/m²K) e geometria única para 24× de faixa de carga; o menor
comprimento de tubo da grade é 186 m contra 6 m. O MC traz o diagnóstico numérico no lugar das
dimensões. Nenhuma alternativa foi adotada.

**Bombas.** Governadas pela carga **estática** (a diferença de pressão entre vasos), com perda de
carga pequena. Geometria de linha, NPSHr e margem são **propostas** do autor; folga de NPSH de
0,81–1,0 m.

## Situação de cada TAG no gate

0 `ERRO_NUMERICO`, 0 `ERRO_OUTPUT`; 316 ausências `NAO_APLICAVEL` e 22 `INVIAVEL`, todas
justificadas pelo próprio resultado. MC gerado para os 11 (o do P-001 com diagnóstico).
