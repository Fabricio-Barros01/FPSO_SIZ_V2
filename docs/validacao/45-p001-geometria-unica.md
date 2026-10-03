# 45 — P-001: uma geometria só, do rating ao memorial

Commit de partida: `8b64dbe` (auditado). Data: 2026-10-02.

## Defeitos confirmados no commit de partida

1. **Duas geometrias no mesmo TAG.** `pfd/planta.dimensionar` fazia a busca discreta e o rating
   (`equipamento.avaliar_p001`), propagava `Q_real` ao balanço e, em seguida, chamava
   `equipamento.executar` para o P-001 como para qualquer TAG. Isso rodava `size_envelope`
   (DESIGN) sobre o estado **pós-rating**, com os parâmetros do método (2 passes, 30°, tubo de
   6 m), e redimensionava o equipamento para a carga reduzida: 695 tubos/passe, 2 passes,
   L ≈ 5,70 m, um casco. O JSON trazia as duas (`operacao_integrada.geometria` e
   `envelope.resultado`); o memorial só mostrava a segunda, que nunca foi avaliada no rating.
2. **Caminho por TAG ignorava a dependência.** A integração existia só em `planta.dimensionar`.
   `dimensionar --tag P-002` lia o balanço preliminar: no caso 3, T de entrada do óleo 77,83 °C e
   água 124 kg/s (1701 tubos/passe), contra 62,27 °C e 283 kg/s (2913 tubos/passe) na planta.
3. **O preliminar se perdia.** `aplicar_rating_termico` sobrescrevia `Q_pre`, `T_C07`, `T_C23`,
   `Q_H` e `Q_C` sem guardar os valores anteriores nem marcar a etapa.
4. **Diagnósticos.** `diametro_casco_mm` recebia `d_shell` em **metros** (`_feixe_fixo` trabalha
   em SI): 0,57549 m = 575,49 mm. As perdas de carga nulas não tinham motivo: no casco dos casos
   5 e 11, Re = 2731 e 3821, e no tubo do caso 9, Re = 3474, estão na transição
   (2300 < Re < 4000), onde `darcy_friction` não tem correlação declarada; o caso 12 é inativo
   (Q_Pinch = 0). Nenhum critério de velocidade ou geométrico era classificado, e `avaliar_p001`
   sobrescrevia `l_tubo_max` do caso com o comprimento do próprio candidato — o limite de 6 m do
   método nunca era conferido. A nota 43 dizia que a busca descartava candidatos por velocidade
   e comprimento; o código só exigia convergência e `U` finito.

## Correção

- **Uma definição.** `equipamento.integrar_p001` é a única fonte da geometria instalada e da
  multiplicidade. Para o P-001 automático, `executar` devolve `ResultadoTAG(resultado=None,
  operacao=…)`: não há DESIGN refeito. JSON (`envelope: null`), `P-001_operacao.csv`,
  `planta.csv`, terminal, memorial e gate leem a mesma `OperacaoP001`. O estudo DESIGN do P-001
  continua disponível (`dimensionar(preparar(...))`), sobre o alvo preliminar, como diagnóstico.
- **Áreas.** `areas`: por unidade, em operação (`duty` unidades) e instalada (inclui a reserva,
  que não troca calor; o rating divide as vazões só entre as unidades em serviço).
- **Dependência no serviço por TAG.** O `Contexto` guarda o estado do P-001
  (`definir_p001`, `configurar_dependencias(ctx, ajustes)`) e calcula a integração uma vez.
  `depende_do_rating(t)` lê as regras do TAG: só P-002 e P-003 citam correntes ou cargas que o
  rating altera (`modelo.CORRENTES_RATING`, `CARGAS_RATING`); eles são preparados do estado
  operacional, os demais do preliminar — numericamente idêntico para eles, o que se confirmou
  bit a bit nos 10 TAGs. TAG isolado, planta (inclusive com `somente`) e modo interativo usam o
  mesmo caminho.
- **Etapas.** `EstadoProcesso.etapa` (`preliminar` | `apos_rating_P-001`) e
  `antes_do_rating`; refazer o rating sobre um estado já ajustado é recusado. Cada caso da
  operação traz o preliminar ao lado do realizado; cada TAG exporta `etapa_balanco`.
