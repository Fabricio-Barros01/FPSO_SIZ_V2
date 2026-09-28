# 41 — Mapa de pressão: P_D1 e P_D2 → flash → dimensionamento → TVP

**Estudo de sensibilidade** autorizado pelo usuário em 2026-09-28: P_D1 e P_D2 como variáveis de
estudo, **não** como variáveis do algoritmo multiobjetivo. P-001 fora do subproblema. Nenhuma
física produtiva mudou; o gate é idêntico ao do `main` (`8f89d7f`).

Gerado por `tools/mapa_pressao.py` — só orquestração da API:
`P_D1/P_D2 → Contexto(alteracoes) → resolver_todos → trem produtivo → SG-001/V-001/V-002 → TVP e
métricas`. Tabelas completas: [`mapa_pressao/mapa_pressao.md`](mapa_pressao/mapa_pressao.md);
todos os pontos e colunas: [`mapa_pressao/mapa_pressao.csv`](mapa_pressao/mapa_pressao.csv).
Referência: P_D1 = 700 kPa (P-18), P_D2 = 200 kPa (P-19).

## 1. Grade

P_D1 ∈ {200, 350, 500, 700, 1.000, 1.500, 2.000} kPa × P_D2 ∈ {110, 130, 150, 175, 200, 250} kPa
= 42 pontos (`config/pfd/mapa_pressao.toml`). P_D1 = 200 entra de propósito para que a região
inválida P_D2 ≥ P_D1 apareça classificada. Custo: 11 min 48 s.

## 2. Grade × faixa de projeto

A grade é a **resolução do estudo**. Os seus extremos (200 e 2.000; 110 e 250 kPa) **não são
limites**. Os limites e a sua natureza, sem misturar os conceitos:

| limite | variável | natureza | valor | sustentação |
|---|---|---|---|---|
| TVP ≤ 70 kPa na estocagem | P_D2 (principalmente) | **com fonte** (o critério) | 70 kPa | BOT §2.3.1.1 e §2.7.1.10 |
| P_D1 < sucção do compressor principal | P_D1 | **com fonte** | < 2.200 kPa(a) | BOT §2.7.3.9.20.1 — valor **estimado** pelo próprio BOT |
| P_D2 < P_D1 | ambas | **inferido pelo processo** | ΔP > 0 | topologia (líquido do TO-001 ao V-002 sem bomba); ΔP mínimo sem fonte |
| P_D2 que atende a TVP em todos os 12 casos | P_D2 | **diagnóstico** | ≤ 110–130 kPa, conforme P_D1 (§4) | calculado pelo modelo (trem, Nota 4); não é bound |
| piso de P_D2 | P_D2 | **sem fonte** | — | sucção da VRU não está no BOT |
| 200/2.000 e 110/250 kPa | — | **simples extremo da grade** | — | nenhuma |

## 3. Tabela completa

Ver [`mapa_pressao/mapa_pressao.md`](mapa_pressao/mapa_pressao.md) (estado de cada ponto, análise
termodinâmica, envelope de dimensionamento, sensibilidade) e o CSV. Para cada ponto válido:
P_D1, P_D2, TVP mínima e máxima (12 casos), casos com TVP > 70 kPa, Q_G máximo de SG-001, V-001,
V-002 e VRU (16 casos), diâmetro, Leff, volume, governante e caso governante dos três vasos,
exigência relativa gás/líquido de V-001 e V-002, volume total e potência máxima de B-001, B-002
e B-003.

## 4. Envelope de TVP (12 casos avaliáveis)

| P_D2 (kPa) | TVP máx. na grade (kPa) | casos > 70 kPa |
|---:|---|---|
| 110 | 55,6–60,7 | 0 em todo P_D1 |
| 130 | 67,6–72,8 | 0 com P_D1 ≤ 1.000; 2 com P_D1 = 200 e 1.500; 4 com 2.000 |
| 150 | 79,8–85,0 | 8–12 |
| 175–250 | 95–148 | 12 |

Pontos em que **todos** os 12 casos atendem: (P_D1; P_D2) = (200–2.000; 110) e (350–1.000; 130).
Com a P-19 atual (200 kPa) nenhum caso atende. A TVP é **só dos 12 casos avaliáveis**; os 4 com
gás de lift não têm TVP calculada e **não** estão verificados por esta tabela.

## 5. Efeito de P_D1

