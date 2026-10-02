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
  → pfd/integracao_termica                 → rating do P-001 no ponto fixo das propriedades;
                                             cargas RESIDUAIS dimensionam P-002/P-003 (ADR 0005)
  → pfd/layout (+ tools/buscar_layout_…)   → busca discreta da geometria, frente de Pareto física
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
- **Planta produtiva (16 casos, propostas do pacote):** 11 TAGs dimensionados, incluindo o
  **P-001** — DESIGN no caso de projeto, RATING nos de turndown, e o calor efetivamente
  recuperado propagado ao P-002 e ao P-003 pelas cargas residuais (ADR 0005,
  `docs/validacao/43`). Gate aprovado.
- **Otimização das pressões de separação (nota 42):** P_D1 × P_D2 → mesmo resolvedor → trem →
  SG-001/V-001/V-002 → perda de óleo estabilizado e carga de vapor da VRU, com TVP ≤ 70 kPa como
  restrição contínua (12 casos avaliáveis). Frente do NSGA-II conferida contra grade-oráculo de
  195 pontos: na resolução declarada, **um ponto** sobre a fronteira da TVP — P_D1 ≈ 510–540 kPa,
  P_D2 ≈ 134 kPa, recuperação 97,90 %, VRU 1,216 MSm³/d. Os dois objetivos não conflitam; quem
  limita é a TVP. Subproblema de pressão e separação, não a planta inteira.

## Entregue

| etapa | commit | resumo |
|---|---|---|
| DESIGN × RATING conectado ao P-001 | (este) | geometria escolhida por busca discreta, rating dos 16 casos com propriedades reavaliadas no ponto fixo, perda de carga verificada contra a P-17, cargas residuais dimensionando P-002/P-003 e tabela dos 16 casos — `docs/validacao/43`, ADR 0005 |
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

1. ~~**P-001 inviável**~~ — **resolvida** pela alternativa A5 da árvore de
   `docs/validacao/36-p001-diagnostico.md` (DESIGN no caso de projeto, RATING nos demais;
   ADR 0005, `docs/validacao/43`). A carga do P-001 é a do balanço preliminar; o que a área
   instalada não recupera num caso de turndown é compensado pelas utilidades (P-002 e P-003
   dimensionados pelas cargas residuais). O alarme está fechado em `config/pfd/alarmes.toml`, e
   os testes que reconstruíam o impedimento antigo (regra do Julia aplicada ao P-001, variantes
   "1 passe" e "emulsão no casco") saíram em 2026-10-02.
2. ~~O trem não reconcilia com o BOT~~ — **resolvida** pela recombinação da Nota 4 (nota 38,
   aprovada) e pelo trem produtivo (nota 39). A propagação do Rs do trem à μ do óleo vivo (Beggs
   & Robinson) foi APROVADA em 2026-09-28 (nota 40: rota produtiva, proibido voltar a Standing só
   para a viscosidade). Fase B ENCERRADA (2026-10-02) como sensibilidade documentada: rota vigente
   mantida pela consistência das bases e do modelo (não pela viabilidade do P-001) —
   `tools/comparar_rs_viscosidade.py`, nota 45.
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
   **Fase A — CONSOLIDADA (2026-10-02):** P-18/P-19 = 500/130 kPa absolutos, premissa preliminar
   do autor (`config/premissas.toml`, fonte na nota 44): o ponto exato da grade da nota 42 com
   g_TVP = −0,034 (TVP máxima 67,6 kPa nos 12 avaliáveis). Avisos que permanecem: TVP não
   verificada nos casos 9, 11, 15, 16; compatibilidade de P_D2 com a sucção da VRU não verificada.
   Regressões revistas pela nota 44. Fases seguintes: B — comparação Rs → μ (nota 45);
   C — ΔP do casco por Bell-Delaware (Branan pp. 46-47, Tab. 2-5) + refinamento local da grade +
   nova busca de layout do P-001; D — sensibilidades e tabela de atendimento à ET.
8. **Otimização F15 (problema completo)** — `docs/validacao/23-otimizacao.md` é registro
   histórico (de quando o P-001 estava em alarme); o subproblema de pressão (nota 42) é a otimização que o TCC
   defende.

9. **Multiplicidade de BOMBAS** — o contrato genérico de serviço (`sizing/servico.py`:
   instaladas × duty × standby) existe e é exercitado pela busca de layout do trocador, mas
   **nenhum TAG de bomba o usa**: B-001/B-002/B-003 continuam dimensionadas como uma unidade
   só. A vazão mínima contínua e a curva do fabricante não estão no acervo, e sem elas não há
   como declarar a filosofia de paralelo das bombas. Pendência declarada — não entrega.
10. **Perda de carga do lado CASCO** — não modelada em nenhum trocador. CORREÇÃO (2026-10-02): o
   acervo TEM a correlação — Branan pp. 46-47 (eqs. 2-32 a 2-38) com os coeficientes b1–b4 da
   Tab. 2-5, a mesma tabela do h_o; a conferir a linha 90°/Re 10–100 (b2 = 0,0963 impresso). Fase C. A do lado tubo é calculada (Darcy-Weisbach,
   Moran 2016) e verificada contra a P-17 no P-001, onde o lado tubo é o processo; no P-002 e
   no P-003 o lado tubo é a utilidade, e ali ela é reportada, não aprovada.

Pendências de engenharia de software (não físicas): o leitor do formato de ajustes da F10b
(`pfd/ajustes.estado_legado`) ainda existe — a fixture de teste `ajustes_sinteticos.toml` usa
esse formato; R3/R4 do P-003 (mudam o que o MC mostra). A otimização do problema COMPLETO
(F15) ficou mais lenta: ela dimensiona P-002 e P-003, e por isso cada indivíduo paga o ponto
fixo da integração realizada do P-001 (uma vez por indivíduo, não por TAG). O subproblema de
pressão (nota 42) não é afetado — ele não dimensiona trocador.

## Próximo marco

**Só fechamento documental** depois da nota 42 (instrução do usuário, 2026-09-29): SPRINTS, documentos de arquitetura, tabela de
premissas, balanço final, memoriais, resultados da otimização, figuras e tabelas, limitações, suíte
completa com cobertura e gate, tag de release. Qualquer tarefa nova responde antes: "isso é
necessário para defender a contribuição central do TCC ou para produzir um artefato final?"
