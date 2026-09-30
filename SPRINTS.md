# SPRINTS — FPSO_Siz_V2

Estado atual, pendências reais e próximo marco. Regras permanentes: [`CLAUDE.md`](CLAUDE.md).
Arquitetura vigente: [`docs/arquitetura/arquitetura-alvo.md`](docs/arquitetura/arquitetura-alvo.md).
Histórico completo das fases (F0–F15, R1/R2, F3–F5.1): [`docs/historico/SPRINTS-historico.md`](docs/historico/SPRINTS-historico.md).

**Regra de processo:** cada etapa só começa com aprovação explícita do usuário. **Pronto** é o
caminho inteiro — entrada → processo → propriedades → correntes → dimensionamento → saída →
memorial → gate; comparação, sombra e estudo são marcos internos, não entrega.

## O que está ativo

```
arquivo do BOT + premissas
  → balanco/modelo.resolver_todos          → EstadoProcesso (balanco/estado.py; trem em balanco/trem.py)
  → pfd/entradas.montar (termo/servico)    → entradas dos 11 TAGs, cada propriedade com proveniência
  → pfd/equipamento → core/motor + sizing  → envelopes (EnvelopeResult guarda o que avaliou)
  → pfd/otimizacao + _otim                 → objetivos e restrições (NSGA-II; subproblema de pressão, nota 42)
  → output/* e pfd/memorial (+ core/memoria) → JSON, CSV, MC em LaTeX
  → tools/auditar_saida_pfd.py             → gate
```

- **Balanço:** uma regra de FWKO (eficiência, P-43), congelada por `regressao_eficiencia.json`.
- **Termodinâmica:** uma API (`termo/servico.py`); ChEDL só em `termo/backend.py`; proveniência
  única em `config/termo/proveniencia.toml` (validade × origem × consumidores).
- **Trem SG-001 → V-001 → V-002: produtivo nos 12 casos avaliáveis** — composição do caso pela
  Nota 4 (referência do FWKO, premissa de modelagem, `docs/validacao/38`) e flash em cascata; o
  gás de cada estágio é o do flash. Casos 9, 11, 15, 16 (gás de lift sem composição): não
  avaliáveis, Standing (`docs/validacao/39`).
- **Planta produtiva (16 casos, propostas do pacote):** 10 TAGs dimensionados; **P-001 inviável**
  (alarme aberto). Gate aprovado.
- **Otimização das pressões de separação (nota 42):** P_D1 × P_D2 → mesmo resolvedor → trem →
  SG-001/V-001/V-002 → perda de óleo estabilizado e carga de vapor da VRU, com TVP ≤ 70 kPa como
  restrição contínua (12 casos avaliáveis). Frente do NSGA-II conferida contra grade-oráculo de
  195 pontos: na resolução declarada, **um ponto** sobre a fronteira da TVP — P_D1 ≈ 510–540 kPa,
  P_D2 ≈ 134 kPa, recuperação 97,90 %, VRU 1,216 MSm³/d. Os dois objetivos não conflitam; quem
  limita é a TVP. Subproblema de pressão e separação, não a planta inteira.

## Entregue

