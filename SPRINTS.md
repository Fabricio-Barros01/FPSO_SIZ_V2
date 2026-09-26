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

**FASE ATUAL: resolução dos alarmes de inviabilidade (pré-condição da F15) ← ATUAL; F10x (até F10x.6), F13, F14 e o planejamento da F15 entregues em 2026-09-26. Alarmes do SG-001 (óleo vivo) e das bombas (P-44) explicados; seguem abertos os dos trocadores P-001/P-002/P-003.**
**F11 (MC por TAG) e F11b (MC do balanço por caso) entregues em 2026-09-26, em sessão autônoma
autorizada pelo usuário, no branch `fases/f11` (sem merge; integração pelo usuário). Ver
[`docs/validacao/13-memorial-tag.md`](docs/validacao/13-memorial-tag.md).**
**F10c aprovada e entregue em 2026-09-23. F10v (verificação do balanço + premissa P-42) e
F10w (eficiência do FWKO, P-43) aprovadas e entregues em 2026-09-25. Nenhuma implementação
da F11 autorizada.**

Ordem revista em 2026-09-23, por decisão do usuário: F10 (balanço → equipamentos, em
F10a/b/c) e F11 (MC por TAG) vêm **antes** de F8 (Pinch) e F9 (Song).

F0–F4 entregues: **o balanço preliminar está completo em Python**. O motor é bit a bit, a
auditoria é independente, há JSON/CSV com esquema, e o memorial LaTeX A4 sai em dois
layouts: `original`, idêntico ao script de referência, e `senai`, com o template SENAI
CETIQT. F5 entregue: o contrato de dimensionamento e o motor de envelope foram portados, e
as fixtures do Julia (`ab58fc6`) foram exportadas e são reproduzíveis. F6 entregue: os três vasos
(separador 3F, knockout, tratador) reproduzem o Julia (bit a bit em 2, e ≤ 1,25e-15 no
separador) e os casos-ouro da literatura. F7 entregue: bomba (Moran) e trocador (Saari +
Bell-Delaware) com o ponto escolhido idêntico ao Julia (intermediários a ≤ 4,8e-16). F7b
entregue (fase extra, pedida pelo usuário): modo interativo com cabeçalho no estilo OpenFOAM
e subcomando `dimensionar`. São 516 testes (+2 `-m latex`, +1 `-m julia`) e cobertura de
98 %. Uso: `uv run fpso-siz` (interativo, num terminal) ou
`uv run fpso-siz balanco|memorial --casos tests/fixtures/python_ref/design_cases_bot.json --saida saida/`
e `uv run fpso-siz dimensionar --exemplo alves_komesu [--saida saida/]`.

F10a e F10b entregues: propriedades ChEDL e integração dos 11 TAGs ao balanço, com
origem de cada entrada, lacunas, casos inativos e envelopes. Novo comando:
`uv run fpso-siz pfd --casos tests/fixtures/python_ref/design_cases_bot.json [--ajustes A.toml] [--saida saida/pfd]`.
Sem ajustes, V-001/002 dimensionam, oito TAGs aguardam entradas e SG-001 é inviável com
as premissas atuais. Nenhuma lacuna foi preenchida sem fonte. Ver
[`docs/validacao/09-pfd.md`](docs/validacao/09-pfd.md).

F10c entregue: a unidade de trabalho é o **equipamento/TAG** — preenchimento automático
(balanço), manual ou por arquivo/exemplo; pendências e recomendações por TAG × caso;
revisão, edição por caso, restauração e retomada; a Planta/PFD percorre o mesmo serviço
(`pfd/equipamento.py`). Um único `ajustes_pfd.toml` versionado (esquema 2, lê o legado)
serve à sessão e aos comandos `dimensionar --tag … [--auto-balanco]`, `--avulso` e `pfd`,
que gravam os mesmos bytes. Esquemas da planta e do TAG saem da topologia, em Unicode ou
ASCII (`--ascii`), com tela estreita. **783 testes (+2 `-m latex`, +1 `-m julia`),
cobertura de 96,86 %**; resultados numéricos iguais aos da F10b. Ver
[`docs/validacao/10-fluxo-tag.md`](docs/validacao/10-fluxo-tag.md).

F10v entregue (fase extra, pedida pelo usuário): verificação física do balanço (a água sai
por C-05/C-25 e fecha em 1,3e-11 kg/s; os casos 1 e 4–7 não têm água no BOT) e a premissa
**P-42 — sem fase aquosa**: critérios aquosos "não aplicável" nos casos sem água, sem água
fictícia. Balanço inalterado (bit a bit). SG-001 segue inviável, agora pelo caso 2 (com
água). **802 testes (+2 `-m latex`, +1 `-m julia`), cobertura de 96,92 %.** Ver
[`docs/validacao/11-verificacao-balanco.md`](docs/validacao/11-verificacao-balanco.md).

F10w entregue: a separação de água livre do SG-001 passou a ser uma **eficiência**, η_A =
máx(η_padrão = 0,85; η_req), com η_req calculado no laço para que o óleo não passe de 40 %
de água (BOT 2.7.1.2). η_padrão é a P-43, premissa do autor editável. A regra do script de
referência segue como **modo de paridade** (`--regra-fwko referencia`, layout `original`,
testes do oráculo). Casos 15–16 exigem η acima do padrão (92,4 % e 91,5 %). Nos casos 2, 8,
9 e 11, Q_H (P-002 + DWH-001) cai de 12,8 % a 49,5 % e Q_C (P-003) de 2,9 % a 18,1 %,
porque o P-001 recupera mais calor. O V-001 vai a 4700 mm, e o SG-001 segue inviável (teto
de 3612 mm, caso 2). **Pendência:** a η_A adotada não é sustentada pela geometria do SG-001
nos casos 2 e 3. **814 testes (+2 `-m latex`, +1 `-m julia`),
cobertura de 96,95 %.** Ver
[`docs/validacao/12-eficiencia-fwko.md`](docs/validacao/12-eficiencia-fwko.md).

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
| Dependências | numpy/scipy/jinja2 permitidos. numpy/scipy ficam **isolados em `fpso_siz/_num.py`** (port para C/Java); jinja2 só em `output/`. thermo/chemicals (ChEDL, MIT) desde a F10a, só em `pfd/_chedl.py` |
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
  pfd/        propriedades (ChEDL via _chedl), TAGs, adaptadores automático/manual,
              serviço por TAG (equipamento.py), estado de sessão (ajustes.py), planta
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

### F7b — CLI interativa ✅
Fase extra, aprovada em 2026-09-23 fora do plano original. Pedido: dar ao usuário noção do
contexto, dos casos e um resumo dos resultados, e deixar exportar como opção. Pedido
adicional: um cabeçalho "como o do OpenFOAM e dos CLIs de agentes".
Entregue:
- `output/terminal/`:
  - `cabecalho.py`: moldura do OpenFOAM, com o acrônimo **F**loating **P**roduction
    **S**torage and **O**ffloading no lugar de Field/Operation/And/Manipulation, degradê ANSI
    e linha de dicas.
  - `estilo.py`: cor só em TTY; respeita `NO_COLOR`, `FORCE_COLOR` e `TERM=dumb`.
  - `relatorio.py`: resumos.
  - `sessao.py`: menus.
  - `comum.py`
- Fluxo da sessão:
  1. mostra o contexto: arquivo, sha256, fonte, casos e fluidos;
  2. o usuário escolhe balanço, equipamento, premissas ou casos;
  3. vem o resumo: no balanço, convergência e o caso que maximiza cada critério; no
     equipamento, cartão, governante e folga por caso;
  4. o usuário pode ver auditoria, correntes, varredura ou rastro;
  5. se quiser exportar, a sessão grava e mostra o **comando equivalente**. Um teste
     garante que esse comando grava os mesmos bytes.
- Subcomando `fpso-siz dimensionar --exemplo|--casos [--equipamento] [--metodo] [--saida]`.
  Sem `--saida`, só mostra o resumo. Sai com 1 se o resultado for inviável.
- `output/dimensionamento.py` grava o JSON (entrada, cartão, casos) e o CSV da varredura.
- Exemplos do Julia embutidos em `config/exemplos/`; um teste garante que são idênticos às
  fixtures. Novas funções `core.configuracao.exemplos()` e `core.registro.resolver()`.
