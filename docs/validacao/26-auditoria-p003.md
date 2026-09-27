# Auditoria algorítmica do P-003 — as 913 mil avaliações de Bell-Delaware, explicadas

A baseline (`performance-baseline.md`) mostrou que o P-003 é 95 % do tempo de `avaliar()`. Este
documento responde à pergunta seguinte, que é outra: **esse custo é necessário?**

Gerado por `tools/auditar_p003.py`; números brutos em `26-auditoria-p003.json`. **Nada foi
alterado**: nenhuma equação, correlação, critério de projeto ou estratégia de otimização. A
ferramenta só instrumenta e conta.

**Resposta curta: não.** A árvore fecha exatamente com o número medido, e mostra que a parte
fisicamente necessária é ~0,03 % das chamadas. O resto se divide entre busca que continua depois
de a resposta já estar determinada e recomputação bit a bit idêntica.

## 1. A árvore, e o fechamento com o número medido

Uma avaliação da F15 dimensiona a planta inteira. Só dois TAGs chamam Bell-Delaware:

| TAG | chamadas de `_tubo` | chamadas de `bell_delaware` | iterações médias do ponto fixo |
|---|---|---|---|
| P-003 | 180.883 | 875.148 | 4,838 |
| P-002 | 13.378 | 37.575 | 2,809 |
| P-001 | 0 | 0 | — (recusado antes, no fator F do arranjo 1-2) |
| **total** | **194.261** | **912.723** | |

O perfil da baseline mediu **194.261** chamadas de `_tubo` e **912.723** de `bell_delaware`.
**A árvore abaixo reproduz os dois números exatamente**, sem resto.

### P-003

Não há produto cartesiano de configuração no caminho normal: `passes_tubo = 1`,
`cascos_serie = 1`, `cascos_paralelo = 1` são valores fixos (o `passes` só vira variável na F15,
que refaz o envelope inteiro; os cascos, só na ferramenta de reotimização F10x.7).

```
dimensionar P-003  =  1 × size_envelope,  16 casos ativos
│
├─ RAMO A — per_case: 16 varreduras de CASO ISOLADO (motor.size_single)
│    cada caso varre a SUA grade; Σ = 17.523 pontos
│    × 3 chamadas de _tubo por ponto (requirement, derived, case_admissible)
│    = 52.569 chamadas                                                    29,1 %
│
└─ RAMO B — envelope conjunto: 1 varredura
     grade = UNIÃO das bandas de velocidade dos 16 casos:
     n ∈ [36 ; 22.571], passo 5  →  4.508 pontos
     │
     ├─ 1.498 pontos ANTES do 1.º admissível  (16 requirement + 1 derived
     │    + 3.502 case_admissible no total)            =  28.968          16,0 %
     ├─ 1 ponto ESCOLHIDO, n = 7.526  (16 + 1 + 16)    =      33           0,02 %
     ├─ 3.009 pontos DEPOIS do escolhido               =  99.297          54,9 %
     └─ operacao_por_caso, no ponto final              =      16           0,01 %
                                                        = 128.314         70,9 %
TOTAL _tubo = 52.569 + 128.314 = 180.883
   × 4,838 iterações do ponto fixo em L
= 875.148 chamadas de bell_delaware
```

### P-002 (mesma estrutura, escala menor)

```
16 → 10 casos ativos; grade conjunta n ∈ [25 ; 2.159], passo 5 → 427 pontos
├─ RAMO A: Σ 1.847 pontos × 3                          =  5.541          41,4 %
└─ RAMO B: 316 antes → 3.726 · escolhido (n=1.605) → 21
           110 depois → 4.080 · operacao_por_caso → 10 =  7.837          58,6 %
TOTAL _tubo = 13.378  ×  2,809  =  37.575 bell_delaware
```

### De onde vem o RAMO A

`motor._size_envelope` faz duas coisas por caso: monta a restrição para a varredura conjunta
(linha 124) **e** chama `m.size_equipment(...)` (linha 130), que entra em `motor._size_single` e
**varre a grade inteira outra vez, para aquele caso sozinho**. É o `per_case` do resultado — o
diagnóstico "este caso tem solução isolada?", que o relatório, a memória de cálculo e a métrica
de violação da F15 consomem. É produto real, não trabalho morto; mas custa 29 % das chamadas.

