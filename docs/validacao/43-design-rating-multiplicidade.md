# 43 — DESIGN × RATING e multiplicidade: o P-001 conectado ao caminho produtivo

Decisão de arquitetura: [ADR 0005](../decisoes/0005-design-rating-multiplicidade.md).
Diagnóstico que motivou: [36 — P-001](36-p001-diagnostico.md), alternativa **A5** da árvore.
Data desta nota: 2026-10-02.

> **O que esta nota entrega, e que a versão anterior desta mesma nota não entregava:** a
> geometria escolhida do P-001, a comparação dos candidatos que a produziu, a integração com o
> P-002 e o P-003 e a tabela dos 16 casos do BOT. A versão de 2026-09-30 documentava apenas
> contratos e três casos ilustrativos, e o `SPRINTS.md` já marcava a etapa como entregue: era
> declaração sem entrega, e é isso que esta revisão corrige.

## 1. O que estava errado, em uma frase

O balanço preliminar escreve a carga do P-001 como **máxima recuperação** na aproximação da
P-32 — alvo TERMODINÂMICO, o mesmo que a Análise Pinch devolve. O envelope do motor exigia
que **uma mesma geometria realizasse esse alvo inteiro em todos os casos**. Isso é DESIGN
aplicado como off-design: num serviço com turndown de até ~24× em capacidade térmica, os casos
de baixa vazão caem no laminar, o U despenca para ~25 W/m²K e o envelope passa a pedir uma
área que o caso de projeto não precisa. O comprimento de tubo exigido chegava a 186 m contra o
limite de 6 m, e o alarme ficava aberto para sempre, porque **nenhuma correlação resolve um
problema que é de regra de dimensionamento**.

## 2. A regra nova

1. **DESIGN** no caso de **projeto** — o de maior vazão volumétrica no tubo, a mesma regra que
   a P-45 já usava para a banda de velocidade.
2. **RATING** nos demais: em cada caso, o calor trocado é a raiz de
   `Q = U·A·F(Q)·ΔT_lm(Q)` com a **área instalada**, limitada pelo alvo do Pinch e sem
   cruzamento de temperatura (`sizing/rating.py`).
3. A recuperação **não realizada** é declarada caso a caso e **cobrada das utilidades**: o
   aquecedor e o resfriador passam a ser dimensionados pelo envelope das cargas **residuais**
   (`pfd/integracao_termica.py`).
4. O **balanço preliminar não é reaberto** — e isso é *verificado*, não presumido (§6).

O alvo do Pinch continua sendo o limite: `Q_real ≤ Q_rec_max` em todo caso, e isso é testado
(`tests/sizing/test_design_rating.py`, `tests/pfd/test_integracao_termica.py`).

### 2.1 Ausência é estado, nunca zero

O rating devolve o seu estado, e os quatro são distintos:

| estado | significado |
|---|---|
| `limitado_pelo_alvo` | a área instalada transferiria MAIS; quem limita é a termodinâmica |
| `limitado_pela_area` | a raiz é interior; a diferença é recuperação não realizada |
| `sem_forca_motriz` | o lado quente não entra acima do frio; `Q = 0` é RESULTADO |
| `nao_avaliavel` | o `U·A` não pôde ser avaliado; `Q` é **NaN com motivo**, não zero |

O último era um defeito real da primeira implementação: `U·A` não finito virava transferência
nula, isto é, a afirmação "esta geometria não troca calor" sem que isso tivesse sido calculado.
Corrigido e coberto por teste.

### 2.2 O U não é o do ponto de projeto

O rating muda a temperatura de saída; a temperatura média muda `µ(T)` e `ρ(T)`; e com elas
mudam o Reynolds, a película e o U. `pfd/integracao_termica.py` **reavalia as propriedades na
temperatura média realizada e repete**, até a saída não mudar mais. O ponto fixo é em
temperatura de saída, com tolerância de 1e-4 K.

## 3. A geometria escolhida

<!--GEOMETRIA-->

## 4. Comparação dos candidatos

<!--CANDIDATOS-->

## 5. Os 16 casos do BOT

<!--CASOS-->

## 6. A integração não reabre o balanço — verificado

<!--INTEGRACAO-->

## 7. Perda de carga

<!--PERDA-->

## 8. O que NÃO está resolvido

<!--PENDENCIAS-->
