# 42 — Otimização das pressões de separação (P_D1 × P_D2)

**Subproblema de pressão e separação**, não otimização da planta inteira: as variáveis são só
P_D1 (V-001) e P_D2 (V-002), os vasos restringidos são só SG-001, V-001 e V-002, e P-001, P-002,
P-003, TO-001, TO-002 e as bombas ficam fora (P-001 segue inviável, `36-p001-diagnostico.md`, e não
bloqueia este recorte). Autorizado pelo usuário em 2026-09-29 ("fechamento do FPSO_SIZ_V2").

Gerado por `tools/otimizar.py --sub pressao --repetir --processos 4`. Tabelas completas:
[`otimizacao_pressao/otimizacao_pressao.md`](otimizacao_pressao/otimizacao_pressao.md); dados:
[`otimizacao_pressao/otimizacao_pressao.json`](otimizacao_pressao/otimizacao_pressao.json),
[`grade.csv`](otimizacao_pressao/grade.csv) (todos os pontos da grade) e
[`nsga2.csv`](otimizacao_pressao/nsga2.csv) (todas as avaliações do algoritmo).

## 1. Cadeia avaliada

```
x = (P_D1, P_D2)
  → premissas (destino = "premissa", config/pfd/otimizacao.toml)
  → Contexto(alteracoes) → resolver_todos        (o resolvedor produtivo; nenhum segundo)
  → recombinação da Nota 4 → trem SG-001 → V-001 → V-002 (flash em cascata, casos avaliáveis)
  → EstadoProcesso (correntes, gás por estágio, TVP do óleo tratado)
  → pfd/equipamento → SG-001, V-001, V-002       (o mesmo serviço e o mesmo motor do pfd)
  → objetivos e restrições (pfd/otimizacao.py: agregações do estado, nenhuma física)
  → NSGA-II (_otim.py, porta única do pymoo)
```

Cada indivíduo recalcula o trem inteiro. `pfd/otimizacao.py` e `_otim.py` não importam motor,
sizing nem termo (teste de arquitetura). A única grandeza nova no estado é a **TVP**
(`EstadoProcesso.tvp_kPa`): a mesma leitura de ponto de bolha que as notas 39 e 41 usavam
(`trem.tvp_kpa`, bisseção sobre o próprio flash), agora lida sob demanda pelo estado para que a
otimização a consuma sem fazer física — a proveniência a declara (`tvp_estocagem`, consumidor
`otimizacao`, só casos avaliáveis). O mapa da nota 41 reproduz as suas TVPs bit a bit por ela.

## 2. Objetivos — definição

Nenhum preço, custo ou peso. Ambos minimizados.

**(1) Recuperação de óleo estabilizado → `perda_oleo` = 1 − R**, com

    R = Σ_c ṁ_O(C-25, c) / Σ_c ṁ_O(C-01, c),   c nos 12 casos avaliáveis

- `O` é o teor de óleo de tanque de cada corrente (a parte que fica líquida no flash até a
  condição padrão), **conservado** pelo trem (nota 39): o que não chega a C-25 (óleo à estocagem)
  sai pelas outras saídas globais — como O nos vapores do SG-001 (C-04), V-001 (C-09) e V-002
  (C-17), e no óleo da água do FWKO (C-05, fixado pela premissa de teor de óleo na água, não
  pela pressão). O teste `test_objetivos_sao_as_grandezas_do_estado` fecha essa conta.
- **Por que em massa e agregada:** é adimensional; por caso, massa e volume padrão dão a mesma
  razão (mesma ρ_O do caso), então a escolha não é de unidade; a soma sobre os casos pondera cada
  caso pela sua vazão, e o denominador (a alimentação recombinada, C-01) não depende de P_D1 nem
  de P_D2 — o objetivo responde só ao que os estágios vaporizam. Minimizar 1 − R é o mesmo que
  maximizar R, com o valor na escala da perda (~2–4 %).
- Os 4 casos com gás de lift não entram (sem composição, O não é o do flash).

**(2) Carga de vapor da VRU → `carga_vru`** = máx_c [Q_G(V-001, c) + Q_G(V-002, c)] em Sm³/d, nos
16 casos — o envelope, como os vasos são dimensionados. É a vazão que o balanço já calcula; **não**
é potência de compressor (sem modelo de compressor). Nos pontos da frente o caso governante é
avaliável (BOT 03, §7): nenhum caso com gás de lift decide o objetivo ali.

As potências das bombas (B-001, B-002, B-003) são **métricas auxiliares** na ficha de cada ponto,
não objetivo.

## 3. Restrições

