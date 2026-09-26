# BOT — especificação técnica do projeto

`I-ET-3010.2K-1200-941-P4X-001_C.pdf`: *General Technical Description — BOT*, Petrobras,
revisão C (170 folhas). Documento público, versionado a pedido do usuário (2026-09-26) para
que as citações "BOT …" do código e dos memoriais possam ser conferidas no próprio
repositório. É a mesma especificação citada no acervo local (`references/`).

| Campo | Valor |
|---|---|
| Arquivo | `I-ET-3010.2K-1200-941-P4X-001_C.pdf` |
| SHA-256 | `7393b438075dec28b949379b54801581d02e6975f247ba58cd62dabc0210e5d6` |
| Tamanho | 2.505.981 bytes |

Itens citados no código e conferidos no texto (F10x/F13):

| Item | Conteúdo | Uso |
|---|---|---|
| Tab. 2.2.2.3/2.2.2.4 | casos de projeto | `design_cases_bot.json` |
| 2.7.1.2 | BSW máximo do óleo do FWKO | F-06, P-43 |
| 2.7.1.4 | "the maximum heating medium temperature shall be 120°C" | limite do insumo `t_agua_in` do P-002 |
| 2.7.1.5 | aquecedor de produção casco-e-tubos, feixe removível | método Saari (casco-e-tubos) |
| 2.7.1.6 | temperatura de entrada do FWKO de 40 °C por recirculação | F-07 |
| 2.7.1.10 | óleo tratado resfriado no pré-aquecedor e no resfriador até 40 °C; separação ≤ 99 °C | F-08 (P-003) |
| 2.7.1.12 | bombas reserva para todas as bombas do tratamento de óleo | configuração das bombas (reserva, não paralelo) |
| 3.3 / 3.4 | água doce em circuito fechado como meio de resfriamento; água quente como meio de aquecimento (WHRU) | utilidades de P-002 e P-003 |
| 10.3.4 | casco-e-tubos conforme TEMA, API 660 e ASME VIII-1 | (normas fora do acervo) |

O BOT **não fixa** temperaturas de suprimento/retorno das utilidades, incrustações,
condutividades, arranjo de tubulação, NPSHr nem a gotícula após coalescência: por isso esses
valores seguem como propostas em `docs/propostas/pendencias_propostas.toml`.
