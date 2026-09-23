# SPRINTS — FPSO_Siz_V2 (backend Python)

Estado, contexto, requisitos e backlog do projeto. Escrito para que uma pessoa ou uma IA
retome o trabalho **a qualquer momento lendo só este arquivo**. As regras permanentes estão
em [`CLAUDE.md`](CLAUDE.md); a razão da migração está em
[`docs/decisoes/0001-backend-python.md`](docs/decisoes/0001-backend-python.md).

**Manutenção:** ao fechar uma fase, marque-a ✅, registre `Entregue:` com o hash do commit
e os números de teste/cobertura, e mova `← ATUAL` para a próxima. **Cada fase só começa
com aprovação explícita do usuário** ("aprovado, pode implementar" ou equivalente para
aquela fase).

---

## Estado atual

**FASE ATUAL: F8 — Pinch (Kemp) ← ATUAL (aguardando aprovação)**

F0–F4 entregues: **o balanço preliminar está completo em Python**. O motor é bit a bit, a
auditoria é independente, há JSON/CSV com esquema, e o memorial LaTeX A4 sai em dois
layouts: `original`, idêntico ao script de referência, e `senai`, com o template SENAI
CETIQT. F5 entregue: o contrato de dimensionamento e o motor de envelope foram portados, e
as fixtures do Julia (`ab58fc6`) foram exportadas e são reproduzíveis. F6 entregue: os três vasos
(separador 3F, knockout, tratador) reproduzem o Julia (bit a bit em 2, e ≤ 1,25e-15 no
separador) e os casos-ouro da literatura. F7 entregue: bomba (Moran) e trocador (Saari +
Bell-Delaware) com o ponto escolhido idêntico ao Julia (intermediários a ≤ 4,8e-16). São 449
testes (+2 `-m latex`, +1 `-m julia`) e cobertura de 98 %. Uso:
`uv run fpso-siz balanco|memorial --casos tests/fixtures/python_ref/design_cases_bot.json --saida saida/`.

---

## Contexto

- **Projeto de origem:** `../FPSO_Siz` (Julia). É **somente leitura** para este projeto:
  nada é escrito lá, nem por ferramentas. Referência fixada: branch `PFD-Version`, commit
  `ab58fc6`. Tem cerca de 10,4 mil linhas de núcleo, deps só `Printf` + `TOML`, 5.327
  testes de núcleo e 7 aplicações: separador trifásico, knockout bifásico, tratador
  eletrostático, bomba centrífuga, trocador casco-e-tubos, Pinch e separador dinâmico
  (Song). Tem motor de envelope multi-caso e memoriais A4.
- **Estado do Julia:** o port do balanço preliminar para Julia **não existe**. O PFD
  (`docs/validacao/10-pfd-casos-bot.md` do Julia) está só na F1: 11 TOMLs com 16 casos
  por TAG, sem dimensionamento. As F2/F3 do PFD Julia viram a **F10** daqui.
- **Por que Python:** distribuição a terceiros, rota para um port posterior a C/Java e
  familiaridade/ecossistema. É uma exploração **com intenção de substituir** o Julia. A
  estrutura pode divergir; a física de dimensionamento é reaproveitada e validada contra o
  Julia.
- **Prazo:** o mais rápido possível, com dedicação integral.

## Requisitos (decididos no planejamento de 2026-09-23)

