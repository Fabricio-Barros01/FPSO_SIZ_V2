# 46 — P-001: segunda auditoria (hidráulica, memoriais, ρ do casco, premissa de comprimento)

Commit de partida: `8b64dbe`, com as alterações locais da nota 45 (não commitadas). Data: 2026-10-02.
Caso de referência: BOT 03 — Early Life Blend (caso de projeto da P-45).

A geometria única do P-001 (nota 45) e a dependência de P-002/P-003 em relação ao estado
pós-rating foram preservadas: 400 tubos/passe × 1 passe, 9,0 m, 45°, 2 em operação + 1 reserva;
215,45 m² por unidade, 430,90 m² em operação, 646,35 m² instalada; casco 575,49 mm. Os resultados
térmicos do P-001 (Q_real, T C-07, T C-23, Q P-002, Q P-003) e os envelopes e entradas dos outros
dez TAGs ficaram **idênticos** nos 16 casos (comparação JSON a JSON da execução anterior).

## Defeitos confirmados e causa raiz

1. **Carga térmica nula tratada como ausência de vazão.** `avaliar_p001` classificava o caso com
   `Q_pre = 0` como `papel = inativo` e `hidraulico = nao_aplicavel`. O balanço não modela bypass
   nem isolamento do P-001 (`balanco/modelo.py`: `s07 = s06`, `s23 = s21`): nos casos 10 e 12–16 as
   correntes atravessam o equipamento (caso 12: 141,8 kg/s no tubo e 82,3 kg/s no casco), e o
   rating já devolvia velocidades e Δp nesses casos — que eram descartados.
2. **Resumo hidráulico "atende" com lacunas.** `_resumo` olhava só os critérios com limite; as
   perdas de carga ausentes (casos 5, 9, 11, 12…) e sem limite vigente não entravam, e o resumo da
   planta dizia `atende`.
3. **Metodologia do MC do P-001 como TAG pendente.** O template escolhia o ramo
   `metodologia` (texto "nenhuma foi avaliada: o TAG está aguardando entrada") sempre que não havia
   envelope DESIGN — e o P-001 integrado, por construção, não tem envelope.
4. **Tabela de 12 colunas** (preliminar × pós-rating) saía da moldura.
5. **Sem rastreabilidade documental** entre o balanço preliminar (MC-SEN-SEP-COO-001) e os MC de
   P-001, P-002 e P-003.
6. **ρ do casco = ρ do tubo.** `avaliar_p001` montava as propriedades do casco com
   `propriedades_declaradas(entrada_unidade.rho_tubo, …)`. O método `saari_lmtd` não recebe ρ do
   casco (`EXCHANGER_KEYS`), e o atalho usava a ρ da emulsão do FWKO (C-06) para o óleo tratado
   (C-22). Dependem dela **só** a velocidade no casco e a perda de carga indicativa do casco;
   `h_o` (Bell–Delaware) usa o fluxo mássico, não ρ — por isso nada térmico mudou.
7. **Duas premissas de comprimento.** A busca lia o domínio 6–9 m de `p_001_busca.toml`
   (nota 43); a classificação lia `l_tubo_max` = 6 m das entradas do TAG; e a ADR 0005 diz que a
   busca rejeita candidato que viole o método. O `l_tubo_max` é **default do método** (Branan
   p. 38, tubo de estoque), com origem `metodo` e revisão `pendente` — nunca confirmado como
   limite do projeto. A nota 45 o classificou como restrição não atendida.

## Correção

