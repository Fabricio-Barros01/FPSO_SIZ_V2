# F11 — diagnóstico inicial e proposta documental

Data: 2026-09-26. **Estado: preparação; formato aguardando confirmação.**
Não é entrega da F11. Nenhum código de produção, TOML de engenharia, teste, caso-ouro
ou snapshot foi alterado. Os números abaixo são resultados do código existente.

## Fase selecionada e diferença de escopo

Leitura integral de `SPRINTS.md` (929 linhas no estado inicial), `AGENTS.md` e
`CLAUDE.md`: a única fase selecionada é **F11 — MC por equipamento/TAG**.
O backlog ainda registra a implementação como não autorizada. O pedido de execução
autoriza a descoberta e a preparação; esta proposta torna a próxima confirmação concreta.
O portão do pedido atual, seção 2, é: **“Casos-ouro, fixtures de regressão e decisões
de formato documental são portões: apresente os valores ou o modelo calculado e
aguarde minha confirmação antes de fixá-los.”**

Diferenças frente ao pedido anexado:

- F10x, F11b, F13, F14 e F15 não constam do backlog atual. Não foram inseridas nem iniciadas.
- A ordem registrada segue F11 → F8 (Pinch) → F9 (Song), com F12 de distribuição.
- `thermo` e `chemicals` já entraram na F10a; suas versões instaladas são 0.6.1 e 1.5.2.
  A F11 não exige flash novo nem dependências novas de física.
- O backlog pede A4/SENAI por TAG, mantendo o memorial do balanço e sua paridade.
  Os 16 anexos individuais por caso pertencem à F11b do pedido, fora desta execução.
- Os identificadores operacionais existentes são SG-001, V-001/002 etc. A proposta de
  identificação documental usa `LL-SEN-SEP-DDD-NN-0`, sem renomear a topologia.

## Estado inicial e preservação

| Item | Registro |
|---|---|
| Branch inicial | `main` |
| Commit inicial | `73f7ca3a06f1f4d70b2c409b5fd8972a45cc700a` |
| Alterações rastreadas iniciais | Nenhuma |
| Arquivos preexistentes não rastreados | `design_cases_bot.json`, `skills-lock.json` |
| Branch desta preparação | `fases/f11`, criado a partir do commit inicial |
| Commit da fase | Nenhum: F11 incompleta, aguardando portão documental |
| Integração | Não realizada; depende de autorização explícita, usando `--ff-only` |

Os SHA-256 dos dois arquivos não rastreados e de todas as fixtures Julia foram
registrados antes dos comandos e conferidos depois: preservados. O repositório Julia
tem alterações preexistentes e foi apenas lido. O teste Julia executou um `git archive`
de `ab58fc631749aa81fdf7db566aa14a0cecd777c4` em diretório temporário.

| Commit existente | Conteúdo relevante |
|---|---|
| `73f7ca3` | Organização das skills e do contrato |
| `9eeb5b2` | Cargas por TAG e eficiência nula nos casos sem água |
| `3a36f8f` | P-43 e modo de paridade do FWKO |

## Descoberta de skills, instruções e dados

Foram procuradas instruções na árvore do projeto e nos diretórios ancestrais;
`/home/fabricio/.claude/CLAUDE.md` também foi lido (somente o gatilho `/graphify`, inaplicável).
Acervos de skills encontrados: `.agents/skills/`, `.claude/skills/`,
`/home/fabricio/.agents/skills/`, `/home/fabricio/.codex/skills/`,
`/home/fabricio/.claude/skills/` e o marketplace
`/home/fabricio/.claude/plugins/marketplaces/claude-code-skills/`, inclusive diretórios
`claude-skills` em `.hermes/skills/` e `.vibe/skills/`.

Foi lida a skill pertinente [code-reviewer](../../.agents/skills/code-reviewer/SKILL.md)
e seu checklist. A revisão adotou as invariantes concretas do projeto; nenhum script
de skill foi executado. As demais skills locais são para plugins Claude Code e não
foram aplicadas ao dimensionamento ou à geração de MC.

Fontes documentais consultadas: `docs/validacao/03-memorial-balanco.md`,
`09-pfd.md`, `10-fluxo-tag.md`, `12-eficiencia-fwko.md`; histórico F10v/F10w completo no
backlog; templates SENAI atuais; `src/memorial_specs/` do Julia (somente leitura).

**`pendencias_propostas.toml` ausente** no repositório, nos anexos acessíveis em
`/home/fabricio/.codex/attachments/` e na árvore de `Code_TCC/`. Nenhum valor do pedido
foi presumido como dado confirmado. A ausência impede executar aquela incorporação
da F10x; não impede a F11 de emitir relatórios de pendências.

