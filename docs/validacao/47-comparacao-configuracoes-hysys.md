# 47 — Otimização no contrato atual do P-001, comparação de configurações e pacote para o HYSYS

Commit de partida: `8b64dbe`, com as alterações locais das notas 45 e 46 (não commitadas). Data: 2026-10-03.

O fluxo principal auditado (geometria única do P-001, áreas por unidade × em operação × instalada,
P-002/P-003 no estado pós-rating, MC com continuidade, classificação de restrições e decisões
pendentes) foi preservado: nenhum resultado de TAG mudou e o gate segue aprovado.

## Diagnóstico e causa raiz

1. **`AttributeError` no avaliador (confirmado).** `pfd/otimizacao._objetivo` lia
   `rt.resultado.derivados` para o objetivo de área; desde a nota 45 o P-001 integrado devolve
   `ResultadoTAG(resultado=None, operacao=OperacaoP001)`. O objetivo `area_trocadores` quebrava
   em toda avaliação do problema completo.
2. **Objetivo de utilidade lido do balanço preliminar (defeito real, não citado antes).**
   `carga_aquecimento` (Q_H + Q_D, máximo entre casos) lia `planta.balanco`, o preliminar; a
   parcela que a geometria instalada não recupera vai ao P-002 só no estado operacional. Na
   referência: 10.759,9 kW (preliminar) contra 21.062,8 kW (pós-rating).
3. **A violação ignorava restrições do TAG dimensionado.** `_violacao` devolvia 0 para todo TAG
   `dimensionado`, inclusive com `rt.restricoes` (requisito obrigatório não atendido na geometria
   instalada). Hoje a lista está vazia, mas a regra aprovaria um P-001 que violasse velocidade ou
   diâmetro de casco.
4. **Pendência e verificação incompleta saíam como "viável".** O ponto só distinguia
   não convergido / não avaliável / inviável / viável; um ponto com o comprimento do P-001 em
   decisão pendente e hidráulica incompleta seria apresentado como viável.
5. **`investigacao.evidencia`** quebraria (`rt.resultado` None) se o P-001 integrado ficasse
   inviável (busca sem geometria).

### Origem das falhas "anteriores" (bisseção, mesma suíte em cópias `git archive`)

| teste | `9480e09` | `c3ad341` | `8b64dbe` (HEAD) | local antes desta nota | classificação |
|---|---|---|---|---|---|
| `test_otimizacao::criterio_1`, `a_violacao…` | passa | falha (P-001 sem violação) | falha | `AttributeError` | expectativa obsoleta (P-001 não é mais DESIGN inviável) + defeito 1 |
| `test_otimizacao::criterio_4` | passa | falha (P-002 2913 → 2948 tubos/passe ao reusar o contexto) | falha | `AttributeError` | defeito real em `c3ad341` (rating reaplicado sobre estado já ajustado), corrigido pela nota 45; agora o teste também congela áreas, operação e etapa |
| `test_alarmes::um_passe…` | passa | falha | falha | falha | expectativa obsoleta: o DESIGN do P-001 deixou de ser o resultado do TAG; a física do alarme continua verificada no estudo DESIGN explícito |
| `test_alarmes::alarme_no_memorial…` | passa | falha | falha | falha | expectativa obsoleta: o P-001 instalado não é TAG inviável; o alarme no MC continua verificado para um P-001 sem geometria |
| `test_consolidacao::sem_consumidor` (`sizing/bombas_paralelo`) | passa | falha | falha | falha | **lacuna real**: `c3ad341` removeu o único consumidor; a multiplicidade de bombas (ADR 0005 item 6) não está ligada à planta. Não corrigida aqui (mudaria as bombas) |
| `test_pelicula_planta` (P-002 e P-003 em BOT 04/05) | passa | falha | falha | falha | nasce em `c3ad341` (a nota 45 atribuía a `50ca9ac`): os regimes esperados são do balanço preliminar; com a carga pós-rating o P-002/P-003 saem de laminar para transição. Provável expectativa obsoleta, **não revista aqui** — exige conferir os regimes novos antes de alterar o teste |

Nenhuma das falhas é anterior ao conjunto de mudanças do P-001: todas nascem em `c3ad341`
("integrar rating do P-001 ao fluxo PFD").

## Correções

- **Uma regra de área** (`pfd/equipamento.areas_troca`): por unidade, em operação e instalada.
  P-001 = `OperacaoP001.areas` (a mesma do JSON, terminal e MC); envelope DESIGN = área do
  ponto escolhido, com cascos série × paralelo, sem reserva (o método não modela standby).
  `equipamento.derivado` substitui o acesso direto a `rt.resultado.derivados`.
- **Objetivo de área** (`otimizacao.toml`): `tipo = "soma_area_troca"`, `base = "instalada_m2"`,
  rotulado "indicador de investimento, não custo". A avaliação térmica usa a área em serviço
  (o `UA/U` do rating = área em operação, testado caso a caso). Replicar por `fator_vazao` um
  TAG que já tem multiplicidade própria é recusado (contagem dupla).
- **Utilidade pós-rating**: objetivo `carga_balanco` com `etapa = "apos_rating"` lê
  `planta.balanco_operacional`. O subproblema de pressão (nota 42) não declara etapa e segue no
  preliminar — as grandezas dele (perda de óleo, gás da VRU, TVP) não dependem do rating e ele
  não dimensiona o P-001.
