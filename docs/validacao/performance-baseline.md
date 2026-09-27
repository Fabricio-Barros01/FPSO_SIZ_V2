# Baseline de desempenho — onde o tempo está hoje

Gerado por `tools/benchmark.py`; os números brutos das três rodadas estão em
`performance-baseline.json`. **Nada foi otimizado nesta fase.** O objetivo é medir o estado
atual, já com as correções da Fase 1 aplicadas (commit `87e8c62`), para que qualquer otimização
posterior tenha um antes contra o qual se comparar.

Toda conclusão aqui vem de medição — `time.perf_counter`, `cProfile` e contagem de chamadas —,
nunca de hipótese sobre onde o custo "deve" estar. Onde a medida não foi possível, o relatório
diz que não foi.

## Máquina de referência

Esta máquina **não é premissa de nada**: ela é registrada para que os números sejam
interpretáveis, e nenhuma regra de produção pode depender dela.

| | |
|---|---|
| Plataforma | Linux 6.18.48, x86_64, glibc 2.42 |
| Python | 3.13.15 |
| CPUs lógicas | 12 |
| CPUs na afinidade do processo (`sched_getaffinity`) | 12 |
| Núcleos físicos (`/proc/cpuinfo`) | 6 |
| RAM total | 7,63 GiB |
| RAM disponível durante o benchmark | 2,4 – 3,0 GiB |
| Swap | 8,80 GiB |

O número que vale para dimensionar paralelismo é a **afinidade**, não `cpu_count()`: sob cpuset,
container ou `taskset` eles divergem, e só o primeiro diz o que o processo pode usar. Aqui os
dois coincidem, o que não autoriza confundi-los.

## 1. Onde está o tempo

Uma avaliação completa da F15 — `otimizacao.avaliar(dados, x)`, o que o pymoo chama uma vez por
indivíduo — custa **21,7 s**. A decomposição nas etapas que ela executa:

| Etapa de `avaliar()` | Tempo | Fração |
|---|---|---|
| decodificar o vetor + carregar propostas | 6,8 ms | 0,03 % |
| montar o contexto e **resolver o balanço** (16 casos) | 19,5 ms | 0,09 % |
| montar ajustes (divisão por trens) | 0,010 ms | ~0 % |
| **dimensionar a planta (11 TAGs)** | **21,62 s** | **99,88 %** |
| estados, violações e objetivos | 0,073 ms | ~0 % |
| soma das etapas | 21,65 s | |
| total medido de `avaliar()` | 21,71 s | overhead ≈ 60 ms |

O recorte `sg_001` dá o mesmo: 21,67 s, dos quais 21,54 s no dimensionamento.

**O balanço de massa e energia não é o problema.** `resolver_caso` custa 0,51 ms e
`resolver_todos` (16 casos) custa **19,5 ms** — 0,09 % da avaliação. Nenhuma otimização do
balanço muda o tempo da F15 de forma perceptível.

### Dentro do dimensionamento: um único TAG

| TAG | preparar | dimensionar | total | estado |
|---|---|---|---|---|
| **P-003** | 0,014 s | **20,570 s** | **20,584 s** | dimensionado |
| P-002 | 0,014 s | 0,908 s | 0,922 s | dimensionado |
| SG-001 | 0,573 s | 0,021 s | 0,594 s | dimensionado |
| V-001 | 0,074 s | 0,010 s | 0,084 s | dimensionado |
| V-002 | 0,063 s | 0,010 s | 0,073 s | dimensionado |
| B-001 | 0,011 s | 0,014 s | 0,025 s | dimensionado |
| B-002 / B-003 | 0,010 s | 0,010 s | 0,020 s | dimensionado |
| P-001 | 0,018 s | 0,001 s | 0,018 s | inviável |
| TO-001 / TO-002 | 0,009 s | 0,008 s | 0,017 s | dimensionado |
| **soma** | | | **22,37 s** | |

**O P-003 é 95 % de toda a avaliação.** P-002 é 4 %. Os outros nove TAGs juntos são 4 %. O
P-001, que é o TAG em alarme, custa 18 ms: ele é recusado cedo, antes de chegar ao laço caro.

### Dentro do P-003: a varredura do envelope

`cProfile` de uma avaliação (48,2 s sob o profiler, contra 21,7 s sem — sobrecarga ≈ 2,2×;
as **proporções** é que valem, não os tempos absolutos):

