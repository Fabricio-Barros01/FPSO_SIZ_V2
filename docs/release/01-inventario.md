# Release do TCC — 01. Inventário do estado final

Auditoria de fechamento, **sem alteração de código nem de física**. Baseline físico congelado:
`main` em `b638c193e97450ac563aa5c5099ec3f2a6242e74` (merge do PR #9). Branch de auditoria:
`claude/tcc-release-audit`. Todos os números abaixo foram **medidos nesta auditoria** sobre o
baseline (suíte, gate e planta rodados de novo em 2026-09-29), salvo quando indicada a nota de
origem.

## BASELINE

| item | valor |
|---|---|
| SHA | `b638c193e97450ac563aa5c5099ec3f2a6242e74` |
| pacote | `fpso_siz` 0.1.0 |
| entrada | `tests/fixtures/python_ref/design_cases_bot.json` (sha256 `ca3dfe559b32…`, 16 casos) |
| propostas | `config/pfd/pendencias_propostas.toml` (sha256 `a1715287ab3a…`), carregadas por padrão |
| bibliotecas de propriedade | thermo 0.6.1; chemicals 1.5.2; pymoo 0.6.2 (otimização) |
| arquivos locais `design_cases_bot.json` / `main.tex.j2` | **ausentes neste checkout** (nada a preservar aqui) |

## ARQUITETURA ATIVA

```
arquivo do BOT + premissas (config/premissas.toml)
  → balanco/modelo.resolver_todos            → EstadoProcesso (único estado; trem em balanco/trem.py)
  → pfd/entradas (termo/servico)             → entradas dos 11 TAGs, cada propriedade com proveniência
  → pfd/equipamento → core/motor + sizing/*  → envelopes sobre os 16 casos
  → pfd/otimizacao + _otim (pymoo)           → subproblema de pressão (nota 42)
  → output/* e pfd/memorial (+ core/memoria) → JSON, CSV, memória de cálculo LaTeX
  → tools/auditar_saida_pfd.py               → gate
```

Um resolvedor produtivo, uma API termodinâmica (`termo/servico.py`; ChEDL só em
`termo/backend.py`), proveniência única (`config/termo/proveniencia.toml`), sem modos de paridade
nem modo sombra (ADR 0004). Estudos ficam em `tools/` chamando a mesma API.

## 11 TAGs (planta produtiva, premissas P-18 = 700 kPa e P-19 = 200 kPa)

| TAG | equipamento / método | estado | resultado principal | governante / caso |
|---|---|---|---|---|
| SG-001 | separador trifásico / Stewart & Arnold | dimensionado | d = 6.050 mm, Leff = 17,867 m, 684,8 m³ | líquido / BOT 12 |
| V-001 | knockout bifásico / S&A 2F | dimensionado | d = 4.700 mm, Leff = 11,719 m, 284,9 m³ | líquido / BOT 02 |
| V-002 | knockout bifásico / S&A 2F | dimensionado | d = 4.700 mm, Leff = 11,807 m, 286,4 m³ | líquido / BOT 02 |
| TO-001 | tratador eletrostático / Arnold | dimensionado | d = 5.550 mm, Leff = 16,428 m, 531,7 m³ | líquido / BOT 02 |
| TO-002 | tratador eletrostático / Arnold | dimensionado | d = 5.550 mm, Leff = 16,402 m, 531,1 m³ | líquido / BOT 02 |
| P-001 | trocador óleo/óleo / Saari + Bell-Delaware | **inviável** | — (diagnóstico numérico no MC) | — |
| P-002 | aquecedor / Saari + Bell-Delaware | dimensionado | 1.701 tubos/passe, L = 6,000 m, 407,2 m² | térmica / BOT 02 |
| P-003 | resfriador / Saari + Bell-Delaware | dimensionado | 7.435 tubos/passe, L = 4,910 m, 1.456,4 m² | térmica / BOT 07 |
| B-001 | bomba / Moran | dimensionado | DN 600, H = 75,02 m, 307,3 kW | estática / BOT 03 |
| B-002 | bomba / Moran | dimensionado | DN 250, H = 183,4 m, 143,3 kW | estática / BOT 03 |
| B-003 | bomba / Moran | dimensionado | DN 125, H = 252,2 m, 45,5 kW | estática / BOT 03 |

**10 dimensionados, 1 inviável (P-001).** O P-001 é inviabilidade legítima do modelo
(nota 36): aproximação P-32 de 10 K numa troca balanceada + óleo viscoso laminar no turndown +
arranjo 1-2 fora do domínio de F.

## 16 CASOS BOT

Tab. 2.2.2.3 do BOT (I-ET-3010.2K-1200-941-P4X-001 rev. C), sete composições por tipo de fluido
(Tab. 2.2.2.4). Os 16 são o **envelope de dimensionamento** de todos os TAGs (nota 35).

## 12 CASOS TERMODINAMICAMENTE AVALIÁVEIS

Casos **1–8, 10, 12, 13, 14** (sem gás de lift): composição do caso pela recombinação da Nota 4 na
referência do FWKO (2.500 kPa(a), T do caso — premissa de modelagem aprovada, nota 38) e trem de
flashes SG-001 → V-001 → V-002 (nota 39). Reproduzem Q_G do BOT e Q_O de óleo morto com erro relativo ≤ 1,2·10⁻⁹ (nota 39 §3).

## 4 CASOS COM LIMITAÇÃO DE LIFT

Casos **9, 11, 15, 16**: o gás de lift não tem composição na fonte (BOT §2.3.3 só dá
especificação). "Não avaliáveis termodinamicamente para integração completa": seguem no envelope
por Standing, sem TVP e sem recuperação de óleo verificadas. Nenhuma composição suposta.

## MODELOS PRODUTIVOS

| domínio | modelo | fonte |
|---|---|---|
| balanço | massa e energia sensível (cp constante por componente), reciclo por substituição sucessiva, FWKO por eficiência (P-43) | script de referência portado; F10w |
| gás por estágio | avaliáveis: flash PR com pseudo-componentes (trem); não avaliáveis: ΔRs de Standing | Peng-Robinson (1976), Riazi & Al-Sahhaf (1996); Standing (1947) |
| composição do caso | recombinação da Nota 4 (FWKO) | BOT Tab. 2.2.2.3, Notas 2–4 (premissa de modelagem, nota 38) |
| TVP | ponto de bolha do líquido final pelo mesmo flash, a 40 °C | BOT §2.3.1.1, §2.7.1.10 |
| vasos | Stewart & Arnold (3F e 2F); Arnold (eletrostático) | S&A (2008) |
| trocadores | Saari LMTD + Bell-Delaware; película do tubo em três regimes | Saari; Branan (2012) pp. 40–41 |
| bombas | Moran (2016) | Moran |
| otimização | NSGA-II (subproblema de pressão) | pymoo; ADR 0003 |

## PROPRIEDADES PRODUTIVAS

Do contrato de proveniência (28 declarações; medido):

- **consumidas e validadas**: MW, ρ_std e cp do gás do corte leve; ρ do óleo pela API; ρ e μ das
  fases (BOT, Beggs & Robinson, Laliberté, Zanker); Z, ρ e μ do gás (PR/Brokaw); Pv = P do vaso;
  água de utilidade (IAPWS); **nos 12 avaliáveis**: composição do caso, β, x, y, MW_v, Z_v, ρ_v do
  trem; **TVP** (consumida só pela otimização).
- **restrita aos não avaliáveis**: gás por Standing, ρ padrão do gás, ρ e Z do gás do corte leve.
- **sem consumidor (diagnóstico)**: MW da mistura (`MW_mistura`).
- **não validada, sem consumidor**: ρ da fase líquida pela PR (razão 0,541).
- **ausentes**: h/cp dos pseudo-componentes; μ e k das fases do fluido de poço.
- **limitação declarada**: Beggs & Robinson recebe só o volume de gás dissolvido, sem composição;
  aplicabilidade a gás rico em CO2 não demonstrada pela fonte (nota 40).

## PREMISSAS PRINCIPAIS

Tabela completa (55 linhas F-xx/P-xx, com justificativa e classe) em
`output/latex/balanco/premissas_memorial.toml`; valores em `config/premissas.toml`.

| id | premissa | valor | classe |
|---|---|---|---|
| F-02 | P do FWKO | 2.500 kPa(a) | BOT |
| **P-18** | P do V-001/TO-001 | 700 kPa | A VALIDAR |
| **P-19** | P do V-002/TO-002 | 200 kPa | A VALIDAR — **não atende a TVP no modelo** (ver pendências) |
| P-32 | aproximação do P-001 | 10 K | premissa do autor; decide a inviabilidade do P-001 |
| P-43 | η padrão do FWKO | 0,85 | premissa do autor |
| P-10/11/12 | cp do óleo/água/diluição | 2,0 / 3,35 / 4,18 kJ/kg·K | premissa |
| F-08 | T de estocagem | 40 °C | BOT |
| P-25, P-26 | óleo na água; arraste | 2 kg/m³; 0,1 gal/MMscf | S&A; premissa |
| Nota 4 (FWKO) | referência da recombinação | 2.500 kPa, T do caso | premissa de modelagem (nota 38) |
| propostas | 43 entradas sem fonte (bombas, trocadores, tratadores) | — | "proposto" pelo autor (`pendencias_propostas.toml`) |

## LIMITAÇÕES PRINCIPAIS

1. Gás de lift sem composição → 4 casos fora da termodinâmica integrada.
2. h e cp dos pseudo-componentes ausentes → energia sensível com cp constante, sem calor latente.
3. ρ líquida pela PR não validada (sem Péneloux) → ρ líquida pela API, sem correção de T e Bo.
4. μ do gás pelo corte leve (sem método de transporte para a composição y).
5. Beggs & Robinson sem variável de composição do gás (CO2) — nota 40.
6. Composição do caso validada **por consistência com o BOT**, sem PVT medido.
7. 43 entradas de TAG são **propostas** do autor, sem fonte.
8. Grades desalinhadas caso × envelope nos trocadores (nota 33; muda número se revisto).
9. Domínio de P_D1/P_D2 da otimização é de **estudo** (sem fonte para o piso de P_D2).
10. Subproblema de pressão não é otimização da planta inteira.

## PENDÊNCIAS DE PROJETO (decisão, não defeito)

1. **P-001 inviável** — alternativas A1–A9 da nota 36; nenhuma adotada.
2. **P-19 = 200 kPa não atende a TVP ≤ 70 kPa no modelo**: TVP de 93,1–110,8 kPa nos 12
   avaliáveis (medido agora). A otimização (nota 42) aponta P_D1 ≈ 510–540 kPa e P_D2 ≈ 134 kPa,
   mas **as premissas produtivas continuam 700/200** — a planta, os memoriais e o gate são os de
   um ponto que viola a especificação do BOT. Decidir: manter 700/200 com a não conformidade
   declarada, ou adotar o ponto da frente como premissa (muda número produtivo).
3. Piso de P_D2 e ΔP de transferência sem fonte.

## ITENS NÃO CONSUMIDOS

- `MW_mistura` (diagnóstico); `rho_liquido_flash` (não validada); h/cp e transporte do fluido de
  poço (ausentes).
- `docs/validacao/23-otimizacao.md`: otimização F15 do problema completo — diagnóstico do alarme
  do P-001, não resultado do TCC.
- Ferramentas de estudo em `tools/` (mapa de pressão, sensibilidade de viscosidade, relatório do
  trem, alarmes, pinch): fora do caminho produtivo, chamam a mesma API.
- Leitor do formato de ajustes da F10b (`pfd/ajustes.estado_legado`), mantido pela fixture de teste.

## RESULTADO DA OTIMIZAÇÃO (nota 42)

Subproblema de pressão e separação: P_D1 × P_D2 → mesmo resolvedor → trem → SG-001/V-001/V-002;
objetivos perda de óleo estabilizado (1 − R) e carga de vapor da VRU; TVP ≤ 70 kPa como restrição
contínua (12 avaliáveis). Grade-oráculo de 195 pontos (frente: 1 ponto, (500; 130)); NSGA-II 40 ×
20, semente 1: 3 pontos na fronteira da TVP — **P_D1 ≈ 510–540 kPa, P_D2 ≈ 134 kPa, recuperação
97,90 %, VRU 1,216 MSm³/d**; na resolução declarada, um ponto. Os objetivos não conflitam; a TVP
limita. Frente reproduzida, reavaliação fora do otimizador idêntica, mesma semente → mesma
sequência.

## TESTES

- suíte padrão (`-m 'not latex'`): **1.321 passed**, 0 falhas, 9 min 10 s (`-n 4 --dist loadscope`,
  com cobertura);
- coletados: 1.345; **24 testes `latex` não executados nesta auditoria** — o contêiner não tem
  `latexmk`/`pdflatex`/`pdftotext`. A compilação dos memoriais fica a verificar no ambiente Nix.

## COBERTURA

**95,93 %** (branch), limiar 90 %.

## GATE

`tools/auditar_saida_pfd.py`: **APROVADA**, código de saída 0; identidade completa (commit
`b638c193e974`, árvore limpa); 0 `ERRO_NUMERICO`, 0 `ERRO_OUTPUT`, 316 `NAO_APLICAVEL` e 22
`INVIAVEL`, todos justificados.

## Achados da leitura

> **Situação:** D1–D7 corrigidos como documentação; D8 mantido (agrupamentos deliberados); T1
> aceito como limitação; decisões de fechamento em `docs/auditoria/AUDITORIA_TCC.md`.

### Documentais (texto desatualizado ou rastreabilidade quebrada; não mudam número)

| # | onde | achado |
|---|---|---|
| D1 | `README.md` §5–7 | "1.177 testes" (hoje 1.345 coletados); descreve o Julia como oráculo de paridade (deixou de ser requisito, ADR 0004); não menciona trem, TVP nem a otimização; P-001 "434 m" sem o "186 m" mínimo da grade (nota 36) |
| D2 | `SPRINTS.md` pendência 2 | "decisão pendente: propagação do Rs do trem à μ" — decidida na nota 40; pendência 1 "a reconferir com o flash" ainda aberta; várias linhas "Entregue" com commit "(este)" |
| D3 | `config/pfd/tags/p_002.toml`, `p_003.toml` | a fonte da geometria recomendada cita `tools/reotimizar_trocadores.py` e `config/pfd/reotimizacao.toml`, **removidos** na consolidação (ADR 0004) — a rastreabilidade aponta para arquivos que não existem |
| D4 | `config/termo/fluidos.toml` | comentários citam a flag `--oleo-morto` (removida) e "paridade bit a bit mantida" |
| D5 | `pfd/entradas._rs` | docstring diz "(Standing)"; nos avaliáveis o Rs vem do trem |
| D6 | notas 35, 36, 37 | 35 ainda se apresenta como "pendente de aprovação" (decidida na 38); tabelas da 36 são do baseline Standing `f196f36` (Q_pre do caso 2: 16.532 → 16.343 kW com o trem, nota 39 §8) |
| D7 | `premissas_memorial.toml`, P-19 | justificativa "último estágio próximo da atmosfera (TVP/RVP)" — o próprio modelo mostra que 200 kPa não atende a TVP |
| D8 | `config/premissas.toml` | ids repetidos (P-17 ×2, P-30 ×3, P-31 ×2) — agrupamento proposital a confirmar |

### Candidato técnico (não é bug objetivo; limitação não declarada)

**T1 — base do trem × base do balanço.** O trem flasha o fluido recombinado de C-01; o balanço
tira do líquido o óleo que sai na água do FWKO (P-25) e o arraste (P-26), e soma o óleo do reciclo.
Os vapores de V-001/V-002 são calculados sobre o líquido do trem, não sobre o C-06 do balanço. A
diferença de base é de 10⁻⁶ a **0,55 %** (máximo no caso 12; medida agora), e a massa fecha porque
o líquido é obtido por diferença. Não é erro de conservação; é aproximação que nenhuma nota
declara. Proposta: declarar como limitação (nenhuma alteração de física).