P_D1 **redistribui** o gás entre os desgaseificadores e muda menos o total (amplitude média do
gás à VRU de 97 mil Sm³/d ao longo de P_D1, contra 173 mil ao longo de P_D2): Q_G do V-001 cai de
1,27 MSm³/d (P_D1 = 200) a 0,36 MSm³/d (2.000), e o do V-002 sobe de 9 mil a 1,02 MSm³/d. A
potência do B-002 (recalque da água do TO-001 de P_D1 a P_rec) cai de 166 para 41 kW. Na TVP o
efeito é pequeno (amplitude média 5 kPa, contra 81 kPa de P_D2). Nos vasos: Leff do V-001 varia
3,2 % (não monotônico), sem mudar o diâmetro.

## 6. Efeito de P_D2

P_D2 **governa a TVP** (crescente em todas as linhas, 45 → 148 kPa) e o gás total à VRU
(decrescente, amplitude média 173 mil Sm³/d), e a potência do B-001 (recalque de P_D2 a 800 kPa:
257–320 kW). O óleo tratado recuperado cresce com P_D2 (+3 % na grade): menos óleo morto vaporiza
no V-002.

## 7. Efeito combinado

Não há interação que mude o quadro: a TVP é governada por P_D2 em qualquer P_D1 (com um
deslocamento de ~5 kPa ao ir de 350 a 2.000 kPa); a partição de gás é governada por P_D1. O ponto
de maior gás à VRU é (2.000; 110) e o de menor, (700; 250).

## 8. Sensibilidade de Q_G por estágio

Critério declarado antes dos resultados (`[sensibilidade]`): Δrel = (máx − mín)/|referência|;
INSENSÍVEL < 1 %, FRACAMENTE SENSÍVEL 1–5 %, SENSÍVEL ≥ 5 %.

| grandeza (16 casos) | referência | Δ abs | Δ rel | mínimo (P_D1; P_D2) | máximo | em P_D1 | em P_D2 | domina | classe |
|---|---:|---:|---:|---|---|---|---|---|---|
| Q_G SG-001 máx. (Sm³/d) | 12.046.580 | 933 | 0,01 % | (200; 175) | (1.500; 110) | não mon. | decrescente | P_D1 | INSENSÍVEL |
| Q_G V-001 máx. | 861.091 | 913.981 | 106 % | (2.000; 110) | (200; 175) | decrescente | crescente | P_D1 | SENSÍVEL |
| Q_G V-002 máx. | 265.189 | 1.009.272 | 381 % | (200; 175) | (2.000; 110) | crescente | decrescente | P_D1 | SENSÍVEL |
| Q_G VRU máx. | 1.126.280 | 298.962 | 27 % | (700; 250) | (2.000; 110) | não mon. | decrescente | P_D2 | SENSÍVEL |

## 9. Sensibilidade das geometrias

| grandeza (16 casos) | referência | Δ rel | domina | classe |
|---|---:|---:|---|---|
| SG-001 d | 6.050 mm | 0 | — | INSENSÍVEL |
| SG-001 Leff / volume | 17,867 m / 684,8 m³ | 0,01 % | P_D1 | INSENSÍVEL |
| V-001 d | 4.700 mm | 0 | — | INSENSÍVEL |
| V-001 Leff / volume | 11,719 m / 284,9 m³ | 3,2 % / 2,3 % | P_D1 | FRACAMENTE SENSÍVEL |
| V-002 d | 4.700 mm | 0 | — | INSENSÍVEL |
| V-002 Leff / volume | 11,807 m / 286,4 m³ | 3,0 % / 2,2 % | P_D2 | FRACAMENTE SENSÍVEL |
| V-001 exigência gás/líquido | 0,125 | 401 % | P_D1 | SENSÍVEL — mas ≤ 0,53 na grade |
| V-002 exigência gás/líquido | 0,108 | 644 % | P_D1 | SENSÍVEL — mas ≤ 0,70 na grade |

A exigência de gás varia muito, mas **nunca governa**: o maior valor na grade é 0,70 do que o
líquido exige (V-002 em (2.000; 110)). O Leff dos desgaseificadores varia pelo **líquido** que
sai (menos óleo morto vaporizado em pressão maior), não pelo gás.

## 10. Volume total dos três vasos

1.246,3–1.257,6 m³ (referência 1.256,1): **Δrel 0,90 % — INSENSÍVEL**. Só na região em que a TVP
atende nos 12 casos: 1.246,3–1.254,4 m³ (0,65 %).

## 11. Bombas