| Função | chamadas | tottime | cumtime |
|---|---|---|---|
| `sizing/bell_delaware.colburn_ideal` | 912.723 | 5,12 s | 6,52 s |
| `sizing/bell_delaware.bell_delaware` | 912.723 | 4,92 s | 29,85 s |
| `sizing/trocador._tubo_bell_delaware` | 194.261 | 4,84 s | 52,23 s |
| `sizing/pelicula.filme_tubo` | 885.326 | 3,72 s | 11,65 s |
| `math.isfinite` | 25.413.157 | 2,30 s | 2,30 s |
| `sizing/bell_delaware.leakage_areas` | 912.723 | 2,26 s | 3,84 s |

São 86,7 milhões de chamadas de função numa avaliação. O custo é **aritmética escalar em Python
puro**, executada cerca de 900 mil vezes pelo método de Bell-Delaware dentro da varredura de
`n_tubos` do trocador. Não há I/O, não há rede, não há biblioteca externa no caminho quente.

## 2. Quanto custa cada camada

### Inicialização, medida em processo novo (é o que cada worker paga ao nascer)

| Camada | Custo |
|---|---|
| `import fpso_siz` | 0,15 ms |
| `import fpso_siz.pfd.planta` | 55 ms |
| `import fpso_siz.pfd.otimizacao` | 56 ms |
| `import pymoo` (porta `_otim`) | 55 ms |
| `import thermo` + `chemicals` (porta `_chedl`) | 146 ms |
| ler os 62 TOML do pacote, a frio | 35 ms |
| ler os mesmos 62 TOML, já em `functools.cache` | 0,004 ms |

Inicialização **não é regime**: 0,3 s por processo contra 21,7 s por avaliação. Com o
`forkserver` e o lote de 12 avaliações da varredura, o custo de nascimento dos workers é
ruído — menos de 0,2 % do tempo de parede.

### Termodinâmica em uso hoje, em regime

| Chamada | 1.ª vez | regime (mín.) |
|---|---|---|
| `fluidos.agua` (IAPWS) | 0,105 ms | 0,043 ms |
| `fluidos.agua_saturada` (IAPWS) | 0,048 ms | 0,031 ms |
| `fluidos.salmoura_fracao` (Laliberté) | **134 ms** | 0,29 ms |

A primeira chamada da salmoura paga a montagem das tabelas do `thermo` (134 ms, 450× a de
regime): é custo de inicialização, não de regime. Numa avaliação inteira, **toda a camada
termodinâmica soma menos de 0,5 s** — 2 % do total. Não é o gargalo.

## 3. Como o throughput varia com workers

### Como a varredura foi feita, e um erro que ela quase produziu

A varredura roda um **lote fixo** de pontos do recorte `sg_001` para cada número de workers, de
modo que todo W faça exatamente o mesmo trabalho. O processo pai é aquecido antes, para não
creditar a `W = 1` o custo de importação.

Há uma armadilha nisso, e a primeira varredura caiu nela. Com `Pool.map`, o tempo de parede é o
do worker mais carregado: **ceil(lote ÷ W) × custo de um ponto**. Com um lote de 8 pontos, W = 6
e W = 7 dão makespan de 2 pontos e W = 8 dá 1 — e a medida "mostrou" que 8 workers rendem 23 %
mais que 6:

| workers | lote 8 | vazão | ceil(8 ÷ W) |
|---|---|---|---|
| 6 | 49,1 s | 0,1629/s | 2 |
| 7 | 50,4 s | 0,1588/s | 2 |
| 8 | 39,9 s | 0,2006/s | 1 |

Isso é **divisibilidade, não hardware**. A varredura boa usa um lote que todo W testado divide
por inteiro; é a tabela abaixo. A tabela acima fica registrada porque o engano é fácil de
cometer e o método de autotuning da Fase 10 precisa evitá-lo.

### Varredura principal — lote de 24 pontos, divisível por todo W testado