- Descritores de apresentação em `config/interativo.toml`. A invariante 4 passou a cobrir a
  CLI inteira: `cli.py`, `output/terminal/*` e `output/dimensionamento.py`. Também ficam
  proibidos nesses módulos os nomes dos parâmetros dos métodos e as chaves de corrente.

Detalhes em `docs/validacao/07-cli-interativa.md`.
**Notas para a F8:** um método novo registrado em `sizing/__init__.py` aparece sozinho no
menu e no `dimensionar`. O Pinch precisa de exemplo em `config/exemplos/` (copiar
`exemplo_pinch_kemp.toml`) e talvez de resumo próprio: não tem varredura de diâmetro, e a
tabela de caso usa `sweep_columns()[0]`.

### F8 — Pinch (Kemp) (depois da F11)
**Aceite:** `golden_kemp`, `pinch_encaixe`; cobertura ≥ 90 %.

### F9 — Separador dinâmico (Song)
Portar o Euler próprio do Julia, para ter paridade de trajetória. scipy.integrate só como
verificação cruzada, fora do núcleo.
**Aceite:** trajetórias iguais às fixtures; oráculo de convergência por refino de malha;
cobertura ≥ 90 %.

### F10 — Integração balanço → equipamentos/TAGs (adiantada; em três subfases)
**Visão do usuário:** o arquivo de casos 1–16 alimenta o balanço, e o balanço fornece
**automaticamente** as entradas do dimensionamento dos 11 TAGs (SG-001, V-001/002,
TO-001/002, P-001..003, B-001..003). A unidade de trabalho é **um equipamento/TAG**:
o usuário pode preencher manualmente, escolher o preenchimento automático ou sobrescrever
valores. O automático usa balanço + propriedades com fonte; o que faltar é solicitado,
sem valor suposto. Pode-se adiar o preenchimento, mantendo o TAG aguardando entrada.
Planta/PFD é o atalho que percorre esse mesmo fluxo para todos os TAGs.
O detalhamento que falta ao balanço preliminar (propriedades na condição do
equipamento) é feito numa camada **oculta no balanço** (`src/fpso_siz/pfd/`, a jusante; o
balanço e a paridade não mudam) e **exposta no MC do equipamento** (F11).

**Regra das fontes (usuário, 2026-09-23): "para as referências sem fonte não suponha
nada, complete o que é possível".**
- Entra só o que tem equação, tabela ou premissa citável **no acervo** (`references/`)
  ou referência da docstring ChEDL, conforme a decisão posterior da F10a.
- O que não tem vira **lacuna de entrada** (sem valor recomendado): o TAG fica "aguardando
  entrada" até o usuário informar.
- O levantamento inicial está em `docs/decisoes/0002-pfd-automatico.md`. μ da água e do
  gás já foram atendidas pela F10a; as lacunas efetivas da F10b estão em
  `docs/validacao/09-pfd.md`. O alerta será calculado das entradas do TAG/caso, nunca
  copiado dessa lista histórica.
- Mapeamento TAG → método → correntes: igual ao PFD F1 do Julia
  (`../FPSO_Siz/docs/validacao/10-pfd-casos-bot.md`, lacunas L01–L12).

#### F10a — Propriedades na condição real ✅
**Decisão do usuário (2026-09-23):** thermo/chemicals (ChEDL, MIT) como dependência direta
de runtime, só por `pfd/_chedl.py`, com import preguiçoso e cache das constantes. O teste de
arquitetura garante essa porta única.

Entregue:
- `pfd/{_chedl,fluidos}.py`, `config/fluidos.toml` e `core/unidades.mgl_para_kgm3`.
- Z do gás por Peng-Robinson com a composição do balanço; ρ = P·MW/(Z·R·T) (S&A eq. 1.8).
- μ e k do gás pelo thermo (Brokaw, Lindsay-Bromley).
- Água de diluição por IAPWS; salmoura (ρ, μ, cp) por Laliberté (2009).
- Óleo morto pelo BOT com P-40; emulsão por Zanker (Branan eq. 27-4); Pv = P do vaso
  (Branan Ex. 5-2).
- **Lacunas:** k da salmoura, k do óleo, óleo vivo e Bo.
- Cada propriedade vai para o rastro, no bloco "propriedades", com a fonte. O que sai da
  faixa de validade vira aviso.
- 548 testes, cobertura de 98 % (`pfd/fluidos.py` 100 %). Detalhes e a tabela dos 16 casos
  em `docs/validacao/08-propriedades.md`: o gás ideal subestima ρ do gás no FWKO em 5–11 %.

**Notas para a F10b:**
- As funções recebem (T, P) e os dados do balanço (`r.gp["y"]`, `r.gp["MW"]`,
  `r.rho`, premissas `S_W`, `rho_W`, poço via `poco_do_fluido`).
- As lacunas (NaN) viram entradas obrigatórias do TAG.
- A vazão real de gás é ṁ_G/ρ_g.
- **NixOS:** para rodar os testes é preciso o `LD_LIBRARY_PATH` do flake (numpy agora é
  importado de fato).

#### F10b — Mapeamento balanço → TAG e `fpso-siz pfd` ✅
- `pfd/{tags,entradas,planta}.py` e `config/pfd/<tag>.toml`.
- Cada valor tem sua **origem** registrada: balanço, correlação, recomendada, default ou
  usuário.
- A bomba ganha `pv_informada`, com paridade preservada.
- Caso sem vazão no TAG fica inativo, com o motivo.
- Override de faixa para a salmoura.

**Aceite:**
- sem lacunas preenchidas, "aguardando entrada" com a lista exata do que falta;
- com ajustes de teste, 11 envelopes;
- o que vem do balanço é igual, bit a bit, às fixtures do PFD F1 do Julia (copiadas para
  `tests/fixtures/julia/pfd/`).

Entregue: `pfd/{tags,entradas,planta}.py`, 11 TOMLs de TAGs, defaults com fontes, ajustes
por TAG/caso e `fpso-siz pfd`, com JSON por TAG e `planta.csv`. `pv_informada` preserva
Antoine no default e a paridade Julia; faixas de salmoura ampliadas só nos descritores do
PFD. **608 testes, cobertura 97,93 % (PFD 98 %)**. Commit: `f9d5300`.

Verificação: 528 entradas compartilhadas com o PFD F1 bit a bit; hashes das 11 fixtures
preservados; 11 envelopes viáveis com ajustes **sintéticos, exclusivos dos testes**;
exportação API/CLI idêntica byte a byte. Núcleo do balanço e oráculos não alterados.

Decisões/limitações documentadas em `docs/validacao/09-pfd.md`:
- gás na base padrão exigida por S&A Eq. 3.8b (o rascunho F1 usava a base de operação);
- uma solução aquosa W+D, com conservação da massa de sal; utilidades com ambas as
  temperaturas pendentes, água pura IAPWS saturada à temperatura média;
- knockouts com 5 min para alto CO₂, como no plano aprovado;
- SG-001 mantém a inviabilidade e o teto do caso 6: retirar a restrição de decantação
  quando não há água livre exige revisão física específica; não foi alterada nesta fase;
- o teste de registro de métodos foi isolado, corrigindo dependência da ordem da suíte.

**Notas para a F10c:** reutilizar `EntradasTAG.lacunas`, `specs`, `CasoTAG.insumos`,
`valores`/`rastro` e `output.terminal.pfd.resumo`. Recomendações ainda aparecem como "a
confirmar"; a proposta abaixo distingue **confirmar a recomendação** de **editar o valor**,
preservando a origem no primeiro caso e marcando usuário no segundo. Exportação do TOML
de ajustes e reprodução da sessão são parte da F10c. Campos do CSV/JSON estão em
`docs/esquemas/README.md`. Não tratar código 1 do `pfd` como falha de exportação: os
arquivos são gravados também com lacunas/inviabilidade.

#### F10c — Fluxo por equipamento/TAG no terminal; PFD como atalho ✅

**Aprovada em 2026-09-23 e entregue** (registro da entrega no fim desta seção). O texto
abaixo é a especificação aprovada. Esta seção substituiu a proposta anterior de começar
pelo menu Planta. Aprovar esta fase não autorizou a F11 nem revisões de física.
O produto continua sendo `fpso-siz` no terminal, com o cabeçalho atual no estilo OpenFOAM.
Sem GUI, web, HTTP, app separado ou novas dependências de interface.

**1. Um serviço por TAG, usado por todas as entradas**