### TOMLs confirmados

Existem 45 TOMLs em `src/fpso_siz/config/`. Inventário completo da execução:
[`tomls-configuracao.txt`](/tmp/fpso-f11-diagnostico-qmt7dhqm/tomls-configuracao.txt).

| Conteúdo | Caminhos relativos ao repositório |
|---|---|
| Premissas do balanço | `src/fpso_siz/config/premissas.toml`, `constantes.toml`, `pocos.toml`, `composicao_bot.toml` |
| Propriedades | `src/fpso_siz/config/fluidos.toml` |
| Catálogo de dimensionamento/PFD | `src/fpso_siz/config/pfd/pfd.toml`, `src/fpso_siz/config/pfd/metodos.toml` |
| TAGs de vasos | `src/fpso_siz/config/pfd/tags/sg_001.toml`, `v_001.toml`, `v_002.toml`, `to_001.toml`, `to_002.toml` |
| TAGs de trocadores | `src/fpso_siz/config/pfd/tags/p_001.toml`, `p_002.toml`, `p_003.toml` |
| TAGs de bombas | `src/fpso_siz/config/pfd/tags/b_001.toml`, `b_002.toml`, `b_003.toml` |
| Métodos e constantes | `src/fpso_siz/config/equipment/{comum,separator,knockout,treater,pump,exchanger}/*.toml` |
| Casos de exemplo e corrente | `src/fpso_siz/config/exemplos/*.toml`, `src/fpso_siz/config/stream.toml` |
| Metadados documentais existentes | `src/fpso_siz/config/memorial_balanco.toml` |
| Textos/rastros do memorial | `src/fpso_siz/output/latex/balanco/{premissas_memorial,rastro_memorial,envelopes_memorial,criticos_memorial}.toml` |

Os nomes abreviados em cada linha pertencem ao mesmo diretório do primeiro arquivo.
Os TOMLs de `tests/fixtures/` são oráculos ou ajustes sintéticos; não são premissas
aprovadas de projeto. O esquema legado não tem uniformemente os cinco campos de fonte
do pedido atual; a preparação não migrou dados nem atribuiu fontes retrospectivamente.

## Verificações iniciais executadas

Ambiente: Python 3.13.15, pytest 9.1.1, uv 0.11.21, Julia 1.12.6,
latexmk 4.88, MiKTeX-pdfTeX 4.23 (MiKTeX 25.12).
Foi usado o `LD_LIBRARY_PATH` declarado no perfil do flake em `.direnv/`, sem executar
o perfil inteiro. Cache uv, cobertura e depot gravável Julia ficaram em `/tmp`.
`--offline --no-sync` reutilizou a instalação existente, sem baixar ou alterar dependências.

| Comando, após `uv run --offline --no-sync` | Resultado |
|---|---|
| `pytest --cov=fpso_siz --cov-fail-under=90 --cov-report=term --cov-report=json:/tmp/fpso-f11-diagnostico-qmt7dhqm/cobertura.json` | **814 aprovados**, 3 marcadores excluídos, 111,56 s |
| `pytest -m latex -vv --basetemp=/tmp/fpso-f11-diagnostico-qmt7dhqm/latex-test` | **2 aprovados**: `original` e `senai`, 32,80 s |
| `pytest -m julia -vv` | **1 aprovado**: regeneração idêntica, 24,77 s |
| `python tools/comparar_memorial.py` | **Falhou**, saída 1: comparação parcial desatualizada, descrita abaixo |
| `fpso-siz pfd --casos tests/fixtures/python_ref/design_cases_bot.json --saida /tmp/fpso-f11-diagnostico-qmt7dhqm/pfd` | Saída **1 esperada**, com exportação dos 11 TAGs; há lacunas/inviabilidade |

Total: **817 testes aprovados, nenhum reprovado ou pulado** nas três rodadas.
Cobertura global com ramos: **96,9548%**; cobertura global de linhas: **97,8874%**.
Núcleo, excluindo `output/` e `cli.py`: **98,6870% de linhas** (3758/3808),
**97,9832% com ramos**. O limiar de 90% foi satisfeito.

Não houve comando de validação indisponível. `pdftotext`/`pdftoppm` não estão no PATH,
mas foram localizados em `/nix/store/*poppler-utils*/bin/` para revisar as prévias.
MiKTeX avisou que seu log em `~/.miktex` é somente leitura no sandbox; as compilações
em `/tmp` terminaram com sucesso. A criação do branch exigiu execução autorizada fora
da restrição de escrita em `.git`; não houve rejeição de aprovação automática.