| bomba (16 casos) | referência | faixa | Δ rel | domina | classe |
|---|---:|---|---:|---|---|
| B-001 (óleo tratado, P_D2 → 800 kPa) | 281,6 kW | 257,4–319,8 | 22 % | P_D2 | SENSÍVEL |
| B-002 (água do TO-001, P_D1 → P_rec) | 131,2 kW | 41,4–165,8 | 95 % | P_D1 | SENSÍVEL |
| B-003 (água do TO-002, P_D2 → P_rec) | 42,7 kW | 41,2–44,7 | 8,2 % | P_D2 | SENSÍVEL |

Cada uma fica entre ~40 e ~320 kW — ordem de grandeza pequena frente às cargas térmicas (MW), e
as potências de bomba **não são objetivo** da otimização atual.

## 12. Mudanças de governante

Diâmetro e mecanismo governante (líquido) **não mudam** em nenhum dos 40 pontos, nos três vasos.
O caso governante do SG-001 (BOT 12) e do V-002 (BOT 02) também não. O do **V-001** passa de BOT 02
a BOT 03 quando P_D1 ≥ 1.000 kPa: os dois casos estão praticamente empatados no líquido (nota 39
§7), e a pressão decide o desempate — sem efeito no diâmetro.

## 13. Regiões inválidas e não avaliáveis

| classe | pontos |
|---|---|
| inválido: P_D2 ≥ P_D1 (limite de processo) | (200; 200), (200; 250) — classificados, não calculados |
| flash sem convergência / trem incompleto | nenhum |
| TVP sem solução | nenhum |
| TAG inviável | nenhum |
| casos não avaliáveis termodinamicamente | os 4 com gás de lift (9, 11, 15, 16), em **todos** os pontos: dimensionados por Standing, sem TVP |

## 14. 16 casos de dimensionamento × 12 casos termodinâmicos

- **Envelope de dimensionamento**: SG-001, V-001 e V-002 sobre os 16 casos do BOT, com os 4 de
  lift por Standing (a pressão os afeta pelo ΔRs de Standing nas mesmas P_D1/P_D2); Q_G e
  potências também são máximos sobre os 16.
- **Análise termodinâmica**: TVP e óleo tratado só sobre os 12 avaliáveis. A região "TVP atende"
  do §4 **não** verifica os 16 casos.

## 15. Conclusão — P_D1 e P_D2 justificam variáveis de uma otimização multiobjetivo?

| | resposta, pelos números |
|---|---|
| A. impacto termodinâmico | **grande**: P_D1 redistribui o gás entre V-001 e V-002 (Δrel 106 % e 381 %); P_D2 muda o gás total à VRU (27 %) e o óleo recuperado (3 %) |
| B. impacto no dimensionamento | **pequeno**: diâmetros e governantes constantes; Leff de V-001/V-002 variam 2–3 % pelo líquido; o gás nunca governa (≤ 0,70 do líquido) |
| C. impacto em TVP | **grande e dominado por P_D2**: 45–148 kPa; atende nos 12 casos só com P_D2 ≈ 110–130 kPa |
| D. impacto nas bombas | sensível (22 %, 95 %, 8 %), em potências de centenas de kW, e **fora** dos objetivos atuais |
| E. volume total dos vasos | **INSENSÍVEL** (0,90 %) |
| F. caso/mecanismo governante | mecanismo constante; só o caso governante do V-001 alterna entre BOT 02 e BOT 03, empatados |

Objetivos atuais (`config/pfd/otimizacao.toml`): **volume dos vasos** — insensível (0,90 % nos
três vasos deste subproblema; TO-001/TO-002 não foram mapeados); **carga de aquecimento** e **área
de trocadores** — não mapeadas aqui (P-001 fora do subproblema); pelo diagnóstico do P-001 a
sensibilidade de Q_pre às pressões era ~0,2 % (nota 36), a ser reconferida com o trem.

**Conclusão: C — nenhuma delas produz efeito suficiente nos objetivos atuais.**

As pressões respondem fortemente em grandezas que **não são objetivo hoje**: a TVP (P_D2), a
partição e o total de gás à VRU (P_D1 e P_D2), as potências de bomba e o óleo recuperado. O efeito
físico existe; os objetivos atuais é que não o capturam. Capturá-lo exigiria, por exemplo, carga ou
potência de VRU (sem modelo e sem as pressões de estágio da VRU na fonte) ou recuperação de óleo
como objetivo — decisões que **não** foram tomadas nesta intervenção. A TVP ≤ 70 kPa segue como
critério físico do BOT, e o P_D2 que a satisfaz segue diagnóstico, não bound.
