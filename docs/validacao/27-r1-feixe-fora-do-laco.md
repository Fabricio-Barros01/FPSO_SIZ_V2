# R1 — o feixe sai do laço de ponto fixo

Intervenção restrita no P-003, autorizada depois da auditoria
(`26-auditoria-p003.md`). **Só R1.** R2, R3 e R4 não foram implementados.

Nenhuma equação, tolerância, critério de convergência, malha ou correlação foi alterada. O
resultado é **bit a bit idêntico** ao anterior.

## 1. O que mudou, conceitualmente

A auditoria mostrou que `bell_delaware` não depende do iterando do ponto fixo em L. A causa é
estrutural, e é ela que a refatoração segue — não um cache:

> Das cinco correções da Eq. 2-18, **só Js (Eq. 2-28) é função do número de chicanas n_b**.
> Jc, Jl, Jb, Jr, h_ideal, Re e A_s dependem apenas da geometria do casco e do escoamento do
> casco, que o laço não muda.

```
ANTES   para cada iteração do ponto fixo em L:
            bell_delaware(geo, …, n_b, l_bc, l_bc, k)
              └─ A_s, Re, j, h_ideal, Jc, Jl, Jb, Jr   (invariantes)  +  Js  (variante)

DEPOIS  feixe_ideal(geo, …, k)                    ← UMA vez, antes do laço
          └─ A_s, Re, j, h_ideal, Jc, Jl, Jb, Jr
        para cada iteração do ponto fixo em L:
            com_chicanas(feixe, n_b, l_bi, l_bo, l_bc, k)
              └─ Js  +  produto  +  h_o
```

`bell_delaware()` continua existindo com a mesma assinatura, definida agora como
`com_chicanas(feixe_ideal(...))`. Nenhum chamador externo nem o caso-ouro precisou mudar.

**Por que não é um cache.** Um cache guardaria um resultado por chave e dependeria de a chave
estar certa. Aqui não há chave: a conta invariante foi movida para fora do laço porque **as suas
entradas estão fora do laço**. Se amanhã Js passar a variar (vãos de ponta diferentes), o código
continua correto sem tocar em nada — `com_chicanas` recalcula Js a cada passagem, que é
exatamente o que a equação pede.

Arquivos: `src/fpso_siz/sizing/bell_delaware.py` (novo `FeixeIdeal`, `feixe_ideal`,
`com_chicanas`; `bell_delaware` reescrita como composição das duas) e
`src/fpso_siz/sizing/trocador.py` (`_tubo_bell_delaware` avalia o feixe antes do laço).

## 2. Paridade numérica

Instantâneo de **tudo** o que a planta produz — 11 TAGs, 5.391 linhas de varredura, com cada
float em hexadecimal (`float.hex`, sem perda): x, y, admissibilidade, governante, caso diretor,
teto, mecanismo, folgas, todos os derivados, os derivados de envelope e o `per_case`.

| | SHA-256 do instantâneo |
|---|---|
| antes | `409f180069ce809662d9020d9daa3cfed23cd96cbf53c001beafc5cd19f16414` |
| depois | `409f180069ce809662d9020d9daa3cfed23cd96cbf53c001beafc5cd19f16414` |

**Idêntico bit a bit. Nenhuma diferença, nem no último bit de mantissa.** Era o esperado: a
ordem das multiplicações foi preservada (`produto = jc·jl·jb·js·jr`, depois `h_ideal·produto`),
e os caminhos de falha devolvem os mesmos `Fatores` de antes.

## 3. Antes e depois

| grandeza | antes | depois | variação |
|---|---|---|---|
| `avaliar(dados, x)` | 21,713 s | **15,346 s** | **−29,3 % (1,41×)** |
| P-003, `dimensionar` | 20,570 s | **14,210 s** | **−30,9 % (1,45×)** |
| P-002, `dimensionar` | 0,908 s | 0,723 s | −20,4 % |
| planta completa | 21,768 s | 15,313 s | −29,7 % |
| chamadas de função por avaliação | 86.689.073 | **53.785.827** | −38,0 % |
| **avaliações completas do feixe** | **912.723** | **194.261** | **−78,7 % (4,70×)** |
| combinações com Js (`com_chicanas`) | 912.723 | 912.723 | inalterado |
| chamadas de `_tubo` | 194.261 | 194.261 | inalterado (é o R2) |
| `colburn_ideal` | 912.723 · 5,12 s | 194.261 · 1,24 s | −78,7 % |
| total sob `cProfile` | 48,196 s | 30,740 s | −36,2 % |

A previsão da auditoria — 4,70× nas avaliações completas de Bell-Delaware — **saiu exata**
(912.723 / 194.261 = 4,700). O ganho de ponta a ponta é 1,41×, e a diferença entre os dois
números é a resposta honesta: aquele termo era ~40 % do tempo, não o tempo todo.