- **Classificação do ponto** (`Avaliacao`): violação (g > 0, inclusive um por restrição do TAG
  dimensionado), `decisao_pendente`, `verificacao_incompleta`, limitação aceita (informativa).
  `admissivel` = avaliável e sem violação (o que o algoritmo enxerga); `viavel` = admissível sem
  pendência nem verificação incompleta. `motivos()` devolve o porquê, estruturado.
  `ResultadoTAG` ganhou `verificacoes_incompletas` e `limitacoes_aceitas` (recuperação parcial,
  teto Pinch nulo), lidos da `OperacaoP001.avaliacao()` — a mesma do JSON e do MC.
- **Comparação finita** (`otimizacao.comparar`, `Comparacao`): domínio explícito (`grade` do
  subproblema, a referência primeiro), limite de avaliações (`[subproblema.comparacao]`),
  candidatos com situação e motivos, pontos não avaliados quando o limite corta, término normal
  sem candidato aprovado, frente por dominância entre admissíveis (sem pesos).
- **Alarmes**: testes no contrato atual; `evidencia` lê a mensagem da busca do P-001.

## Critérios e domínio da comparação

Subproblema `configuracao`: trens do SG-001 (1–3) × passes do P-002 (1–2) × passes do P-003
(1–2) = 12 pontos; premissas na base (η_F é premissa de processo, fica fora); a planta inteira
pelo serviço por TAG; o P-001 sai da busca própria e é o mesmo em todos. Objetivos (minimizar):
volume dos vasos (m³), área instalada de troca (m², indicador) e carga de aquecimento pós-rating
(kW, máximo entre os 16 casos — cenários alternativos, não consumo simultâneo nem energia anual).

| obrigatório (violação) | decisão pendente | verificação incompleta | limitação aceita |
|---|---|---|---|
| TAG inviável; restrição não atendida da geometria instalada; restrição do balanço | comprimento do tubo do P-001 (nota 46) | perdas de carga do P-001 (sem critério vigente; casco só indicativo) | recuperação parcial (ADR 0005); teto Pinch nulo nos casos 10, 12–16 |

## Resultados (referência + 3 alternativas; limite 4, 4 processos, 93 s)

| trens SG | passes P-002 | passes P-003 | volume (m³) | carga aquec. (kW) | área instalada (m²) | situação | não dominado |
|--:|--:|--:|--:|--:|--:|---|---|
| 1 | 1 | 1 | 2.318,8 | 21.062,8 | 2.825,0 | decisão pendente (referência) | sim |
| 1 | 1 | 2 | 2.318,8 | 21.062,8 | 3.246,2 | decisão pendente | não |
| 1 | 2 | 1 | 2.318,8 | 21.062,8 | 2.908,3 | decisão pendente | não |
| 1 | 2 | 2 | 2.318,8 | 21.062,8 | 3.329,4 | decisão pendente | não |

Nenhum candidato é aprovado: todos dependem da decisão do comprimento do P-001 e têm a
hidráulica dele incompleta. Os 8 pontos com 2 e 3 trens não foram avaliados (limite). A área da
referência = P-001 646,35 (3 × 215,45; 2 em operação + 1 reserva) + P-002 696,89 + P-003 1.481,79 m².

## Pacote para o HYSYS

`fpso-siz pfd --casos … --saida DIR --hysys` (ou `tools/comparar_configuracoes.py`, que inclui
a comparação) grava em `DIR/hysys/`: `hysys.json` (proveniência com sha256 dos casos e das
propostas, condições padrão, premissas, 16 casos com composição de caso e estágios do trem quando
existem, MW/ρ das frações plus do arquivo de casos, topologia com conexões e TAG de cada bloco,
equipamentos com geometria, multiplicidade, áreas, classificação, valores propostos usados e o
rating do P-001 por caso — UA, U, F, ΔT_lm, h, Re, velocidades, Δp com a natureza de cada um —,
comparação e dados faltantes), `hysys_correntes.csv` (caso × corrente, estado pós-rating),
`hysys_cargas.csv` (caso × etapa: preliminar e pós-rating) e `hysys_equipamentos.csv`.

Não há integração automática nem verificação de importação. Dados faltantes declarados em
`config/pfd/hysys.toml`: composição do gás de lift (casos 9, 11, 15, 16), h/cp dos
pseudo-componentes, ρ líquida pela EOS e k líquido, comprimento do tubo do P-001, limites de
perda de carga, pressões dos degaseificadores e o pacote termodinâmico/kij do HYSYS. As vazões
estão em pseudo-fases (O, W, D, G); nenhuma conversão para componentes foi feita.

## Verificação

- Direcionados (`test_otimizacao` sem `@otim`, `test_alarmes`, `test_pacote_hysys`, arquitetura,
  P-001, CLI, gate): 604 passam, 2 falhas — `bombas_paralelo` (acima) e uma do teste do pacote
  corrigida em seguida (o teste confundia Q_H do balanço.json, Σ dos aquecedores, com
  `duties["Q_H"]`). 1:59.
- Ampla (`tests/pfd` inteiro com `@otim`, arquitetura, CLI, terminal, MC, fluxo do TAG): 907
  passam; 4 falhas, todas da tabela de origem acima (`bombas_paralelo` e 3 de película). 7:38.
- Gate `tools/auditar_saida_pfd.py`: consistência aprovada, 0 erros (24 s).
- Um ponto do problema completo: ~55 s sequencial (dominado pela busca do P-001).

## Limitações remanescentes

Todas as das notas 45/46 continuam (recuperação parcial, propriedades simplificadas, hidráulica
incompleta, comprimento em decisão pendente — a precedência documentada foi mantida, o domínio
6–9 m não foi reduzido). A comparação não cobre a geometria do P-001 como variável (ela vem da
busca própria). A multiplicidade de bombas da ADR 0005 segue desligada da planta.
