# 00 — Oráculo do balanço preliminar (F1)

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): o oráculo do script de referência e a regra do FWKO que ele usa saíram; o balanço produtivo é congelado por `regressao_eficiencia.json`. O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Data: 2026-09-23. **Estado: entregue.**

## O que é
O oráculo é a fixture numérica contra a qual o balanço modularizado (F2–F4) prova
paridade. Ele é gerado **executando o script original sem nenhuma edição**. Nada nele é
recalculado por código novo.

| Arquivo (versionado) | Conteúdo |
|---|---|
| `tests/fixtures/python_ref/oraculo_balanco.json` | constantes, premissas, topologia, 16 casos completos, balanços por bloco e global, auditoria, envelopes, críticos, sensibilidade |
| `tests/fixtures/python_ref/main_ref.tex` | `main.tex` produzido pelo original: a referência do `diff` da F4 |
| `tools/gerar_oraculo_balanco.py` | gerador |

Regenerar: `uv run python tools/gerar_oraculo_balanco.py`. A regeneração precisa de
`references/`.

## Origem e hashes
| Item | SHA-256 |
|---|---|
| `references/Balanço_Preliminar.py` (cabeçalho: `gerar_memorial.py`) | `1542e267bd03659234785e556d4934f5cd393ed851206f95f24944c73b764e8e` |
| `references/design_cases_bot.json` (BOT, Tab. 2.2.2.3/2.2.2.4) | `ca3dfe559b32926c9d9ca4d9e75e2cec711f00f7fdfd2247242bbf3a754dac60` |
| `main_ref.tex` (218.713 bytes; stdout do original: `ok 1658`) | `e256ab4799cf598fde38dc91f36941a1c62e24b0e760747614d3a249235f02ce` |
| `oraculo_balanco.json` (339.610 bytes) | `9e5b4178e7b4789d337d9455e8753d090be32affa7cc2ed0248b0877fe16060c` |

## Como é gerado
1. Copia o JSON de casos para uma pasta temporária e usa essa pasta como cwd, porque o
   original lê e escreve pelo diretório corrente.
2. Carrega o script como módulo registrado em `sys.modules`, pois o original faz
   `M = sys.modules[__name__]`. Os `SyntaxWarning` do original são silenciados.
3. Lê as globais `R`, `BLOCKS`, `AUD`, `env`, `crit`, `SC`, `SENS` e chama só as funções do
   próprio script: `block_balance`, `global_balance` e `run`, esta última para as
   3 × 8 sensibilidades.
4. Serializa em JSON sem carimbo de tempo nem caminho absoluto, com floats em `repr`
   exato (ida e volta sem perda).

## Verificações (tests/balanco/test_oraculo.py)
- **Determinismo:** a regeneração é byte-idêntica, tanto no JSON quanto no `main_ref.tex`.
- **Proveniência:** os hashes batem com o acervo local.
- **Reciclo:** os 16 casos e as 24 sensibilidades convergem em 4 a 35 iterações (limite 500).
- **Sensibilidade:** a variação "Base" é idêntica ao resultado do caso correspondente.
- **Snapshot Julia** (`references/bot/balanco_python.json`, gerado por
  `scripts/gerar_casos_bot.py` no repo Julia, não commitado lá): **igualdade exata** em
  3.168 valores escalares nos 16 casos (fluido, poço, API, ρ, cp, gás, BSW, 26 correntes ×
  O/W/D/G, T, P, cargas, gás por estágio), mais `iters`, `mu`, balanços por bloco e
  global, auditoria, premissas, stdout e hash do `main.tex`. **Nenhuma divergência.**

## Auditoria independente do original (maior desvio absoluto, 16 casos)
Os maiores desvios são ≈ 2e-9: 1,997e-9 kW no balanço de energia global e 1,863e-9 Sm³/d no
gás liberado por estágio. Todos os demais ficam abaixo de 1e-10.

## Limitações registradas
- O script não expõe o resíduo do laço de reciclo. O oráculo registra `iters` e
  `convergiu = iters < 499`; o critério original é `diff < 1e-10` com `it > 3`. Uma medida
  indireta do resíduo é o desbalanço por componente no M-01, da ordem de 1e-10 kg/s: a
  corrente C-02 que entra no M-01 é a da iteração anterior. A F2 deve reproduzir esse
  valor, não "corrigi-lo".
- Os envelopes do original guardam só texto formatado. Os valores numéricos estão em
  `criticos` e nos resultados por caso.
- Para a F4 e a portabilidade: o original escreve o `main.tex` com
  `open("main.tex", "w")`, sem `encoding`. No Windows, com o locale cp1252, isso pode falhar
  nos caracteres Unicode do memorial. O módulo novo deve escrever com `encoding="utf-8"`.