`_tubo` não mudou de contagem, como esperado: R1 não mexe na repetição por par (caso, n).

## 4. O novo perfil

P-003 passa de **94,7 %** para **92,6 %** do tempo de `avaliar()`. Continua sendo o gargalo, mas
o que domina dentro dele **mudou de dono**:

| função | chamadas | tottime | cumtime |
|---|---|---|---|
| `trocador._tubo_bell_delaware` | 194.261 | 4,77 s | 35,10 s |
| **`pelicula.filme_tubo`** | **885.326** | **3,64 s** | **11,56 s** |
| `bell_delaware.com_chicanas` | 912.723 | 1,86 s | 6,64 s |
| `math.isfinite` | 18.946.999 | 1,78 s | 1,78 s |
| `bell_delaware.colburn_ideal` | 194.261 | 1,24 s | 1,57 s |
| `trocador._pelicula` | 885.326 | 1,22 s | 12,78 s |
| `bell_delaware.feixe_ideal` | 194.261 | 0,95 s | 6,13 s |

**O novo primeiro colocado é `filme_tubo`**, a película do lado tubo — e isso é informação
física, não só de desempenho: é ela, e não Bell-Delaware, que faz o ponto fixo iterar. No regime
laminar/de transição h_i depende de L pela correlação de Hausen (Gz = Re·Pr·d/L), então
recalculá-la a cada passagem é trabalho **necessário**, não redundância. As 885.326 chamadas de
`_pelicula` contra 194.261 de `_tubo` dizem que, em média, 4,6 passagens por chamada precisam
mesmo da película.

Qualquer otimização seguinte deve ser decidida sobre **este** perfil, não sobre o anterior.

## 5. Js: a premissa, registrada

**Conclusão da investigação: a igualdade é estrutural e deliberada no seu efeito, mas nunca
tinha sido escrita como premissa.** Não é default acidental nem reaproveitamento de variável.

O que se apurou:

- o modelo tem **um único** parâmetro de espaçamento, `espacamento_chicana` (Lbc/Ds, default
  0,40, faixa 0,20–1,00), cuja nota até aqui só falava da área de escoamento cruzado;
- **não existe entrada** para vão de entrada ou de saída — não há outro valor a passar;
- `_tubo_bell_delaware` passa `l_bc` explicitamente nas três posições
  (`com_chicanas(feixe, n_b, l_bc, l_bc, l_bc, kbd)`), desde o commit que criou o trocador
  (`2471739`, F7);
- com l_bi = l_bo = l_bc, a Eq. 2-28 dá
  `Js = (n_b − 1 + 1^(1−n) + 1^(1−n)) / (n_b − 1 + 1 + 1) = 1`, para qualquer n_b e qualquer
  expoente — e é o que se mede: **Js = 1,0 em 875.148 de 875.148 avaliações no P-003**, com
  **zero** ocorrências de espaçamento de ponta desigual.

A equação **não foi removida nem neutralizada**, e continua avaliada a cada passagem do laço. A
premissa foi registrada em três lugares: em comentário sobre o parâmetro `espacamento_chicana`,
num bloco próprio junto às constantes da Eq. 2-28 (`saari_lmtd.toml`) e na docstring de
`_tubo_bell_delaware`.

**Um detalhe que o oráculo pegou.** A primeira tentativa escreveu a premissa no campo `note` do
parâmetro — e `tests/sizing/test_paridade_julia.py` reprovou na hora: `note` é **dado**, e o
oráculo do Julia o confere campo a campo. A premissa foi para comentário, que fica igualmente no
modelo e não é dado. O oráculo fez exatamente o que existe para fazer, e a fixture não foi
tocada.

**O que fica em aberto, e é decisão de engenharia:** vão de ponta maior que o central é prática
corrente, por causa dos bocais. Representá-lo pede **uma entrada nova, com fonte** — e aí a
Eq. 2-28 passa a valer diferente de 1 sem que o algoritmo mude, porque `com_chicanas` já
recalcula Js a cada passagem. Nenhum valor foi introduzido aqui.

## 6. As duas grades

### O que é `n`

**Número de tubos por passe** do lado tubo. O total do feixe é `n_total = n × passes_tubo`. É o
eixo varrido (`sweep_axis`), e fixa a velocidade no tubo — `v = ṁ/(ρ·n·A_i)` —, que por sua vez
fixa o Reynolds, a película e, por ela, U e a área. É a mesma variável física nos dois ramos.

### De onde vem Δn = 5

Do parâmetro `n_step` (default 5,0), cuja nota diz: *"Número de tubos é inteiro; passo 5 mantém a
varredura legível sem perder resolução útil no diâmetro do feixe."*

**É granularidade numérica, não restrição física.** A restrição física é n inteiro, isto é,
passo 1. O passo 5 é escolha de apresentação, declarada como tal.

