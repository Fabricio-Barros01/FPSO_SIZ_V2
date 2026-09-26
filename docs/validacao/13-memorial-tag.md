# F11 + F11b — memorial de cálculo por TAG e memorial do balanço por caso

Relatório final da sessão autônoma de 2026-09-26 (branch `fases/f11`, base `73f7ca3`).
Decisões tomadas sem confirmação: [`f11-decisoes.md`](f11-decisoes.md). Retomada:
[`f11-checkpoint.md`](f11-checkpoint.md).

## Commits

| Commit | Passo | Testes (suíte normal) | Cobertura global (ramos) / núcleo (linhas) |
|---|---|---|---|
| `edf8fff` | F11.1 infraestrutura (substitui o WIP `59e0bf1`) | 832 passed, 5 skipped | 96,72 % / 98,61 % |
| `032c42b` | F11.2 MC do V-001 | 835 passed, 5 skipped | 96,72 % / 98,61 % |
| `ebc99b2` | F11.3 V-002 e SG-001 | 838 passed, 5 skipped | — |
| `4435f17` | F11.4 TO, P e B aguardando entrada | 848 passed, 5 skipped | 96,78 % / 98,66 % |
| `012515a` | F11.5 lote, CLI e interativo | 858 passed, 5 skipped | 96,87 % / 98,66 % |
| `87bd36b` | F11b MC do balanço por caso | 872 passed, 5 skipped | 96,72 % / 98,66 % |
| (este) | Fechamento: SPRINTS, CLAUDE.md, relatório | 872 passed, 5 skipped; 19 `-m latex` | 96,72 % / 98,66 % |

Os commits de checkpoint (`Docs: checkpoint …`) não mudam código.

## Verificações

| Verificação | Resultado |
|---|---|
| Suíte (`uv run pytest`) | 872 passed, 5 skipped (acervo `references/` e snapshot Julia ausentes na nuvem) |
| Compilação (`-m latex`) | 19 passed: memoriais do balanço `original` e `senai`; os 11 MCs por TAG (PDF × JSON); SG-001 (inviabilidade no PDF); 4 MCs com ajustes sintéticos; os 32 MCs por caso |
| Memorial original × oráculo | idêntico byte a byte (`test_layout_original_identico_ao_script` e `tools/comparar_memorial.py` → IDÊNTICO) |
| Paridade com o Julia (fixtures exportadas) | intacta: `tests/sizing/test_paridade_julia.py` (knockout e tratador bit a bit; demais ≤ 1e-13) |
| Regeneração das fixtures do Julia (`-m julia`) | **não rodou**: Julia e `../FPSO_Siz` indisponíveis na nuvem (pulado com o motivo) |
| Testes do acervo local (oráculo do script, snapshot Julia) | **não rodaram** (5 pulados): `references/` ausente na nuvem |
| PDF × JSON | o cartão de resultados, o teto e as lacunas do JSON do TAG aparecem no PDF com a regra de 4 algarismos (11 TAGs) |
| Conta à mão | V-001 e V-002: C_D, V_t, Re, K, capacidades, Leff, Lss, SR refeitos com os operandos do MC reproduzem o rastro bit a bit (volume ≤ 1e-15); SG-001: ΔSG, (h_o)max, d_max e retenção |
| Isolado × lote | MC por TAG: todos os arquivos iguais byte a byte (`dimensionar --tag … --mc` × `pfd --mc`); MC por caso: `.tex` byte a byte e texto do PDF igual |
| Listas de entradas faltantes | as do MC são as do `pfd` (JSON), TAG a TAG |

## Onde está cada coisa

- Núcleo: `core/trace.py` (`Rastro.operandos`, `Rastro.iteracoes`), `pfd/memorial.py`,
  hooks em `sizing/vasos.py`, conversões de campo em `core/unidades.py`.
- Configuração: `config/memorial_tag.toml` (numeração, conteúdo por método) e
  `config/memorial_balanco.toml [caso]`.
- Saída: `output/latex/tag/` (MC por TAG) e `output/latex/caso/` (MC por caso).
- Comandos: `dimensionar --tag X --mc [--pdf]`, `pfd --mc [--pdf]` → `<saida>/mc/<número>/`;
  `memorial --caso N|lista|todos` e `memorial --casos todos` → `MC_CasoNN`.

## Estado dos 11 TAGs no MC (sem ajustes)

| MC | TAG | Estado no MC |
|---|---|---|
| MC-SEN-SEP-EQP-001-0 | SG-001 | diagnóstico: teto 3.612 mm (caso 2) < menor d na banda 5.600 mm |
| MC-SEN-SEP-EQP-002-0 | P-001 | aguardando entrada |
| MC-SEN-SEP-EQP-003-0 | P-002 | aguardando entrada |
| MC-SEN-SEP-EQP-004-0 | V-001 | dimensionado: d 4.700 mm, Leff 11,74 m, Lss 16,44 m, SR 3,499, V 285,3 m³ (caso 3) |
| MC-SEN-SEP-EQP-005-0 | TO-001 | aguardando entrada |
| MC-SEN-SEP-EQP-006-0 | B-002 | aguardando entrada |
| MC-SEN-SEP-EQP-007-0 | V-002 | dimensionado (caso 3) |
| MC-SEN-SEP-EQP-008-0 | TO-002 | aguardando entrada |
| MC-SEN-SEP-EQP-009-0 | B-003 | aguardando entrada |
| MC-SEN-SEP-EQP-010-0 | B-001 | aguardando entrada |
| MC-SEN-SEP-EQP-011-0 | P-003 | aguardando entrada |

## Não entregue / pendências

- Gráficos específicos de trocador (T × Q, parcelas de U) e de bomba (curva do sistema,
  NPSHd × NPSHr) e o passo a passo desses métodos: não há dados (todos aguardam entrada);
  registrados na F10x.
- `pendencias_propostas.toml` não foi anexado nesta sessão: `docs/propostas/` não foi
  criado e nenhum valor proposto foi carregado.
- Fases F10x, F13, F14 e F15 registradas no `SPRINTS.md`, com aceite, sem execução.
