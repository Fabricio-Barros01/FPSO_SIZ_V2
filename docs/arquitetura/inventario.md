# Inventário da consolidação arquitetural (etapa A)

Base: commit `bd87be0`. Consumidores medidos por análise estática dos `import` (AST) de
`src/`, `tests/` e `tools/`. "Consumidor produtivo" = um módulo de `src/` no caminho
`CLI → processo → entradas → motor → saída → memorial`.

Classes: ATIVO · REDUNDANTE · HISTÓRICO · COMPARATIVO · SOMBRA · ADAPTADOR TEMPORÁRIO · FERRAMENTA.
Destinos: MANTER · FUNDIR · MIGRAR · REMOVER · HISTÓRICO.

## Módulos de `src/fpso_siz`

| módulo | responsabilidade atual | consumidores produtivos | classe | destino |
|---|---|---|---|---|
| `balanco/modelo.py` | resolve um caso: reciclo, FWKO, desgaseificação por Standing, energia | planta, equipamento, CLI, memoriais | ATIVO (+ ramo `referencia`) | MANTER; `ResultadoCaso` → `EstadoProcesso`; ramo `referencia` REMOVER |
| `balanco/dados.py`, `balancos.py` | entrada do BOT, premissas, topologia | todos | ATIVO | MANTER |
| `balanco/propriedades.py` | MW/cp do gás (corte leve), Standing, µ do óleo por tabela, splits | modelo, entradas, fluidos | ATIVO | MANTER (correlações de processo) |
| `balanco/indicadores.py`, `auditoria.py`, `exportacao.py` | indicadores, auditoria independente, JSON/CSV do balanço | CLI, memoriais | ATIVO | MANTER |
| `pfd/_chedl.py` | porta única do ChEDL | fluidos, estado_termodinamico | ATIVO | MIGRAR → `termo/backend.py` |
| `pfd/fluidos.py` | propriedades produtivas: gás (PR, composição fixa), água (IAPWS), salmoura (Laliberté), óleo (BOT + Beggs & Robinson) | entradas, equipamento | ATIVO | FUNDIR → `termo/servico.py` |
| `pfd/estado_termodinamico.py` | `flash_tp`, `flash_poco` (EOS + pseudo-componentes) | só `integracao`, `cascata` | SOMBRA | FUNDIR → `termo/servico.py` (API única com `fluidos`) |
| `pfd/caracterizacao.py` | Riazi & Al-Sahhaf dos SCN e frações plus | só `estado_termodinamico` | SOMBRA | MIGRAR → `termo/caracterizacao.py` |
| `pfd/integracao.py` | mapa de proveniência da sombra, guarda, fechamento de flash | só `cascata` | SOMBRA | REMOVER (fechamento → `termo/servico`; proveniência → contrato único) |
| `pfd/cascata.py` | trem SG-001→V-001→V-002 em sombra | nenhum | SOMBRA | MIGRAR → `balanco/trem.py` (parte do `EstadoProcesso`) |
| `pfd/termodinamica.py` (F14) | balanço × ChEDL, comparação | nenhum | COMPARATIVO | REMOVER |
| `pfd/contrato.py` (F13) | confere o contrato de propriedades contra o código | nenhum | COMPARATIVO | REMOVER (vira teste de arquitetura sobre o contrato único) |
| `pfd/reotimizacao.py` | busca discreta em grade de parâmetros dos trocadores | nenhum | REDUNDANTE (segundo otimizador) | REMOVER |
| `pfd/circulacao.py` | estudo de circulação fixa da utilidade (física própria) | `investigacao` | HISTÓRICO (estudo) | REMOVER |
| `pfd/investigacao.py` | alarmes + execução de variantes | `pfd/memorial` (executa variantes dentro do MC) | ATIVO por acidente | MANTER enxuto: alarme lido do registro; variantes só por ferramenta |
| `pfd/pinch.py` | rede do pré-aquecedor sobre o balanço (F8 na planta) | nenhum em `src` | FERRAMENTA (análise do estado oficial) | MANTER (consome o `EstadoProcesso`) |
| `pfd/equipamento.py` | `Contexto`, serviço por TAG, cache | CLI, sessão, planta | ATIVO (+ flags `oleo_vivo`, `topologia_julia`) | MANTER; flags REMOVER |
| `pfd/planta.py`, `tags.py`, `entradas.py`, `ajustes.py`, `propostas.py`, `manual.py` | serviço da planta, entradas dos TAGs, estado de sessão | CLI, sessão | ATIVO (+ `topologia_alternativa` Julia, `oleo_vivo`) | MANTER; ramos de paridade REMOVER |
| `pfd/memorial.py` | conteúdo do MC do TAG | `output/latex/tag` | ATIVO (recalcula restrições e hooks do método) | MANTER; recálculo → motor |
| `pfd/otimizacao.py` + `_otim.py` | avaliador F15 + porta pymoo | só ferramenta | ATIVO (estudo) | MANTER; consome `Contexto`/`planta` (estado oficial) |
| `core/*` | contrato, motor, grade, rastro, unidades, parâmetros | todos | ATIVO | MANTER (contrato ganha estado estruturado de não aplicabilidade) |
| `core/formato_julia.py`, `grade.faixa_julia`, `ieee.py` | semântica numérica e mensagens | métodos | ATIVO | MANTER (fixam a discretização e as mensagens atuais; mudar é mudar número) |
| `sizing/*` | métodos | registro, motor | ATIVO | MANTER |
| `analysis/pinch.py` | Problem Table (Kemp) | `sizing/pinch_kemp`, `pfd/pinch` | ATIVO | MANTER |
| `output/latex/balanco` layout `original` | reprodução do memorial do script de referência; força a regra `referencia` | CLI (padrão!) | ADAPTADOR TEMPORÁRIO (paridade) | REMOVER; `senai` é o único layout |
| `output/latex/caso` layout `original` | segundo layout visual do MC por caso | CLI | REDUNDANTE | REMOVER |
| `output/*` restante, `cli.py`, `output/terminal/*` | saídas e interface | — | ATIVO | MANTER; opções de paridade REMOVER |

