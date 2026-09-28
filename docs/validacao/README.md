# Documentos de validação

Cada documento é o registro de uma etapa. A arquitetura vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md); o que mudou na consolidação, em [`../arquitetura/inventario.md`](../arquitetura/inventario.md).

## Vigentes — descrevem o comportamento atual

- [01-motor-balanco.md](01-motor-balanco.md) — 01 — Motor do balanço modularizado (F2)
- [02-auditoria-saidas-cli.md](02-auditoria-saidas-cli.md) — 02 — Auditoria independente, saídas estruturadas e CLI (F3)
- [04-contrato-nucleo.md](04-contrato-nucleo.md) — 04 — Contrato do núcleo de dimensionamento + fixtures do Julia (F5)
- [05-vasos.md](05-vasos.md) — 05 — Vasos: separador trifásico, knockout, tratador eletrostático (F6)
- [06-bomba-trocador.md](06-bomba-trocador.md) — 06 — Bomba centrífuga (Moran) e trocador casco-e-tubos (Saari + Bell-Delaware) (F7)
- [07-cli-interativa.md](07-cli-interativa.md) — 07 — CLI interativa e subcomando `dimensionar` (F7b)
- [08-propriedades.md](08-propriedades.md) — 08 — Propriedades na condição do equipamento (F10a)
- [10-fluxo-tag.md](10-fluxo-tag.md) — F10c — fluxo por equipamento/TAG no terminal; PFD como atalho
- [11-verificacao-balanco.md](11-verificacao-balanco.md) — F10v — verificação física do balanço e premissa "sem fase aquosa" (P-42)
- [12-eficiencia-fwko.md](12-eficiencia-fwko.md) — F10w — eficiência de água livre do SG-001 (P-43)
- [13-memorial-tag.md](13-memorial-tag.md) — F11 + F11b — memorial de cálculo por TAG e memorial do balanço por caso
- [17-banda-bombas.md](17-banda-bombas.md) — F10x.6 — banda de velocidade das bombas pelo caso de projeto (P-44, P-44b)
- [19-trocadores-premissas.md](19-trocadores-premissas.md) — F10x.7 — trocadores: P-45, P-46, cascos em série e paralelo, P-001 como lacuna metodológica
- [20-correlacao-tubo-laminar.md](20-correlacao-tubo-laminar.md) — F13/Etapa 1 — correlação do lado tubo fora da faixa de Dittus-Boelter: fontes localizadas
- [22-pinch-planta.md](22-pinch-planta.md) — F8 — alvos de energia do pré-aquecedor (Análise Pinch na planta do BOT)
- [23-otimizacao.md](23-otimizacao.md) — F15 — otimização multiobjetivo do módulo (estudo)
- [24-pelicula-baixo-reynolds.md](24-pelicula-baixo-reynolds.md) — Película do lado tubo nos três regimes — fechamento dos alarmes dos trocadores
- [25-termo-memoria-de-calculo.md](25-termo-memoria-de-calculo.md) — 25 — O termo adotado é "memória de cálculo"
- [30-caracterizacao-fluido-de-poco.md](30-caracterizacao-fluido-de-poco.md) — Fase 4 — caracterização do fluido de poço (pseudo-componentes)
- [32-auditoria-de-saida.md](32-auditoria-de-saida.md) — 32 — Gate de sanidade do dimensionamento e dos memoriais
- [33-discretizacao-das-grades.md](33-discretizacao-das-grades.md) — 33 — Pendência de discretização: a grade do caso e a grade do envelope
- [35-casos-bot.md](35-casos-bot.md) — 35 — O que os 16 casos do BOT representam (Nota 4: flash + recombinação); decisão pendente
- [36-p001-diagnostico.md](36-p001-diagnostico.md) — 36 — P-001: restrição, caso e requisito que o tornam inviável; árvore de alternativas
- [37-faixas-pressao-degaseificadores.md](37-faixas-pressao-degaseificadores.md) — 37 — Faixas de P_D1 e P_D2: TVP do BOT como teto de P_D2; o que falta
- [38-recombinacao-nota4.md](38-recombinacao-nota4.md) — 38 — Recombinação da Nota 4: condição padrão × FWKO; recomendada a do FWKO

## Registros de medição e de sessão — datados, continuam corretos para a data

- [26-auditoria-p003.md](26-auditoria-p003.md) — Auditoria algorítmica do P-003 — as 913 mil avaliações de Bell-Delaware, explicadas
- [27-r1-feixe-fora-do-laco.md](27-r1-feixe-fora-do-laco.md) — R1 — o feixe sai do laço de ponto fixo
- [28-r2-reaproveitamento-do-feixe.md](28-r2-reaproveitamento-do-feixe.md) — R2 — o feixe é calculado uma vez por estado
- [performance-baseline.md](performance-baseline.md) — Baseline de desempenho — onde o tempo está hoje
- [f11-checkpoint.md](f11-checkpoint.md) — F11 — checkpoint de retomada
- [f11-decisoes.md](f11-decisoes.md) — F11 / F11b — decisões tomadas sem confirmação (sessão autônoma de 2026-09-26)
- [f11-preparacao.md](f11-preparacao.md) — F11 — diagnóstico inicial e proposta documental

## Históricos — descrevem caminhos que saíram na consolidação

- [00-oraculo-balanco.md](00-oraculo-balanco.md) — 00 — Oráculo do balanço preliminar (F1)
- [03-memorial-balanco.md](03-memorial-balanco.md) — 03 — Memorial LaTeX do balanço (F4)
- [09-pfd.md](09-pfd.md) — F10b — balanço → entradas dos TAGs → envelopes
- [14-alarmes.md](14-alarmes.md) — F13 — alarmes de inviabilidade: anotação e investigação
- [15-termodinamica.md](15-termodinamica.md) — F14 — termodinâmica preliminar: balanço × propriedades do ChEDL
- [16-oleo-vivo.md](16-oleo-vivo.md) — F10x.5 — viscosidade de óleo vivo (Beggs & Robinson) na camada do PFD
- [18-trocadores.md](18-trocadores.md) — F10x.7 — trocadores P-002 e P-003: reotimização discreta
- [21-circulacao-cascos.md](21-circulacao-cascos.md) — F13/Etapa 2 — circulação fixa da utilidade e cascos em série (estudos)
- [29-servico-termodinamico.md](29-servico-termodinamico.md) — Fase 3 — serviço termodinâmico ativo, exercitado na planta
- [31-integracao-modo-sombra.md](31-integracao-modo-sombra.md) — Fase 5 — integração do serviço termodinâmico, em modo sombra
- [34-cascata-composicional.md](34-cascata-composicional.md) — Fase 5.1 — cascata composicional do trem, em modo sombra
