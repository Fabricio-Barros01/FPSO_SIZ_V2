# 04 — Contrato do núcleo de dimensionamento + fixtures do Julia (F5)

Data: 2026-09-23. **Estado: entregue.**

## Port do contrato (FPSO_Siz Julia @ `ab58fc6`)
| Python | Julia | Conteúdo |
|---|---|---|
| `core/parametros.py` | `src/interfaces.jl`, `config.jl` | `ParameterSpec`, `validate`/`validar`, `defaults`, `with_defaults`, grupos repetíveis (`group_instance`, `single_box`), leitura de `[[parameter]]`/`[[group]]` |
| `core/casos.py` | `src/types/cases.jl` | `Interval`, `Case`, `CaseSet`, `expand` em cantos, `case_set_from_config` |
| `core/corrente.py` | `src/types/stream.jl` | `PhaseProps`, `StreamState`, `stream_from_case` (NaN no que não se exige), `stream_parameters()` |
| `core/contrato.py` | `src/engine/contract.jl`, `types/results.jl` | `SweepAxis`, `ResultField`, `SweepColumn`, `SweepRow`, `SizingResult`, `EnvelopeRow`, `EnvelopeResult`; bases `Equipamento` e `MetodoDimensionamento`, com os hooks (mesmos nomes do Julia) e seus defaults |
| `core/motor.py` | `src/engine/single.jl`, `envelope.jl` | `size_single`, `size_envelope`, `_sem_intersecao`, `governing_summary` |
| `core/registro.py` | `src/registry.jl` | `register`, `equipments`, `methods_for`, `sizing_method` |
| `core/trace.py` (`Rastro`) | `CalcTrace` Julia | rastro sequencial (bloco, eq., var., fórmula, valor, unidade) |
| `core/formato_julia.py` | `string(::Float64)` | números nas mensagens exatamente como o Julia os imprime |
| `config/stream.toml` | `config/stream.toml` | cópia literal |

## Decisões
- **Nomes dos hooks mantidos em inglês**, iguais aos do Julia (`sweep_axis`, `requirement`,
  `case_admissible`...). O port de cada método nas F6–F9 fica linha a linha.
- **Dois rastros.** `CalcTrace` (balanço) é indexado por (equação, escopo), e a última
  iteração prevalece, porque resolve um laço. `Rastro` (dimensionamento) é uma sequência
  ordenada, porque o memorial de equipamento segue a ordem do cálculo.
- **Ordem dos cantos = `Iterators.product` do Julia**, com o primeiro eixo variando mais
  rápido. Nomes (`"caso [a↓ b↑]"`) e ordem saem idênticos aos do Julia.
- **Mensagens com texto do Julia**, incluindo o prefixo `ArgumentError:` do `showerror` e o
  formato dos números (`1.0e6`, `100.0–300.0`).
- **O teto do motor é genérico.** O Julia consultava `VesselConstraints.mechanism` dentro do
  envelope; aqui é o hook `ceiling_mechanism_of`, como já fazia o caso único.
- O limite de 256 cantos está em `constantes.toml [motor]`.

## Fixtures do Julia (`tests/fixtures/julia/`)
`tools/exportar_fixtures_julia.sh [commit]` extrai `git archive <commit>` numa pasta
temporária, que é descartada ao fim, e roda `tools/exportar_fixtures_julia.jl`. O
repositório Julia só é lido. O resultado é um JSON por box do catálogo, com:
- descritores (parâmetros, corrente, grupos, `global_keys`) e constantes do TOML;
- casos do exemplo e a expansão em cantos;
- `size_envelope` completo: linhas da varredura, folgas e casos individuais com varredura e
  rastro;
- cartão de resultados, colunas e resumo de governança.

Acompanham `formatos_julia.json`, com strings de números impressas pelo Julia, e
`manifesto.json`, com o commit (`ab58fc631749aa81fdf7db566aa14a0cecd777c4`) e o Julia
1.12.6. Os TOMLs de exemplo e o `stream.toml` são copiados para `casos/`.

| Box | Resultado (envelope do exemplo) |
|---|---|
| separador-3f | d = 6300 mm, Leff = 18,5856 m, governa "Fim de vida" (10 cantos) |
| knockout-2f | d = 900 mm, Leff = 2,0826 m |
| vaso-eletrostatico | d = 3300 mm, Leff = 9,4799 m (3 casos) |
| bomba-centrifuga | DN 250, carga 15,855 m (2 casos) |
| trocador-calor | x = 75 (nº de tubos), 5,7166 (2 casos) |
| analise-pinch | x = 10, 20 (1 caso) |
| controle-separador | só descritores (a simulação dinâmica entra na F9) |

## Verificações
- **Formato de números:** `jl()` e `jl_round()` iguais às 22 × 3 strings do Julia.
- **Descritores de corrente:** idênticos aos do Julia. A filtragem por `stream_keys` dá as
  mesmas chaves nos 7 boxes. Knockout, tratador e bomba **reetiquetam** campos herdados;
  isso é do método e fica para as F6/F7.
- **Casos:** os 6 arquivos de exemplo, lidos pelo Python, dão os mesmos casos e **a mesma
  expansão** (nomes, ordem e valores) do Julia.
- **Motor**, com métodos-brinquedo declarados no teste (um "tanque" com teto e piso por
  caso, e uma "linha" que não é vaso e escolhe o menor x):
  - um caso ≡ dimensionamento simples;
  - o envelope é o máximo em cada x e nomeia o governante, com folga zero no governante;
  - faixas viram cantos e o pior canto governa;
  - o teto é o menor entre os casos, com o caso que o impôs;
  - 7 estados de inviabilidade com a mensagem exata;
  - diagnóstico de faixas que não se cruzam;
  - método aplicado ao equipamento errado.
- **Invariante 4 no núcleo:** `motor.py` e `contrato.py` não contêm nenhuma chave de
  corrente nem de grandeza de método.
- **Reprodutibilidade:** `uv run pytest -m julia` regenera as fixtures a partir do snapshot
  e confere byte a byte (16 s).

## Para a F6 (vasos)
- Portar `config/equipment/{separator,knockout,treater}/*.toml` do snapshot e a família de
  vasos (`VesselConstraints`, `requirement`/`governing_of`/`ceiling_of` por restrições,
  `envelope_params` com grade-união × banda-interseção, `selection_message`,
  `result_fields`).
- Incluir `field_units` (conversão SI → unidades de Stewart & Arnold) e o reetiquetamento
  de corrente do knockout e do tratador.
- Oráculo: `tests/fixtures/julia/{separador-3f,knockout-2f,vaso-eletrostatico}.json` (varredura
  e rastro por caso) e os casos-ouro `test/golden_*.jl`.