| Tema | Decisão |
|---|---|
| Escopo | Núcleo (biblioteca `fpso_siz`) + CLI. Entrada TOML/JSON, saída JSON/CSV/LaTeX. **Sem HTTP nem GUI** nesta fase |
| Ordem | Balanço preliminar → contrato do núcleo → equipamentos → integração PFD → memoriais → doc de portabilidade |
| Equipamentos | Todos os 7 do Julia |
| Balanço | Modularizar `Balanço_Preliminar.py` com **paridade numérica** nos 16 casos do BOT. Entrada por arquivo de dados; topologia do diagrama de blocos fixa (sem flowsheet genérico) |
| Saídas do balanço | Motor + balanços, auditoria independente, memorial LaTeX A4, JSON/CSV de correntes |
| Oráculos | Balanço: saída do script original congelado. Equipamentos: casos-ouro Julia (`docs/validacao/`, `test/golden_*.jl`) + fixtures exportadas do Julia |
| Invariantes | Ver `CLAUDE.md` (4 invariantes, todas com teste de arquitetura) |
| Dependências | numpy/scipy/jinja2 permitidos. numpy/scipy ficam **isolados em `fpso_siz/_num.py`** (port para C/Java); jinja2 só em `output/` |
| "Pronto" | Paridade com o oráculo + cobertura de linha ≥ 90 % no núcleo + testes de arquitetura verdes |
| Memoriais | Tudo em LaTeX A4, a partir do template SENAI (`references/Memorial_Template_Final (1).zip`) |
| Java/C | Só um documento comparativo (F12), com PyInstaller/Nuitka como baseline; nenhum código Java/C |

## Acervo local (`references/`, fora do git)

Cópia de `../FPSO_Siz/References/`, sem os mockups de UI, que estão fora do escopo:

- `Balanço_Preliminar.py`: script de referência do balanço. O cabeçalho o chama de
  `gerar_memorial.py`. Na prática são 3 módulos concatenados: `[1] modelo` (l.22–227),
  `[2] balanços` (l.228–274; `M = sys.modules[__name__]`, `B = M`) e `[3] auditoria +
  LaTeX` (l.275–1526, mais de 80 % do arquivo). Lê `design_cases_bot.json` pelo diretório
  corrente e escreve `main.tex`.
- `design_cases_bot.json`: 16 casos, tabelas 2.2.2.3/2.2.2.4 do BOT.
- `I-ET-3010.2K-1200-941-P4X-001_C (Design).pdf`: o BOT (especificação técnica).
- `bot/balanco_python.json`, `bot/manifesto.json`: exportação do balanço feita no Julia
  (não commitada lá). É a comparação secundária da F1.
- `Memorial_Template_Final (1).zip`: template LaTeX SENAI.
- Bibliografia dos métodos: Stewart & Arnold / Alves-Komesu (separadores), Moran/Pump
  Sizing (bomba), Saari + Delaware (trocador), Kemp/Pinch, Song (dinâmico), coalescedor
  eletrostático, Serna-Jiménez, Branan.

Se `references/` não existir, recrie a pasta com
`rsync -a --exclude 'FPSO SIZ UI mockups*' ../FPSO_Siz/References/ references/`
e `cp ../FPSO_Siz/config/bot/*.json references/bot/`.

## Ambiente

- NixOS + `flake.nix` (Python 3.13 + uv) via direnv; `uv sync` cria o `.venv`.
- LaTeX: o sistema tem **MiKTeX**, que instala pacotes sob demanda em `~/.miktex`.
  `texlive` **não** entrou no flake: ele sobreporia o MiKTeX no shell do projeto. Esse
  desvio do plano está registrado. Reavaliar na F4 ou na F12, se for preciso distribuir a
  compilação do memorial.
- Comandos: `uv run pytest`, `uv run pytest --cov=fpso_siz --cov-fail-under=90`,
  `uv run pytest -m latex` (compila os memoriais; lento), `uv run pytest -m julia`
  (regenera as fixtures do Julia; precisa de `julia` e `../FPSO_Siz`).
- Fixtures do Julia: `tools/exportar_fixtures_julia.sh [commit]` (git archive → pasta
  temporária; o repositório Julia só é lido).
- Com o `.envrc` bloqueado no direnv, bibliotecas com binário (ex.: pymupdf) precisam do
  `LD_LIBRARY_PATH` do flake; ele está em `.direnv/flake-profile-*.rc`.

## Arquitetura-alvo

```
src/fpso_siz/
  core/       ParameterSpec, ResultField, CalcTrace, CaseSet, envelope, unidades, config
  balanco/    propriedades, modelo (solve_case + reciclo), balancos, auditoria, correntes_io
  sizing/     separador, knockout, tratador, bomba, trocador
  analysis/   pinch          dynamics/  song
  output/     latex/ (jinja2), csv, json   ← único lugar que formata
  _num.py     única porta para numpy/scipy
  cli.py      argparse; itera descritores, nunca nomeia parâmetro
  config/     TOML do modelo DENTRO do pacote (constantes, premissas, pocos, topologia_db,
              equacoes_balanco), lidos via importlib.resources
tests/        arquitetura/, balanco/, golden/, fixtures/{python_ref/, julia/}
tools/        gerar_oraculo_balanco.py, exportar_fixtures_julia.jl
```