- **Atividade térmica × vazão** (`pfd/equipamento.py`): `papel` passa a ser o papel
  **hidráulico** (`projeto`, `turndown`, `sem_vazao`). Só a ausência de vazão nos dois lados torna
  a hidráulica `nao_aplicavel`. O caso de projeto da P-45 é o de maior vazão volumétrica no tubo
  entre os casos **com vazão** (o escopo documentado da P-45 é hidráulico: "o teto vale em todos os
  casos"). Nos casos sem carga, a validade da película (critério térmico) fica `nao_aplicavel`,
  com motivo; o térmico traz o motivo (sem força motriz; sem bypass modelado).
- **Atendimento × completude × informativos**: cada caso e a planta têm
  `atendimento` (só critérios vigentes efetivamente avaliados: `atende`, `alerta`, `nao_atende`,
  ou `nao_avaliado` se nenhum foi avaliado), `completude` (`incompleta` se alguma grandeza da
  verificação está ausente, sem critério de aceitação vigente ou é só estimativa), `lacunas`
  (com motivo) e `informativos` (valores sem critério). A conclusão é uma frase única, do TOML:
  "Critérios avaliados atendidos, com alerta de turndown (P-45); verificação hidráulica
  incompleta." Nenhum limite de perda de carga foi inventado; ausência continua `None` + motivo.
  Propagado a JSON (`operacao_integrada`), `P-001_operacao.csv` (`hidraulica_atendimento`,
  `hidraulica_completude`, `hidraulica_lacunas`), `planta.csv` (`hidraulica`,
  `decisoes_pendentes`), terminal, MC e gate.
- **ρ do casco**: o descritor de TAG ganhou `[auxiliares]` — grandezas fora do método, resolvidas
  pelas **mesmas regras** e com a mesma proveniência das entradas (`entradas._auxiliares`). O P-001
  declara `rho_casco = densidade_fase(C-22, líquido, T média C-22→C-23)`; o rating a usa no casco.
  Fase líquida, T média da corrente, kg/m³; a pressão não entra na regra (óleo pela API na
  condição padrão, sem correção por T — `proveniencia.toml`, `densidade_fase`). Exportada em JSON
  (`auxiliares`), CSV de operação e MC (seção 4). A perda de carga do casco é rotulada
  `estimativa_indicativa` (Darcy–Weisbach sobre L/d_o, sem correlação de casco no acervo) e a do
  tubo `correlacao_aplicavel`; a estimativa indicativa conta como lacuna de completude — corrigir
  ρ não a transforma em verificação.
- **Premissa única de comprimento** (`premissa_comprimento`): lida pela busca, pela classificação
  e pelo memorial. Se `l_tubo_max` for informado pelo usuário ou confirmado na revisão, é limite do
  projeto: a busca descarta tubos maiores e a classificação reprova acima dele. Enquanto for
  default não confirmado e o domínio da busca o exceder, o estado é `divergente`: o critério
  `comprimento_tubo` fica `decisao_pendente` (nem atendido nem reprovado), a situação da geometria
  fica `decisao_pendente`, e a decisão necessária aparece no JSON, no terminal, no MC (seção 8) e
  no gate. O limite **não** foi alterado e o domínio da busca **não** foi reduzido; nenhuma busca
  nova foi executada.
- **MC do P-001** (`mc_tag.tex.j2`, `memorial_tag.toml [rating_p001]`): objetivo, escopo e
  metodologia do **rating** (temperaturas em função de Q, carga transferida pela área fixa, carga
  realizada, cargas residuais, velocidades, Δp), distinguindo sizing de rating; as correlações do
  método aparecem como "avaliadas na geometria instalada".
- **Continuidade preliminar → pós-rating** (`pfd/memorial.continuidade`,
  `[continuidade]`): no MC do P-001 (seção 7) e nos de P-002/P-003 (subseção 4.3), gerada dos
  estados calculados — documento preliminar, origem do teto (aproximação mínima, P-32), geometria
  e multiplicidade, caso de referência, tabelas preliminar/pós-rating/Δ (no máximo duas grandezas
  por tabela), parcela não recuperada, resíduo `ΔQ_utilidade − não recuperado` e fechamento de
  massa e energia do estado operacional.
- **Gate** (`tools/auditar_saida_pfd.py`): o código de saída continua sendo a **consistência das
  saídas**; o relatório ganhou a seção "Atendimento de engenharia (informativo; não decide o
  código de saída)". Novas conferências: caso com vazão não pode ser hidraulicamente
  `nao_aplicavel`; lacuna obriga `completude = incompleta`; grandeza sem limite não pode ser
  `atende`; ρ do casco do rating = auxiliar do TAG; o limite de comprimento da classificação = o
  da premissa; premissa indefinida não pode virar aprovado/reprovado; o MC do P-001 não pode
  apresentar a metodologia como de TAG pendente; a continuidade dos MC reproduz o preliminar e o
  pós-rating dos estados usados e o fechamento atende.

## Antes × depois (P-001; o resto da planta idêntico)