| restrição | natureza | forma | casos |
|---|---|---|---|
| TVP ≤ 70 kPa na estocagem (T_store = 40 °C) | **com fonte** (BOT §2.3.1.1, §2.7.1.10) | **contínua**: g = TVP_máx/70 − 1 (g < 0 é folga) | **só os 12 avaliáveis**; nos 4 com gás de lift (9, 11, 15, 16) a TVP **não é verificada** |
| P_D2 < P_D1 | **de processo** (topologia do BOT, Fig. 2.7.1.17; ΔP mínimo sem fonte) | g = 1 + (P_D2 − P_D1)/P_D1 se P_D2 ≥ P_D1; o ponto não é avaliado | — |
| SG-001, V-001 e V-002 viáveis | contrato de dimensionamento | a medida de violação da F15 (`_violacao`), pelo mesmo serviço | 16 |

A TVP é restrição, **não** bound fixo de P_D2. TVP sem solução (flash que não converge em algum
passo da bisseção, ou bolha fora de 1–5.000 kPa) deixa o ponto **não avaliável** — nunca viável
por omissão.

## 4. Domínio e limites

| limite | variável | natureza | valor | como entra |
|---|---|---|---|---|
| TVP ≤ 70 kPa | P_D2 (principalmente) | com fonte | 70 kPa | restrição contínua (§3) |
| sucção do compressor principal | P_D1 | com fonte (valor **estimado** pelo BOT, §2.7.3.9.20.1) | < 2.200 kPa(a) | fora do domínio: nunca ativo |
| P_D2 < P_D1 | ambas | de processo | ΔP > 0 | restrição entre variáveis (§3) |
| P_D2 que atende a TVP | P_D2 | diagnóstico (nota 41) | 120–130 kPa conforme P_D1 | **não** é bound: sai da restrição |
| piso de P_D2 (sucção da VRU) | P_D2 | sem fonte | — | não vira bound |
| **domínio de estudo** | P_D1 ∈ [200; 2.000], P_D2 ∈ [110; 250] kPa | **domínio de estudo declarado** (região da nota 41) | — | `min`/`max` das variáveis, `natureza_* = "dominio_estudo"` |

## 5. Validação antes do algoritmo — a grade-oráculo

A grade é avaliada **antes** do algoritmo, pelo mesmo avaliador: P_D1 de 200 a 2.000 kPa a cada
150 kPa (13 valores) × P_D2 de 110 a 250 kPa a cada 10 kPa (15 valores) = 195 pontos
(`grade_passo` do subproblema). Custo: 21 min em 4 processos.

- **32 viáveis, 163 inviáveis**: `tvp` barra 157 e `p_d2_menor_que_p_d1` barra 6 (P_D1 = 200 com
  P_D2 ≥ 200, não avaliados). Nenhum vaso fica inviável em ponto nenhum; nenhum ponto sem TVP.
- **Região viável**: P_D2 ≤ 120 kPa em todo P_D1, e P_D2 = 130 kPa só com P_D1 entre 350 e 1.100
  kPa (a TVP máxima a 130 kPa vai de 67,6 kPa em P_D1 = 500 a 72,8 kPa em 2.000).
- **Os dois objetivos NÃO conflitam no domínio.** Em toda linha de P_D2, a perda de óleo e a carga
  da VRU têm mínimo no mesmo P_D1 (500 kPa na grade) e crescem para os dois lados; e ambas caem com
  P_D2 (a 500 kPa: perda 2,50 → 2,32 → 2,16 % de 110 a 130 kPa; VRU 1,259 → 1,240 → 1,222
  MSm³/d). O que as limita é a TVP.
- **Frente da grade: um ponto só**, (P_D1; P_D2) = (500; 130) kPa — perda 2,158 %, carga da VRU
  1.221.881 Sm³/d, g_TVP = −0,034.
- **Resolução declarada** (lida da grade antes do algoritmo): a maior diferença de cada objetivo
  entre dois pontos viáveis vizinhos — ε(perda) = 0,713 p.p. e ε(VRU) = 61.949 Sm³/d. Abaixo
  disso a grade não distingue nada.

Critério de reprodução, declarado antes de rodar o NSGA-II (indicador ε aditivo, por objetivo):
(a) nenhum ponto da grade é melhor que um ponto da frente do NSGA-II por mais de ε em **todos** os
objetivos; (b) todo ponto da frente da grade é coberto por algum ponto do NSGA-II dentro de ε
(p_i ≤ g_i + ε_i). As duas listas vazias = a frente do NSGA-II reproduz a da grade na resolução
declarada (`pfd/otimizacao.resolucao` e `conferir_frente`).

## 6. NSGA-II e conferência contra a grade

NSGA-II (pymoo 0.6.2) com os parâmetros **já declarados** em `[algoritmo]` antes desta nota —
população 40, 20 gerações, semente 1 — sem ajuste: 800 avaliações, 800 pontos distintos, 85 min em
4 processos. **561 viáveis, 235 inviáveis, 4 não avaliáveis.**