## Flags e modos de compatibilidade

| flag/modo | pontos no código | consumidor real | destino |
|---|--:|---|---|
| `regra_fwko = "referencia"` / `--regra-fwko` | 29 | oráculo do script, layout `original` | REMOVER |
| `topologia_julia` / `--topologia-julia` + variantes `p_002/p_003_oleo_tubo` | 18 | oráculo do PFD F1 do Julia, ajustes sintéticos | REMOVER |
| `oleo_vivo = False` / `--oleo-morto` | 30 | fixtures F10b–F13 | REMOVER |
| layout `original` (balanço e caso) | 12 | reprodução do `main.tex` do script | REMOVER |
| propostas (`--propostas`/`--sem-propostas`) | — | produto: preencher lacunas com valores propostos, ou deixá-las abertas | MANTER — é capacidade de produto (dado), não compatibilidade |
| `dimensionar --exemplo/--casos` | — | produto: dimensionar equipamento avulso a partir de arquivo | MANTER |

## Configurações

REMOVER: `pfd/integracao_termodinamica.toml`, `pfd/contrato_propriedades.toml` (fundidos num
contrato único de proveniência), `pfd/termodinamica.toml`, `pfd/circulacao.toml`,
`pfd/reotimizacao.toml`, `pfd/variantes/p_002_oleo_tubo.toml`, `pfd/variantes/p_003_oleo_tubo.toml`,
chaves `topologia_julia` dos TAGs, `limitacao_oleo.morto`.
MIGRAR para `config/termo/`: `pfd/estado_termodinamico.toml`, `pfd/caracterizacao_scn.toml`,
`fluidos.toml`.

## Ferramentas

| ferramenta | o que faz | lógica de domínio própria? | destino |
|---|---|---|---|
| `auditar_saida_pfd.py` | gate | não (lê saídas) | MANTER; não aplicabilidade por estado estruturado |
| `otimizar.py`, `pinch_planta.py`, `benchmark.py`, `gerar_regressao_eficiencia.py`, `investigar_alarmes.py`, `pelicula_baixo_re.py`, `caracterizacao_poco.py` | orquestram a API | não | MANTER (ajustar à API nova) |
| `cascata_composicional.py` | relatório F5.1 | **sim** (GOR por flash, bases molares) | MIGRAR a regra para `balanco/trem.py`; ferramenta fina |
| `gerar_golden_pelicula.py` | caso-ouro independente da película | **sim**, por construção (implementação independente) | REMOVER; a fixture fica como regressão |
| `gerar_oraculo_balanco.py`, `comparar_memorial.py` | oráculo e memorial do script de referência | — | REMOVER (modo `referencia`) |
| `integracao_termodinamica.py`, `servico_termodinamico.py`, `termodinamica_preliminar.py` | relatórios da sombra F3/F5/F14 | — | REMOVER |
| `reotimizar_trocadores.py`, `estudo_circulacao.py`, `auditar_p003.py` | estudos encerrados | — | REMOVER |
| `exportar_fixtures_julia.sh/.jl` | reexportar fixtures do Julia | — | REMOVER (paridade deixou de ser requisito) |

## Testes

| conjunto | classe | destino |
|---|---|---|
| `balanco/test_paridade.py`, `test_oraculo.py`; `pfd/test_oraculo_pfd.py`; paridade de `test_memorial.py` com `main_ref.tex` | HISTÓRICO | REMOVER (com `oraculo_balanco.json`, `main_ref.tex`, `tests/fixtures/julia/pfd`, `tests/fixtures/pfd/*`) |
| `balanco/test_auditoria/fechamento/trace/verificacao_fisica` (hoje no modo `referencia`) | CONTRATO ATUAL | REESCREVER sobre a regra produtiva |
| `balanco/test_eficiencia_fwko.py` + `regressao_eficiencia.json` | REGRESSAO_UTIL | MANTER |
| `sizing/test_golden*`, `test_paridade_julia.py`, `core/test_fixtures_julia.py` | REGRESSAO_UTIL (métodos, sem modo) | MANTER |
| `pfd/test_estado_termodinamico`, `test_caracterizacao_poco`, `test_integracao_sombra`, `test_cascata_composicional` | SOMBRA | REESCREVER sobre `termo/` e `balanco/trem` |
| `pfd/test_termodinamica`, `test_reotimizacao`, `test_circulacao` | COMPARATIVO/HISTÓRICO | REMOVER |
| testes sobre `planta_ajustada`/`planta_referencia`/`planta_oleo_morto` | presos a modos | REESCREVER sobre a planta produtiva |
| `arquitetura/*`, `pfd/test_auditoria_saida.py`, memorial, CLI, sessão, motor | CONTRATO ATUAL | MANTER e ampliar |

## Caminhos que resolvem ou representam o processo, hoje

1. `balanco.modelo.resolver_todos` (regra de eficiência) — produtivo;
2. o mesmo com `regra_fwko="referencia"` — paridade;
3. `pfd.integracao.rodar` — flashes independentes em sombra;
4. `pfd.cascata.rodar` — trem em sombra, com base molar própria;
5. `pfd.termodinamica` — balanço × ChEDL, comparativo;
6. o resolvedor dentro do layout `original` do memorial (re-resolve na regra de referência).

**Seis.** A meta é **um**: `resolver_todos` → `EstadoProcesso`, com o trem como parte dele.