Consequência medida: `sizing_constraints` é chamada **32 vezes** para 16 casos, e os dois ramos
trabalham sobre **objetos de restrição diferentes**, então nada é compartilhado entre eles.

## 2. As sete verificações pedidas

### 2.1 Loops aninhados ou produtos cartesianos grandes demais

Não há aninhamento de configuração. O tamanho vem de **um** eixo: `n_tubos`, com 4.508 pontos.
A grade é grande porque `n_min`/`n_max` saem da banda de velocidade **caso a caso**
(`r_grade_velocidade`: n = ṁ/(ρ·v·A_i)) e `envelope_params` toma `min(n_min)` e `max(n_max)` —
isto é, **a UNIÃO das bandas**. Mas um feixe viável tem de atender a todos os casos ao mesmo
tempo: o que importa é a **INTERSEÇÃO**.

### 2.2 e 2.7 Candidatos equivalentes, e limites físicos antes da enumeração

A interseção é **fechada**, não precisa de busca: v = ṁ/(ρ·n·A_i) dá, por caso,
n ∈ [ṁ/(ρ·v_max·A_i) ; ṁ/(ρ·v_min·A_i)].

| | P-003 | P-002 |
|---|---|---|
| grade enumerada | 4.508 pontos | 427 |
| interseção fechada das bandas de velocidade | n ∈ [7.524,4 ; 22.573,2] | [719,6 ; 2.158,9] |
| pontos da grade dentro dela | 3.010 | 288 |
| teto geométrico fechado (d_casco_max, d_feixe ∝ √n) | n ≤ 22.036,5 | n ≤ 19.084,1 |
| pontos que sobrevivem aos dois limites | **2.903** | **288** |

O primeiro ponto admissível do P-003 é **n = 7.526** — o primeiro múltiplo da grade acima de
7.524,4, o limite analítico. **A busca redescobre por enumeração um número que uma divisão dá.**

### 2.3 Recomputação de invariantes dentro dos loops

Dentro de `_tubo_bell_delaware`, o ponto fixo itera em L. `bell_delaware` só enxerga L através
de `n_b` (número de chicanas), e `n_b` só entra em **Js** (Eq. 2-28). Como
`_tubo_bell_delaware` chama sempre `bell_delaware(..., n_b, l_bc, l_bc, kbd)` — espaçamento de
ponta **igual** ao central —, a Eq. 2-28 vira

    Js = (n_b − 1 + 1^(1−n) + 1^(1−n)) / (n_b − 1 + 1 + 1) = (n_b + 1)/(n_b + 1) = 1

para qualquer n_b. **Logo a saída inteira de `bell_delaware` não depende do iterando.**

Isto não ficou na álgebra. A ferramenta comparou, chamada a chamada, as saídas sucessivas:

| | P-003 | P-002 |
|---|---|---|
| chamadas de `_tubo` com mais de uma `bell_delaware` | 180.883 | 13.378 |
| dessas, com **todas** as saídas bit a bit idênticas | **180.883** | **13.378** |
| com alguma saída diferente | **0** | **0** |
| `Js` exatamente igual a 1,0 | 875.148 de 875.148 | 37.575 de 37.575 |
| chamadas redundantes (todas menos a primeira) | **694.265 (79,3 %)** | **24.197 (64,4 %)** |

O laço itera de verdade — mas por causa de **h_i**, que no regime laminar/transição depende de L
pela correlação de Hausen e é calculado em `_pelicula`, **fora** de `bell_delaware`. As 718.462
chamadas extras de Bell-Delaware por avaliação não mudam um bit de nada.

Há ainda re-leitura de tabelas constantes: `layout_pitches` é chamada **1.106.984** vezes por
avaliação e reconstrói `[int(x) for x in k["layouts"]]` em cada uma; `colburn_ideal` (912.723
chamadas) reconstrói duas listas e faz varredura linear de faixas; `baffle_clearance` (194.261)
reconstrói mais duas. São listas derivadas do TOML, fixas durante toda a execução.