Frente do NSGA-II — três pontos, todos **sobre a fronteira da TVP** (g_TVP entre −0,002 e
−0,0003):

| P_D1 (kPa) | P_D2 (kPa) | perda de óleo (%) | carga da VRU (Sm³/d) | g_TVP |
|---:|---:|---:|---:|---:|
| 510,5 | 133,7 | 2,1030 | 1.215.765 | −0,0020 |
| 537,6 | 133,9 | 2,1033 | 1.215.717 | −0,0003 |
| 538,2 | 133,9 | 2,1033 | 1.215.716 | −0,0003 |

A troca entre os três é de 0,0002 p.p. de perda contra 49 Sm³/d de VRU — quatro ordens de
grandeza abaixo da resolução da grade. **Na resolução declarada a frente é um ponto**: P_D1 ≈ 510–
540 kPa, P_D2 ≈ 134 kPa, com a TVP no limite. O algoritmo acha a fronteira que a grade só
enquadra (a grade salta de 130 para 140 kPa), por isso fica 0,055 p.p. e 6 mil Sm³/d abaixo do
ponto da grade.

**Conferência**: (a) 0 pontos da frente do NSGA-II superados pela grade; (b) 0 pontos da frente
da grade descobertos. **A frente do NSGA-II reproduz a da grade na resolução declarada.**

Os 4 pontos não avaliáveis são pontos em que o flash não convergiu num passo da bisseção da TVP
(§9). Três — (539,8; 127,8), (365,3; 132,6) e (508,5; 126,5) — seriam dominados pela frente mesmo
se viáveis; o quarto, (1.556,3; 185,3), não, mas fica no meio da região em que a grade dá TVP
acima do limite em todos os vizinhos (g_TVP = +0,45 a +0,55 em P_D1 = 1.550–1.700 e P_D2 =
180–190). Nenhum muda a frente.

**Por que a frente degenera.** No trem modelado, perda de óleo e gás à VRU medem a mesma coisa —
o que os estágios V-001 e V-002 vaporizam: mais vapor leva mais óleo de tanque junto. Por isso os
dois têm o mínimo no mesmo P_D1 intermediário (a pressão em que o conjunto V-001 + V-002 menos vaporiza)
e ambos querem P_D2 alto. O único freio é a TVP. Para comparação, o ponto das premissas atuais
(P-18 = 700, P-19 = 200 kPa) teria perda de 1,342 % e VRU de 1.126.280 Sm³/d, **mas** TVP de
110,8 kPa (g_TVP = +0,583): é inviável. **Atender a TVP custa 0,76 p.p. de recuperação e 89 mil
Sm³/d de gás à VRU** em relação a ele — esse é o efeito que o subproblema quantifica, e é
consequência da restrição, não de uma troca entre objetivos.

## 7. Pontos não dominados

Ficha de cada ponto da frente, reavaliada **fora** do otimizador pelo mesmo serviço
(`tools/otimizar.ficha`: Contexto → resolver_todos → TAGs). Máximos entre os 16 casos, com o caso
governante; TVP entre os 12 avaliáveis.

| grandeza | (510,5; 133,7) | (537,6; 133,9) | (538,2; 133,9) |
|---|---:|---:|---:|
| recuperação de óleo estabilizado R | 97,897 % | 97,897 % | 97,897 % |
| Q_G V-001 máx. (Sm³/d) | 975.490 | 957.455 | 957.086 |
| Q_G V-002 máx. (Sm³/d) | 240.274 | 258.262 | 258.630 |
| carga da VRU máx. (Sm³/d) / caso | 1.215.765 / BOT 03 | 1.215.717 / BOT 03 | 1.215.716 / BOT 03 |
| TVP máx. (kPa) / caso | 69,86 / BOT 14 | 69,98 / BOT 14 | 69,98 / BOT 14 |
| SG-001 vol. (m³) / d (mm) / governante / caso | 684,8 / 6.050 / líquido / BOT 12 | idem | idem |
| V-001 vol. (m³) / d (mm) / governante / caso | 283,9 / 4.700 / líquido / BOT 02 | 284,1 / 4.700 / líquido / BOT 02 | 284,1 / idem |
| V-002 vol. (m³) / d (mm) / governante / caso | 284,7 / 4.700 / líquido / BOT 02 | 284,8 / 4.700 / líquido / BOT 02 | 284,8 / idem |
| W B-001 / B-002 / B-003 (kW) — auxiliar | 310,1 / 144,3 / 43,6 | 310,1 / 142,4 / 43,7 | 310,1 / 142,4 / 43,7 |
| estado | viável | viável | viável |

