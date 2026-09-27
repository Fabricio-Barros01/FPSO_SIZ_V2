# 32 — Gate de sanidade do dimensionamento e dos memoriais

Ferramenta: `tools/auditar_saida_pfd.py`. Roda o dimensionamento **real** dos 11 TAGs pelo
mesmo fluxo do usuário (`pfd/planta.py` → `pfd/equipamento.py` → `core/motor.py`), grava os
mesmos artefatos que `fpso-siz pfd --mc` grava, em `saida/_auditoria_fase/` (pasta temporária,
fora do git), e confere se o que saiu tem significado numérico. Não há um segundo caminho de
dimensionamento: a auditoria só lê o que o fluxo de produção produziu.

```
uv run python tools/auditar_saida_pfd.py            # 0 = aprovada, 1 = erro de aceite, 2 = a auditoria não rodou
```

## O que é conferido

**Três níveis, antes de qualquer formatação.** `SizingResult`/`EnvelopeResult` (memória) →
`<TAG>.json` (`output/dimensionamento.py`) → `<número>.json` (`pfd/memorial.py`). São
comparados por igualdade exata de float: x, y, todos os derivados, cada campo do cartão pelo
rótulo, e por caso o x isolado e a folga. Diferença além do arredondamento de apresentação é
`ERRO_OUTPUT`; número finito no núcleo que o MC não apresenta, também.

**Erros de aceite num TAG dimensionado:** resultado principal (`ResultField.highlight`) não
finito; qualquer campo do cartão não finito sem declaração do método; grandeza negativa onde a
física não admite (a regra é pela **unidade** do campo — `mm`, `m²`, `m³`, `m/s`, `W/m²K`, `K`
—, não pelo nome: a auditoria não cita grandeza); x ou y não positivos; TAG que se diz
dimensionado com entrada faltando; TAG aguardando entrada que não diz qual entrada falta.

**TAG inviável** não precisa de dimensão final: precisa de mensagem e de **diagnóstico
numérico**. O gate lista qual diagnóstico satisfez a exigência (teto, menor abscissa na banda,
feixe mais próximo de atender, séries, variantes do alarme).

**Travessão precisa de justificativa.** Cada ausência do documento do MC é classificada em
`NAO_APLICAVEL`, `LACUNA`, `INVIAVEL`, `ERRO_NUMERICO` ou `ERRO_OUTPUT`, e a classificação só
vale com uma justificativa **positiva vinda do próprio resultado** — o mecanismo que o método
declara, o regime que a correlação registrou, a inviabilidade do caso isolado, a equação que
não declara conversão de constante de campo. Sem justificativa: `ERRO_OUTPUT`, e a auditoria
reprova.

## Primeira rodada: o defeito do P-002

**Sintoma.** O P-002 dimensiona (1605 tubos por passe, L = 5,993 m) e mesmo assim o MC
mostra travessão: a coluna **critério governante** da tabela "demais casos" saía vazia em
**8 dos 10 casos** ativos. No P-003, em **15 dos 16**.

**Onde nasce.** Não no motor, não em `result_fields`, não no template: em `pfd/memorial.py`.
A tabela procurava a linha da varredura **individual do caso** na abscissa escolhida pelo
**envelope**, por igualdade de float (`_linha_em(pc.sweep, x)`), e lia dali o governante.

**Por que falha.** A grade de cada caso é `n_min:n_step:n_max` com os parâmetros **daquele
caso** e a do envelope é a da união (`n_min` mínimo, `n_step` mínimo). Nos trocadores o
`n_min` é o mínimo hidráulico de cada caso, e ele é diferente em cada um: mesmo passo,
origens diferentes, grades desalinhadas em fase.

| TAG | grade do envelope | grade do caso governante | x escolhido | está na grade do caso? |
|---|---|---|--:|:--:|
| P-002 | 25 : 5 : 2159 | BOT 02 → 668 : 5 : 2006 | 1605 | não |
| P-003 | 36 : 5 : 22574 | BOT 07 → 7524 : 5 : 22574 | 7526 | não |

Nos vasos e nas bombas as grades coincidem, e por isso o defeito só aparecia nos dois
trocadores. O template (`mc_tag.tex.j2:254`) faz `(l.governante or '--')`: o dado já chegava
vazio, o template só imprimiu o que recebeu.

**Correção, na origem.** O critério governante de um caso em x é `governing_of(x, cons)` — uma
função de x e das restrições congeladas do caso, que **não depende de grade nenhuma**. O MC
passou a chamá-la sobre as restrições que `pfd/memorial.restricoes()` já preparava, em vez de
procurar uma linha. Mesmo tratamento para as capacidades envelopadas do diagrama
(`pfd/memorial.capacidades()`), que tinham a mesma origem e o mesmo risco latente — e de
quebra deixaram de ser uma busca linear por linha da varredura.

**Nada mudou de número.** Onde a busca antiga funcionava, o rótulo é idêntico — é o que o
teste `test_governante_bate_com_a_varredura_individual_onde_a_grade_contem_o_x` prova, caso a
caso, em quatro métodos. A correção só passou a responder onde antes devolvia vazio.

**Nota:** o desalinhamento das grades continua existindo (registrado desde a R1). Ele não é
mais um defeito de saída, mas segue sendo uma escolha de discretização a revisar; o MC agora
descreve o mesmo ponto para todos os casos, que é o que o envelope de fato dimensiona.

## Segundo achado: campo vazio sem declaração (V-001, V-002)

O cartão dos vasos tem **Teto de decantação**, e num vaso bifásico esse critério não existe:
o campo saía NaN, virava `null` no JSON e sumia do MC por um filtro `isfinite` sem motivo
declarado. O gate reprovou — corretamente: era ausência sem justificativa.

