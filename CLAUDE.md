# FPSO_Siz_V2 — contrato do projeto

Backend Python (biblioteca + CLI) que substitui gradualmente o FPSO_Siz Julia. Estado e
backlog: [`SPRINTS.md`](SPRINTS.md), que deve ser lido primeiro.

## Regras de processo
- **Fase a fase.** Nenhuma fase do SPRINTS.md começa sem aprovação explícita do usuário.
- **`../FPSO_Siz` (Julia) é somente leitura.** Para executar o Julia, use um
  `git archive <commit>` extraído em pasta temporária.
- **`references/` é o acervo local fora do git.** O script `references/Balanço_Preliminar.py`
  nunca é editado: ele é o oráculo do balanço.
- **Refatoração não muda número.** O balanço tem paridade bit a bit com o oráculo
  (`tests/fixtures/python_ref`). Mudar um resultado exige justificativa escrita em
  `docs/validacao/` e a revisão do oráculo.
- Toda fase fecha com os testes verdes, cobertura ≥ 90 % no núcleo e o SPRINTS.md
  atualizado.

## Invariantes (cada uma terá teste de arquitetura em `tests/arquitetura/`)
1. **Núcleo sem UI e sem rede.** `fpso_siz` fora de `output/` e `cli.py` não formata
   nem imprime; nenhum módulo importa bibliotecas de rede nem contém URL remota; caminhos
   são resolvidos em runtime, nunca absolutos no código.
2. **Constantes e premissas em TOML** (`src/fpso_siz/config/`, dentro do pacote), com a
   fonte citada. Nenhum literal numérico no código fora de {0, 1, 2, 10}; os fatores de
   conversão exatos ficam só em `core/unidades.py`.
3. **Uma física, três saídas.** Toda equação avaliada emite `CalcTrace`, e o memorial, o
   JSON e o CSV saem desse mesmo rastro, com bijeção equação↔rastro.
4. **A CLI não nomeia parâmetros.** Ela itera os `ParameterSpec` declarados por cada método.

## Contrato de dimensionamento
Todo método herda `core.contrato.MetodoDimensionamento` e implementa os hooks com os
**mesmos nomes do Julia**. O motor (`core/motor.py`) nunca cita grandeza. Inviabilidade é
estado (`feasible = False` + mensagem), nunca exceção. Oráculo dos equipamentos:
`tests/fixtures/julia/` (commit no `manifesto.json`).

## Dependências
numpy/scipy só via `fpso_siz/_num.py`, para manter o port a C/Java mapeável; jinja2 só em
`fpso_siz/output/`.

## Comandos
```
uv sync
uv run pytest
uv run pytest --cov=fpso_siz --cov-fail-under=90
uv run pytest -m latex                      # compila os memoriais (lento)
uv run pytest -m julia                      # regenera as fixtures do Julia e compara
tools/exportar_fixtures_julia.sh [commit]   # fixtures do Julia (git archive, só leitura)
uv run python tools/comparar_memorial.py    # paridade do memorial, template a template
```

## Memoriais (LaTeX)
Os templates ficam em `src/fpso_siz/output/latex/*/templates/` (Jinja2 com `<< >>`, `<% %>`,
`<# #>`). O template só formata. Toda grandeza vem do núcleo (resultado, rastro,
`balanco/indicadores.py`). Premissa escrita no texto vem de `P[...]` com `mbn`, nunca
digitada.