Os três vasos são governados pelo líquido e não mudam de diâmetro na frente (como na nota 41: o
volume dos vasos é insensível às pressões). Os casos governantes são todos avaliáveis — nenhum dos
4 com gás de lift governa a VRU ou a TVP.

## 8. Critérios de aceitação

| critério | resultado | onde |
|---|---|---|
| um único resolvedor produtivo | ✔ `Contexto(alteracoes) → resolver_todos`; nenhum caminho paralelo | `pfd/otimizacao.avaliar` |
| trem recalculado por indivíduo | ✔ cada avaliação reconstrói o balanço com as premissas do vetor | idem |
| objetivos respondem às variáveis | ✔ perda 0,93–3,95 % e VRU 1,075–1,374 MSm³/d nos pontos avaliados (viáveis ou não) | `grade.csv`, `nsga2.csv` |
| TVP como restrição explícita e contínua | ✔ g = TVP_máx/70 − 1, só nos 12 avaliáveis; os 4 com lift declarados não verificados | §3; `test_restricao_de_tvp_e_continua_e_so_dos_avaliaveis` |
| mesmo motor para os vasos | ✔ `pfd/equipamento` (o serviço do `pfd`); estados iguais aos da planta | `test_objetivos_sao_as_grandezas_do_estado` |
| frente da grade calculada | ✔ 195 pontos, frente exata (1 ponto) | §5 |
| NSGA-II comparado com a grade | ✔ 0 superados, 0 descobertos na resolução declarada | §6 |
| mesma semente → mesma frente | ✔ rodada repetida: mesma sequência de 800 pontos e mesma frente; teste com avaliador sintético | `--repetir`; `test_mesma_semente_mesma_frente_no_subproblema` |
| cada ponto reproduzível fora do otimizador | ✔ reavaliação por `ot.avaliar`: objetivos, restrições e estados idênticos bit a bit | §7 |
| nenhuma física em `_otim.py`/`pfd/otimizacao.py` | ✔ sem motor, sizing nem termo (teste de arquitetura); TVP lida do estado | `test_a_otimizacao_passa_pelo_servico` |
| suíte completa | ✔ **1321 passed** (`-n 4 --dist loadscope`, com cobertura, 8 min 43 s) | — |
| cobertura ≥ 90 % | ✔ **95,93 %** (`pfd/otimizacao.py` 93 %, `_otim.py` 92 %, `balanco/estado.py` 100 %) | — |
| gate | ✔ `tools/auditar_saida_pfd.py` sai 0, e a saída é **idêntica** à do `main` (`d9c565d`) exceto hash do commit e caminho | — |
| nenhum instantâneo atualizado | ✔ instantâneo da planta, `regressao_eficiencia.json` e fixtures do Julia intactos | — |
| subproblema, não planta inteira | ✔ declarado no TOML, no relatório gerado e aqui | — |

## 9. Correção feita durante a rodada (sem mudar número ativo)

A primeira rodada caiu: num ponto do NSGA-II, o solver do ChEDL levantou `OscillationError`
(fluids.numerics) num passo da bisseção da TVP. Essa exceção não descende de `ArithmeticError`
nem de `ValueError`, e escapava do contrato do `flash_tp` ("não convergir é `ok = False`, nunca
exceção"). Duas correções, com teste:

1. `termo/backend.flash_pseudo` traduz as exceções de não convergência do solver para
   `ArithmeticError` — o serviço devolve estado com `ok = False`;
2. `termo/servico.pressao_bolha` devolve NaN se o flash não convergir em **qualquer** pressão
   da busca. Antes, um passo sem equilíbrio contava como "não ferve" e deslocaria a TVP para baixo
   em silêncio — o que, com a TVP virando restrição, poderia aprovar um ponto por omissão.

Nenhum resultado ativo mudou: nenhuma avaliação anterior passava por esses caminhos (a TVP máxima
e mínima da nota 41 em (700; 200) e (2.000; 110) conferem bit a bit; instantâneo, regressão e gate
na §8).

## 10. O que esta nota não é, e o que fica congelado

- Não é otimização da planta: trocadores, tratadores e bombas não são restringidos; P-001 segue
  inviável e **não** foi tratado (placas, rating, cascos, P-32, topologia ficam fora).
- Os 4 casos com gás de lift não têm TVP nem recuperação verificadas (composição do gás de lift
  ausente na fonte).
- Limitações herdadas, congeladas como trabalho futuro: h/Cp dos pseudo-componentes, Péneloux e ρ
  líquida pela EOS, k líquido, μ do gás com pseudo-componentes, R3/R4 do P-003, o leitor de
  ajustes da F10b, a discretização das grades do trocador; a decisão da viscosidade (nota 40) está
  fechada.
- O domínio é de estudo; o piso de P_D2 continua sem fonte, e o resultado não o substitui.
