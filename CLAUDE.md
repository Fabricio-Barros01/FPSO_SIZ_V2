# FPSO_Siz_V2 — contrato do projeto

Backend Python (biblioteca + CLI) que substitui gradualmente o FPSO_Siz Julia. Estado e
backlog: [`SPRINTS.md`](SPRINTS.md), que deve ser lido primeiro.

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
  nunca é editado: ele é o oráculo do balanço.
- **Refatoração não muda número.** O balanço tem paridade bit a bit com o oráculo
  (`tests/fixtures/python_ref`) na regra do FWKO do script de referência (modo de
  paridade, `--regra-fwko referencia`); a regra padrão (eficiência, P-43, F10w) é congelada
  por `regressao_eficiencia.json`. Mudar um resultado exige justificativa escrita em
  `docs/validacao/` e a revisão do oráculo ou da regressão.
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
`fpso_siz/pfd/_chedl.py`, com import preguiçoso. **Regra das fontes:** correlação ou valor
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

**A suíte não executa mais o Julia** (decisão do usuário em 2026-09-27: o código amadureceu e
segue em outra direção). O marcador `julia` e o teste que reexecutava o FPSO_Siz para regenerar as
fixtures saíram; `tests/fixtures/julia/` continua versionado e continua sendo o **oráculo
numérico** dos equipamentos, com a proveniência em `manifesto.json` (commit `ab58fc6`) e o script
`tools/exportar_fixtures_julia.sh` guardado para uma exportação manual. Rodar a suíte não exige
mais Julia nem o repositório irmão.

## Comandos
```
uv sync
uv run pytest -n 4 --dist loadscope         # rodada do dia a dia (~10 min nesta máquina)
uv run pytest -n 4 --dist loadscope --cov=fpso_siz --cov-fail-under=90   # fechamento de fase (~52 min)
uv run pytest -m latex                      # compila os memoriais (lento)
tools/exportar_fixtures_julia.sh [commit]   # só à mão: reexporta as fixtures do Julia (git archive)
uv run python tools/comparar_memorial.py    # paridade da memória de cálculo, template a template
uv run fpso-siz                             # modo interativo (num terminal); --ascii
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/ [--regra-fwko referencia]
uv run python tools/gerar_regressao_eficiencia.py   # regressão da regra padrão do FWKO (F10w)
uv run fpso-siz dimensionar --exemplo alves_komesu [--saida saida/]      # contrato Julia
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --auto-balanco \
    [--ajustes ajustes_pfd.toml] [--saida saida/tag]
uv run fpso-siz pfd --casos design_cases_bot.json [--ajustes ajustes_pfd.toml] [--saida saida/pfd]
    # propostas (config/pfd/pendencias_propostas.toml) e óleo vivo por padrão;
    # --sem-propostas / --oleo-morto / --topologia-julia voltam ao modo das fixtures (F10b, Julia)
uv run python tools/reotimizar_trocadores.py   # reotimização discreta P-002/P-003 (F10x.7; lenta)
uv run fpso-siz pfd --casos design_cases_bot.json --saida saida/pfd --mc [--pdf]   # MC de cada TAG (F11)
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --auto-balanco --saida saida/tag --mc [--pdf]
uv run fpso-siz memorial --casos todos [--layout original|senai|ambos] [--pdf]    # MC_Caso01…16 (F11b)
uv run fpso-siz dimensionar --exemplo pinch_kemp             # Análise Pinch (F8), exemplo do livro
uv run python tools/pinch_planta.py          # alvos do pré-aquecedor pela rede do balanço (F8)
uv run python tools/estudo_circulacao.py     # circulação fixa e cascos em série (estudo; muito lenta)
uv run python tools/otimizar.py [--sub sg_001 --varredura]   # otimização NSGA-II (F15; lenta)
FPSO_SNAPSHOTS=1 uv run pytest tests/test_terminal_pfd.py   # regenera os snapshots de tela
```

## Memoriais (LaTeX)
Os templates ficam em `src/fpso_siz/output/latex/*/templates/` (Jinja2 com `<< >>`, `<% %>`,
`<# #>`). O template só formata. Toda grandeza vem do núcleo (resultado, rastro,
`balanco/indicadores.py`). Premissa escrita no texto vem de `P[...]` com `mbn`, nunca
digitada.
