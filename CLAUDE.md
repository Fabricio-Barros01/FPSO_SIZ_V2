# FPSO_Siz_V2 — contrato do projeto

Backend Python (biblioteca + CLI) de balanço, termodinâmica, dimensionamento e otimização do
módulo de separação de um FPSO. Estado e backlog: [`SPRINTS.md`](SPRINTS.md), que deve ser lido
primeiro; a arquitetura vigente está em [`docs/arquitetura/arquitetura-alvo.md`](docs/arquitetura/arquitetura-alvo.md).

## Skills instaladas
Fonte e hashes em `skills-lock.json` (todas de `anthropics/claude-code`). O acervo real é
`.agents/skills/` (lido também pelo ChatGPT Astra); `.claude/skills/` é a visão do Claude
Code, feita de symlinks para `.agents/skills/` — exceto `code-reviewer`, replicada de fato
nos dois, para não depender de link relativo. Cada skill é acionada automaticamente pelo
Claude quando a descrição do `SKILL.md` casa com o pedido; nenhuma delas define comando de
barra próprio.

| Skill | Categoria |
|---|---|
| `code-reviewer` | Revisão |
| `agent-development` | Desenvolvimento (plugins Claude Code) |
| `command-development` | Desenvolvimento (plugins Claude Code) |
| `hook-development` | Desenvolvimento (plugins Claude Code) |
| `mcp-integration` | Desenvolvimento (plugins Claude Code) |
| `plugin-structure` | Desenvolvimento (plugins Claude Code) |
| `plugin-settings` | Desenvolvimento (plugins Claude Code) |
| `skill-development` | Desenvolvimento (plugins Claude Code) |

Removidas do acervo (não se aplicam a este projeto: núcleo sem UI e sem rede, invariante 1)
— `frontend-design`, `browser-use`, `valyu-best-practices`, `writing-hookify-rules`,
`claude-opus-4-5-migration`. `code-reviewer` cobre linguagens genéricas (inclui
TypeScript/Go/Swift, que não existem aqui); as verificações específicas deste projeto — dados
sem fonte, refatoração não muda número, contrato de dimensionamento — continuam sendo
`/code-review` e `/simplify` (comandos nativos do Claude Code, não uma skill deste diretório).

## Regras de processo
- **Fase a fase.** Nenhuma fase do SPRINTS.md começa sem aprovação explícita do usuário.
- **`../FPSO_Siz` (Julia) é somente leitura.** Para executar o Julia, use um
  `git archive <commit>` extraído em pasta temporária.
- **`references/` é o acervo local fora do git.** O script `references/Balanço_Preliminar.py`
  nunca é editado (é a origem do balanço portado; o modo que o reproduzia saiu na consolidação).
- **Refatoração não muda número.** Um caminho produtivo só (sem modos de paridade), congelado
  por: o instantâneo bit a bit da planta (os 11 TAGs, varredura inteira), a
  `regressao_eficiencia.json` do balanço, as fixtures de equipamento do Julia
  (`tests/fixtures/julia/`, regressão dos métodos) e o gate de sanidade
  (`tools/auditar_saida_pfd.py`). Mudar um resultado ativo exige parar, identificar a causa e
  justificar por escrito em `docs/validacao/` antes de rever a regressão.
- **Pronto é o caminho inteiro**: entrada → processo → propriedades → correntes →
  dimensionamento → saída → memorial → gate. Comparação, modo sombra, estudo e protótipo são
  marcos internos, não capacidade entregue; nada fica em paralelo ao caminho produtivo.
- Toda fase fecha com os testes verdes, cobertura ≥ 90 % no núcleo e o SPRINTS.md
  atualizado.

## Invariantes (cada uma terá teste de arquitetura em `tests/arquitetura/`)
1. **Núcleo sem UI e sem rede.** `fpso_siz` fora de `output/` e `cli.py` não formata
   nem imprime; nenhum módulo importa bibliotecas de rede nem contém URL remota; caminhos
   são resolvidos em runtime, nunca absolutos no código.
2. **Constantes e premissas em TOML** (`src/fpso_siz/config/`, dentro do pacote), com a
   fonte citada. Nenhum literal numérico no código fora de {0, 1, 2, 10}; os fatores de
   conversão exatos ficam só em `core/unidades.py`.