---

## Backlog por fase

### F0 — Bootstrap ✅
Criados `git init`, `.gitignore`, `pyproject.toml` (uv_build), o pacote vazio com teste de
fumaça, `references/`, este arquivo, `CLAUDE.md`/`AGENTS.md` e o ADR 0001. O
`requirements.txt` herdado de outro projeto (HYSYS) foi removido.
**Aceite:** `uv sync` limpo; `pytest` verde; o script original roda sem modificação dentro
de `references/` e gera `main.tex`.
Entregue: ver `git log` (commit inicial).

### F1 — Oráculo do balanço ✅
`tools/gerar_oraculo_balanco.py` importa o script original **sem editá-lo** (cwd =
`references/`) e serializa os 16 casos: correntes O/W/D/G, T, P, Q, W, laço de reciclo
(iterações/resíduo), `block_balance`/`global_balance`, `auditoria_independente()`,
envelopes e sensibilidades, mais o SHA-256 do JSON de entrada e o do `main.tex`. Depois,
comparar com `references/bot/balanco_python.json`.
**Aceite:** a fixture `tests/fixtures/python_ref/` é determinística (mesmo byte em duas
execuções); `docs/validacao/00-oraculo-balanco.md` registra origem, hashes e divergências.
Entregue: fixture `tests/fixtures/python_ref/{oraculo_balanco.json, main_ref.tex}` e 8 testes
(3 dependem do acervo). Igualdade exata com o snapshot Julia (3.168 valores nos 16 casos e
todos os demais campos). Os 16 casos convergem em 4 a 35 iterações. Commit: ver `git log`
("F1: …").
**Notas para a F2:** o resíduo de componente no M-01 (≈1e-10 kg/s) é o resíduo do reciclo e
deve ser reproduzido. O original escreve `main.tex` sem `encoding`; o novo usa utf-8.

### F2 — Motor do balanço modularizado ✅
`balanco/propriedades.py`, `modelo.py`, `balancos.py`; topologia (BLOCKS/STREAMS/GLOBAL_*)
e constantes/premissas (PREM, MW, CP0, API_WELL, MU_WELL) em TOML com a fonte citada;
CalcTrace por equação.
**Aceite:** paridade com a F1 nos 16 casos × 26 correntes × componentes, com erro relativo
≤ 1e-12 e cada desvio justificado; fechamento de massa/energia por bloco e global;
cobertura ≥ 90 %; invariantes 1–2 testadas.
Entregue: paridade **exata** (tolerância travada em 0) em todos os campos, incluindo
sensibilidades, balanços, iterações e μ. Fechamentos relativos < 5e-14. Resíduo do reciclo
agora exposto (`residuo_reciclo`, `convergiu`). CalcTrace com 26 equações e 52 pares por
caso, com bijeção testada. Invariantes 1–2 testadas por AST. 113 testes, cobertura de 100 %.
O wheel inclui os TOML. **Desvio:** os TOML do modelo ficam em `src/fpso_siz/config/`, não
em `config/` na raiz, por causa da distribuição.
**Notas para a F3:** a auditoria deve reproduzir `oraculo["auditoria"]` (16 verificações);
os envelopes e críticos têm os valores em `oraculo["criticos"]`, e seus textos
formatados vão para a F4.

