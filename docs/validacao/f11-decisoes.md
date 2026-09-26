# F11 / F11b — decisões tomadas sem confirmação (sessão autônoma de 2026-09-26)

O pedido da sessão autorizou a execução autônoma da F11 completa e da F11b, com o registro
aqui de cada decisão que normalmente seria perguntada. Cada item traz as opções
consideradas e o motivo da escolha. Nenhuma decisão muda física ou resultado: a paridade
com o oráculo do balanço e com as fixtures do Julia segue intacta.

## Retomada

| # | Decisão | Opções | Escolha e motivo |
|---|---|---|---|
| R1 | WIP `59e0bf1` do agente anterior | manter; reimplementar do zero; reaproveitar e reorganizar | **Reaproveitar e reorganizar.** A suíte passava no WIP (809 + 5 pulados), e a mudança em `core/trace.py` era aditiva (novo atributo fora de `entries`), logo a projeção do rastro usada pelo oráculo do Julia não mudou. Mas o WIP tinha um dicionário `documentacao` ad hoc, um TOML de memorial só do knockout e conversões com literais soltos. Substituído no primeiro commit (`git reset --soft 73f7ca3`) por `Rastro.operandos`/`Rastro.iteracoes` genéricos, `config/memorial_tag.toml` para todos os métodos e conversões nomeadas em `core/unidades.py`. |
| R2 | `docs/validacao/f11-minutas/gerar_minuta.py` do WIP | manter; remover | **Removido.** Dependia de arquivos temporários (`inicial.json`) que não estão no repositório; o gerador de produção o substitui. |
| R3 | `tools/comparar_memorial.py` | corrigir; remover | **Corrigido** (correção do WIP conferida): usa a regra de referência, o layout `original` e o filtro de premissas de `gerar`, e sai com 1 se algum template divergir. Roda e responde `IDÊNTICO`. |

## Ambiente de verificação (nuvem)

| # | Item | Situação |
|---|---|---|
| A1 | TeX Live | Não havia; instalado via apt (TeX Live 2023, `latexmk` 4.83, pgfplots). Os dois memoriais do balanço compilam (`-m latex`). O projeto usa MiKTeX no NixOS; os templates novos só usam pacotes da distribuição padrão. |
| A2 | Julia / `../FPSO_Siz` | O repositório Julia não está acessível nesta sessão (não aparece em `list_repos`). **O teste `-m julia` (regeneração das fixtures) não rodou.** A paridade com as fixtures já exportadas (`tests/sizing/test_paridade_julia.py`, bit a bit/≤1e-13) roda na suíte normal e passa. |
| A3 | `references/` (acervo local) | Ausente na nuvem: 5 testes que dependem do script original ou do snapshot Julia foram pulados (como previsto no código). O memorial `original` segue idêntico byte a byte a `tests/fixtures/python_ref/main_ref.tex` (teste na suíte e `comparar_memorial.py`). As páginas citadas das formas de campo de S&A vêm do TOML do WIP (lidas pelo agente anterior com o acervo); não foram reconferidas aqui. |
| A4 | Cobertura de partida | 96,85 % global (ramos) e 98,54 % no núcleo, com os 5 testes pulados. A referência anterior (96,95 %/98,69 %) inclui os testes do acervo. |

## Formato do MC por TAG