### 2.4 Chamadas repetidas com exatamente as mesmas entradas

`_tubo(c, n)` não é memoizada, e o motor a chama por vários caminhos no mesmo ponto:

| TAG | chamadas | pares (caso, n) distintos | fator |
|---|---|---|---|
| P-003 | 180.883 | 89.651 | **2,018×** |
| P-002 | 13.378 | 6.117 | **2,187×** |

No RAMO B, `requirement` calcula `_tubo(c,n)["l"]`, `case_admissible` recalcula o mesmo
`_tubo(c,n)` para ler `v`/`ok`/`nu_valido`, e `derived` o recalcula uma terceira vez para o caso
argmax. Mesmo objeto, mesmo n, três construções.

### 2.5 Rejeições que poderiam ocorrer antes da chamada de Bell-Delaware

`case_admissible` reprova por velocidade — e **v é fechada**: `v = ṁ/(ρ·n·A_i)`, calculada nas
três primeiras linhas de `_tubo`, antes de qualquer geometria de casco. Hoje uma reprovação por
velocidade paga o ponto fixo de Bell-Delaware inteiro.

| critério que reprovou o ponto (P-003) | pontos |
|---|---|
| velocidade fora da banda | 1.178 |
| correlação do tubo (Prandtl fora da faixa declarada) | 320 |
| nenhum (ponto admissível) | 3.010 |

O curto-circuito do `all()` do motor já poupa 20.466 de 72.128 chamadas possíveis de
`case_admissible` — a otimização barata já está lá. O que falta é não chamar Bell-Delaware para
descobrir uma velocidade.

### 2.6 Loops que continuam depois de a resposta já estar determinada

O achado mais caro. O objetivo é a área, `area = UA_exigido/U`; com n crescendo, a velocidade cai,
U cai e a área cresce. Medido sobre as linhas do resultado:

| | P-003 | P-002 |
|---|---|---|
| objetivo monótono crescente em n nos admissíveis | **sim** | **sim** |
| pontos admissíveis | 2.903 | 111 |
| índice do ponto escolhido entre eles | **0** | **0** |
| pontos avaliados **depois** do escolhido | **3.009** | 110 |

**A resposta é sempre o primeiro ponto admissível**, e a varredura continua por mais 3.009
pontos (67 % da grade) para reconfirmá-la.

### 2.8 Envelope refeito quando só mudam variáveis alheias ao P-003

Já medido na Fase 2 e repetido aqui por completude: variando **apenas** `passes_p002`, o P-003 é
redimensionado 4 vezes com **1 entrada distinta** — 3 recomputações idênticas, 80,8 s de 88 s.

## 3. Classificação do custo

Percentuais sobre as 194.261 chamadas de `_tubo` por avaliação, exceto onde indicado.

### Necessário pela física / espaço de projeto — **0,03 %**

As 54 chamadas dos pontos escolhidos (33 no P-003, 21 no P-002). Se o diagnóstico "cada caso tem
solução isolada?" continuar sendo produto desejado, o RAMO A acrescenta o seu mínimo — mas ele
próprio só precisa do primeiro admissível de cada caso, não da grade inteira.

### Estruturalmente ineficiente, numericamente correto — **~70 %**

| item | chamadas de `_tubo` | % |
|---|---|---|
| busca continua depois do ótimo (objetivo monótono) | 103.377 | 53,2 % |
| busca começa muito antes da interseção fechada das bandas | 32.694 | 16,8 % |
| RAMO A varre a grade inteira por caso, com grades desalinhadas da conjunta (só 11,6 % dos pontos coincidem no P-003; 28,8 % no P-002) | (dentro dos 58.110 do ramo A) | — |

### Recomputação redundante

| item | quantidade | % |
|---|---|---|
| `bell_delaware` bit a bit idêntica dentro do ponto fixo | **718.462 de 912.723** | **78,7 %** das chamadas de BD |
| `_tubo` repetida para o mesmo (caso, n) | 98.493 de 194.261 | 50,7 % |
| tabelas constantes reconstruídas (`layout_pitches`, `colburn_ideal`, `baffle_clearance`) | ~2,2 M reconstruções de lista | — |
| envelope inteiro refeito quando só mudam variáveis alheias | 3 de 4 avaliações | 75 % |