| caso | ρ tubo (C-06) | ρ casco (C-22) | v_s antes | v_s depois | Δp_s antes | Δp_s depois (indic.) | hidráulica antes | depois |
|---|--:|--:|--:|--:|--:|--:|---|---|
| 1 | 889,0 | 889,0 | 6,387 | 6,387 | 243.821 | 243.821 | atende | atende / incompleta |
| 2 | 894,2 | 889,6 | 6,373 | 6,405 | 244.235 | 245.490 | atende | atende / incompleta |
| 3 | 890,4 | 885,8 | 6,350 | 6,384 | 228.543 | 229.742 | atende | atende / incompleta |
| 4 | 889,0 | 889,0 | 0,829 | 0,829 | 5.196 | 5.196 | alerta | alerta / incompleta |
| 5 | 885,2 | 885,2 | 1,080 | 1,080 | — | — | alerta | alerta / incompleta |
| 6 | 889,0 | 889,0 | 0,276 | 0,276 | 1.846 | 1.846 | alerta | alerta / incompleta |
| 7 | 889,0 | 889,0 | 6,381 | 6,381 | 243.376 | 243.376 | atende | atende / incompleta |
| 8 | 915,0 | 889,6 | 4,132 | 4,250 | 116.969 | 120.306 | atende | atende / incompleta |
| 9 | 929,2 | 889,6 | 3,249 | 3,394 | 78.076 | 81.551 | atende | atende / incompleta |
| 10 | 937,6 | 889,6 | 2,451 | 2,583 | 48.387 | 50.999 | nao_aplicavel | atende / incompleta |
| 11 | 974,1 | 889,7 | 1,636 | 1,791 | — | — | atende | atende / incompleta |
| 12 | 968,6 | 889,6 | 1,656 | 1,803 | — | — | nao_aplicavel | atende / incompleta |
| 13 | 956,1 | 889,6 | 2,016 | 2,166 | 35.100 | 37.722 | nao_aplicavel | atende / incompleta |
| 14 | 956,1 | 889,6 | 2,016 | 2,166 | 35.099 | 37.721 | nao_aplicavel | atende / incompleta |
| 15 | 981,3 | 889,6 | 0,715 | 0,789 | 4.508 | 4.972 | nao_aplicavel | alerta / incompleta |
| 16 | 981,2 | 889,6 | 0,796 | 0,878 | 5.019 | 5.535 | nao_aplicavel | alerta / incompleta |

ρ em kg/m³, v_s em m/s, Δp_s em Pa. Onde a emulsão do tubo leva água, ρ_s cai até 9,3 % e v_s e Δp_s
sobem na mesma proporção (v_s·ρ_s/ṁ_s constante, testado). Casos 15 e 16 passam a ter **alerta** de
piso de velocidade no tubo (P-45, turndown). Resumo da planta: `atende` → "Critérios avaliados
atendidos, com alerta de turndown (P-45); verificação hidráulica incompleta." Situação da geometria:
`com_restricoes` (comprimento) → `decisao_pendente` (comprimento).

Caso 3 (gerado pelo MC a partir dos estados): Q P-001 16.137,5 → 6.095,5 kW; T C-07 77,83 → 62,27 °C;
T C-23 62,82 → 80,03 °C; Q P-002 7.851,3 → 17.893,3 kW; Q P-003 13.313,1 → 23.355,2 kW; parcela
não recuperada 10.042,0 kW, integralmente transferida a P-002 e a P-003 (resíduo ~10⁻¹² kW).
Fechamento do estado operacional: ε_m ≤ 2,2·10⁻¹³ e ε_E ≤ 5,8·10⁻¹³ (adimensionais; fronteira e
blocos; massas em kg/s, energias em kW), critério ≤ 10⁻⁶ (`constantes.toml [criterios]`).

## Fechamento da rodada (mesma data)

Duas correções direcionadas, sem nova busca de geometria:

1. **Estado térmico dos seis casos com recuperação zerada (10, 12–16).** Eram rotulados
   `sem_carga` (térmico) e `sem_carga` / "caso sem carga térmica" (convergência), o que se confunde
   com ausência de serviço. A causa é o **teto Pinch nulo**: a aproximação disponível entre as
   entradas, T(C-22) − T(C-06) ≈ 0,47 K, é menor que ΔT_app = 10 K (P-32). Então Q_rec_max = 0 e
   Q_real = 0 por construção do balanço preliminar, não por limitação da geometria. Agora o estado
   térmico é `teto_nulo`, com `aproximacao_disponivel_K` e `aproximacao_minima_K` lidas da própria
   equação do balanço que zerou o teto (`carga_preaquecedor` no `CalcTrace`) e
   `fracao_recuperada = None` (0/0 não é recuperação plena nem parcial). A convergência é
   `intervalo_nulo` (a bisseção não tem o que iterar). O resumo traz `casos_teto_nulo`, e o MC
   (seção 7.1) explica e lista as duas aproximações por caso. Nenhum número mudou; a hidráulica
   desses casos continua avaliada.
