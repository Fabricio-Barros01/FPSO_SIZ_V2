# 0004 — Consolidação arquitetural

**Estado: decidida e executada (2026-09-28).** Pedido do usuário: interromper o ciclo
"implementar → comparar → preservar legado → modo sombra → nova subfase" e deixar uma
implementação produtiva por responsabilidade. Inventário: [`../arquitetura/inventario.md`](../arquitetura/inventario.md).
Arquitetura resultante: [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

## Decisões

1. **Paridade com o Julia e com o script de referência deixa de ser requisito.** Saem a regra de
   referência do FWKO (`--regra-fwko`), a alocação do PFD F1 (`--topologia-julia`), o óleo morto
   (`--oleo-morto`), o layout `original` dos memoriais e os oráculos que só existiam nesses
   modos. Ficam como regressão: `regressao_eficiencia.json`, as fixtures Julia dos métodos, o
   caso-ouro da película e o instantâneo bit a bit da planta.
2. **Uma API termodinâmica** (`termo/`): as propriedades de fase e o flash do fluido de poço no
   mesmo serviço; o flash de água/salmoura/hidrocarboneto sem pseudo-componentes, que duplicava
   as propriedades produtivas, sai.
3. **O trem é parte do processo** (`EstadoProcesso.trem`), como diagnóstico declarado; o modo
   sombra (`pfd/integracao.py`, `pfd/cascata.py`) sai. Base molar sem depender de flash
   (`MW_z = Σ zᵢ·MWᵢ`); fechamento do trem distingue completo de parcial.
4. **Proveniência única** com validade e origem independentes, e consumidores reais.
5. **Saída e memorial não avaliam física**: o motor guarda a preparação dos casos
   (`EnvelopeResult.preparo`) e `core/memoria.py` calcula uma vez o que o MC mostra; as variantes
   dos alarmes só rodam por ferramenta.
6. **Estudos fora do produto**: circulação fixa e reotimização discreta (segundo otimizador) saem;
   a divisão de vazão em trens é uma função do serviço, usada pela otimização e pelas variantes.

## Consequências

Nenhum número produtivo mudou (instantâneo `409f1800…f16414`, regressão do balanço e fixtures dos
métodos idênticos; gate aprovado). Mudaram: o esquema do `balanco.json` (3, sem `FWKO.regra`), o
memorial do balanço (só SENAI), a seção de alarme do MC do P-001 (sem resultados de variante) e os
snapshots da tela do SG-001 inviável (cenário por μ informada, não mais óleo morto).