| etapa | commit | resumo |
|---|---|---|
| DESIGN × RATING e multiplicidade | (este) | rating térmico limitado por Pinch, contrato genérico de unidades físicas, bombas em paralelo, busca discreta/Pareto e reauditoria atual do P-001 — `docs/validacao/43`, ADR 0005 |
| Otimização das pressões | (este) | subproblema P_D1 × P_D2: TVP no estado, objetivos e restrições no TOML, grade-oráculo, NSGA-II, frente reproduzida na resolução da grade — `docs/validacao/42` |
| Mapa de pressão e viscosidade | `d9c565d` | Rs do trem → Beggs & Robinson (nota 40); mapa determinístico P_D1 × P_D2, conclusão C (nota 41) |
| Trem produtivo | (este) | recombinação da Nota 4 + flash no gás de SG-001/V-001/V-002 nos 12 casos avaliáveis; Standing só nos 4 com lift — `docs/validacao/39` |
| Etapas A–C e nota 38 | `046eb3f`, `593f7d9` | casos do BOT, P-001, faixas de P_D1/P_D2, recombinação F — `docs/validacao/35`–`38` |
| Consolidação arquitetural | (este) | um resolvedor de processo, uma API termo, trem no estado, proveniência única, sem modos de paridade; memorial só lê — `docs/arquitetura/` |
| Gate de sanidade da saída | `426c667` | `tools/auditar_saida_pfd.py` — `docs/validacao/32-auditoria-de-saida.md` |
| F3–F5.1 termodinâmica | `70179dc`…`bd87be0` | flash com pseudo-componentes (Riazi), fechamentos, trem — hoje fundidos em `termo/` e `balanco/trem.py` |
| R1/R2 desempenho do P-003 | `346d09b`, `3a78178` | 9,5× sem mudar número |
| F0–F15 | ver histórico | balanço, métodos, PFD, MC, pinch, otimização (estudo) |

## Pendências físicas reais

1. **P-001 inviável** — troca óleo/óleo com aproximação de 10 K (P-32) exige ~186 m de tubo
   contra 6 m; nenhuma correlação resolve. Decisão de projeto (P-32, arranjo, ou aceitar).
   Diagnóstico e árvore de alternativas: `docs/validacao/36-p001-diagnostico.md` (no modelo atual,
   por Standing, a sensibilidade do P-001 a P_D1/P_D2 é desprezível, ~0,2 %; a reconferir com o flash).
2. ~~O trem não reconcilia com o BOT~~ — **resolvida** pela recombinação da Nota 4 (nota 38,
   aprovada) e pelo trem produtivo (nota 39). Decisão pendente dela: aceitar ou não a propagação
   do Rs do trem à μ do óleo vivo (Beggs & Robinson), que muda SG-001 (teto), P-001, P-002 e
   TO-001 (nota 39 §8).
3. **Composição do gás de lift** — ausente na fonte (BOT §2.3.3 só dá especificação); casos 9, 11,
   15 e 16.
4. **h e cp dos pseudo-componentes** — sem Cp_ig com fonte (a rota PNA para H/C não fecha).
5. **ρ da fase líquida pela EOS** (Péneloux) e **k líquido de hidrocarboneto** — não validados.
6. **Discretização das grades** do trocador (caso × envelope) — `docs/validacao/33-…`; muda número.
7. **Faixas de P_D1 e P_D2** — sem fonte: o BOT não dá pressão de degaseificador. A otimização
   (nota 42) usa um **domínio de estudo declarado** (região da nota 41) e a TVP ≤ 70 kPa como
   restrição contínua; o piso de P_D2 (sucção da VRU) segue sem fonte e não vira bound.
   Com as premissas atuais (P-19 = 200 kPa) a TVP é 110,8 kPa: a P-19 não atende o BOT —
   `docs/validacao/37`, `41`, `42`.
8. **Otimização F15 (problema completo)** — `docs/validacao/23-otimizacao.md` segue como
   diagnóstico do alarme do P-001; o subproblema de pressão (nota 42) é a otimização que o TCC
   defende.

Pendências de engenharia de software (não físicas): o leitor do formato de ajustes da F10b
(`pfd/ajustes.estado_legado`) ainda existe — a fixture de teste `ajustes_sinteticos.toml` usa
esse formato; R3/R4 do P-003 (mudam o que o MC mostra).

## Próximo marco

**Só fechamento documental** depois da nota 42 (instrução do usuário, 2026-09-29): SPRINTS, documentos de arquitetura, tabela de
premissas, balanço final, memoriais, resultados da otimização, figuras e tabelas, limitações, suíte
completa com cobertura e gate, tag de release. Qualquer tarefa nova responde antes: "isso é
necessário para defender a contribuição central do TCC ou para produzir um artefato final?"
