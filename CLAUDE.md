# FPSO_Siz_V2 — contrato do projeto

Backend Python (biblioteca + CLI) que substitui gradualmente o FPSO_Siz Julia. Estado e
backlog: [`SPRINTS.md`](SPRINTS.md), que deve ser lido primeiro.

## Regras de processo
- **Fase a fase.** Nenhuma fase do SPRINTS.md começa sem aprovação explícita do usuário.
- **`../FPSO_Siz` (Julia) é somente leitura.** Para executar o Julia, use um
  `git archive <commit>` extraído em pasta temporária.
- **`references/` é o acervo local fora do git.** O script `references/Balanço_Preliminar.py`
  nunca é editado: ele é o oráculo do balanço.
- Toda fase fecha com os testes verdes, cobertura ≥ 90 % no núcleo e o SPRINTS.md
  atualizado.

## Invariantes (cada uma terá teste de arquitetura em `tests/arquitetura/`)
1. **Núcleo sem UI e sem rede.** `fpso_siz` fora de `output/` e `cli.py` não formata
   nem imprime; nenhum módulo importa bibliotecas de rede nem contém URL remota; caminhos
   são resolvidos em runtime, nunca absolutos no código.
2. **Constantes e premissas em TOML** (`config/`), com a fonte citada. Nenhum número físico
   literal nas equações além de fatores de conversão exatos.
3. **Uma física, três saídas.** Toda equação avaliada emite `CalcTrace`, e o memorial, o
   JSON e o CSV saem desse mesmo rastro, com bijeção equação↔rastro.
4. **A CLI não nomeia parâmetros.** Ela itera os `ParameterSpec` declarados por cada método.

## Dependências
numpy/scipy só via `fpso_siz/_num.py`, para manter o port a C/Java mapeável; jinja2 só em
`fpso_siz/output/`.

## Comandos
```
uv sync
uv run pytest
uv run pytest --cov=fpso_siz --cov-fail-under=90
```