### Possível erro lógico — **nenhum que altere número**

Dois pontos para **decisão do usuário**, não correções:

1. **`Js` é sempre exatamente 1** (875.148 de 875.148 chamadas no P-003). A Eq. 2-28 existe
   justamente para o caso em que os vãos de ponta são maiores que o central — arranjo comum, por
   causa dos bocais. O código passa `l_bi = l_bo = l_bc` sempre, então a correção nunca é
   exercitada. Ou a geometria de espaçamento igual é a intenção declarada, e então Js é código
   morto a documentar; ou os vãos de ponta deveriam ser maiores, e aí falta uma entrada. **É
   pergunta de física, e não a respondo aqui.**
2. **As grades do RAMO A e do RAMO B estão desalinhadas.** Cada caso começa no seu próprio
   `n_min`, com passo 5; a conjunta começa no menor de todos. No P-003 só 11,6 % dos pontos
   coincidem — o mesmo n físico é discretizado em posições diferentes conforme o ramo.

## 4. Chamadas elimináveis e speedup teórico (nenhum implementado)

Sobre as 912.723 chamadas de `bell_delaware`, que é o termo dominante.

| # | mudança | elimina | fator teórico | muda algum número? |
|---|---|---|---|---|
| R1 | não repetir `bell_delaware` dentro do ponto fixo (a saída é idêntica, provado acima) | 718.462 BD (78,7 %) | **4,70×** | **não** — bit a bit idêntica |
| R2 | memoizar `_tubo` por (caso, n) | 98.493 `_tubo` (50,7 %) | **2,03×** | não |
| R3 | parar no primeiro admissível (objetivo monótono) | 103.377 `_tubo` (53,2 %) | **2,14×** | **sim**: encurta a tabela de varredura |
| R4 | entrar pela interseção fechada das bandas de velocidade | 32.694 `_tubo` (16,8 %) | 1,20× | **sim**: idem |
| R5 | testar velocidade (fechada) antes de Bell-Delaware | subconjunto de R3/R4 | — | não |

**R1 é o único que não pode mudar resultado nenhum** — é remover chamadas cujas saídas foram
medidas como idênticas — e sozinho vale 4,7× no termo dominante. É o candidato óbvio para
primeiro.

Compondo R1+R2 (os dois seguros): 912.723 → ~95.800 avaliações completas, **≈ 9,5×**. Com R3 e
R4, o RAMO B cai para dezenas de pontos e o limite superior passa de 15×. **São limites
superiores sobre o termo dominante**, não promessas de tempo de parede: o memo tem custo
próprio, as iterações baratas não são de graça, e o resto do programa continua ali. Medir
antes/depois é obrigatório.

### O que R3 e R4 custam

`r.rows` não é só diagnóstico: alimenta o CSV (`output/dimensionamento.py`), o relatório de
terminal, a memória de cálculo (bordas da banda admissível, diagrama, tabela de bloqueios —
`pfd/memorial.py`) e a métrica de violação da F15 (`pfd/otimizacao.py`, que lê `min(row.x)`).
Encurtar a varredura **muda o que esses artefatos mostram**. Não é otimização invisível: é
decisão sobre o que a memória de cálculo apresenta, e por isso fica para o usuário.

## 5. Critério de aceite

> Não considerar o gargalo normal até que as ~913 mil avaliações sejam explicadas
> quantitativamente a partir do algoritmo.

Explicadas: 875.148 (P-003) + 37.575 (P-002) = **912.723**, e 180.883 + 13.378 = **194.261**
chamadas de `_tubo` — os dois números do perfil, sem resto, a partir da árvore da seção 1.
**O gargalo não é normal:** 0,03 % do custo é a física do ponto escolhido; 78,7 % das avaliações
de Bell-Delaware são bit a bit idênticas à primeira da sua própria chamada.

## Como reproduzir

```
uv run python tools/auditar_p003.py --dados docs/validacao/26-auditoria-p003.json
```
