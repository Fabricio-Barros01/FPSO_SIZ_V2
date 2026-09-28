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
- **Trem SG-001 → V-001 → V-002:** parte do `EstadoProcesso`, **diagnóstico** — a vazão de gás
  por estágio consumida é a de Standing.
- **Planta produtiva (16 casos, propostas do pacote):** 10 TAGs dimensionados; **P-001 inviável**
  (alarme aberto, área). Instantâneo bit a bit `409f1800…f16414`; gate aprovado.

## Entregue

| etapa | commit | resumo |
|---|---|---|
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
2. **O trem não reconcilia com o BOT** — a composição é por tipo de fluido; GOR(flash)/GOR(BOT)
   de 0,62 a 2,16. Enquanto isso, β/x/y ficam `nao_validada` e sem consumidor. Consumi-los muda
   o dimensionamento por capacidade de gás e exige decidir o que os 16 casos representam
   (envelope de projeto × estado composicional). Leitura da fonte: o BOT (Tab. 2.2.2.3, Nota 4)
   prevê flash + recombinação para ajustar o GOR de cada caso — `docs/validacao/35-casos-bot.md`
   (condição de referência comparada em `docs/validacao/38-recombinacao-nota4.md`: recomendada a do
   FWKO, 2.500 kPa(a) e T do caso, por consistência com Nota 3 e Tab. 2.5.2; aguarda aprovação).
3. **Composição do gás de lift** — ausente na fonte (BOT §2.3.3 só dá especificação); casos 9, 11,
   15 e 16.
4. **h e cp dos pseudo-componentes** — sem Cp_ig com fonte (a rota PNA para H/C não fecha).
5. **ρ da fase líquida pela EOS** (Péneloux) e **k líquido de hidrocarboneto** — não validados.
6. **Discretização das grades** do trocador (caso × envelope) — `docs/validacao/33-…`; muda número.
7. **Faixas de P_D1 e P_D2** para a otimização — sem fonte ainda; a arquitetura já as aceita por
   configuração (`destino = "premissa"`), e o trem as lê do estado. O BOT não dá pressão de
   degaseificador; a TVP ≤ 70 kPa (§2.3.1.1/§2.7.1.10) é o critério do teto de P_D2. No modelo
   diagnóstico atual (composição não reconciliada, x `nao_validada`) o teto preliminar sai
   ≈ 137–162 kPa(a) e a P-19 = 200 kPa o excede — não é verificação de projeto nem limite de
   otimização antes da recombinação da Nota 4; o piso depende da VRU, fora do BOT —
   `docs/validacao/37-faixas-pressao-degaseificadores.md`.
8. **Otimização F15** — `docs/validacao/23-otimizacao.md` desatualizado; rodar de novo depois de
   decidir 1 e 7.

Pendências de engenharia de software (não físicas): o leitor do formato de ajustes da F10b
(`pfd/ajustes.estado_legado`) ainda existe — a fixture de teste `ajustes_sinteticos.toml` usa
esse formato; R3/R4 do P-003 (mudam o que o MC mostra).

## Próximo marco

**Fechar o laço P → flash → dimensionamento → otimização** (a contribuição central do TCC).
Depende de decisão do usuário sobre as pendências 2 e 7: o que os casos do BOT representam para
o trem e com que faixa, e com que fonte, P_D1/P_D2 entram como variáveis.
