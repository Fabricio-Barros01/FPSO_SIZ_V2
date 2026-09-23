# 01 — Motor do balanço modularizado (F2)

Data: 2026-09-23. **Estado: entregue.** O motor novo reproduz o oráculo da F1 **bit a bit**.

## Estrutura
| Módulo | Conteúdo | Origem no script |
|---|---|---|
| `balanco/dados.py` | arquivo de casos validado (`carregar_casos`), `constantes()`, `pocos()`, `premissas()` | l.25–54 (JSON, constantes, `PREM`) |
| `balanco/propriedades.py` | `poco_do_fluido`, `gas_props`, `standing_rs`, `mu_interp`, `split_water` | l.56–100 |
| `balanco/modelo.py` | `resolver_caso` (laço de reciclo), `ResultadoCaso` | l.102–225 (`solve_case`) |
| `balanco/balancos.py` | `balanco_bloco`, `balanco_global`, `topologia()` | l.228–272 |
| `core/trace.py` | `CalcTrace` | novo |
| `core/unidades.py` | conversões exatas (86400 s/d, 273,15 K, °C→°F) | literais do original |
| `config/*.toml` (no pacote) | constantes, premissas (P-xx/F-xx), poços, topologia, catálogo de equações | literais do original |

**Mudança em relação ao plano:** os TOML ficaram em `src/fpso_siz/config/`, dentro do
pacote, e não em `config/` na raiz. Assim o wheel e o executável os carregam por
`importlib.resources`, sem depender do diretório corrente. Isso foi verificado instalando
o wheel num venv isolado.

## Paridade
- **Critério do plano:** erro relativo ≤ 1e-12. **Obtido:** igualdade exata (`==`) em
  todos os campos, nos 16 casos, nas 24 sensibilidades, nos balanços por bloco e global,
  nas iterações do reciclo, na viscosidade e nas premissas. A tolerância do teste foi
  travada em **zero** (`tests/balanco/test_paridade.py`).
- **Como:** a ordem das operações do original foi mantida, inclusive onde ela é
  contraintuitiva:
  - o pré-aquecedor e o aquecedor são resolvidos duas vezes por iteração, e a T_16 usa a
    primeira estimativa de T_08;
  - o `dRsD1` reportado usa o T_D1 já atualizado, diferente do usado na última iteração;
  - a ordem de soma dos componentes (O, W, D, G) e a dos gases leves (N2…nC4) é a do
    original; essa ordem está fixada nos TOML.
- A entrada versionada `tests/fixtures/python_ref/design_cases_bot.json` tem o SHA-256
  conferido contra a proveniência do oráculo.

## O que o motor novo acrescenta, sem mudar número
- `ResultadoCaso.residuo_reciclo` e `convergiu`. O original não expunha o resíduo e
  seguia em silêncio se esgotasse as 500 iterações. Resíduo final máximo nos 16 casos:
  9,9e-11 (tol 1e-10). O caminho de não convergência é testado com o limite reduzido.
- `CalcTrace`: 27 equações catalogadas, 52 pares (equação, escopo) por caso. A bijeção
  catálogo↔rastro é testada nos 16 casos, e os valores do rastro são iguais aos do
  resultado.
- Validação da entrada: chaves obrigatórias, fluido sem composição, poço ambíguo
  (C20+ e C20++ ao mesmo tempo) e premissa desconhecida na sensibilidade.

## Fechamentos medidos (16 casos)
| Grandeza | Máximo |
|---|---|
| erro relativo de massa por bloco | 2,6e-14 (M-01, caso 3) |
| erro relativo de energia por bloco | 4,4e-14 (M-01, caso 3) |
| resíduo por componente | 9,9e-11 kg/s (M-01, caso 2; é o resíduo do reciclo) |
| erro global massa / energia | 2,9e-14 / 4,4e-14 |

## Invariantes com teste (tests/arquitetura/test_invariantes.py)
1. Sem import de rede nem de UI; `print` só em `output/` e `cli.py`; sem URL, caminho
   absoluto ou `__file__`; numpy/scipy só em `_num.py` e jinja2 só em `output/`.
2. Nenhum literal numérico fora de {0, 1, 2, 10} no código (exceto `core/unidades.py`).
   Toda seção de `constantes.toml` cita a fonte, e toda premissa tem id P-xx/F-xx, unidade
   e descrição.

Cobertura de linha e ramo do pacote: 100 %.
