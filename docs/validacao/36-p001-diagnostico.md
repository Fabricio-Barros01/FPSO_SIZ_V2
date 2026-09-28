# 36 — P-001: o que torna o pré-aquecedor inviável (etapa B)

Diagnóstico **sem alteração de física**, com a planta produtiva do baseline `f196f36` (propostas do
pacote; gate aprovado). Números lidos do `EstadoProcesso` (`resolver_todos`) e do motor
(`fpso-siz dimensionar --tag P-001`); os de 1 passe vêm de `24-pelicula-baixo-reynolds.md`.
Nenhuma alternativa abaixo foi escolhida: a decisão é do usuário.

## 1. A cadeia da inviabilidade

O balanço define a carga do P-001 como a **máxima recuperação** na aproximação P-32:

```
Q_pre = min(C_frio, C_quente) · (T_22 − T_06 − ΔT_app)          (balanco/modelo.py)
```

Com C_frio ≈ C_quente (R = 0,99–1,05 nos casos 1–7), a troca é quase **balanceada**: em
contracorrente ΔT_ml ≈ ΔT_app em todo o trocador, logo **UA ≈ Q_pre/ΔT_app**. A P-32 fixa a área.

| caso | Q_pre (kW) | T frio in→out (°C) | T quente in→out (°C) | ΔT_ml (K) | P | R | NTU | UA (kW/K) |
|---:|---:|---|---|---:|---:|---:|---:|---:|
| **2** | 16.532 | 52,7 → 79,1 | 90,5 → 62,7 | 10,7 | 0,70 | 1,05 | 2,5 | **1.547** |
| 3 | 16.367 | 52,9 → 79,1 | 90,5 → 62,9 | 10,7 | 0,70 | 1,05 | 2,5 | 1.532 |
| 1 | 9.119 | 65,0 → 80,3 | 90,5 → 75,0 | 10,1 | 0,60 | 1,01 | 1,5 | 905 |
| 5 | 4.533 | 35,0 → 80,0 | 90,5 → 45,0 | 10,3 | **0,81** | 1,01 | **4,4** | 442 |
| 6 | 1.170 | 35,0 → 79,9 | 90,5 → 45,0 | 10,3 | 0,81 | 1,01 | 4,4 | 114 |
| 4 | 2.716 | 45,0 → 80,1 | 90,5 → 55,0 | 10,2 | 0,77 | 1,01 | 3,4 | 266 |
| 8, 9, 7, 11 | 3.229–6.892 | — | — | 10,0–14,9 | 0,31–0,50 | 1,0–2,2 | 0,5–1,2 | 231–588 |
| 10, 12–16 | 0 (inativo) | T_06 ≈ 90 °C: o óleo já chega à T de tratamento | | | | | | |

## 2. Respostas da auditoria

| pergunta | resposta |
|---|---|
| restrição que governa | com **2 passes** (default de Saari): o fator F do casco 1-2 sai do domínio (P > P_máx ≈ 0,59 para R ≈ 1) — primeiro no caso 1, e em todos os casos 1–6. Com **1 passe** (contracorrente): **comprimento de tubo > 6 m** (`l_tubo_max`) |
| caso que governa | a **área** é fixada pelo caso **2** (UA 1.547 kW/K, caso de projeto da banda); o **comprimento** é fixado pelos casos de turndown **laminares** 4, 5, 6 e 11 (U ≈ 25 W/m²K; caso 5 pede 434 m no feixe escolhido). O menor comprimento de toda a grade é 186 m |
| requisito térmico | NTU de 2,5 (projeto) a 4,4 (casos 5/6), consequência de ΔT_app = 10 K numa troca balanceada |
| da fonte (BOT) | existência do pré-aquecedor óleo/óleo (§2.7.1.1), T de chegada 35–90 °C (Tab. 2.2.2.3), T_trat ≥ 90 °C (§2.7.1.4), T de estocagem 40 °C (§2.7.1.10), reserva instalada (§2.7.1.11), TEMA/API 660 (§10.3.4), vazões |
| premissa | **ΔT_app = 10 K (P-32, do autor)**; regra de máxima recuperação; 2 passes; uma geometria para todos os casos; k = 0,13 W/m·K e incrustação 3,5·10⁻⁴ m²K/W nos dois lados (propostas); cp_O = 2,0 (P-10); μ de emulsão (Beggs & Robinson + Zanker) |
| limite construtivo | L ≤ 6 m (Branan p. 38, default do método), D_casco ≤ 2.500 mm e v ≤ 3 m/s (Saari Tab. 3.1) |
| natureza do problema | **combinação**: (a) abordagem térmica (P-32) × troca balanceada → UA alto; (b) óleo viscoso que não chega ao turbulento sob o teto de 3 m/s → U baixo; (c) **turndown** de até ~24× em capacidade térmica (C_frio de 627 a 26 kW/K) numa geometria única → laminar (U ≈ 25) nos casos de baixa vazão; (d) arranjo 1-2 incompatível com P ≈ 0,7–0,8. Não é vazão nem numérico |

