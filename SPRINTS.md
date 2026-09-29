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
  → pfd/otimizacao + _otim                 → objetivos e restrições (NSGA-II; estudo)
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

## Entregue

| etapa | commit | resumo |
|---|---|---|
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
7. **Faixas de P_D1 e P_D2** para a otimização — sem fonte ainda; a arquitetura já as aceita por
   configuração (`destino = "premissa"`), e o trem as lê do estado. O BOT não dá pressão de
   degaseificador; a TVP ≤ 70 kPa (§2.3.1.1/§2.7.1.10) é o critério do teto de P_D2. Com z_caso e
   o trem produtivo (nota 39 §9), a 40 °C: P-19 = 200 kPa dá TVP de 93–111 kPa, e a TVP atinge
   70 kPa com P_D2 entre 133,4 e 157,3 kPa(a) — ainda diagnóstico, não bound; o piso depende da
   VRU, fora do BOT —
   `docs/validacao/37-faixas-pressao-degaseificadores.md`.
8. **Otimização F15** — `docs/validacao/23-otimizacao.md` desatualizado; rodar de novo depois de
   decidir 1 e 7.

Pendências de engenharia de software (não físicas): o leitor do formato de ajustes da F10b
(`pfd/ajustes.estado_legado`) ainda existe — a fixture de teste `ajustes_sinteticos.toml` usa
esse formato; R3/R4 do P-003 (mudam o que o MC mostra).

## Próximo marco

**Fechar o laço P → flash → dimensionamento → otimização** (a contribuição central do TCC). O
trecho P → flash → dimensionamento está ativo (nota 39). O mapa determinístico de P_D1 × P_D2
(nota 41) concluiu **C**: nenhuma das duas produz efeito suficiente nos objetivos atuais (volume
dos três vasos 0,90 %, diâmetros e governantes constantes); elas respondem na TVP (P_D2), no gás
à VRU (P_D1/P_D2), nas bombas e no óleo recuperado, que não são objetivos. Próxima decisão do
usuário: se e com que modelo e fonte um objetivo capturaria esse efeito (P-001 segue fora).