- **Classificação**, em separado: convergência numérica (`rating.estado`), atendimento térmico
  (`pleno`, `parcial`, `sem_carga`, `nao_avaliado` diante do teto Pinch) e hidráulico. Critérios
  vigentes, sem limite novo:
  - velocidade no tubo, P-45: teto `v_max` em todos os casos ativos; piso `v_min` reprova só no
    caso de projeto (maior vazão volumétrica no tubo) e é alerta no turndown;
  - validade da película do lado tubo em cada caso ativo;
  - comprimento do tubo ≤ `l_tubo_max` e diâmetro do casco ≤ `d_casco_max` do método;
  - perda de carga: **sem limite vigente** (BOT e acervo não fixam); valor informativo. Ausente
    é `nao_avaliado` com o motivo (regime e Re), nunca zero nem atendido. A do casco é
    estimativa indicativa (Darcy–Weisbach sobre L/d_o, com ρ do lado tubo; a nota 43 já
    registrava que o acervo não tem correlação de casco).
  Caso inativo: `nao_aplicavel`, com motivo (corrigido na nota 46: só a ausência de vazão torna a hidráulica não aplicável). A situação da geometria é `atende`,
  `com_restricoes`, `nao_avaliado` ou `inviavel`; as restrições aparecem no JSON, na
  `planta.csv`, no terminal, na identificação do memorial e no gate.
- **Sem geometria** (nenhum candidato admissível): `OperacaoP001(geometria=None, mensagem)`,
  TAG `inviavel`, dependentes no preliminar identificado — término normal.

## Antes × depois (caso 3, BOT 03 — Early Life Blend)

| grandeza | antes: `operacao_integrada` | antes: `envelope`/PDF | depois (única) |
|---|---|---|---|
| tubos por passe × passes | 400 × 1 | 695 × 2 | 400 × 1 |
| comprimento do tubo | 9,0 m | 5,70 m | 9,0 m |
| arranjo | 45° | 30° | 45° |
| unidades | 3 (2 em operação + 1 reserva) | 1 casco | 3 (2 + 1) |
| área | — | 474,2 m² | 215,5 m²/unidade; 430,9 em operação; 646,4 instalada |
| diâmetro do casco | 0,5755 (rotulado mm) | 970,4 mm | 575,5 mm |

| caso 3 | preliminar | após rating |
|---|--:|--:|
| Q do P-001 (kW) | 16.137,5 | 6.095,5 |
| T C-07, saída fria (°C) | 77,83 | 62,27 |
| T C-23, saída quente (°C) | 62,82 | 80,03 |
| Q do P-002 (kW) | 7.851,3 | 17.893,3 |
| Q do P-003 (kW) | 13.313,1 | 23.355,2 |

Os números do rating não mudaram (a fixture `p001_busca_regressao.json` passa sem revisão); mudou
o que se apresenta como P-001. P-002, P-003 e os demais TAGs da planta ficaram idênticos.

## Classificação atual da geometria instalada

- Convergência: os 16 casos (10 convergidos, 6 sem carga).
- Térmico: recuperação **parcial** nos 10 casos ativos (no caso 3, 37,8 % do teto Pinch); o
  restante vai a P-002/P-003, como admitido pela ADR 0005.
- Hidráulico: atende ao teto de velocidade em todos os casos ativos e ao piso no caso de projeto
  (caso 3, 2,59 m/s); **alerta** de piso no turndown dos casos 4, 5 e 6 (0,33; 0,43; 0,12 m/s).
- **Restrição não atendida: `comprimento_tubo`** (reclassificada na nota 46 como decisão pendente: o limite de 6 m é default do método, não confirmado) — 9,0 m instalados contra `l_tubo_max` = 6 m
  do método (limite de fabricação, Branan p. 38). O domínio de busca (`p_001_busca.toml`, nota
  43) vai até 9 m e não aplica esse limite; a correção expõe a violação em vez de escondê-la. Ela
  é uma restrição física/de projeto em aberto, não falha de software.

## Limitações remanescentes

- **Software:** a busca não aplica os critérios de velocidade, película nem os limites
  geométricos como admissibilidade (só classifica a escolhida); aplicar mudaria a seleção e está
  fora do escopo desta correção. O turndown não usa `minimo_ativas` (opera sempre com as duas
  unidades). Testes de P-002/P-003 em `test_pelicula_planta.py` (regimes de BOT 04/05/06) e
  `test_nenhum_modulo_sem_consumidor` (`sizing/bombas_paralelo.py`) já falhavam no commit de
  partida e seguem falhando: as expectativas são do balanço anterior ao rating (`50ca9ac`).
- **Física/dados:** comprimento acima do limite do método; recuperação parcial em todos os casos;
  perda de carga sem correlação na transição e sem correlação de casco no acervo; ρ do casco
  tomada do lado tubo (corrigida na nota 46); propriedades do óleo congeladas na temperatura média preliminar durante o
  rating (k do óleo sem validação, nota 44).
