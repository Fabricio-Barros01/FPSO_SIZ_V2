# 33 — Pendência de discretização: a grade do caso e a grade do envelope

**Estado: aberta.** Pendência **própria**, de política de discretização. **Não é parte da R1
nem da R2** — as duas estão encerradas, foram intervenções de desempenho e não mudaram número
nenhum. Esta aqui muda número se for resolvida, e por isso é uma decisão de projeto do
usuário, registrada à parte. As medições que a descrevem foram feitas durante a auditoria do
P-003 (`26-auditoria-p003.md`) e detalhadas em `27-r1-feixe-fora-do-laco.md` §6; este documento
é o registro da pendência em si.

## O fato

`n` (número de tubos por passe) é a mesma variável física nos dois ramos do motor, e cada ramo
a discretiza com uma âncora diferente:

| ramo | grade | âncora |
|---|---|---|
| por caso (`size_single`, diagnóstico `per_case`) | `n_min,i : n_step : n_max,i` | o `n_min` **daquele** caso |
| conjunto (`_size_envelope`, o que dimensiona) | `min_i n_min,i : min_i n_step : max_i n_max,i` | o **menor** `n_min` de todos |

`n_min,i = max(1, ⌊ṁ_i/(ρ_i·v_max·A_i)⌋)` depende do caso, então cada grade cai numa classe de
resto diferente módulo `n_step`. Medido: só **11,6 %** dos pontos das varreduras por caso do
P-003 coincidem com a grade conjunta (**28,8 %** no P-002).

`n_step = 5` é granularidade declarada de apresentação, não restrição física — a restrição
física é `n` inteiro, isto é, passo 1.

## O que isso custa hoje

- **No resultado:** o ótimo do ramo conjunto é o primeiro ponto admissível da grade acima do
  limite analítico da interseção. Mudar a âncora o desloca em até `n_step − 1` = 4 tubos por
  passe, o que vale **0,0187 % de área por passo** (P-003: 1.473,4355 m² em n = 7.526 contra
  1.473,7111 m² em n = 7.531). Desprezível em engenharia, mas é dependência real do resultado
  numa escolha de granularidade.
- **Nenhum caso se perde pelo passo 5:** a largura da banda admissível de um caso é
  `2·n_min,i` com a banda de 1–3 m/s, e o menor `n_min` observado é 25 — largura ≥ 50, dez
  vezes o passo.
- **Na apresentação: já não custa nada.** Era o que fazia o MC do P-002 e do P-003 imprimir
  travessão no critério governante por caso; corrigido em `32-auditoria-de-saida.md`, lendo o
  critério de `governing_of`, que não depende de grade. O gate de sanidade cobre a regressão.

## Proposta, não implementada

Uma **política canônica única** de discretização de `n`, ancorada de forma independente do
recorte (em `n = 1`, ou no limite analítico da banda), para que o mesmo `n` físico caia sempre
no mesmo ponto nos dois ramos.

**Muda números** (o ótimo pode andar até 4 tubos por passe), então exige aprovação explícita do
usuário, tabela dos 16 casos antes/depois e revisão do oráculo ou da regressão, na regra do
projeto. Fica registrada, não feita.