Inspeção da F10b: `pfd/entradas.montar` já é a única montagem automática. Porém
`pfd/planta.dimensionar` contém a sequência montar → verificar pendências → dimensionar,
enquanto `Sessao._equipamento` e `cmd_dimensionar` carregam TOML/exemplos e chamam o
motor diretamente. Há caminhos separados de orquestração, sem uma segunda física PFD.

Proposta de unificação:

- Extrair o serviço por equipamento/TAG, por exemplo `pfd/equipamento.py`, com operações
  de preparar entradas e dimensionar um `EntradasTAG`. O serviço retorna dados/estados;
  não pergunta, imprime, desenha nem gera arquivos. O TAG identifica a instância; o tipo
  de equipamento e método continuam no registro existente.
- O adaptador automático continua em `pfd/entradas.py`: balanço → propriedades → ajustes
  → pendências, sem duplicar regras. Um adaptador manual normaliza dados digitados,
  TOML e exemplos para o mesmo contrato de entradas, origem e revisão. Ambos chegam à
  mesma verificação de completude e à mesma chamada de `core.motor.size_envelope`.
- Inviabilidade física, inclusive identificada ao preparar as entradas, retorna estado
  e diagnóstico (`feasible = False`), nunca exceção para o usuário. Lacuna mantém
  aguardando entrada. Erros de sintaxe, chave desconhecida ou contexto incompatível são
  erros de entrada/uso separados; não se confundem com inviabilidade de equipamento.
- O contexto compartilhado contém dados dos casos, premissas, balanço resolvido e versões.
  Calcula-se o balanço uma vez por contexto quando houver preenchimento automático.
  Selecionar um TAG não dimensiona os outros dez. O manual não consulta balanço/ChEDL
  para completar campos que o usuário decidiu informar.
- `pfd/planta.py` passa a percorrer o serviço por TAG e agregar resultados. O menu Planta
  percorre também o mesmo formulário por TAG. O comando `pfd` usa o mesmo serviço, mas
  sem perguntas: retorna as pendências em aberto e prossegue com os demais TAGs.
- Os comandos e menus mantêm apenas seleção, leitura/escrita e apresentação. Extrair o
  serializador de resultado por TAG de `output/pfd.py`, hoje dependente de `Planta`,
  para exportar um equipamento sem fabricar uma execução dos onze.

**2. Menu principal e percurso por equipamento**

Ordem e textos propostos, declarados em `config/interativo.toml` por ids de ações:

```text
1) Equipamento / TAG
2) Planta / PFD — todos os TAGs
3) Balanço de massa e energia
4) Casos de projeto
5) Premissas do balanço
6) Abrir / salvar ajustes
0) Sair
```

Em Equipamento/TAG: escolher um TAG da planta ou um equipamento avulso. O catálogo de
TAGs vem de `config/pfd/tags/`; tipos/métodos e parâmetros vêm do registro e dos
`ParameterSpec`. Para o avulso, o automático solicita primeiro um TAG compatível, pois
o tipo isolado não identifica suas correntes no balanço.

```text
Equipamento: V-001 · Vaso desgaseificador 1
1) Preenchimento automático — balanço preliminar
2) Preenchimento manual
3) Carregar arquivo de entradas / exemplo
0) Voltar
```

O automático mostra arquivo/hash, casos e premissas em uso, prepara o TAG, exibe o esquema
local e a tabela de entradas por caso, depois o alerta exato de pendências. O manual
permite começar sem os valores automáticos. Nos dois modos, qualquer entrada pode ser
editada para todos os casos ou para casos específicos; a edição registra origem usuário.
Os defaults numéricos de `ParameterSpec` não bastam como fonte: só oferecer os respaldados
pelo catálogo de fontes, incluindo no manual. Arquivos/exemplos identificam sua origem;
campos ausentes sem fonte continuam pendências, nunca herdam números silenciosamente.

Com entradas completas nos casos ativos, dimensionar e mostrar resultado, governante,
folga por caso e avisos. A tela permite ver entradas/fontes, propriedades/rastro,
varredura, editar, redimensionar e exportar. Deve ser possível suspender um preenchimento
incompleto, visitar outro TAG e retomar sem perder o trabalho. Inviabilidade mantém a
mensagem e as entradas; não altera premissas para obter uma solução.

**3. Pendências por TAG × caso e recomendações**

- **Lacuna sem valor:** alerta destacado com chave, rótulo, unidade, faixa aplicável,
  casos ativos afetados, motivo/dica e valores que dependem dela. Pergunta sem padrão;
  Enter adia, não significa zero nem aceitação. Agrupar casos apenas quando a pendência
  e seu contexto coincidirem; o detalhe por caso permanece acessível.
- **Recomendada com fonte:** seção separada, com valor, fonte, casos e revisão. Oferecer
  confirmar, editar ou deixar para revisão; aceitar todas exige ação explícita após
  mostrar o conjunto. Confirmar preserva origem recomendada e registra a revisão;
  editar registra origem usuário e preserva o valor/fonte anterior para auditoria.
- **Default com fonte:** identificado como default, com referência e indicação de escolha
  de projeto quando aplicável. Revisão não se confunde com disponibilidade numérica.
  Recomendações/defaults ainda não revisados podem produzir cálculo preliminar, como na
  F10b, mas seguem destacados no terminal, JSON e MC; nunca parecem confirmados.
- A coluna Origem apresenta balanço, correlação, recomendada, default ou usuário. Premissa
  do balanço mantém seu identificador; o rótulo de tela não elimina a classificação
  detalhada já exportada na F10b. Lacuna tem marcador próprio, sem número.
- Casos inativos mostram motivo, não pedem dados desnecessários e não governam o envelope.
  Os estados continuam dimensionado / aguardando entrada / inviável / inativo. Avisos
  de extrapolação e revisão são informações adicionais, não novos estados de viabilidade.

**4. Ajustes únicos, reaproveitamento e reprodução**

Um único estado de sessão, persistido em **`ajustes_pfd.toml`**, serve ao TAG isolado e ao
PFD. Ao abrir Planta, os ajustes feitos em um equipamento já estão aplicados; somente
pendências restantes são solicitadas. Nada é aplicado a outros TAGs implicitamente.

Propor um esquema versionado, com seções de contexto e TAGs, em vez de misturar metadados
com as tabelas de parâmetros hoje aceitas pela F10b:

| Conteúdo | Persistência proposta |
|---|---|
| Contexto | versão do esquema, SHA-256 do BOT, premissas alteradas, versões do pacote/ChEDL e identidade da configuração |
| Fonte por TAG | modo automático ou manual, método, identificação dos casos |
| Ajustes | valores gerais do TAG e valores específicos por caso; caso prevalece sobre geral; manter origem/valor/fonte substituídos |
| Revisões | confirmação por campo/caso com valor e fonte confirmados; independente da origem |
| Manual | entradas e atividade por caso dentro do mesmo arquivo, inclusive preenchimento parcial |

O leitor aceita os TOMLs legados da F10b (`["TAG"]` e `["TAG".caso."n"]`) como ajustes
automáticos sem revisões registradas; o escritor gera o novo formato canônico. O contrato
e a migração entram em `docs/esquemas/README.md`. O manual salvo de um TAG é respeitado
pelo PFD, sem novo autopreenchimento. O avulso pode ser associado explicitamente a um TAG
compatível; sem associação, não é transferido silenciosamente para a planta.

Ao editar, invalidar o resultado afetado e recalcular antes de exibi-lo como atual. Ao
trocar BOT/premissas, invalidar o balanço/propriedades/resultados automáticos dependentes.
Revisões cujo valor/fonte mudou voltam a pendentes. Incompatibilidade de hash, casos ou
método pede reconciliação explícita no terminal; no comando não interativo, erro de
contexto com diagnóstico, sem reaplicar ajustes silenciosamente.

Restaurar um campo automático remove seu ajuste e reaplica a regra com a origem original.
Sobrescritas de entradas finais do método não reescrevem o balanço: editar a premissa
de processo ou o insumo de propriedade correspondente é o caminho para recalcular seus
dependentes. Essa distinção aparece na ação de edição e no rastro.

**5. Subcomandos equivalentes**

Formas propostas (disponíveis desde a entrega; o avulso ganhou `--avulso`, ver Entregue):

