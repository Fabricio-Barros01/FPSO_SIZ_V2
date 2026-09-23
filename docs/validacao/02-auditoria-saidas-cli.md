# 02 — Auditoria independente, saídas estruturadas e CLI (F3)

Data: 2026-09-23. **Estado: entregue.**

## Auditoria independente (`balanco/auditoria.py`)
- Port de `auditoria_independente()`. As 16 verificações estão catalogadas em
  `config/auditoria.toml` (id, texto LaTeX, base do recálculo, unidade), gerado a partir
  do oráculo e conferido byte a byte.
- **Paridade:** a lista (verificação, base, valor, unidade) é **idêntica** à do oráculo F1.
- **Independência, com teste:** o módulo não importa `modelo`, `balancos` nem
  `propriedades`. O recálculo usa a forma logarítmica de Standing, °C→°F como T·1,8+32,
  V_m recalculado, Ċ ΔT por corrente e as definições de BSW e salinidade.
- **Sensibilidade a erro, com teste:** somar 1 kW à carga do aquecedor de um caso faz as
  verificações de cargas térmicas e de energia global saltarem de ~1e-12 para ≥ 1. A de
  massa não muda.
- Uma verificação sem caso aplicável é omitida, como no original. Exemplo: a salinidade,
  quando nenhum caso tem água no desidratador (teste com os casos 1, 4, 5, 6 e 7).
- Para comparar V_m, o motor passou a expor `ResultadoCaso.VM`. Nenhum número mudou.

## Saídas (`balanco/exportacao.py` monta os dados; `output/arquivos.py` grava)
- `balanco.json`: validado por `docs/esquemas/balanco.schema.json` (JSON Schema 2020-12).
  Traz a entrada com SHA-256, as premissas (com a marca `alterada`), os 16 casos
  completos com o rastro (CalcTrace) e a auditoria.
- `correntes.csv`: 16 × 26 = 416 linhas. As colunas são declaradas em
  `config/saida_correntes.toml` e documentadas em `docs/esquemas/README.md` (há teste de
  sincronia).
- **Round-trip exato:** os valores lidos do JSON e do CSV são iguais bit a bit ao oráculo
  (floats em `repr`).

## CLI (`fpso-siz`, também `python -m fpso_siz`)
```
fpso-siz balanco --casos <json> --saida <pasta> [--premissa NOME=VALOR ...]
fpso-siz premissas [--casos <json>]
```
- Código de saída: 0 se tudo convergiu; 1 se algum caso não convergiu (o caso é listado);
  2 para erro de entrada (premissa desconhecida, formato inválido, arquivo ausente).
- **Invariante 4, com teste:** `cli.py` não contém como texto nenhum nome de premissa,
  equação, verificação, coluna ou campo de resultado. Ele itera descritores.
- `--premissa` é validado contra `premissas.toml`. A premissa alterada é impressa com o
  id e o valor-base e marcada no JSON. Teste: `--premissa BSW_pre=0.02` reproduz a linha
  correspondente da sensibilidade do oráculo.

## Achado registrado
Com o limite de iterações reduzido a 2, 5 dos 16 casos já passam no critério de resíduo,
porque os casos sem água não têm reciclo. Isso é coerente com o original: `iters = 4` é
justamente o mínimo imposto por `it > 3` nesses casos.

## Mudanças de núcleo nesta fase
- `P_FWKO` agora está declarada em `premissas.toml` com `chave_casos` (valor lido do
  arquivo de casos). `descritores_premissas()` alimenta a CLI e o JSON.
- `core/unidades.py` ganhou `SEGUNDOS_POR_HORA`, `HORAS_POR_DIA` e `c_para_f_linear`.
- A regra de literais numéricos (invariante 2) vale para o núcleo. `output/`, `cli.py` e
  `__main__.py` só apresentam e ficam fora dela.

Testes: 152, com cobertura de 100 % do pacote (`__main__.py` roda por subprocesso e fica
fora da medição).