### F3 — Auditoria independente, saídas estruturadas e CLI ✅
`balanco/auditoria.py` não importa `modelo`. Esquema JSON/CSV documentado. CLI
`fpso-siz balanco --casos <json> --saida <dir>`.
**Aceite:** auditoria idêntica à F1; esquemas validados; invariante 4 testada; cobertura ≥ 90 %.
Entregue: auditoria idêntica (16 verificações), independente do motor por teste de AST e
sensível a erro injetado. JSON validado por `docs/esquemas/balanco.schema.json`; CSV com
colunas declaradas em TOML e documentadas; ida e volta exata. CLI com os subcomandos
`balanco` e `premissas`, `--premissa NOME=VALOR` e códigos de saída 0/1/2; invariante 4
testada. 152 testes, cobertura de 100 %. Detalhes em `docs/validacao/02-auditoria-saidas-cli.md`.
**Notas para a F4:** os envelopes e os críticos do memorial (seção 16) ainda não têm função
no núcleo; eles entram na F4, com os valores numéricos de `oraculo["criticos"]` e o texto
de `main_ref.tex` como referência. O memorial deve ler o catálogo `auditoria.toml`, o
`equacoes_balanco.toml` e os descritores de premissas.

### F4 — Memorial LaTeX do balanço ✅
Seções 1–18 e apêndices em templates jinja2 com o template SENAI; os dados vêm só de
ResultField/CalcTrace.
**Aceite:** `diff` do `main.tex` contra o original vazio ou com lista branca documentada;
`latexmk` compila; bijeção equação↔rastro testada (invariante 3).
Entregue: 41 templates Jinja2 fatiados do `main.tex` de referência, mais o parcial das
bombas. O layout `original` é idêntico byte a byte; o `senai` usa o template SENAI. As
contas do memorial foram para o núcleo (`balanco/indicadores.py`). Teste de robustez:
original × novo com dados perturbados e com 15 premissas alteradas, só com as diferenças
previstas (literais fixos do original que agora acompanham o dado). Bijeção: 26
equações↔`\label`, mais 4 definições de fechamento. Os dois layouts compilam (MiKTeX, 17 s,
71/68 páginas). CLI `fpso-siz memorial [--layout] [--pdf]`. Detalhes em
`docs/validacao/03-memorial-balanco.md`.
**Notas para a F5:** o balanço está fechado. Seguem para o contrato de dimensionamento: o
`CalcTrace`/catálogo (26 equações com âncora), o padrão "fatiar a referência → template"
para os memoriais de equipamento (F11) e o `indicadores.maximo` (regra de empate), que o
envelope multi-caso vai reusar.

### F5 — Contrato do núcleo + fixtures Julia ✅
`core/` espelhando `interfaces.jl`, `engine/{contract,envelope,single}.jl` e `types/` do
Julia. `tools/exportar_fixtures_julia.jl` roda sobre um `git archive ab58fc6` extraído em
pasta temporária (o repo Julia não é tocado) e grava em `tests/fixtures/julia/`, com o hash
do commit.
**Aceite:** 4 invariantes testadas; envelope validado com um método-brinquedo; fixtures
reproduzíveis.
Entregue: `core/{parametros,casos,corrente,contrato,motor,registro,formato_julia}.py` e o
`Rastro` sequencial. Hooks com os nomes do Julia; cantos na ordem do `Iterators.product`;
mensagens com o texto e o formato numérico do Julia. Fixtures de 7 boxes: envelope completo
com varredura e rastro por caso, descritores e constantes, mais os TOMLs de exemplo. Os 6
exemplos dão expansão idêntica à do Julia. O motor foi provado com dois métodos-brinquedo
(vaso com teto/piso por caso; equipamento que não é vaso) e 7 estados de inviabilidade.
Detalhes em `docs/validacao/04-contrato-nucleo.md`.
**Notas para a F6:** portar os TOMLs de `config/equipment/` do snapshot, `field_units`, a
família de vasos (`VesselConstraints` e hooks) e o reetiquetamento de corrente do
knockout/tratador. Oráculo: fixtures dos 3 vasos + `test/golden_{alves_komesu,knockout}.jl`
e `test/treater.jl`.