2. **Mensagem do template comum.** "Equações do método (nenhuma foi avaliada: o TAG está aguardando
   entrada)" aparecia em **oito MC de TAGs dimensionados** (P-002, P-003, TO-001, TO-002, B-001,
   B-002, B-003; antes desta nota também no P-001). O ramo dependia da falta de forma com
   substituição numérica (que esses métodos não declaram), não do estado do TAG. Defeito
   anterior às notas 45/46. Agora a abertura da metodologia segue o estado (dimensionado,
   inviável, inativo, aguardando). Na mesma linha, a identificação dos MC de P-002/P-003 dizia
   "Preenchimento: automático (balanço preliminar…)"; agora diz "estado operacional após o rating
   do P-001". O gate passou a reprovar, em qualquer TAG não pendente, a frase de "aguardando
   entrada" na metodologia.

Verificação: JSON dos outros dez TAGs e `planta.csv` idênticos à rodada anterior; no
`P-001_operacao.csv` mudam só as colunas `convergencia` e `termico`; gate aprovado; 26 testes do
P-001 e 971 de `tests/pfd`, arquitetura, balanço, memoriais, terminal e CLI passam, com as mesmas
9 falhas preexistentes listadas abaixo.

## Decisão necessária (não tomada aqui)

**Comprimento do tubo do P-001.** O domínio de busca 6–9 m (nota 43) e o `l_tubo_max` = 6 m do
método divergem, e nada no repositório confirma qual é o limite do projeto. Opções: (a) confirmar
6 m (revisar `l_tubo_max` do P-001) — a busca descartará 7,5 e 9 m e a geometria mudará; (b)
informar o comprimento máximo admitido (ex.: 9 m) com a justificativa de fornecimento — o
critério passa a `atende`. Até a decisão, o P-001 sai como `decisao_pendente`.

## Limitações remanescentes

- Perda de carga sem limite vigente (BOT e acervo): a verificação hidráulica do P-001 é
  incompleta por construção; a do casco é só estimativa indicativa; na transição
  (2300 < Re < 4000) não há fator de atrito declarado.
- ρ do óleo pela API na condição padrão, sem correção por T (a T média entra só na fase aquosa).
- Propriedades congeladas na T média preliminar durante o rating (nota 44); k do óleo proposto.
- O rating (bisseção) não emite `CalcTrace` próprio: os números vêm de `OperacaoP001` e do
  segundo passe do balanço, que emite (`aplicar_rating_termico`).
- A busca não aplica velocidade nem película como admissibilidade (nota 45).
- Falhas anteriores a esta intervenção, inalteradas (confirmadas rodando os mesmos testes contra
  a cópia do `src` de antes desta intervenção):
  - `test_nenhum_modulo_sem_consumidor` (`sizing/bombas_paralelo.py`) e três testes de
    `test_pelicula_planta.py` (regimes de P-002/P-003 com expectativas do balanço anterior ao
    rating, `50ca9ac`) — já registradas na nota 45;
  - **não registradas na nota 45**: `test_alarmes.py::test_p001_um_passe_troca_o_dominio_de_f_pela_area`,
    `test_alarmes.py::test_alarme_no_memorial_e_registro_sem_execucao` e três de `test_otimizacao.py`
    (`criterio_1`, `a_violacao_soma_so_os_tags_que_violam`, `criterio_4`). Causa: desde a nota 45 o
    P-001 integrado não tem envelope DESIGN (`rt.resultado is None`); o alarme F13 e o objetivo de
    área da otimização F15 (`pfd/otimizacao._objetivo`, linha 218) ainda leem `rt.resultado`.
    Corrigir exige decidir o que esses estudos devem ler da geometria instalada (área em operação
    ou instalada; alarme "aberto" ou fechado pelo rating) — fora do escopo desta intervenção.
    **Resolvido na nota 47**, que também refaz a origem: todas estas falhas (e as de película)
    nascem em `c3ad341`, não em `50ca9ac`.