| # | Decisão | Opções | Escolha e motivo |
|---|---|---|---|
| D1 | Numeração | ordem alfabética; ordem de exportação; sequência de processo | **Sequência de processo** do diagrama de blocos, igual à seção 11 do memorial do balanço: SG-001 001, P-001 002, P-002 003, V-001 004, TO-001 005, B-002 006, V-002 007, TO-002 008, B-003 009, B-001 010, P-003 011. Tabela fixa em `config/memorial_tag.toml [numeracao]`; a exportação só consulta a tabela. |
| D2 | Código documental | `MC-SEN-SEP-<sigla do método>-NN-0` (minuta anterior); `MC-SEN-SEP-EQP-NNN-0` | **`MC-SEN-SEP-EQP-NNN-0`**, Rev. 0 própria por MC. EQP (equipamento) distingue do COO do balanço; a sequência é a de D1. Marcado "numeração a confirmar na LI-SEN-SEP-COO-01". |
| D3 | Layout | SENAI; original; ambos | **SENAI** (A4, folha de rosto e índice de revisões no padrão das minutas), reaproveitando o preâmbulo do memorial do balanço por um gancho `preambulo_extra` que não altera os bytes do balanço. |
| D4 | Onde se decide o conteúdo | código por método; TOML por método | **TOML por método** (`[metodos.<id>]`: objetivo, escopo, referências, hipóteses, equações com placeholders `@operando@`, colunas da tabela de casos, gráficos). O gerador é genérico: não há código por TAG nem por método na saída. |
| D5 | Substituição numérica | recalcular no template; operandos capturados | **Operandos capturados** na avaliação (`Rastro.anotar`) e o histórico da iteração de C_D (`Rastro.iteracoes`). O template só formata. Parcelas de Lss, bordas da banda e capacidades no d escolhido vêm de hooks do método (`selecao_memorial`, `bordas_banda`), com as mesmas expressões de `lss_from`/`per_constraint`. |
| D6 | Precisão exibida | casas fixas; 4 algarismos significativos | **4 algarismos significativos** (`formatacao.sig`), decimal entre 10⁻² e 10⁴, científica fora; constantes publicadas com `mbn` (exatas). A regra é declarada na identificação e na seção 10. |
| D7 | "SI" das equações de S&A | SI puro (m, Pa, m³/s, s); forma métrica publicada | **Forma métrica publicada** (mm, m, kPa, K, m³/h, min, µm, cP), que é a avaliada no código, ao lado da forma de campo (ft, in, °R, psia, MMscfd, bpd) e da constante de campo convertida por funções exatas (`core/unidades.coef_*_metrico`). O desvio entre a convertida e a publicada é mostrado: V_t +0,75 %, gás −0,86 %, líquido do bifásico −0,081 % (arredondamento próprio do 42.441 publicado), espessura −1,48 %. O cálculo usa sempre o coeficiente publicado (ou o derivado, no trifásico). |
| D8 | Caso do passo a passo | o de maior exigência; o governante do envelope | **Governante do envelope** (V-001: caso 3); no inviável, o caso do teto (SG-001: caso 2). |
| D9 | Diagnóstico do SG-001 | só a mensagem; teto + diâmetro mínimo + gráfico | **Teto (3.612 mm, caso 2) e menor diâmetro da grade com a esbeltez na banda (5.600 mm)**, no diagrama d × Leff e num gráfico de teto por caso. O "diâmetro mínimo" é o menor d do envelope com `admissible` verdadeiro (banda de SR), ignorando o teto. |
| D10 | Gráficos | TikZ com números no `.tex`; pgfplots lendo CSV | **pgfplots lendo CSV** gravados pelo mesmo comando (`<número>_diagrama.csv`, `_ponto.csv`, `_teto.csv`, `_minimo.csv`, `_casos.csv`). Trocadores e bombas não têm os gráficos de perfil T × Q, resistências e NPSH nesta entrega: todos aguardam entrada e não há dados (ver pendências). |
| D11 | Entradas no MC | uma linha por caso; agrupado | **Comuns** (um valor para todos os casos ativos) numa tabela e **variáveis** numa matriz caso × entrada, com a legenda de origem e fonte por coluna. |
| D12 | Texto com caracteres especiais | `esc` do balanço; escape completo | **Escape completo** (`formatacao.tx`) no MC por TAG; `esc` fica como está, pela paridade do balanço. Caracteres gregos e símbolos do rastro são mapeados no preâmbulo (`newunicodechar`). |
| D14 | "Interface web" | criar uma; usar o modo interativo | O projeto não tem interface web (núcleo + CLI, CLAUDE.md). A **ação equivalente entrou no modo interativo**: "Gerar memorial de cálculo (MC)" no menu do TAG e "Gerar os memoriais…" no da planta, pelos ids de `interativo.toml`, sem código por TAG. |
| D13 | Data e commit na folha de rosto | fixos; da geração | **Da geração**, ambos parâmetros (`data`, `git`), para que individual × lote e os testes comparem bytes com a data fixada. |

## F11b — memorial do balanço por caso