3. **Uma física, três saídas.** Toda equação avaliada emite `CalcTrace`, e a memória de
   cálculo, o JSON e o CSV saem desse mesmo rastro, com bijeção equação↔rastro.
4. **A CLI não nomeia parâmetros.** Ela itera os `ParameterSpec` declarados por cada método.
   Isso vale para `cli.py`, `output/terminal/*` (modo interativo), `output/dimensionamento.py`,
   `output/pfd.py` e `output/ajustes.py`. O que aparece na tela e em que ordem vem de
   `config/interativo.toml` (menus por id de ação). A interface também não fixa TAG, bloco
   nem corrente (os desenhos saem de `config/topologia_db.toml`) e não monta entradas nem
   chama o motor: isso é do serviço por TAG.
5. **Backend devolver número ≠ propriedade validada para engenharia.** Que uma biblioteca
   retorne um valor não o torna utilizável em projeto. Toda propriedade que o processo consome
   fica numa de três situações, e a situação é **declarada**, não presumida:
   **(a) ausente** — não existe e não é estimada: vira NaN e lacuna declarada;
   **(b) calculada dentro do domínio validado** — com fonte, faixa conferida e teste;
   **(c) devolvida pelo backend, porém extrapolada ou não validada** — pode ser exposta para
   rastreabilidade, sempre com o método ao lado e com aviso, e **não pode ser promovida a
   propriedade de projeto** nem consumida por cálculo de dimensionamento ou de otimização.
   Casos vivos: `ρ` da fase líquida por Peng-Robinson sem translação de volume (razão medida
   0,541 contra mistura ideal de volumes) e `k` da fase líquida de hidrocarboneto — ambos em
   (c); `h` e `cp` dos pseudo-componentes — em (a). Ver `docs/validacao/30-caracterizacao-fluido-de-poco.md`.
   Corolário: um estado que mistura proveniências **não** se apresenta como produzido por um
   modelo só — cada propriedade carrega de onde veio. A declaração é única:
   `config/termo/proveniencia.toml`, com `validade` e `origem` independentes e os
   **consumidores reais** (lista vazia = diagnóstico); o `EstadoProcesso` e cada entrada de TAG
   apontam para ela, e um teste prova que a declaração descreve o código.

## Contrato de dimensionamento
Todo método herda `core.contrato.MetodoDimensionamento` e implementa os hooks com os
**mesmos nomes do Julia**. O motor (`core/motor.py`) nunca cita grandeza. Inviabilidade é
estado (`feasible = False` + mensagem), nunca exceção. Oráculo dos equipamentos:
`tests/fixtures/julia/` (commit no `manifesto.json`). Um TAG da planta (ou um equipamento
avulso) é sempre preparado e dimensionado por `pfd/equipamento.py` — o TAG isolado, o PFD e
o modo interativo passam pelo mesmo serviço; o estado de sessão é um `ajustes_pfd.toml`
versionado (`docs/esquemas/README.md`).

## Dependências
numpy/scipy só via `fpso_siz/_num.py`, para manter o port a C/Java mapeável; jinja2 só em
`fpso_siz/output/`; thermo/chemicals (ChEDL, MIT; propriedades de fluido) só via
`fpso_siz/termo/backend.py`, com import preguiçoso; fora de `termo/`, só a API de
`termo/servico.py`. **Regra das fontes:** correlação ou valor
sem fonte citável (acervo `references/` ou referência da docstring do ChEDL) é lacuna de
entrada, nunca número suposto. No NixOS, os testes precisam do `LD_LIBRARY_PATH` do flake.
Entre pelo devShell (`nix develop`, ou direnv): ele também fornece `pdftotext`
(`poppler-utils`), necessário para comparar o texto dos PDFs nos testes LaTeX.
**Custo da suíte, medido (i7-10750H: 6 núcleos físicos/12 threads, 7 GB de RAM).** O que domina
não é o número de processos, é a **cobertura de branch**: ela custa cerca de 3,2× (o mesmo teste
vai de 164 s para 527 s), e o `COVERAGE_CORE=sysmon` NÃO ajuda, porque o `sys.monitoring` só
cobre branch a partir do Python 3.14 e a coverage.py volta ao tracing. Por isso a cobertura é
verificação de **fechamento de fase**, não de cada rodada. Medições da suíte inteira: sem
cobertura, 9:45 com `-n 4 --dist loadscope` e 21:22 sequencial; com cobertura, 51:54 e 1:06:07.
Mais workers pioram: `-n 12` (são 6 núcleos físicos, e cada worker carrega uma planta) deu 50 min
com `loadscope` e 1:07 com `load`, porque `load` faz cada worker reconstruir as fixtures de
sessão. `loadscope` mantém o módulo no mesmo worker; a cobertura sob `-n` é combinada pelo
pytest-cov, e cada worker grava um `.coverage.*` (ignorado pelo git).
O paralelismo que rende de fato está DENTRO do cálculo caro: os testes de validação da F15
avaliam a população em processos (`_otim.py`), o que levou o `criterio_2` de 1441 s para 164 s sem
mudar um único número — a equivalência é testada em `tests/pfd/test_otimizacao_paralela.py`.