| workers | tempo | vazão (aval./s) | speedup | eficiência | pico de memória (PSS) |
|---|---|---|---|---|---|
| 1 | 526,9 s | 0,0456 | 1,00 | 1,00 | 0,24 GiB |
| 2 | 275,8 s | 0,0870 | 1,91 | 0,96 | 0,69 GiB |
| 3 | 191,0 s | 0,1256 | 2,76 | 0,92 | 0,88 GiB |
| 4 | 150,5 s | 0,1595 | 3,50 | 0,88 | 1,10 GiB |
| 6 | 108,9 s | **0,2203** | 4,84 | 0,81 | 1,51 GiB |
| 8 | — | **não medido** | | | projeção 1,83 GiB > orçamento 1,65 GiB |
| 12 | — | **não medido** | | | projeção 2,75 GiB > orçamento 1,65 GiB |

A curva é monotônica e a eficiência cai suavemente (1,00 → 0,96 → 0,92 → 0,88 → 0,81). Uma
varredura independente, com lote de 12, deu os mesmos valores: W = 1 a 0,0456 aval./s e W = 6 a
0,2213 — **reprodutibilidade dentro de 0,5 %**, o que dá confiança nos números.

A memória é medida por **PSS** (`/proc/pid/smaps_rollup`), não pela soma de `VmRSS`: os filhos do
`forkserver` compartilham páginas copy-on-write, e somar RSS contaria cada página compartilhada
uma vez por worker. Pela PSS, **cada worker acrescenta ≈ 0,23 GiB**.

### O que isto responde, e o que deixa em aberto

1. **Até 6 workers o paralelismo rende bem**, com eficiência ainda de 0,81 em 6 — número de
   núcleos físicos desta máquina.
2. **A memória vinculou antes das CPUs.** Havia 2,4 GiB livres e a varredura reserva 0,8 GiB de
   margem; a 0,23 GiB por worker, 8 workers projetam 1,83 GiB contra um orçamento de 1,65 GiB.
   Medi-los teria levado a máquina a swap, e o número mediria o swap, não o programa. **Isto é
   resultado**: o limite de workers tem de considerar CPU **e** RAM, e aqui a RAM chegou antes.
3. **Se o SMT rende acima dos 6 núcleos físicos, este benchmark NÃO respondeu.** Os pontos de 8 e
   12 não foram medidos por memória, e o único W = 8 obtido veio do lote de 8, contaminado pela
   divisibilidade. A pergunta fica aberta para a Fase 10, numa máquina com mais RAM livre ou com
   o consumo por worker reduzido.

**Nenhum destes números é regra.** Eles descrevem este laptop num dado momento — inclusive a
memória livre, que depende do que mais estava aberto. O que se extrai para a Fase 10 é o método
(medir; respeitar RAM; não confiar em `cpu_count`; lote divisível por W), não o valor 6.

## 4. Qual é o gargalo dominante

> **O envelope térmico do P-003 — 20,6 s dos 21,7 s de cada avaliação (95 %).** Dentro dele, o
> método de Bell-Delaware avaliado ~913 mil vezes em Python escalar durante a varredura de
> `n_tubos`.

Tudo o mais é ruído de medição perto disso: balanço 0,09 %, termodinâmica < 2 %, overhead da
otimização 0,0003 %, nascimento dos workers < 0,2 %.

Projeção da rodada F15 declarada no TOML (população 40, 20 gerações = 800 avaliações), com o
custo medido: **4 h 49 min sequencial**; a 0,2203 aval./s com 6 workers, **cerca de 1 h**. É
projeção, e está aqui como ordem de grandeza — a rodada de verdade é a Fase 13.

## 5. Candidatos a otimização (medidos, não implementados)

Em ordem de ganho medido. **Nenhum foi implementado nesta fase**; cada um é uma hipótese com
número atrás, a ser decidida e testada na fase própria.

### A. Dimensionar só os TAGs que o recorte usa — ganho medido: ~99 % no subproblema

Entre 4 indivíduos do recorte `sg_001`:

| TAG | tempo nas 4 avaliações | usado pelo recorte? |
|---|---|---|
| P-003 | **84,10 s** | **não** |
| P-002 | **3,73 s** | **não** |
| todos os outros nove | 0,36 s somados | sim (exceto P-001) |

O recorte `sg_001` não restringe nem pontua P-001, P-002 e P-003 — e mesmo assim
`planta.dimensionar` dimensiona os 11 TAGs. **99,6 % do tempo do subproblema é gasto em TAGs
cujo resultado o subproblema descarta.** Avaliar apenas os TAGs que entram nas restrições ou nos
objetivos declarados resolveria isso; o cuidado é que um TAG a menos não pode alterar o que os
outros veem (hoje não altera: cada envelope é independente).

