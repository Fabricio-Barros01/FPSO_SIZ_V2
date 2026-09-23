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

**FASE ATUAL: F3 — Auditoria independente, saídas estruturadas e CLI ← ATUAL (aguardando aprovação)**

F0, F1 e F2 entregues. O motor do balanço (`fpso_siz.balanco`) reproduz o script original
**bit a bit** nos 16 casos e nas 24 sensibilidades (ver `docs/validacao/01-motor-balanco.md`).
São 113 testes e cobertura de 100 %.

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
- Comandos: `uv run pytest`, `uv run pytest --cov=fpso_siz --cov-fail-under=90`.

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
agora exposto (`residuo_reciclo`, `convergiu`). CalcTrace com 27 equações e 52 pares por
caso, com bijeção testada. Invariantes 1–2 testadas por AST. 113 testes, cobertura de 100 %.
O wheel inclui os TOML. **Desvio:** os TOML do modelo ficam em `src/fpso_siz/config/`, não
em `config/` na raiz, por causa da distribuição.
**Notas para a F3:** a auditoria deve reproduzir `oraculo["auditoria"]` (16 verificações);
os envelopes e críticos têm os valores em `oraculo["criticos"]`, e seus textos
formatados vão para a F4.

### F3 — Auditoria independente, saídas estruturadas e CLI ← ATUAL
`balanco/auditoria.py` não importa `modelo`. Esquema JSON/CSV documentado. CLI
`fpso-siz balanco --casos <json> --saida <dir>`.
**Aceite:** auditoria idêntica à F1; esquemas validados; invariante 4 testada; cobertura ≥ 90 %.

### F4 — Memorial LaTeX do balanço
Seções 1–18 e apêndices em templates jinja2 com o template SENAI; os dados vêm só de
ResultField/CalcTrace.
**Aceite:** `diff` do `main.tex` contra o original vazio ou com lista branca documentada;
`latexmk` compila; bijeção equação↔rastro testada (invariante 3).

### F5 — Contrato do núcleo + fixtures Julia
`core/` espelhando `interfaces.jl`, `engine/{contract,envelope,single}.jl` e `types/` do
Julia. `tools/exportar_fixtures_julia.jl` roda sobre um `git archive ab58fc6` extraído em
pasta temporária (o repo Julia não é tocado) e grava em `tests/fixtures/julia/`, com o hash
do commit.
**Aceite:** 4 invariantes testadas; envelope validado com um método-brinquedo; fixtures
reproduzíveis.

### F6 — Vasos (separador 3F, knockout, tratador)
**Aceite:** `golden_alves_komesu` (d = 6300 mm, Leff = 18,59 m, Lss = 24,78 m, SR = 3,93;
governa "Fim de vida"; teto de decantação 9124 mm), `golden_knockout` e `treater` com as
tolerâncias Julia; cobertura ≥ 90 %.

### F7 — Bomba (Moran) + trocador (Saari/Bell-Delaware)
**Aceite:** `golden_moran`, `golden_saari`; cobertura ≥ 90 %.

### F8 — Pinch (Kemp)
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