```sh
# Um TAG: inicia pelo balanço e usa os ajustes daquele TAG.
fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --auto-balanco \
  --ajustes ajustes_pfd.toml --saida saida/tag

# Planta: mesmo fluxo por TAG; respeita modos/ajustes salvos, automático nos demais.
fpso-siz pfd --casos design_cases_bot.json \
  --ajustes ajustes_pfd.toml --saida saida/planta

# Retomar um TAG manual salvo; não usa o balanço para preencher esse TAG.
fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json \
  --ajustes ajustes_pfd.toml --saida saida/tag

# Preservar a entrada avulsa existente (TOML/exemplo).
fpso-siz dimensionar --exemplo alves_komesu --saida saida/exemplo
fpso-siz dimensionar --casos entradas.toml --equipamento knockout --saida saida/manual
```

Com `--tag`, `--casos` identifica o contexto BOT JSON. Sem `--tag`, mantém o TOML atual.
`--auto-balanco` seleciona o modo automático; sem ele, o TAG deve ter modo salvo no arquivo
de ajustes (legado F10b implica automático). Conflito com modo manual salvo, método ou
opções incompatíveis gera erro explícito; a troca de modo é uma decisão persistida.
`--exemplo` não se combina com `--tag`/`--auto-balanco`. `--premissa` segue disponível,
com a mesma validação de contexto nos dois comandos. Nenhum deles pede input em execução
não interativa. Códigos 0/1/2 mantêm os significados documentados na F10b.

A sessão exporta o arquivo único de ajustes e imprime o comando correspondente ao escopo
escolhido. Um JSON e CSV de varredura por TAG saem do serializador comum; o PFD apenas
acrescenta `planta.csv`. A exportação do mesmo TAG, pelo menu, comando isolado ou PFD,
deve ser **idêntica byte a byte** para o mesmo contexto e ajustes. Estado dos outros TAGs
não pode alterar seu artefato. A exportação dos ajustes também tem ordenação e números
determinísticos, sem timestamps ou caminhos de saída embutidos. Resultado parcial pode
ser salvo e reproduzido. A promessa é dos arquivos, não de prompts, cor ou tempo de execução.

**6. Representação no terminal**

Toda composição de telas/esquemas/tabelas fica em `output/terminal/`, inclusive para os
subcomandos. `cli.py` delega a apresentação. `config/interativo.toml` passa a declarar
menus, textos de ações/alertas, rótulos de estado/origem, legendas, ordem das colunas,
formatos Unicode/ASCII e prioridades em telas estreitas. Rótulos/unidades de parâmetros
continuam nos `ParameterSpec`; fontes permanecem no catálogo técnico, sem duplicação.
Migrar também os menus hoje fixos em `sessao.py`, pois o teste atual verifica nomes de
parâmetros, mas não assegura que textos e ordem venham da configuração.

A conectividade vem exclusivamente de `config/topologia_db.toml`, acessada pelo módulo
de topologia existente, e a associação bloco→TAG vem dos descritores de TAG. Misturadores,
reciclo, ambos os lados do trocador e saídas de fronteira são preservados. Bloco fora do
escopo de dimensionamento não recebe status inativo. Evitar um desenho fixo do FPSO em
código: renderizar linhas bloco/correntes a partir das adjacências, em ordem declarada.

Usar biblioteca padrão e a infraestrutura de estilo atual. Detectar capacidade da saída;
degradar setas, bordas, símbolos, acentos e unidades para ASCII seguro quando necessário.
Oferecer `--ascii` nos percursos de terminal e nos subcomandos relevantes para forçar o
modo. Cor é independente de Unicode, respeita `NO_COLOR`, pipes e `TERM=dumb`. Os estados
têm rótulos além de cor. Em terminal estreito, dividir o desenho em linhas e expandir
fontes longas em detalhe; nunca truncar TAG, corrente ou a identificação de uma pendência.

Exemplo de tela PFD (contexto real F10b, sem ajustes; cabeçalho OpenFOAM omitido aqui).
O desenho mostra conectividade; o estado entre colchetes é do envelope dos 16 casos:

```text
Planta / PFD · design_cases_bot.json · casos 1–16
2 dimensionados · 8 aguardando entrada · 1 inviável · 0 inativos

C-01, C-02  → [M-01   ·] → C-03
C-03        → [SG-001 X] → C-04 (saída), C-05 (saída), C-06
C-06, C-22  → [P-001  ?] → C-07, C-23
C-07        → [P-002  ?] → C-08
C-08        → [V-001  D] → C-09 (saída), C-10
C-10        → [TO-001 ?] → C-11, C-12
C-12        → [B-002  ?] → C-13
C-14        → [DWH-001·] → C-15
C-11, C-15  → [M-02   ·] → C-16
C-16        → [V-002  D] → C-17 (saída), C-18
C-18        → [TO-002 ?] → C-19, C-21
C-19        → [B-003  ?] → C-20
C-13, C-20  → [M-03   ·] → C-02 (retorno ao M-01)
C-21        → [B-001  ?] → C-22 (retorno ao P-001)
C-23        → [P-003  ?] → C-24
C-24        → [MED-001·] → C-25 (saída), C-26 (saída)

D dimensionado   ? aguardando entrada   X inviável   - inativo
· bloco sem dimensionamento; permanece no balanço

TAG     Caso governante         Resultado
V-001   BOT 08 — Mid Life       Diâmetro: 4850 mm
V-002   BOT 03 — Early Life Blend  Diâmetro: 4700 mm

1) Abrir um TAG   2) Preencher pendências   3) Exportar   0) Voltar
```

No desenho ASCII, `→` vira `->` e o marcador de bloco sem dimensionamento vira `.`;
os rótulos também degradam para ASCII. Um filtro por caso mostra, por exemplo, B-002/003
inativos no caso 1, sem confundir essa atividade com a viabilidade do envelope.

Exemplo da tela de um TAG (TO-001 antes de preencher a gotícula; filtro de entradas no
caso 1, pendências listadas para todos os casos ativos):

```text
TO-001 · Desidratador · casos 1–16 · aguardando entrada
                  ┌────────────────┐
V-001 ── C-10 ──→ │    TO-001 ?    │ ── C-11 ──→ M-02
                  └────────────────┘ ── C-12 ──→ B-002

! FALTA 1 ENTRADA, AFETANDO 16 CASOS ATIVOS
Chave      Entrada                         Unidade  Casos
dm_water   Gotícula após coalescência       µm       1–16
Valor: não informado; sem recomendação com fonte disponível.
Necessário: dado de coalescência/laboratório para este serviço.

RECOMENDADAS COM FONTE — REVISÃO PENDENTE
Entrada           Valor   Unidade  Casos  Origem       Fonte
Retenção óleo     20      min      1–16  recomendada  S&A Tab. 4.1, nota
Retenção água     10      min      1–16  recomendada  S&A §4.7.4
Fonte detalhada: óleo intermediário, limite superior ×2 pela emulsão.

ENTRADAS · caso 1 (trecho; as demais estão no detalhe)
Entrada           Valor   Unidade  Origem       Fonte
Vazão de água     0       m³/h     correlação   C-10: massa/ρ(T), Laliberté
Retenção óleo     20      min      recomendada  S&A Tab. 4.1, nota
Gotícula água     —       µm       lacuna       dado não informado

Aplicar preenchimento: 1) todos os casos afetados  2) escolher casos
Gotícula após coalescência [µm] (Enter adia): _
1) Confirmar recomendadas   2) Editar entradas   3) Salvar   0) Voltar
Dimensionamento pendente; nenhum resultado concluído é apresentado.
```

A tela real inclui a faixa do descritor e a referência completa em detalhe. Zero de vazão
existente não é lacuna nem torna o TAG inativo enquanto houver outra fase com vazão.
As folgas só aparecem após o cálculo, com o nome/unidade definidos pelo método.

**7. Gancho para o MC e critérios de aceite da F10c**

Recomendação: F10c entrega o fluxo e o contrato de dados; **a geração efetiva de MC fica
inteira na F11**. O resultado por TAG já reúne entradas, revisões, fontes, propriedades,
pendências e rastro do método. Preparar a conexão da ação de exportação a esse resultado,
sem templates provisórios nem uma segunda execução da física. Até a F11, a interface
informa que o memorial do equipamento ainda não está disponível; não oferece uma ação
que aparenta gerar um MC. Após a F11, a mesma tela oferece gerar LaTeX/PDF ao dimensionar.

Aceite proposto:

- Sessões roteirizadas: escolher TAG, automático, manual, importação, preenchimento parcial,
  editar por caso, restaurar, confirmar recomendações, redimensionar e retomar.
- Sequência equipamento → PFD → equipamento reutiliza exatamente entradas, revisões e
  resultados; trocar contexto invalida o que depende dele. Nenhum dado sem fonte é suposto.