### B. Separar `x_processo` de `x_equipamento` — ganho medido: ~99 % quando só a geometria muda

Quatro avaliações do problema completo variando **apenas** `passes_p002` (premissa e arranjo
fixos):

| TAG | chamadas do envelope | entradas distintas | repetidas | tempo |
|---|---|---|---|---|
| P-003 | 4 | **1** | **3** | 80,79 s |
| P-002 | 4 | 2 | 2 | 3,50 s |
| os outros nove | 4 cada | 1 cada | 3 cada | 0,31 s somados |

Mudar um parâmetro geométrico do P-002 **não muda nada** para os outros dez TAGs — e o P-003, que
custa 95 % do tempo, é recalculado três vezes com entrada bit a bit idêntica. É a evidência
direta que a Fase 8 pede: mudança exclusivamente geométrica não deveria recalcular processo nem
os TAGs que ela não toca.

### C. Memoizar `sizing/trocador._tubo(c, n)` — fator de recomputação medido: 2,03×

Numa avaliação, `_tubo` é chamada **194.261 vezes** cobrindo apenas **95.768 pares
(caso, n) distintos** — 52 objetos de caso distintos ao todo. O motor a chama por vários caminhos no mesmo ponto da varredura — `requirement`, `derived` e
`case_admissible` dentro do laço, e ainda `operacao_por_caso`, `bloqueios` e `parcelas_u` na
apresentação — e ela não é memoizada. **Cerca de metade das chamadas é repetição exata.** A
função responde por 20,9 s dos 21,8 s da avaliação instrumentada.

O teto aqui é ~2×, não mais: o ganho é o das chamadas repetidas, e um memo tem custo próprio
(chave, dicionário, memória por caso). Precisa de medição antes/depois, e de cuidado com a
identidade do objeto de caso como chave.

### D. Baratear o núcleo aritmético — sem número ainda

Os 86,7 milhões de chamadas por avaliação são aritmética escalar. As opções (vetorizar a
varredura, reduzir chamadas intermediárias, revisar o laço de ponto fixo do comprimento) são
mutuamente exclusivas com a invariante de rastreabilidade em graus diferentes e não foram
medidas. Fica registrado como direção, não como candidato quantificado.

### E. O que NÃO vale a pena

- **Cache termodinâmico entre indivíduos.** Existe repetição — `salmoura_laliberte` teve 452
  repetições em 768 chamadas numa mini-população — mas o total da camada é **0,26 s em 4
  avaliações** (0,3 %). Otimizar ali seria trabalho sem efeito.
- **Otimizar o balanço.** 19,5 ms por avaliação.
- **Reduzir o custo de inicialização dos workers.** 0,3 s por processo, amortizado em dezenas de
  avaliações.

## Observação à parte: o tempo da suíte

O fechamento da Fase 1 rodou `pytest -n 4 --dist loadscope --cov=fpso_siz` em **19 min 36 s**
(1.186 testes, cobertura 95,86 %). O `CLAUDE.md` registra 51 min 54 s para a mesma configuração.
A diferença não foi investigada aqui e não afeta as medidas acima, que são de processo isolado;
fica anotada para quem for revisar aquele número.

## Como reproduzir

```
uv run python tools/benchmark.py --etapas camadas,perfil,repeticoes,portag --dados a.json
uv run python tools/benchmark.py --etapas nucleo,workers --rotulo b_nucleo_workers --dados b.json
uv run python tools/benchmark.py --etapas geometria,workers --workers-lista 6,7,8 \
    --rotulo c_geometria_smt --dados c.json
uv run python tools/benchmark.py --etapas workers --pontos 24 --workers-lista 1,2,3,4,6,8,12 \
    --rotulo d_workers_lote24 --dados d.json
uv run python tools/benchmark.py --merge a.json b.json c.json d.json \
    --dados docs/validacao/performance-baseline.json
```

A ferramenta emite JSON; este `.md` é escrito a partir dele, porque ler os números é análise e
não formatação. A varredura de workers respeita um freio de memória (`MARGEM_RAM_GIB`): um W
cuja projeção de PSS não caiba no orçamento (memória disponível menos a margem) é registrado
como **não medido**, em vez de medir o swap.