### Regra do primeiro ponto

`sweep_axis(p)` devolve `faixa_julia(p["n_min"], p["n_step"], p["n_max"])`, que gera
`n_min + i·Δn`. **A grade é ancorada exatamente no seu próprio `n_min`** — semântica do
`range(start, step, stop)` do Julia, preservada por paridade.

E `n_min`/`n_max` saem da banda de velocidade, por caso (`r_grade_velocidade`):

    n_min,i = max(1, ⌊ṁ_i/(ρ_i·v_max·A_i)⌋)        n_max,i = ⌈ṁ_i/(ρ_i·v_min·A_i)⌉

### Por que os offsets diferem

- **ramo por caso** (`size_single`): cada caso usa os **seus** `n_min,i`/`n_max,i`, logo âncora
  em `n_min,i`;
- **ramo conjunto** (`_size_envelope`): `envelope_params` toma `n_min = min_i(n_min,i)`,
  `n_max = max_i(n_max,i)`, `n_step = min_i(n_step,i)`, logo âncora no **menor** `n_min` de
  todos.

Como os `n_min,i` diferem entre casos e do mínimo global, cada grade cai numa classe de resto
diferente módulo 5. Medido: no P-003 só **11,6 %** dos pontos das varreduras por caso coincidem
com a grade conjunta (28,8 % no P-002).

### Isso pode mudar o projeto escolhido?

**Sim, mas pouco, e de forma quantificada.**

- **O ramo por caso não pode**: ele só produz o diagnóstico `per_case` ("este caso tem solução
  isolada?"). A escolha do projeto sai do ramo conjunto.
- **O ramo conjunto pode**, porque o ótimo é o primeiro ponto admissível: ele é o primeiro ponto
  da grade acima do limite inferior analítico da interseção (7.524,41 no P-003). Mudar a âncora
  desloca esse ponto em até Δn − 1 = **4 tubos por passe**.

Quanto isso vale, medido em pontos consecutivos da grade em torno do ótimo:

| n | admissível | área (m²) | L (m) |
|---|---|---|---|
| 7.521 | não | 1.473,1598 | 4,9093 |
| **7.526** | **sim (escolhido)** | **1.473,4355** | **4,9070** |
| 7.531 | sim | 1.473,7111 | 4,9046 |

**0,0187 % de área por passo da grade** — o deslocamento máximo de 4 tubos vale ~0,015 % na área
escolhida. Numericamente desprezível; mas é uma dependência real do resultado numa escolha de
granularidade, e por isso está escrita aqui.

**Nenhum caso pode ser perdido pelo passo 5.** A largura da banda admissível de um caso é
`n_max,i − n_min,i = n_min,i·(v_max/v_min − 1) = 2·n_min,i` com a banda 1–3 m/s, e o menor
`n_min` observado é 25 (P-002) — largura ≥ 50, dez vezes o passo.

### Proposta (não implementada)

Se `n` é a mesma variável física nos dois ramos — e é —, a discretização deveria ser **uma
política canônica única**, ancorada de forma independente do recorte (por exemplo em n = 1, ou
no limite analítico da banda), de modo que o mesmo n físico caia sempre no mesmo ponto. Isso
**mudaria números** (o ótimo pode andar até 4 tubos), então exige aprovação e uma nota em
`docs/validacao/`. Fica registrado, não feito.

## 7. Proposta arquitetural: separar busca de envelope

Registrada aqui como direção futura, **não implementada**.

A auditoria mostrou que o ótimo é o primeiro ponto admissível e que o limite inferior da
interseção o entrega quase diretamente. R3 e R4 não foram feitos porque `r.rows` — a varredura
inteira — não é subproduto descartável: alimenta o CSV (`output/dimensionamento.py`), o
relatório de terminal, a memória de cálculo (bordas da banda admissível, diagrama, tabela de
bloqueios, em `pfd/memorial.py`) e a métrica de violação da F15 (`pfd/otimizacao.py`).

A separação proposta:

| responsabilidade | o que faz | quando roda |
|---|---|---|
| **busca do projeto** | acha o ponto ótimo, podendo usar limites fechados e parar no primeiro admissível | toda avaliação, inclusive dentro do pymoo |
| **geração do envelope** | produz a varredura completa para diagnóstico, CSV, MC e diagramas | só quando alguém vai ler: `--mc`, CSV, relatório, modo interativo |

Hoje as duas são a mesma varredura, e por isso **a F15 paga a documentação 800 vezes por
rodada** para preservar artefatos que ninguém lê durante a otimização. Com a separação, R3 e R4
deixam de ter o custo que hoje os barra: a busca fica livre para ser fechada, e o envelope
continua íntegro onde é consumido.

A métrica de violação da F15 precisa de atenção própria nesse desenho: ela lê `min(row.x)` das
linhas, e teria de passar a ler um valor que a busca publique explicitamente.