**O P-001 não depende de P_D1/P_D2.** Com Standing, o gás dissolvido em C-06 é fixado pela
pressão do FWKO; P_D1 e P_D2 só entram via aquecimento nas bombas. Caso 2: Q_pre vai de
16.532 a 16.570 kW (0,2 %) com (P_D1, P_D2) de (700, 200) a (400, 120) kPa.

## 3. Árvore de alternativas (hipóteses, não autorização)

Arranjo do casco 1-2 em série para os casos que o exigem (F ≥ 0,8, conta da Fig. 4.3 de Saari
generalizada para N cascos): caso 2 → 3 cascos; caso 4 → 4; casos 5 e 6 → 5 cascos.

| alternativa | o que muda | fonte necessária | impacto no balanço | impacto no resto da planta | muda a contribuição do TCC? |
|---|---|---|---|---|---|
| **A1. Rever P-32** (ΔT_app) | UA cai com 1/ΔT_app: caso 2 → 517 kW/K (20 K) e 153 kW/K (30 K) | valor de aproximação para troca líquido-líquido de óleo com fonte (acervo) | Q_pre ↓, **Q_H ↑** (caso 2: 6,9 → 12,8 → 18,8 MW), Q_C ↑ | P-002 e P-003 maiores; objetivo "carga de aquecimento" piora | não; e P-32 poderia ser **variável** (troca área × utilidade) |
| **A2. Cascos 1-2 em série** | resolve o domínio de F (3–5 cascos) | Saari (já no acervo); método já tem `cascos_serie` | nenhum | só o P-001 | não. **Sozinha não resolve**: a área (~4.000 m² no projeto, ~17.600 m² no turndown laminar) continua |
| **A3. Contracorrente pura** (1 passe, ou grampo/tubo duplo) | F = 1 | Saari §4.2.1 (1 passe já existe); tubo duplo exigiria método novo | nenhum | só o P-001 | não. Mesma limitação de área |
| **A4. Inverter os lados** | óleo tratado quente no tubo | — | nenhum | — | já testada (14-alarmes): segue inviável |
| **A5. Operar o trocador em classificação (rating) nos casos fora do projeto** | P-001 dimensionado no caso de projeto; nos demais Q_pre = o que a área entrega, e o P-002 cobre o resto | prática de projeto (design × rating); decisão de modelagem | Q_pre passa a depender da geometria: acopla balanço ↔ dimensionamento (laço) | P-002/P-003 e cargas mudam em todos os casos | não, mas é mudança de arquitetura do balanço |
| **A6. Unidades em paralelo com desligamento no turndown** | mantém velocidade nos casos de baixa vazão | filosofia de operação (fora do BOT) | nenhum | só o P-001; o envelope teria arranjo por caso (não suportado hoje) | não |
| **A7. Trocador de placas gaxetadas** | U muito maior em óleo viscoso (turbulência em Re baixo) | BOT §10.3.2 **admite** placas (API 667) se o SELLER as considerar; só o aquecedor de produção as veta (§2.7.1.5). Falta método e fonte de correlação no acervo | nenhum | método novo; incrustação/sais (§2.7.1.15) contra placas | não, mas é escopo grande |
| **A8. Aceitar que o P-001 não faz essa recuperação** | Q_pre = 0 (ou recuperação limitada) | BOT §2.7.1.16 admite "optimizations… or different solutions" com aprovação do comprador; contraria o esquema da Fig. 2.7.1.17 | Q_H ↑ até ~23 MW no caso 2; Q_C ↑ | P-002 e P-003 maiores | não |
| A9. Tubo mais longo | L > 6 m | Branan limita a 20 ft | nenhum | — | não. 186 m está fora de qualquer estoque |

**Leitura:** nenhuma alternativa é um ajuste numérico. As que resolvem de fato atacam a
**abordagem (A1)**, o **modo de operação no turndown (A5/A6)** ou o **tipo de equipamento (A7)**.
A2/A3 só trocam o primeiro impedimento pelo segundo. Como o P-001 é independente de P_D1/P_D2,
a decisão sobre ele **não** bloqueia o laço pressão → flash → vasos; bloqueia a otimização da
planta **inteira** (a área dos trocadores é objetivo).