**A paridade com o Julia deixou de ser requisito da arquitetura** (consolidação, 2026-09-28).
`tests/fixtures/julia/` segue versionado como **regressão dos métodos de equipamento** (que não
dependem de modo nenhum), com a proveniência em `manifesto.json` (commit `ab58fc6`). Rodar a
suíte não exige Julia nem o repositório irmão.

## Comandos
```
uv sync
uv run pytest -n 4 --dist loadscope         # rodada do dia a dia (~10 min nesta máquina)
uv run pytest -n 4 --dist loadscope --cov=fpso_siz --cov-fail-under=90   # fechamento de fase (~52 min)
uv run pytest -m latex                      # compila os memoriais (lento)
uv run fpso-siz                             # modo interativo (num terminal); --ascii
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/
uv run python tools/gerar_regressao_eficiencia.py   # regressão da regra padrão do FWKO (F10w)
uv run python tools/auditar_saida_pfd.py     # gate de fim de fase: dimensionamento × JSON × MC (sai != 0 no erro)
uv run fpso-siz dimensionar --exemplo alves_komesu [--saida saida/]      # equipamento avulso por arquivo
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --auto-balanco \
    [--ajustes ajustes_pfd.toml] [--saida saida/tag]
uv run fpso-siz pfd --casos design_cases_bot.json [--ajustes ajustes_pfd.toml] [--saida saida/pfd]
    # propostas (config/pfd/pendencias_propostas.toml) por padrão; --sem-propostas deixa as lacunas abertas
uv run fpso-siz pfd --casos design_cases_bot.json --saida saida/pfd --mc [--pdf]   # MC de cada TAG (F11)
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --auto-balanco --saida saida/tag --mc [--pdf]
uv run fpso-siz memorial --casos todos [--pdf]      # MC_Caso01…16 (layout SENAI)
uv run fpso-siz dimensionar --exemplo pinch_kemp             # Análise Pinch (F8), exemplo do livro
uv run python tools/pinch_planta.py          # alvos do pré-aquecedor pela rede do balanço (F8)
uv run python tools/relatorio_trem.py        # trem SG-001 → V-001 → V-002 de cada caso (diagnóstico)
uv run python tools/investigar_alarmes.py    # variantes de estudo dos alarmes, pelo mesmo serviço
uv run python tools/otimizar.py [--sub sg_001 --varredura]   # otimização NSGA-II (F15; lenta)
uv run python tools/otimizar.py --sub pressao --processos 4 [--repetir]   # P_D1 × P_D2: grade-oráculo + NSGA-II (nota 42; horas)
FPSO_SNAPSHOTS=1 uv run pytest tests/test_terminal_pfd.py   # regenera os snapshots de tela
```

## Memoriais (LaTeX)
Os templates ficam em `src/fpso_siz/output/latex/*/templates/` (Jinja2 com `<< >>`, `<% %>`,
`<# #>`). O template só formata. Toda grandeza vem do núcleo (resultado, rastro,
`balanco/indicadores.py`). Premissa escrita no texto vem de `P[...]` com `mbn`, nunca
digitada.