Evidências da rodada: [suíte](/tmp/fpso-f11-diagnostico-qmt7dhqm/suite.log),
[LaTeX](/tmp/fpso-f11-diagnostico-qmt7dhqm/latex.log),
[Julia](/tmp/fpso-f11-diagnostico-qmt7dhqm/julia.log),
[cobertura](/tmp/fpso-f11-diagnostico-qmt7dhqm/cobertura.json),
[comparador](/tmp/fpso-f11-diagnostico-qmt7dhqm/paridade-memorial.log).
Esses artefatos temporários não são fixtures.

### Divergência do comparador auxiliar

`tools/comparar_memorial.py:17` resolve o balanço na regra padrão de eficiência e
`:19` chama `preparar` sem layout. Compara então templates parciais ao oráculo original,
sem a seleção de regra/layout e sem o filtro de premissas usado por `gerar`.
O primeiro desvio ocorre na P-24 do template `07_premissas`.

O teste `test_layout_original_identico_ao_script` passou e compara o documento completo
byte a byte. Portanto, o comparador auxiliar falhou; isso não demonstra regressão do
documento efetivamente emitido por `gerar(..., layout="original")`.
Recomendação para a F11: alinhar o utilitário ao caminho público de geração e manter
os testes de referência intactos. O utilitário não foi corrigido antes do portão.

## Estados e dimensões calculados dos 11 TAGs

Regra `eficiencia`, BOT da fixture com SHA-256
`ca3dfe559b32926c9d9ca4d9e75e2cec711f00f7fdfd2247242bbf3a754dac60`, sem ajustes.
Todos os valores vêm dos JSONs exportados pelo comando acima. Nenhum TAG mudou nesta
preparação; “dimensionado” não significa que as recomendações foram confirmadas.

| TAG | Estado | Casos ativos | d (m) | Leff (m) | Lss (m) | SR | Pendência/governante |
|---|---|---:|---:|---:|---:|---:|---|
| B-001 | Aguardando entrada | 16 | — | — | — | — | Desnível, sucção, linhas, perdas, NPSHr e margem |
| B-002 | Aguardando entrada | 11 | — | — | — | — | Mesmas lacunas hidráulicas |
| B-003 | Aguardando entrada | 11 | — | — | — | — | Mesmas lacunas hidráulicas |
| P-001 | Aguardando entrada | 10 | — | — | — | — | Condutividades dos fluidos/parede e incrustações |
| P-002 | Aguardando entrada | 10 | — | — | — | — | Condutividade do processo/parede, incrustações, temperaturas da utilidade |
| P-003 | Aguardando entrada | 16 | — | — | — | — | Mesmas categorias de lacunas térmicas |
| SG-001 | Inviável | 16 | — | — | — | — | Teto de decantação **3,611952 m**, caso 2; não é diâmetro selecionado |
| TO-001 | Aguardando entrada | 16 | — | — | — | — | Gotícula após coalescência nos casos 2–3 e 8–16 |
| TO-002 | Aguardando entrada | 16 | — | — | — | — | Mesma lacuna de coalescência |
| V-001 | Dimensionado, revisão pendente | 16 | 4,700 | 11,743162 | 16,443162 | 3,498545 | Capacidade de líquido, BOT 03 |
| V-002 | Dimensionado, revisão pendente | 16 | 4,700 | 11,956842 | 16,656842 | 3,544009 | Capacidade de líquido, BOT 03 |

Volumes de casco: V-001 = 285,279747 m³; V-002 = 288,986970 m³.
B-002/003 inativos nos casos 1 e 4–7; P-001/002 inativos nos casos 10 e 12–16.
O diagnóstico de SG-001 e a inconsistência geométrica dos casos 2 e 3 permanecem
conforme a F10w. Nenhuma alternativa física foi selecionada.

## Modelo documental apresentado para confirmação

Prévia parcial A4/SENAI, com duas páginas por exemplo: folha de rosto/índice de revisões
e identificação com conteúdo calculado. São **minutas**, não memoriais completos:

- [V-001 — MC dimensionado com revisão pendente](/tmp/fpso-f11-diagnostico-qmt7dhqm/minutas/V-001/main.pdf).
- [SG-001 — relatório de diagnóstico](/tmp/fpso-f11-diagnostico-qmt7dhqm/minutas/SG-001/main.pdf).

As prévias reaproveitam o preâmbulo e a folha de rosto SENAI instalados, com campos
de responsáveis sem assinatura. Os templates de produção permanecem intactos.
A data, revisão 0 e códigos
`MC-SEN-SEP-VKO-01-0` / `MC-SEN-SEP-SEP-01-0` são **propostas**, com os responsáveis
sem assinatura. As siglas VKO/SEP vêm das especificações documentais Julia, não de
uma classificação normativa presumida. A numeração deverá ser confirmada na lista
de documentos; não se declara conformidade documental além do formato solicitado.

