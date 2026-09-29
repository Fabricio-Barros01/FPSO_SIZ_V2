# Auditoria da release do TCC — FPSO_SIZ_V2

> **RELEASE TCC: PENDENTE DE VERIFICAÇÃO LATEX**
>
> Os 24 testes que compilam os memoriais em LaTeX não rodaram nesta auditoria (o contêiner não
> tem `latexmk`/`pdflatex`/`pdftotext`). A release só pode receber status final depois de
> `uv run pytest -m latex` passar no ambiente Nix (`nix develop`). Nenhuma tag foi criada.

## 1. Identidade

| item | valor |
|---|---|
| baseline físico congelado | `b638c193e97450ac563aa5c5099ec3f2a6242e74` (`main`, merge do PR #9) |
| branch da auditoria | `claude/tcc-release-audit` |
| alterações de física | **nenhuma** — só documentação, comentários, textos de fonte e uma docstring |
| entrada auditada | `tests/fixtures/python_ref/design_cases_bot.json`, sha256 `ca3dfe559b32926c9d9ca4d9e75e2cec711f00f7fdfd2247242bbf3a754dac60`, 16 casos |
| `design_cases_bot.json` local (raiz) | **ausente** no checkout da auditoria — nada a comparar (§7) |
| propostas | `config/pfd/pendencias_propostas.toml` (sha256 `a1715287ab3a…`), carregadas por padrão |
| registro máquina-legível | [`manifesto_validacao.toml`](manifesto_validacao.toml) |

## 2. Cenário-base × subproblema otimizado

| | P_D1 | P_D2 | usado em | TVP (12 casos avaliáveis) |
|---|---|---|---|---|
| **CENÁRIO-BASE** (premissas iniciais P-18/P-19) | 700 kPa | 200 kPa | todos os resultados produtivos (balanço, 11 TAGs, memoriais, gate, Golden Case) | 93,1–110,8 kPa — **NÃO CONFORME** ao limite de 70 kPa |
| **SUBPROBLEMA OTIMIZADO** (nota 42) | ≈ 510–540 kPa | ≈ 134 kPa | só a nota 42 | ≤ 70 kPa (restrição ativa) |

O resultado otimizado é **resultado do subproblema de otimização de pressões dentro do domínio de
estudo**: não é pressão definitiva de projeto, premissa final da planta nem condição validada
industrialmente (piso de P_D2 sem fonte; TVP só nos 12 casos sem lift; o subproblema não
representa a planta inteira). A planta não foi redimensionada com ele, e o NSGA-II não foi
reexecutado nesta auditoria: as evidências são as da nota 42.

## 3. O que foi feito

1. Leitura integral de README, SPRINTS, CLAUDE.md, arquitetura, notas 32 e 35–42, ADRs 0001–0004,
   premissas, proveniência, os 11 TAGs, propostas, trem, termodinâmica e otimização; leitura do
   balanço (`balanco/modelo.py`) e das regras de entrada (`pfd/entradas.py`).
2. Nova execução, sobre o baseline, da suíte com cobertura, do gate e da planta.
3. Medição de T1 (base do trem × base do balanço) e do fechamento do Golden Case.
4. Correção documental dos achados D1–D7 (§5); D8 verificado e mantido.
5. Documentos novos: `docs/PREMISSAS_E_LIMITACOES.md`, este, `GOLDEN_CASE_01.md`,
   `RESULTADOS_EQUIPAMENTOS.md`, `TABELA_PROCESSO.md`, `manifesto_validacao.toml`; gerador
   `tools/tabelas_auditoria.py` (só orquestra a API).

## 4. Afirmações do TCC — conferência

| # | afirmação | evidência | situação |
|---|---|---|---|
| A1 | Há um único resolvedor de processo; nenhum caminho paralelo | `tests/arquitetura/`; ADR 0004 | **CONFERIDA** |
| A2 | O balanço fecha massa e energia | Golden Case: 1,4·10⁻¹³ global, ≤ 6,5·10⁻¹² por componente; `tests/balanco/`; nota 39 (energia 3·10⁻⁸ kW) | **CONFERIDA** |
| A3 | A composição de cada caso sem lift reproduz as vazões do BOT | nota 39 §3 (≤ 1,2·10⁻⁹); Golden Case §2 | **CONFERIDA — por consistência com o BOT, sem PVT medido** |
| A4 | O gás de SG-001/V-001/V-002 vem do flash nos 12 casos avaliáveis | proveniência + `tests/termo/test_proveniencia.py`; nota 39 | **CONFERIDA** |
| A5 | Os 4 casos com lift não recebem composição suposta | `trem.toml [[lacuna]]`; nota 39 | **CONFERIDA** |
| A6 | 10 dos 11 TAGs dimensionados; P-001 inviável como resultado legítimo | gate; `RESULTADOS_EQUIPAMENTOS.md`; nota 36 | **CONFERIDA** |
| A7 | MC, JSON e CSV saem do mesmo rastro | gate (três níveis, igualdade exata) | **CONFERIDA para JSON/MC; PDF pendente de LaTeX** |
| A8 | Todo valor tem a origem declarada (fonte, premissa, proposta ou lacuna) | `pendencias_propostas.toml`; proveniência; `PREMISSAS_E_LIMITACOES.md` §5 | **CONFERIDA** |
| A9 | "Nenhum número sem fonte" / todo valor tem referência bibliográfica | 43 entradas são propostas sem fonte | **NÃO AFIRMAR** (README corrigido) |
| A10 | A frente do NSGA-II reproduz a da grade-oráculo; mesma semente → mesma frente; pontos reproduzíveis fora do otimizador | nota 42 §6–§8 | **CONFERIDA no subproblema** |
| A11 | As pressões otimizadas são as de projeto | — | **NÃO AFIRMAR** (resultado de subproblema em domínio de estudo) |
| A12 | O cenário-base atende a TVP do BOT | TVP 93,1–110,8 kPa | **FALSA — declarada como não conformidade** |
| A13 | A TVP foi verificada nos 16 casos | só nos 12 avaliáveis | **FALSA — afirmar "12 casos sem lift"** |
| A14 | Refatorações não mudaram número | instantâneo, regressão do balanço, fixtures Julia e caso-ouro inalterados; nenhum número mudou nesta auditoria | **CONFERIDA** |
| A15 | As propriedades são validadas experimentalmente | — | **NÃO AFIRMAR** (validação de consistência e de faixa, sem PVT) |

## 5. Contradições corrigidas (só documentação e rastreabilidade)

| id | onde | correção |
|---|---|---|
| D1 | `README.md` | "Nenhum número sem fonte" → filosofia de quatro categorias com as 43 propostas; testes 1.177 → 1.346 (1.322 + 24 LaTeX); Julia como regressão, não paridade; trem e flash no passo 2; P-001 com o mínimo de 186 m; tabela cenário-base × otimizado; entrada auditada |
| D2 | `SPRINTS.md` | decisão da viscosidade dada como tomada (nota 40); cenário-base e otimizado separados; estado da release |
| D3 | `config/pfd/tags/p_002.toml`, `p_003.toml` | a fonte da geometria recomendada apontava para `tools/reotimizar_trocadores.py` e `config/pfd/reotimizacao.toml`, removidos; agora aponta para `docs/validacao/18` e `24`, ADR 0004, inventário e o commit de remoção `f196f36` (arquivos recuperáveis em `f196f36^`). Os três snapshots de tela do P-002 foram regenerados: só esse texto mudou |
| D4 | `config/termo/fluidos.toml` | comentários sobre a flag `--oleo-morto` (removida) e "paridade bit a bit" |
| D5 | `pfd/entradas._rs` | docstring dizia Standing; agora trem nos avaliáveis, Standing nos com lift |
| D6 | notas 35, 36, 37 | nota de situação no topo (35 decidida; 36 com números anteriores ao trem; 37 §5 superado); texto histórico preservado |
| D7 | `premissas_memorial.toml` | P-19 dizia "último estágio próximo da atmosfera (TVP/RVP)"; agora: cenário-base que **não atende** a TVP do BOT; P-18 também marcada como cenário-base |
| D8 | `config/premissas.toml` | ids repetidos (P-17 ×2, P-30 ×3, P-31 ×2) são **agrupamentos deliberados** — o memorial tem uma linha por id (ΔP de cada trocador; regra de diluição; par de temperaturas da diluição). **Não renomeado** |

## 6. Limitações e aproximações

Ver [`../PREMISSAS_E_LIMITACOES.md`](../PREMISSAS_E_LIMITACOES.md). Destaque desta auditoria:

**T1 — trem × balanço: ACEITO COM LIMITAÇÃO / APROXIMAÇÃO DO MODELO.** O trem flasha a
alimentação recombinada; o balanço tira do líquido o óleo que sai na água do FWKO e o arraste, e
soma o óleo do reciclo; essas alterações não são realimentadas composicionalmente estágio a
estágio. A massa global fecha. Impacto máximo medido: **0,55 %** na base de óleo (caso 12).

## 7. Pendências antes da release final

| item | situação | o que falta |
|---|---|---|
| **A — LaTeX** | 24 testes não executados | rodar `uv run pytest -m latex` no ambiente Nix; só então mudar o status |
| **B — entrada canônica** | auditada: a fixture (sha256 acima); o `design_cases_bot.json` da raiz não existe neste checkout | se ele existir no ambiente do autor, comparar o sha256 com o da fixture, sem modificar nem versionar. Iguais → registrar a identidade; diferentes → parar antes da tag |
| tag de release | não criada | depende de A e B |

## 8. Verificações desta auditoria (depois das correções)

| verificação | resultado |
|---|---|
| suíte padrão (`-m 'not latex'`, `-n 4 --dist loadscope`, com cobertura) | **1.322 passed** (1.321 no baseline + 1 teste de arquitetura parametrizado sobre a nova ferramenta) |
| cobertura | **95,93 %** |
| gate | **APROVADA**, 0 `ERRO_NUMERICO`, 0 `ERRO_OUTPUT` |
| testes LaTeX | **não executados** (§7-A) |

## 9. Fora do escopo desta auditoria

Nova EOS ou correlação, Péneloux, ρ/cp/h/k/μ novos, composição do gás de lift, modelo de VRU ou
compressor, nova otimização ou nova rodada do NSGA-II, novo equipamento, topologia ou arquitetura,
R3/R4, P-32, soluções do P-001, redimensionamento com as pressões otimizadas, melhorias de
desempenho e refatorações.