### F6 — Vasos (separador 3F, knockout, tratador) ✅
**Aceite:** `golden_alves_komesu` (d = 6300 mm, Leff = 18,59 m, Lss = 24,78 m, SR = 3,93;
governa "Fim de vida"; teto de decantação 9124 mm), `golden_knockout` e `treater` com as
tolerâncias Julia; cobertura ≥ 90 %.
Entregue: `sizing/{vasos,capacidade_gas,arrasto,beta,separador,knockout,tratador}.py`,
`core/grade.py` (grade = a do Julia) e `field_units`; os TOMLs dos métodos são cópia
literal do snapshot, e os coeficientes do arrasto e os passos da bisseção foram para
`equipment/comum`. Paridade estrutural com as fixtures: knockout e tratador bit a bit;
separador com 11 números da cadeia de β a ≤ 1,25e-15 (libm do `acos`). Casos-ouro portados
de 5 arquivos de teste do Julia. Detalhes em `docs/validacao/05-vasos.md`.
**Notas para a F7:** a bomba (Moran) e o trocador (Saari/Bell-Delaware) não são vasos:
estendem `MetodoDimensionamento` direto e escrevem os próprios hooks (DN/nº de tubos,
`case_admissible` por caso, `envelope_params`). Oráculo: `bomba-centrifuga.json`,
`trocador-calor.json` e `test/golden_{moran,saari}.jl`. Com dois vasos já comparados bit a
bit, a meta é igualdade exata onde não houver `libm` transcendental.

### F7 — Bomba (Moran) + trocador (Saari/Bell-Delaware) ✅
**Aceite:** `golden_moran`, `golden_saari`; cobertura ≥ 90 %.
Entregue: `sizing/{base,hidraulica,bomba,bell_delaware,trocador}.py` e `core/ieee.py`; TOMLs
literais do snapshot; coeficientes que o Julia deixava no código foram para
`equipment/comum/{hidraulica,trocador}.toml`. Paridade: x, y e caso governante bit a bit;
intermediários ≤ 2,5e-16 (bomba) e ≤ 4,8e-16 (trocador), pela `libm`. Casos-ouro de Moran,
Saari e Branan portados. **Achado:** a divisão por zero do Python quebrava o diagnóstico
que o Julia faz via Inf/NaN. Foram usados `ieee.div` nos pontos críticos e uma rede de
segurança no motor (erro aritmético → inviabilidade). Detalhes em
`docs/validacao/06-bomba-trocador.md`.
**Notas para a F8:** o Pinch (`analysis/pinch.jl` + `pinch_method.jl`, cerca de 1.080
linhas) usa grupos repetíveis de parâmetros (N correntes) e `presentation_data` (curvas
compostas). Oráculo: `analise-pinch.json` + `test/golden_kemp.jl` + `test/pinch_encaixe.jl`.
Ao portar, conferir onde o Julia depende de Inf/NaN (usar `ieee.div`).

### F8 — Pinch (Kemp) ← ATUAL
**Aceite:** `golden_kemp`, `pinch_encaixe`; cobertura ≥ 90 %.

### F9 — Separador dinâmico (Song)
Portar o Euler próprio do Julia, para ter paridade de trajetória. scipy.integrate só como
verificação cruzada, fora do núcleo.
**Aceite:** trajetórias iguais às fixtures; oráculo de convergência por refino de malha;
cobertura ≥ 90 %.

### F10 — Integração balanço → PFD
As correntes do balanço geram as entradas de 16 casos por TAG (SG-001, V-001/002,
TO-001/002, P-001..003, B-001..003). Um envelope independente por TAG, sem interpolação
entre casos.
**Aceite:** 11 envelopes com o caso governante por restrição; lacunas listadas, sem valor
inventado; CLI `fpso-siz pfd`.

### F11 — Memoriais LaTeX dos equipamentos
Mesmo pipeline da F4; conteúdo de referência em `src/memorial_specs/` do Julia.
**Aceite:** um memorial A4 compilável por equipamento/TAG; bijeção testada.

### F12 — Portabilidade (Java/C) e distribuição
Baseline medido com Nuitka/PyInstaller (tamanho, startup, deps) no Linux e passos para
Windows. Comparativo Python empacotado × Java (JVM/GraalVM) × C por módulo, com o mapa de
`_num.py`. Pode ser antecipada para logo depois da F5.
**Aceite:** `docs/portabilidade/` responde que problema cada linguagem resolve e que o
Python empacotado não resolve.