- Teste de delegação: PFD e TAG isolado chamam o mesmo serviço; no PFD o balanço é
  reutilizado, e o TAG isolado não dimensiona os demais. Paridade numérica com a F10b,
  inclusive lacunas, casos inativos e SG-001 inviável, sem revisão implícita do método.
- Ida e volta do TOML versionado e leitura de legados; igualdade byte a byte dos arquivos
  da sessão e dos comandos equivalentes, inclusive modos mistos manual/automático,
  pendências salvas e recomendações não revisadas.
- Snapshots do menu, PFD, esquema local, entradas/Origem, pendências, recomendações e
  resultado/folga: Unicode, ASCII, terminal estreito e saída sem cor. Cor com teste
  próprio; conteúdo/estados não dependem dela. Fixtures incluem os quatro estados.
- Validar arestas dos esquemas contra a topologia, não apenas sua aparência. Teste com
  TAGs/correntes renomeados e ordem alterada em configuração: a tela deve acompanhar;
  verificar também reciclo, fronteiras e trocador com dois lados.
- Expandir arquitetura: proibir TAGs/correntes fixos e montagem de entradas nos módulos
  de interface; verificar ids/textos/ordem dos menus contra o TOML; manter a separação
  núcleo/saída e as portas `_num.py` e `pfd/_chedl.py`. Sem dependências novas.
- Suíte completa verde e cobertura ≥ 90 % no núcleo, incluindo os serviços novos.
  Preservar paridade bit a bit do balanço e fixtures Julia. Registrar a validação, esquema
  de exportação e números finais em docs e neste backlog.

Arquivos previstos após aprovação: `pfd/{equipamento,entradas,planta}.py`, adaptador manual
e persistência de ajustes; `cli.py`; `output/{dimensionamento,pfd}.py`;
`output/terminal/{sessao,pfd,relatorio,estilo}.py` e renderizador de esquemas;
`config/interativo.toml`; testes de integração, arquitetura e snapshots. A topologia é
lida, não redesenhada. Atualizar o ADR 0002 para refletir esta proposta quando aprovada;
as entregas F10a/b continuam registradas como histórico.

**Entregue (2026-09-23).** Commit: `d51782c`.
- Núcleo: `pfd/equipamento.py` (Contexto com balanço único e cache por estado; preparar,
  dimensionar, executar), `pfd/manual.py` (arquivo/exemplo → importados; avulso;
  associação), `pfd/ajustes.py` (EstadoTAG/Ajustes, esquema 2, legado F10b, contexto),
  `pfd/entradas.py` com o adaptador manual, revisões, substituídos, faixas e dependentes
  das lacunas; `pfd/planta.py` percorre o serviço.
- Saída: `output/pfd.py` (serializador por TAG, sem depender da planta; JSON esquema 2 e
  `<TAG>_varredura.csv`), `output/ajustes.py` (TOML determinístico),
  `output/terminal/{esquema,pfd,sessao,estilo,relatorio}.py`; menus, textos, rótulos,
  colunas com prioridade e tabelas Unicode/ASCII em `config/interativo.toml`.
- CLI: `dimensionar --tag/--auto-balanco/--ajustes/--premissa/--avulso`, `pfd --ajustes`
  (esquema 2 ou legado), `interativo --ajustes`, `--ascii`. `dimensionar --exemplo/--casos`
  segue no contrato do Julia, com bytes idênticos aos da F7b.
- Verificação: fixture `tests/fixtures/pfd/f10b_resultados.json` (gerada pelo código da
  F10b via `git archive`) — estados, lacunas, valores, envelopes, folgas e `planta.csv`
  iguais; 4.128 valores e os envelopes conferidos também contra a saída direta da F10b.
  Delegação espionada (11 TAGs com um balanço; TAG isolado sozinho), cache e invalidação,
  manual sem balanço/ChEDL, ida e volta do TOML, sessões roteirizadas (automático, manual
  parcial e retomada, importação por nome, edição por caso, restauração, revisão,
  equipamento → PFD → equipamento, troca de premissa e de BOT, reconciliação, avulso),
  igualdade byte a byte sessão × comando × PFD em modos mistos, snapshots (Unicode,
  ASCII, estreita, sem cor; os quatro estados), esquemas relidos contra a topologia (e
  renomeada/reordenada) e testes de arquitetura novos (sem TAG/corrente fixos nem
  montagem de entradas na interface; textos e menus só no TOML; serviço no núcleo).
- **783 testes (+2 `-m latex`, +1 `-m julia`), cobertura de 96,86 %** (`pfd/` 96–100 %).
  Balanço, memoriais e fixtures Julia inalterados.
- Desvios e decisões (detalhes em `docs/validacao/10-fluxo-tag.md`): `--avulso` para
  reproduzir o avulso; conta impossível (erro de domínio) vira inviabilidade no serviço,
  sem mexer no motor; no manual a atividade vem do usuário e das regras de vazão (a de
  carga térmica depende do balanço); faixas [mín, máx] só no manual; importação casa
  casos pelo nome; a grade do catálogo (F10b) deixa o exemplo de knockout do Julia
  inviável como avulso (passo de 150 mm fora da banda de SR) — registrado, sem revisão de
  física. ADR 0002, `docs/esquemas/README.md` e `CLAUDE.md` atualizados.

**Notas para a F11:**
- O gerador consome `ResultadoTAG` (`entradas`, `resultado`, `estado`) e o `Contexto`:
  entradas com origem/fonte/`revisao`/`anterior`, lacunas com `dependentes`,
  `revisoes()`, rastro por caso (blocos "entradas" e "propriedades") e o rastro do método
  por caso no envelope. O JSON por TAG já tem os mesmos dados; o MC deve reproduzir os
  mesmos valores.
- A tela do TAG mostra só a nota "Memorial … previsto na F11"
  (`textos.memorial_indisponivel`); a ação entra no menu `tag` do `interativo.toml` e no
  `DESPACHO` da sessão. `--mc [--pdf]` entra em `dimensionar --tag` e `pfd`.
- Relatório de pendências/diagnóstico: `status` aguardando/inviável/inativo e
  `preliminar` já distinguem os casos.

### F10v — Verificação física do balanço e premissa "sem fase aquosa" (P-42) ✅

Fase extra, aprovada em 2026-09-25 (plano "verificação rigorosa"). Pedido: o FPSO "parecia
não ter água saindo"; revisar premissas e validade numérica. Decisões do usuário: balanço
só verificado (nenhum número muda); sal do óleo tratado na base do volume da emulsão;
premissa P-42 — "nenhuma água fictícia; BOT 2.3.1.1 é limite superior (BSW_saída =
min(BSW_entrada; especificação)); nos casos 1 e 4–7 as correntes aquosas do FWKO, TO-001 e
TO-002 são nulas e o reciclo (Nota 11) é de óleo; critérios aquosos retornam 'não aplicável
— sem fase aquosa', sem exceção e sem governar o envelope; a fase aquosa é dimensionada
pelos casos com água; o FWKO sempre deixa água no óleo; só o TO-002 chega à especificação".

**Entregue (2026-09-25).** Commit: ver `git log` ("F10v: …").
- Núcleo: `balanco/indicadores.{balanco_agua, verificacao_fisica, bsw, sal_real_mgL}` com
  `config/verificacao_balanco.toml`; `sizing/vasos.sem_fase_aquosa` (mecanismo
  `sem_fase_aquosa`), separador e tratador sem bloco de decantação quando Qw = 0 e Qo > 0
  (capacidades idênticas às da forma geral); `pfd/entradas._fase_aquosa` com
  `config/pfd/metodos.toml [<método>.fase_aquosa]` e a origem `nao_aplicavel`.
- Saída: linhas de água/BSW/sal/T do FWKO no resumo do balanço (interativo e
  `fpso-siz balanco`); "Ver correntes" abre no primeiro caso com água; P-42 na tabela de
  premissas e no apêndice de rastreabilidade do memorial `senai` (o `original` segue byte a
  byte o script de referência); `docs/esquemas/README.md` documenta `nao_aplicavel`.
- Verificação: balanço e oráculo inalterados; fixtures do Julia intactas (nenhuma tem
  `q_water = 0`); a regressão F10b roda com a P-42 desligada e reproduz a fixture, e
  `test_efeito_da_p42_restrito_a_fase_aquosa` prova que só SG-001/TO-001/TO-002 mudam, só
  em `dm_water`/`dm_oil`/`tr_water` dos casos 1 e 4–7, e o teto do SG-001 (caso 6, 1635 mm
  → caso 2, 4434 mm; continua inviável). **802 testes (+2 `-m latex`, +1 `-m julia`),
  cobertura de 96,92 %.**