A forma do cartão é a do Julia (oráculo `tests/fixtures/julia/`), então **o campo não foi
removido**. O que entrou foi a declaração: o contrato ganhou o hook
`MetodoDimensionamento.campos_nao_aplicaveis(r)` (extensão do V2, padrão vazio), `MetodoVaso`
o implementa devolvendo `{"Teto de decantação": "sem teto de decantação"}` quando não há teto
finito, e `pfd/memorial.resultados()` agora omite do MC **só** o que o método declarou — o que
faltar sem declaração aparece e o gate cobra. O documento do MC passou a trazer a seção
`nao_aplicaveis` com campo e motivo. Invariante 5, aplicada ao dimensionamento: ausência é
estado declarado, não campo vazio.

## Resultado da rodada (16 casos, propostas do pacote, óleo vivo)

| TAG | estado | principais | problemas |
|---|---|---|---|
| B-001 | dimensionado | DN 600; H = 75,05 m; 311,5 kW | nenhum |
| B-002 | dimensionado | DN 250; H = 183,4 m; 143,3 kW | nenhum |
| B-003 | dimensionado | DN 125; H = 252,2 m; 45,56 kW | nenhum |
| P-001 | **inviável** | — | arranjo 1-2 não fecha: F fora do domínio da Fig. 4.3 (BOT 01). Diagnóstico numérico presente (perfil T × Q e variantes do alarme) |
| P-002 | dimensionado | 1605 tubos/passe; L = 5,993 m | **governante vazio em 8/10 casos — corrigido** |
| P-003 | dimensionado | 7526 tubos/passe; L = 4,907 m | **governante vazio em 15/16 casos — corrigido** |
| SG-001 | dimensionado | d = 6050 mm | nenhum |
| TO-001 | dimensionado | d = 5550 mm | nenhum |
| TO-002 | dimensionado | d = 5550 mm | nenhum |
| V-001 | dimensionado | d = 4700 mm | **teto de decantação vazio sem declaração — corrigido** |
| V-002 | dimensionado | d = 4700 mm | **teto de decantação vazio sem declaração — corrigido** |

Depois das duas correções: **auditoria aprovada**, 0 `ERRO_NUMERICO`, 0 `ERRO_OUTPUT`,
316 `NAO_APLICAVEL` e 22 `INVIAVEL`, todas com justificativa declarada.

| ausência | vezes | justificativa |
|---|--:|---|
| teto por caso (tabela e série) | 222 | o caso não impõe teto (mecanismo declarado pelo método) |
| conversão de constante de campo | 25 | a equação não declara conversão |
| `resultados[].valor` do P-001 | 16 | inviável: o MC traz diagnóstico no lugar das dimensões |
| rastro da equação de seleção | 12 | lê o ponto escolhido do envelope, não o rastro de um caso |
| peso de transição | 21 | regime turbulento ou laminar: não há interpolação a ponderar |
| colunas da decantação (SG-001) | 10 | «não aplicável — sem fase aquosa» (P-42) |
| diagnóstico do envelope viável | 10 | não há inviabilidade a diagnosticar |
| banda / seleção | 12 | o método não declara o hook |
| x isolado | 2 | o caso não tem solução nem isolado |
| teto de decantação (V-001/V-002) | 2 | o método declara «sem teto de decantação» |

## Os três níveis de resultado de cada método

Derivados dos contratos que já existem — nada é redeclarado. `ResultField.highlight` marca o
principal; `config/memorial_tag.toml` declara o que o MC é obrigado a apresentar; o resto é
diagnóstico.

| método | principal (dimensiona o equipamento) | obrigatório de memorial | diagnóstico / opcional |
|---|---|---|---|
| `moran` (B-001/2/3) | DN; carga do sistema H; potência nominal requerida | 11 campos do cartão | 11 derivados; 3 gráficos |
| `saari_lmtd` (P-001/2/3) | tubos por passe; comprimento do tubo L | 15 campos do cartão | 28 derivados; 3 gráficos |
| `stewart_arnold` (SG-001) | diâmetro d | 7 campos + 15 equações + 4 colunas por caso | 3 derivados; 2 gráficos |
| `stewart_arnold_2f` (V-001/2) | diâmetro d | 7 campos + 10 equações + 5 colunas por caso | 3 derivados; 2 gráficos |
| `arnold_electrostatic` (TO-001/2) | diâmetro d | 7 campos do cartão | 3 derivados; 2 gráficos |

Regra de aceite por nível: **principal** tem de ser finito num TAG dimensionado; **memorial**
tem de bater com o núcleo número a número; **diagnóstico** pode faltar, desde que a falta seja
justificada.

## Testes

`tests/pfd/test_auditoria_saida.py` (21 testes). Além de rodar o gate sobre a planta:

- o caso desalinhado **existe** (senão a regressão seria vazia) e todo caso do MC do P-002 e do
  P-003 tem critério governante;
- onde a grade individual contém o x do envelope, o novo caminho devolve **o mesmo** rótulo da
  varredura individual, e `capacidades()` devolve o mesmo dicionário;
- o defeito reintroduzido à força (governante forçado a `None`) é pego como `ERRO_OUTPUT`;
  resultado principal forçado a NaN é pego como `ERRO_NUMERICO`;
- códigos de saída 0 / 1 / 2.

## Pendências

- A não aplicabilidade de um critério a um **caso** ainda é declarada por texto (o rótulo do
  mecanismo começando por «não aplicável»); a de um **campo do cartão** já é hook. Unificar as
  duas num hook do contrato.
- Grades desalinhadas entre caso e envelope: continua em aberto (R1).
- O gate confere o JSON do MC, que é o contrato do `.tex` (o template só formata); a
  conferência PDF × JSON continua sendo do teste marcado `latex`.
