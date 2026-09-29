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
- **CENÁRIO-BASE** (premissas iniciais P-18 = 700 kPa, P-19 = 200 kPa): é o de todos os
  resultados produtivos, e é **NÃO CONFORME** à TVP ≤ 70 kPa do BOT nos 12 casos avaliáveis
  (TVP 93,1–110,8 kPa). A não conformidade é declarada, não corrigida.
- **Otimização das pressões de separação (nota 42):** P_D1 × P_D2 → mesmo resolvedor → trem →
  SG-001/V-001/V-002 → perda de óleo estabilizado e carga de vapor da VRU, com TVP ≤ 70 kPa como
  restrição contínua (12 casos avaliáveis). Frente do NSGA-II conferida contra grade-oráculo de
  195 pontos: na resolução declarada, **um ponto** sobre a fronteira da TVP — P_D1 ≈ 510–540 kPa,
  P_D2 ≈ 134 kPa, recuperação 97,90 %, VRU 1,216 MSm³/d. Os dois objetivos não conflitam; quem
  limita é a TVP. **Resultado do subproblema de otimização de pressões dentro do domínio de
  estudo** — não é pressão de projeto nem premissa final, e não substitui o cenário-base.

## Entregue

| etapa | commit | resumo |
|---|---|---|
| Auditoria da release do TCC | (branch `claude/tcc-release-audit`) | inventário, premissas e limitações, Golden Case, resultados dos equipamentos, correções documentais D1–D7 — `docs/auditoria/`; **pendente de verificação LaTeX** |
| Otimização das pressões | `2421bd2`, `9077852` | subproblema P_D1 × P_D2: TVP no estado, objetivos e restrições no TOML, grade-oráculo, NSGA-II, frente reproduzida na resolução da grade — `docs/validacao/42` |
| Mapa de pressão e viscosidade | `d9c565d` | Rs do trem → Beggs & Robinson (nota 40); mapa determinístico P_D1 × P_D2, conclusão C (nota 41) |
| Trem produtivo | `23f1828` | recombinação da Nota 4 + flash no gás de SG-001/V-001/V-002 nos 12 casos avaliáveis; Standing só nos 4 com lift — `docs/validacao/39` |
| Etapas A–C e nota 38 | `046eb3f`, `593f7d9` | casos do BOT, P-001, faixas de P_D1/P_D2, recombinação F — `docs/validacao/35`–`38` |
| Consolidação arquitetural | `f196f36` | um resolvedor de processo, uma API termo, trem no estado, proveniência única, sem modos de paridade; memorial só lê — `docs/arquitetura/` |
| Gate de sanidade da saída | `426c667` | `tools/auditar_saida_pfd.py` — `docs/validacao/32-auditoria-de-saida.md` |
| F3–F5.1 termodinâmica | `70179dc`…`bd87be0` | flash com pseudo-componentes (Riazi), fechamentos, trem — hoje fundidos em `termo/` e `balanco/trem.py` |
| R1/R2 desempenho do P-003 | `346d09b`, `3a78178` | 9,5× sem mudar número |
| F0–F15 | ver histórico | balanço, métodos, PFD, MC, pinch, otimização (estudo) |

## Pendências físicas reais

1. **P-001 inviável** — troca óleo/óleo com aproximação de 10 K (P-32) exige ~186 m de tubo
   contra 6 m; nenhuma correlação resolve. Decisão de projeto (P-32, arranjo, ou aceitar).
   Diagnóstico e árvore de alternativas: `docs/validacao/36-p001-diagnostico.md` (números anteriores
   ao trem; a sensibilidade do P-001 a P_D1/P_D2, ~0,2 % por Standing, não foi reconferida com o
   flash — o P-001 ficou fora do subproblema de pressão).
2. ~~O trem não reconcilia com o BOT~~ — **resolvida** pela recombinação da Nota 4 (nota 38,
   aprovada) e pelo trem produtivo (nota 39). A propagação do Rs do trem à μ do óleo vivo foi
   **aceita** (decisão de 2026-09-28, nota 40), com a limitação de aplicabilidade declarada.
3. **Composição do gás de lift** — ausente na fonte (BOT §2.3.3 só dá especificação); casos 9, 11,
   15 e 16.
4. **h e cp dos pseudo-componentes** — sem Cp_ig com fonte (a rota PNA para H/C não fecha).
5. **ρ da fase líquida pela EOS** (Péneloux) e **k líquido de hidrocarboneto** — não validados.
6. **Discretização das grades** do trocador (caso × envelope) — `docs/validacao/33-…`; muda número.
7. **Faixas de P_D1 e P_D2** — sem fonte: o BOT não dá pressão de degaseificador. A otimização
   (nota 42) usa um **domínio de estudo declarado** (região da nota 41) e a TVP ≤ 70 kPa como
   restrição contínua; o piso de P_D2 (sucção da VRU) segue sem fonte e não vira bound.
   **Decisão de fechamento (2026-09-29):** 700/200 ficam como **cenário-base não conforme** à TVP
   (máx. 110,8 kPa); o resultado da nota 42 fica separado, como resultado do subproblema, e não
   substitui as premissas produtivas — `docs/validacao/37`, `41`, `42`; `docs/PREMISSAS_E_LIMITACOES.md`.
8. **Otimização F15 (problema completo)** — `docs/validacao/23-otimizacao.md` segue como
   diagnóstico do alarme do P-001; o subproblema de pressão (nota 42) é a otimização que o TCC
   defende.

9. **T1 — base do trem × base do balanço** (≤ 0,55 %): aceita como limitação / aproximação do
   modelo (`docs/PREMISSAS_E_LIMITACOES.md` §10); física não alterada.

Pendências de engenharia de software (não físicas): o leitor do formato de ajustes da F10b
(`pfd/ajustes.estado_legado`) ainda existe — a fixture de teste `ajustes_sinteticos.toml` usa
esse formato; R3/R4 do P-003 (mudam o que o MC mostra).

## Próximo marco

**Release do TCC — PENDENTE DE VERIFICAÇÃO LATEX.** Auditoria documental concluída
(`docs/auditoria/AUDITORIA_TCC.md`). Antes da tag: (A) rodar `uv run pytest -m latex` no ambiente
Nix (24 testes não executados no contêiner da auditoria); (B) se houver um `design_cases_bot.json`
local, conferir que o sha256 é o da fixture auditada. Nenhuma funcionalidade nova: qualquer tarefa
responde antes "isso é necessário para defender a contribuição central do TCC ou para produzir um
artefato final?"