- Achados documentados (sem mudar número): diluição superdimensionada 0,5–36,7 % (sal real
  × S_W); FWKO a 35 °C nos casos 5–6 (reciclo de óleo da Nota 11 não modelado, P-41);
  Standing usado com γ 0,81–1,22 e fonte fora do acervo; cp_W −1 a −2 % frente a Laliberté;
  gás seco, cp constante, sem calor de flash; resíduo de −2,2e-16 kg/s de gás (1 ulp).
- Desvio do plano: a fixture `f10b_resultados.json` não foi reescrita (regressão com a P-42
  desligada + teste do efeito restrito), o que preserva a proveniência da F10b.

**Notas para a F11:** o MC por TAG deve citar a P-42 (texto em `premissas_memorial.toml`) e
mostrar o mecanismo "não aplicável — sem fase aquosa" nos casos sem água. Propostas em
aberto, cada uma com aprovação própria: M1 (diluição com o sal real), M2 (reciclo de óleo
nos casos 5–6), M3 (fração de reciclo da água tratada), fonte de Standing no acervo e a
premissa que resolva o SG-001 no caso 2.

### F10w — Eficiência de água livre do SG-001 (P-43) ✅

Fase extra, aprovada em 2026-09-25. Pedido: "a eficiência média do separador é uma premissa
que costuma ficar entre 80 % e 90 %; utilize 85 %, editável pelo usuário; redimensione os
cálculos". Decisões do usuário:
- η_A do SG-001 = máx(η_padrão; η_req), com η_padrão = 0,85 em config (P-43, "premissa do
  autor", sem referência bibliográfica);
- η_req = 1 − [BSW_lim/(1 − BSW_lim)]·Q_O/Q_A,e, com BSW_lim = 0,40 (BOT 2.7.1.2), calculado
  no laço com Q_A,e incluindo reciclo e diluição;
- quando η_req > η_padrão, isso é registrado no resultado e no memorial, como estado;
- a regra mín(40 %; BSW) do oráculo fica como modo de paridade;
- a tabela dos 16 casos foi confirmada antes de atualizar testes e oráculo;
- na comparação entram a carga do pré-aquecedor e a carga térmica total dos casos 2, 8, 9
  e 11;
- no memorial `senai`, η_req com a substituição do caso 15 (0,924) e a nota de que
  η_req < η_padrão é diagnóstico.

**Entregue (2026-09-25).** Commit: ver `git log` ("F10w: …").
- **Núcleo:**
  - `balanco/propriedades.split_eficiencia`;
  - `balanco/modelo` (`regra_fwko`: `eficiencia` padrão, `referencia` = paridade; estado
    `ResultadoCaso.fwko`);
  - auditoria `eficiencia_fwko` (independente, 3,3e-16);
  - sensibilidade na regra dos resultados, com η_padrão de 80 % e 90 %;
  - verificação física por regra;
  - `FWKO` no `balanco.json`;
  - `--regra-fwko` em `fpso-siz balanco`.
- **Configuração:** P-43 (`eta_F`) em `premissas.toml`; `constantes.toml [modelo]`; catálogo
  de equações com `regra`/`memorial_regra` (`eficiencia_fwko` ↔ `eq:etaF`).
- **Memorial:**
  - o `original` é sempre gerado na regra de referência (byte a byte igual ao script);
  - o `senai` traz a equação de η_req, a substituição do caso 15, o diagnóstico, os casos
    exigidos (15 e 16), a P-43 e a P-24 derivada;
  - as seções de eficiências, M-03, sensibilidade, fechamento e informações seguem a regra.
- **Testes:**
  - os de paridade (oráculo, PFD F1 do Julia, F10b) rodam na regra de referência;
  - regressão nova `tests/fixtures/python_ref/regressao_eficiencia.json`
    (`tools/gerar_regressao_eficiencia.py`, determinística);
  - `tests/balanco/test_eficiencia_fwko.py` fixa a tabela confirmada;
  - snapshots regenerados (V-001 4700 mm; SG-001 com teto de 3612 mm).
- **Resultados:**
  - a água produzida que sai pela C-05 e a diluição não mudam;
  - menos água passa pelo aquecedor, pelo TO-001 e pelo reciclo;
  - Q_H (P-002 + DWH-001): −3.671, −8.363, −5.064 e −1.197 kW nos casos 2, 8, 9 e 11;
  - Q_C (P-003) cai o que o P-001 passa a recuperar: −2.204, −2.905, −1.286 e −143 kW.
- **Rev. 0 do MC-SEN-SEP-COO-001:** não cita dimensões de TAG. No layout `senai` mudam os
  critérios e envelopes listados no relatório (entre eles o líquido em C-10 do V-001, que
  leva o V-001 de 4850 a 4700 mm); o `original` não muda.
- **Pendência (aberta):** a η_A do SG-001 (P-43) não é sustentada pela geometria nos casos 2
  e 3. O SG-001 é inviável, com teto de 3612 mm no caso 2 e de 4877 mm no caso 3, porque a
  eficiência reduz o reciclo quente e esfria a entrada do FWKO (56,4 → 52,7 °C no caso 2;
  56,8 → 52,9 °C no caso 3). Exige decisão de projeto com fonte (entrada mais quente,
  gotícula/retenção, trens em paralelo ou η menor nesses casos).
- **Números:** **814 testes (+2 `-m latex`, +1 `-m julia`), cobertura de 96,95 %.**
- **Complemento (terceiro commit da série):**
  - `balanco.json` no esquema 2: `cargas.Q_H` = P-002 + DWH-001, `cargas.Q_C` = P-003 e um
    campo por trocador pelo TAG. Os testes de paridade conferem o Q_H antigo no campo do
    P-002.
  - Nos casos 1 e 4–7, η do SG-001 = `null` com o estado "não aplicável — sem fase aquosa"
    no JSON, e "—" na tabela de η por caso do memorial `senai`.

**Notas para a F11:** o MC por TAG deve citar a P-43 e o estado `exigido_acima` do SG-001. A
regra do FWKO muda as entradas do PFD, por isso o memorial de cada TAG deve dizer qual
regra de balanço usou.

### F11 — MC por equipamento/TAG, ligado ao mesmo fluxo ✅

**Preparação (2026-09-26; implementação ainda não iniciada):** diagnóstico no branch
`fases/f11`, base `73f7ca3`; 814 testes + 2 de compilação (`original`/`senai`) + 1 de
regeneração Julia aprovados, cobertura global com ramos de 96,95% e de linhas do núcleo
de 98,69%. O utilitário `tools/comparar_memorial.py` falha por comparar templates com
o contexto de eficiência contra o original; o teste do documento completo original
passa byte a byte. `pendencias_propostas.toml` não foi localizado; nenhum valor foi
incorporado. Minutas de MC viável e diagnóstico, estados dos 11 TAGs, evidências e
recomendações em [`docs/validacao/f11-preparacao.md`](docs/validacao/f11-preparacao.md).
**Próximo portão:** confirmação do formato documental apresentado, conforme o pedido
atual. Nenhum template, snapshot ou caso-ouro novo foi fixado; nenhuma fase posterior
foi iniciada. Preparação sem commit de entrega e sem integração.

**Aguardando aprovação própria.** Mesmo pipeline LaTeX A4 da F4, template SENAI e conteúdo
de referência em `src/memorial_specs/` do Julia. Cada gerador consome o resultado do serviço
por TAG da F10c, com os mesmos valores exportados em JSON/CSV; o template só apresenta.

Ao terminar um dimensionamento, oferecer **Gerar memorial de cálculo** no menu do TAG.
No PFD, oferecer geração para os TAGs selecionados usando o mesmo gerador em laço.
Equivalente proposto: acrescentar `--mc [--pdf]` ao `dimensionar --tag ...` e ao `pfd`;
`--saida` obrigatório para gravar, `--pdf` exige `--mc`. O comando impresso inclui contexto,
ajustes e formato. O memorial do balanço mantém seu comando e sua paridade.

Conteúdo por TAG: identificação e esquema de correntes; casos ativos/inativos e motivo;
entradas com origem, fonte e revisões; valores anteriores às sobrescritas; propriedades
com equações, hipóteses, versões e avisos; lacunas/recomendações/defaults não revisados;
resultado, governante, folga, inviabilidade e rastro. O manual também é rastreável, sem
atribuir ao balanço valores informados pelo usuário.

Com entradas completas e resultado viável, gerar MC de dimensionamento, marcando revisão
pendente quando aplicável. Se houver lacunas, inviabilidade ou inatividade, permitir
**relatório de pendências/diagnóstico**, identificado como tal, sem conclusão de
dimensionamento nem dimensões fictícias. Recomendações não revisadas não desaparecem
do documento só porque o cálculo conseguiu terminar.

Aceite proposto: memorial A4 compilável para os métodos já disponíveis e para cada um dos
11 TAGs; casos manual/automático e diagnósticos exercitados; bijeção equação↔rastro testada;
valores coincidentes entre terminal, JSON, CSV e MC; geração por TAG e em lote usa o mesmo
resultado. LaTeX e dados devem reproduzir bytes sob contexto fixado. PDF exige também
toolchain e metadados determinísticos fixados na F11 antes de prometer igualdade binária.
Testes `-m latex` compilam os documentos; cobertura ≥ 90 % no núcleo e arquiteturas verdes.
Pinch/Song recebem seus memoriais quando seus métodos forem portados nas fases seguintes.

**Entregue (2026-09-26, sessão autônoma; execução autorizada no pedido, decisões em
[`docs/validacao/f11-decisoes.md`](docs/validacao/f11-decisoes.md)).** Commits F11.1–F11.5
(`edf8fff`, `032c42b`, `ebc99b2`, `4435f17`, `012515a`); retomada em
[`f11-checkpoint.md`](docs/validacao/f11-checkpoint.md).
- Núcleo: `Rastro.operandos`/`Rastro.iteracoes` (operandos capturados na avaliação, fora de
  `entries`: projeção e fixtures do Julia inalteradas); `pfd/memorial.py` (as dez seções do
  MC como dados); hooks de vaso `selecao_memorial`, `lss_candidatos`, `bordas_banda`;
  constantes de campo de S&A convertidas em `core/unidades.py`.
- `config/memorial_tag.toml`: numeração fixa pela sequência de processo (SG-001 001 … P-003
  011, `MC-SEN-SEP-EQP-NNN-0`, Rev. 0), conteúdo por método (objetivo, referências,
  hipóteses, equações com `@operando@`, colunas, gráficos).
- `output/latex/tag`: A4/SENAI, 4 algarismos significativos (regra declarada), pgfplots
  lendo CSV gravados pelo mesmo comando (diagrama d × Leff com capacidades, banda de SR,
  ponto escolhido/teto/menor d na banda; critério governante por caso; teto por caso), JSON
  do documento.
- V-001/V-002 com passo a passo completo (caso 3); SG-001 com diagnóstico (teto 3.612 mm no
  caso 2 × menor d na banda 5.600 mm); TO/P/B "aguardando entrada" com as lacunas do `pfd`.
- `dimensionar --tag X --mc [--pdf] [--data]`, `pfd --mc [--pdf]` → `<saida>/mc/<número>/`
  (isolado = lote, byte a byte); ações no menu do TAG e da planta no modo interativo.
- `tools/comparar_memorial.py` corrigido (IDÊNTICO).
- **872 testes (+33 `-m latex`), cobertura 96,72 % global (ramos) e 98,66 % no núcleo**
  (5 testes pulados na nuvem: acervo `references/` ausente). Paridade: memorial original
  byte a byte, fixtures do Julia (bit a bit/≤1e-13) e regressão da eficiência intactos. O
  `-m julia` (regeneração) não rodou na nuvem (repositório Julia inacessível).

### F11b — MC do balanço por caso (MC_Caso01 … MC_Caso16) ✅

Pedido na mesma sessão autônoma. **Entregue (2026-09-26)**, commit `87bd36b`.
`memorial --caso N|lista|todos` e `memorial --casos todos` → `MC_CasoNN` (anexo
`MC-SEN-SEP-COO-CNN-0`) nos layouts `original` e `senai` (padrão: os dois). Folha de rosto
com commit, regra do FWKO, premissas diferentes do padrão e data; "—" nas grandezas da fase
aquosa dos casos 1 e 4–7 (P-42). Ação no menu do balanço iterando os casos. Isolado × lote:
`.tex` byte a byte e texto do PDF iguais; os 32 PDFs compilam.

### F10x — Preenchimento das pendências de entrada com os valores propostos ✅
Carregar os valores do `pendencias_propostas.toml` do usuário (em `docs/propostas/`, com
`status = "proposto"`) como entradas dos TAGs aguardando entrada (TO: gotícula após
coalescência; P: condutividades, incrustações, temperaturas da utilidade; B: arranjo,
singularidades, NPSHr e margem), cada um com a fonte citável ou marcado "valor usual — sem
fonte rastreável", sem alterar o balanço. **O arquivo não foi anexado nesta sessão** (não há
`docs/propostas/`); nenhum valor foi carregado.
**Aceite:** (1) cada valor carregado tem origem `usuario`/`arquivo` e fonte (ou a marca "sem
fonte rastreável") no JSON, no terminal e no MC; (2) só valores com `status` promovido pelo
usuário entram no cálculo (teste que prova que `proposto` é recusado); (3) os 11 TAGs
dimensionam ou ficam inviáveis com diagnóstico, sem lacuna; (4) o MC de TO, P e B passa a ter
passo a passo (equações declaradas em `memorial_tag.toml`) e os gráficos de trocador (T × Q,
parcelas de U) e de bomba (curva do sistema, NPSHd × NPSHr por caso); (5) balanço, oráculo e
fixtures do Julia inalterados; cobertura ≥ 90 % no núcleo.

**Entregue (2026-09-26, aprovada pelo usuário: "continue com as fases por etapas").**
Commits `de962eb` (F10x.1), `04f0139` (F10x.2), `f807387` (F10x.3).
- F10x.1: gráficos de trocador (perfil T × Q, parcelas de 1/U) e de bomba (curva do sistema,
  NPSH disponível × requerido por caso), pelos hooks do método (mesma física).
- F10x.2: `docs/propostas/pendencias_propostas.toml` com as 43 lacunas do inventário, todas
  `status = "proposto"`, origem "proposta do usuário" e justificativa física, sem referência
  atribuída ao número; carga validada (`pfd/propostas.py`: esquema, campos, tipo, unidade,
  faixa, limite, status, duplicidade, casos); origem própria `proposta` (revisão pendente),
  separada dos valores com fonte e dos calculados; `--propostas` em `dimensionar`, `pfd` e
  `interativo`; tabela "Valores PROPOSTOS, a confirmar" no MC. Sem `--propostas` nada muda.
- F10x.3: MC próprio de cada TAG (função no processo, correntes do bloco com T e P, hipóteses do
  TAG; premissas no texto vêm de P[...]); sem texto de vaso em bomba e trocador.
- F10x.4 (`ca1f901`, decisão do usuário: "pode seguir com os valores propostos; para mudar, só
  selecionar a opção e editar"): `pendencias_propostas.toml` em `config/pfd/`, carregado por
  padrão na CLI e no interativo (`--propostas ARQ` troca, `--sem-propostas` desliga); a edição
  no interativo vira entrada do usuário e prevalece. A biblioteca (`Contexto`) segue sem
  propostas se nada for passado.
- F10x.5 (pedido do usuário: "corrija a viscosidade para o valor real"): **viscosidade de óleo
  vivo** por Beggs & Robinson (1975) sobre o óleo morto do BOT, com o Rs da corrente vindo do
  balanço (Q_G/Q_O padrão, Standing), aplicada só dentro da faixa de Rs da correlação (abaixo
  dela fica o óleo morto medido, com aviso). É o padrão; `--oleo-morto` volta ao modo anterior,
  que é o das fixtures do Julia e da F10b. Efeito: **o SG-001 passa a ser viável** (D = 6.050 mm,
  SR 3,94; teto do caso 2 de 3.612 para 6.257 mm) e o Re do óleo no P-002 sobe (1.876–5.588, que
  continua fora de Dittus-Boelter). Os demais TAGs não mudam (correntes desgaseificadas).
  Justificativa e tabelas em [`docs/validacao/16-oleo-vivo.md`](docs/validacao/16-oleo-vivo.md).
  A correlação está fora do acervo local (a conferir).
- F10x.6 (aprovada pelo usuário: "a proposta da bomba pode prosseguir como aprovada"): **P-44**,
  banda de velocidade das bombas pelo caso de projeto (maior vazão). O piso vale só nele, e só
  em água (o B-001, de óleo limpo, tem piso nulo); o teto vale em todos os casos. A **P-44b**
  (a confirmar) aceita, nos casos de turndown, a zona de transição com o f de Colebrook-White
  como limite superior. Hook genérico `envelope_case_params` no motor; os defaults são a regra
  do Julia. Efeito: B-001 DN 600, B-002 DN 250, B-003 DN 125, os três viáveis. O MC da bomba
  ganha a tabela de operação por caso e a potência máxima (no B-002, 140 kW contra os 14 kW do
  caso governante). Ver [`docs/validacao/17-banda-bombas.md`](docs/validacao/17-banda-bombas.md).
- Com as propostas: TO-001/TO-002 dimensionam (d = 5.550 mm); bombas e trocadores seguem
  inviáveis — tratados como alarme na F13.
- **Aceite:** (1) ✓; (2) ✓ (só `proposto` entra); (3) parcial — os TAGs ficam sem lacuna, mas
  bombas/trocadores/SG-001 inviáveis (alarmes F13); (4) gráficos ✓, passo a passo com
  substituição só nos vasos (bomba/trocador: rastro em tabela); (5) ✓; cobertura ✓.

### F13 — Contrato de propriedades + alarmes de inviabilidade (estudo do SG-001) ✅
Formalizar o contrato das propriedades de fluido consumidas pelos métodos (unidade, condição,
correlação, faixa de validade e fonte, por grandeza) e estudar as alternativas para a
inviabilidade do SG-001 (entrada mais quente, gotícula/retenção, trens em paralelo, η menor
nos casos 2 e 3), cada uma com fonte.
**Aceite:** (1) um descritor de propriedade por grandeza, testado contra `pfd/fluidos.py`, sem
mudar número; (2) estudo em `docs/validacao/` com a tabela de alternativas × teto × menor d na
banda, para os 16 casos, gerado pelo mesmo motor; (3) nenhuma premissa nova entra no cálculo
padrão sem aprovação do usuário; (4) o MC do SG-001 cita o estudo.

**Entregue (2026-09-26).** Diretriz do usuário: a unidade do BOT é um projeto básico real;
TAG sem equipamento que atenda é **alarme** de erro de premissa, numérico ou de modelo, com
anotação e investigação.
- `config/pfd/contrato_propriedades.toml` + `pfd/contrato.py`: um descritor por grandeza de
  fluido (regra, unidade, condição, função, fonte, validade), conferido contra o código.
- `config/pfd/alarmes.toml` + `pfd/investigacao.py`: hipóteses por TAG inviável e variantes
  executáveis pelo mesmo motor (η 0,80/0,90 da faixa do usuário, trens em paralelo, 1 passe,
  sem piso de velocidade), sem mudar o cálculo padrão; seção ALARME no MC; estado "inviável —
  ALARME" no terminal; relatório gerado `docs/validacao/14-alarmes.md`
  (`tools/investigar_alarmes.py`).
- Achados (com óleo morto; ver F10x.5 para o óleo vivo, que explica o SG-001): SG-001 inviável só nos casos 2 e 3; conta do teto refeita do rastro sem erro numérico;
  nenhuma variante rastreável resolve (3 trens: SR no teto 6,8 > 5) → premissas suspeitas
  (viscosidade de óleo morto; critério de 500 µm aplicado ao FWKO). Trocadores: óleo laminar no
  tubo, fora de Dittus-Boelter (falta correlação laminar no acervo; P-001 com 1 passe chega ao
  mesmo limite). Bombas: faixa de vazão de 10–23× entre casos numa linha só; B-002 casos 15–16
  no vão da série de DN para a banda 1–1,5 m/s.
- BOT versionado em `docs/bot/` (a pedido do usuário) e conferido nos itens citados.
- **F13.2 (2026-09-26): trocadores com outra alocação de fluidos.** Variantes de topologia
  executáveis (`config/pfd/variantes/*.toml`, `pfd/tags.topologia_alternativa`,
  `equipamento.preparar_tag`) que não entram na planta. Também entraram a regra
  `densidade_utilidade` e o ΔT de processo por corrente em `vazao_utilidade`. Com o óleo no
  casco e a água nos tubos, P-002 e P-003 deixam de ser recusados pela faixa de Dittus-Boelter.
  O que resta:
  - P-002: tubo de 7,08 m contra o limite de estoque de 6 m;
  - P-003: casco acima de 2.500 mm, o que pede cascos em paralelo;
  - nos dois: a banda de velocidade exigida em todos os casos (turndown, como nas bombas antes
    da P-44);
  - P-001 (óleo/óleo): segue sem correlação laminar no tubo.

  O padrão não mudou: a alocação é decisão do usuário.
- **Aceite:** (1) ✓; (2) estudo em `docs/validacao/14-alarmes.md` gerado pelo motor ✓; (3) ✓
  nenhuma premissa nova no padrão; (4) o MC do SG-001 cita a investigação ✓.

### F14 — Termodinâmica preliminar com `thermo` e IAPWS ✅
Flash e propriedades de óleo vivo/gás dissolvido (Bo, Rs, calor de flash) por `thermo`
(ChEDL, só via `pfd/_chedl.py`) e água/vapor por `iapws`, em camada a jusante do balanço.
**Aceite:** (1) `iapws` atrás de uma porta única, com teste de arquitetura; (2) comparação
com o balanço preliminar (gás seco, cp constante) caso a caso em `docs/validacao/`, sem mudar
o balanço nem a paridade; (3) cada propriedade no rastro com a fonte e a faixa de validade;
(4) cobertura ≥ 90 % no núcleo.

**Entregue (2026-09-26).** `pfd/termodinamica.py` + `config/pfd/termodinamica.toml` +
relatório gerado `docs/validacao/15-termodinamica.md` (`tools/termodinamica_preliminar.py`).
- IAPWS via `chemicals` (IAPWS-95/2008/2011, as mesmas normas do pacote `iapws`), atrás da
  porta única `pfd/_chedl.py`: nenhuma dependência nova.
- Balanço × ChEDL, caso a caso, sem alterar o balanço: cp aquoso −2,0 a +0,2 % de Laliberté;
  cp do gás (ideal a 25 °C) 9–15 % abaixo da EOS de Peng-Robinson na condição dos vasos; Z do
  gás no FWKO ≈ 0,93; efeito do cp aquoso na carga do P-002 < 2 %.
- Lacunas de caracterização (sem fonte): Tc/Pc/ω do C20+ (o BOT só dá MW e densidade; as
  correlações do ChEDL pedem Tb) → sem flash do fluido de poço, calor de flash, Rs/Bo pela EOS
  nem viscosidade de óleo vivo (hipótese do alarme do SG-001).
- **Aceite:** (1) porta única (teste de arquitetura existente, `_chedl.py`) ✓; (2) comparação
  caso a caso sem mudar balanço/paridade ✓; (3) fontes no relatório ✓; (4) cobertura ✓.

### F15 — Otimização com `pymoo` (só planejamento) ✅ (planejamento)
**Entregue (2026-09-26):** `docs/decisoes/0003-otimizacao-pymoo.md` — variáveis com limites de
origem declarada, objetivos, restrições como estado, NSGA-II/III, porta única `_otim.py`,
critério de validação; **pré-condição: nenhum alarme aberto** (docs/validacao/14-alarmes.md).
Nenhuma dependência instalada.
Planejar a otimização multiobjetivo do módulo (volume dos vasos, cargas térmicas, área dos
trocadores) sobre o motor de envelope, com `pymoo`.
**Aceite do planejamento:** documento em `docs/decisoes/` com variáveis de decisão (e de onde
vêm os limites), objetivos, restrições (as do contrato de dimensionamento, como estado),
algoritmo (NSGA-II/III) justificado, a porta única para `pymoo` e o critério de validação;
nenhuma dependência nova instalada sem aprovação.

### F12 — Portabilidade (Java/C) e distribuição
Baseline medido com Nuitka/PyInstaller (tamanho, startup, deps) no Linux e passos para
Windows. Comparativo Python empacotado × Java (JVM/GraalVM) × C por módulo, com o mapa de
`_num.py`. Pode ser antecipada para logo depois da F5.
**Aceite:** `docs/portabilidade/` responde que problema cada linguagem resolve e que o
Python empacotado não resolve.