Conteúdo proposto do MC completo:

1. Folha de rosto e índice de revisões; TAG separado do número documental.
2. Identificação, esquema de correntes, método, modo manual/automático e estados por caso.
3. Entradas por `ParameterSpec`, origem/fonte, revisão e valores anteriores às sobrescritas.
4. Propriedades, equações, hipóteses, versões e avisos de validade.
5. Equação → substituição numérica com unidades → resultado, proveniente do rastro.
6. Envelope, caso governante, folgas e casos inativos; ou diagnóstico sem dimensões fictícias.
7. Lacunas, recomendações não revisadas, referências e carimbo de rastreio.

Carimbo proposto: commit, condição de alterações locais, versão do software/propriedades,
hash dos casos e configuração, regra FWKO efetiva, premissas divergentes, ajustes por TAG
e data controlada. Em modo manual, registrar a origem manual; não resolver balanço para
fabricar proveniência. P-42 e P-43 aparecem quando aplicáveis, inclusive
`exigido_acima`; entradas `valor_usual`, se presentes, recebem literalmente a indicação
**“valor usual — sem fonte rastreável”**. P-43 continua “premissa do autor”.

Exemplo real da prévia V-001: `SR = Lss/d = 16,443162 m / 4,700000 m = 3,498545`.
Fonte: Stewart & Arnold (2008), §3.8.5; resultado do rastro de seleção do BOT 03.
Arredondamento apenas de apresentação, sem criar fixture a partir da prévia.

**Decisão única pendente:** confirmar este modelo de MC/diagnóstico por TAG, incluindo
folha de rosto e índice de revisões, para liberar a implementação da F11.
Opção recomendada: A4/SENAI, um documento por TAG, geração individual ou em lote pelo
mesmo gerador; conserva o pipeline da F4 e a unidade de trabalho da F10c.
Alternativa: solicitar ajustes específicos nesta minuta antes de fixar o formato.
A aprovação não autoriza a fase seguinte, novos valores de engenharia ou snapshots
numéricos ainda não apresentados.

## Recomendações de arquitetura para a implementação

- `src/fpso_siz/pfd/equipamento.py:35` e `:57`: consumir `ResultadoTAG` e `Contexto`
  já calculados. Não chamar outro motor no gerador ou no template. Guardar a regra
  efetiva do balanço recebido, em vez de inferi-la da configuração global atual.
- `src/fpso_siz/core/trace.py:50`: `TraceEntry` tem fórmula, resultado e unidade, mas
  não operandos com suas unidades. Capturá-los junto à avaliação no núcleo para
  suportar a substituição. Preservar a projeção legada dos rastros/oráculos; não
  reexecutar fórmulas na camada documental nem alterar testes para absorver regressão.
- `src/fpso_siz/output/pfd.py:43`: compartilhar a preparação dos dados de saída
  por TAG. Preservar a origem, revisões e limitações já exportadas em JSON/CSV.
- `src/fpso_siz/core/registro.py:9`: ligar metadados documentais aos métodos registrados;
  o gerador percorre descritores. Um método novo não introduz condicionais por nome na UI.
- `src/fpso_siz/output/latex/compilacao.py:15`: reutilizar o compilador e o ambiente Jinja
  existentes; concentrar geração por TAG em um módulo documental, sem fragmentar a física.
- `src/fpso_siz/config/interativo.toml:36` e `:52`: acrescentar a ação de MC por registro
  de menu; CLI oferece `--mc [--pdf]` com `--saida`, conforme o backlog.
- `tools/comparar_memorial.py:17`: corrigir o contexto da comparação parcial como
  descrito acima, preservando o documento completo original e o oráculo Julia.

Aceite ainda por executar após confirmação: MC/diagnóstico dos 11 TAGs e dos métodos
registrados; manual/automático; igualdade dos valores terminal/JSON/CSV/MC; bijeção do
rastro; geração individual/lote sobre o mesmo resultado; LaTeX/dados determinísticos;
compilação A4/SENAI; suíte, cobertura, arquitetura e paridades preservadas. Igualdade
binária de PDF só poderá ser prometida após fixar toolchain e metadados.

## Pendências preservadas

P-43 é premissa do autor sem fonte bibliográfica; as recomendações/defaults continuam
pendentes de revisão. SG-001 continua inviável. A F11 poderá documentar as lacunas de
oito TAGs sem preenchê-las. Não foram calculadas as correlações da F10x nem fixados
formatos da F11b, alternativas da F13, caracterização/flash da F14 ou otimização F15.
Nenhum novo número de engenharia sem fonte foi incorporado ao software.