| # | Decisão | Opções | Escolha e motivo |
|---|---|---|---|
| B1 | Opções da CLI | `--caso` só; reinterpretar `--casos` | **As duas**: `memorial --caso N|lista|todos` e `memorial --casos todos` (o comando pedido para o teste local). `--casos` continua aceitando o arquivo do BOT; `todos` (ou ausente) usa o `design_cases_bot.json` da pasta corrente, como o modo interativo. `--saida` passou a ter padrão (`saida/memorial`). |
| B2 | Layouts | um por vez; os dois | Padrão do memorial por caso: **os dois** (`<saida>/original/MC_CasoNN/` e `<saida>/senai/MC_CasoNN/`); `--layout original|senai` gera um só em `<saida>/MC_CasoNN/`. O memorial completo continua com padrão `original` e não aceita `ambos`. |
| B3 | Regra do FWKO | forçar a de referência no `original` (como o memorial completo); a regra em uso | **A regra em uso** (padrão: eficiência; `--regra-fwko` escolhe), declarada na folha de rosto. O `original` completo continua forçado à regra de referência (paridade byte a byte), o que não se aplica ao anexo por caso, que não tem oráculo. |
| B4 | Número do documento | `MC-SEN-SEP-COO-001-CNN-0`; `MC-SEN-SEP-COO-CNN-0` | **`MC-SEN-SEP-COO-CNN-0`** (anexo do MC-SEN-SEP-COO-001), curto para caber no cabeçalho SENAI; arquivo `MC_CasoNN`. |
| B5 | "—" sem fase aquosa | "--"; "---" | **"---"** (travessão) nas vazões de água produzida/diluição, nas η de água e nos BSW dos casos 1 e 4–7 (P-42), e em η_req/η_A nulos. |
| B6 | Igualdade isolado × lote do PDF | bytes; texto extraído | **`.tex` byte a byte** e **texto do PDF** (`pdftotext`), que ignora a data de criação embutida pelo pdfTeX. |
| B7 | Interface | menu do balanço | Ação "Memorial de cálculo por caso (MC_CasoNN)" no menu do balanço, que itera o registro de casos do arquivo carregado (lista, faixa ou todos) e mostra o comando equivalente. |

## F10x.4–F10x.5 — propostas por padrão e óleo vivo

| # | Decisão | Opções | Escolha e motivo |
|---|---|---|---|
| X1 | Carga das propostas | só com `--propostas`; por padrão | **Por padrão** (decisão do usuário), com `--sem-propostas` para desligar. A origem continua `proposta`, com revisão pendente: o usuário confirma ou edita no interativo. |
| X2 | Viscosidade do óleo | óleo morto do BOT (P-40); óleo vivo por correlação | **Óleo vivo por Beggs & Robinson (1975)**, que é a correlação publicada de uso corrente para µ_o a partir de µ_od e Rs, sobre o µ_od medido do BOT. O Rs vem do próprio balanço. Não há PVT de óleo vivo no BOT nem correlação no acervo ou no ChEDL; a referência fica marcada "a conferir". |
| X3 | Corrente do Rs | a da regra; a saída de líquido | A da regra; **no SG-001, a saída de óleo C-06** (`rs = "C-06"`), porque a entrada leva gás livre. |
| X4 | Rs abaixo da faixa (< 20 scf/STB) | extrapolar; óleo morto | **Óleo morto**, com aviso: extrapolada, a correlação com coeficientes arredondados dá µ_o > µ_od para Rs → 0. É conservador para a decantação. |
| X5 | Paridade | regenerar as fixtures; modo óleo morto | **Modo óleo morto** (`--oleo-morto`, `oleo_vivo=False`) para as fixtures do Julia, a regressão F10b e o estudo do alarme da F13. Nenhuma fixture de oráculo foi regenerada; só os snapshots de tela, que mostram o padrão. |

## Pendências novas (sem correção nesta fase)

| # | Pendência |
|---|---|
| N1 | O rastro do knockout cita "Eq. 3.1" para o agrupamento K, que não é o fator de Souders–Brown; o MC registra isso como hipótese (H-3). Não se alterou o rastro (paridade Julia). |
| N2 | Trocadores (P-001/002/003) e bombas (B-001/002/003) não têm passo a passo nem os gráficos específicos (T × Q, parcelas de U, curva do sistema, NPSH): nenhum desses TAGs tem entrada completa. Com entradas, o MC mostra cartão, critérios, tabela e o gráfico por caso; o passo a passo desses métodos fica para quando houver dados (F10x). |
