# R2 — o feixe é calculado uma vez por estado

Segunda intervenção restrita no P-003, autorizada depois do R1
(`27-r1-feixe-fora-do-laco.md`). **Só R2.** R3 e R4 continuam não implementados, Δn = 5 não foi
tocado, as grades não foram alinhadas, e não há cache entre avaliações da F15.

Nenhuma equação, malha, ordem de pontos, `rows`, critério de admissibilidade, governante,
métrica de violação ou artefato de relatório mudou. O resultado é **bit a bit idêntico**.

## 1. De onde vinham as chamadas repetidas

Medido instrumentando o caminho real e registrando, para cada estado (objeto de restrição, n),
qual fase o calculou primeiro e quais o recalcularam:

| origem da repetição | P-003 | P-002 |
|---|---|---|
| `requirement` → `case_admissible` | 69.185 | 4.977 |
| `requirement` → `derived` | 22.031 | 2.274 |
| `requirement` → `operacao_por_caso` | 16 | 10 |
| **total de repetições** | **91.232** | **7.261** |

**Toda repetição tem `requirement` como primeira ocorrência, e nenhuma fase repete dentro de si
mesma.** O motor pergunta o mesmo ponto três vezes por três motivos diferentes: `requirement`
quer o comprimento exigido, `derived` quer os derivados, `case_admissible` quer a velocidade e a
validade da correlação. São três perguntas sobre **o mesmo feixe**.

E as repetições são **locais**: distância, em chamadas de `_tubo`, entre a primeira e a repetição:

| distância ≤ | 1 | 2 | 4 | 8 | 17 | ∞ |
|---|---|---|---|---|---|---|
| repetições acumuladas (P-003) | 17.523 | 35.046 | 35.046 | 35.046 | **91.216** | 91.232 |

17 é exatamente `nº de casos + 1`. As 16 restantes são o `operacao_por_caso` do ponto escolhido,
no fim da varredura. Nada exige guardar a malha inteira — **basta o último estado**.

## 2. De que o feixe realmente depende

A pergunta que autoriza reaproveitar: duas chamadas ditas iguais têm mesmo **todas** as entradas
iguais? O levantamento foi feito campo a campo, e dividiu-se em três:

**(a) entradas que o feixe lê e que mudam o resultado** — nº de passes; diâmetros interno e
externo; passo, área de tubo e área de célula; arranjo do feixe (layout); espaçamento e corte de
chicana, pares de vedação, folga de furo, faixas divisoras; UA exigido, condutividade de parede,
fatores de incrustação dos dois lados, condutividade e Prandtl do tubo; vazão, cp, viscosidade e
condutividade do casco; vazão, densidade e viscosidade do tubo.

**(b) entradas que só agem em outra configuração** — `h_casco` vale apenas com Bell-Delaware
desligado (com ele, h_o vem do método); `razao_visc` e `baixo_re` valem apenas no regime de
baixo Reynolds, com a película estendida.

**(c) campos da restrição que o feixe NÃO lê** — `n_serie` e `n_paralelo`. Eles agem **antes**,
em `sizing_constraints`, dividindo as vazões por casco; o que chega ao feixe já é a vazão de um
casco.

As três categorias estão fixadas por teste (`tests/sizing/test_reaproveitamento_feixe.py`),
inclusive a (c) como **não**-dependência: se um dia esses campos passarem a ser lidos no feixe, é
esse teste que avisa. Nada mais entra: fora de `c` e de `n`, o cálculo só lê as constantes do
método, que não mudam durante a execução.

## 3. A forma da correção

Não é cache global, persistente nem compartilhado entre indivíduos. **A memória vive no objeto
de restrição**, que o motor cria por caso dentro de uma execução de dimensionamento e descarta
ao terminá-la:

```python
@dataclass(frozen=True)
class ExchangerConstraints:
    ...
    _ultimo_feixe: dict = field(default_factory=dict, compare=False, repr=False, init=False)
```

Três decisões, e o porquê de cada uma:

- **a chave é a identidade do objeto, não uma tupla de campos.** Duas restrições diferentes —
  outro caso, outros passes, outra geometria, outro arranjo de cascos — são objetos diferentes,
  com memórias diferentes. Não há chave que alguém precise manter correta e que possa ficar
  incompleta quando a F15 ganhar uma variável nova. **É a propriedade que faz esta correção
  sobreviver à Fase 8.**
- **guarda um estado só, o último `n`.** É o que a locality da seção 1 pede. Guardar a malha
  inteira custaria ~110 MB por dimensionamento (72 mil estados × ~1,5 kB) e não acertaria uma
  chamada a mais.
- **`init=False`.** Sem isso `dataclasses.replace()` copiaria a **referência** da memória para a
  restrição nova, e um estado calculado com um número de passes poderia ser devolvido para
  outro. Foi um defeito real da primeira versão, pego pelo teste que varia um campo por vez.

`_tubo` devolve uma **cópia** do dicionário. Antes do R2 cada chamada devolvia um dicionário
novo, e manter esse contrato custa ~1 µs contra os ~78 µs do cálculo — barato demais para abrir
mão da garantia de que ninguém escreve no resultado de outro.

## 4. Paridade

O mesmo teste forte do R1: 11 TAGs, 5.391 linhas de varredura, cada float em hexadecimal —
resultado principal, `ok`, governante, caso diretor, teto, mecanismo, folgas, derivados,
derivados de envelope e `per_case`.

| | SHA-256 |
|---|---|
| antes do R1 | `409f180069ce809662d9020d9daa3cfed23cd96cbf53c001beafc5cd19f16414` |
| depois do R2 | `409f180069ce809662d9020d9daa3cfed23cd96cbf53c001beafc5cd19f16414` |

**Idêntico bit a bit** — e note que a comparação é contra o estado **anterior ao R1**: as duas
intervenções juntas não moveram um bit.

## 5. Antes e depois

| grandeza | baseline | depois do R1 | **depois do R2** | R2 | acumulado |
|---|---|---|---|---|---|
| `avaliar(dados, x)` | 21,713 s | 15,346 s | **8,924 s** | −41,9 % | **2,43×** |
| P-003 `dimensionar` | 20,570 s | 14,210 s | **7,950 s** | −44,1 % | **2,59×** |
| P-002 `dimensionar` | 0,908 s | 0,723 s | **0,390 s** | −46,0 % | 2,33× |
| planta completa | 21,768 s | 15,313 s | **8,858 s** | −42,2 % | 2,46× |
| chamadas de função | 86,7 M | 53,8 M | **29,1 M** | −45,9 % | 2,98× |
| **avaliações do feixe** (`feixe_ideal`) | 912.723 | 194.261 | **95.794** | −50,7 % | **9,53×** |
| `com_chicanas` | 912.723 | 912.723 | **471.493** | −48,3 % | 1,94× |
| `filme_tubo` | 885.326 | 885.326 | **464.529** | −47,5 % | 1,91× |
| `_tubo` (chamadas) | 194.261 | 194.261 | 194.261 | inalterado | — |
| total sob `cProfile` | 48,196 s | 30,740 s | **16,779 s** | −45,4 % | 2,87× |

**`_tubo` continua sendo chamada 194.261 vezes — e deve continuar.** R2 não removeu chamadas:
removeu **recomputações**. Das 194.261 chamadas, 98.467 são servidas pela memória e 95.794
calculam. O número que importa é esse último, e ele bate com os 95.768 estados distintos
medidos na auditoria, mais 26 — exatamente os `operacao_por_caso` do fim da varredura, que caem
fora da janela do último estado, como a seção 1 previa.

**A previsão da auditoria para R1+R2 era ~9,5× nas avaliações completas de Bell-Delaware. O
medido é 9,53×.**

## 6. O novo perfil

| função | chamadas | tottime | cumtime |
|---|---|---|---|
| `trocador._tubo_bell_delaware` | 95.794 | 2,42 s | 18,18 s |
| **`pelicula.filme_tubo`** | **464.529** | **1,93 s** | **6,14 s** |
| `bell_delaware.com_chicanas` | 471.493 | 0,96 s | 3,46 s |
| `math.isfinite` | 9.809.932 | 0,94 s | 0,94 s |
| `trocador._pelicula` | 464.529 | 0,64 s | 6,79 s |
| `bell_delaware.colburn_ideal` | 95.794 | 0,62 s | 0,78 s |
| `pelicula.nusselt_hausen` | 413.150 | 0,49 s | 0,69 s |
| `bell_delaware.feixe_ideal` | 95.794 | 0,47 s | 3,08 s |

A película do lado tubo continua sendo o maior item isolado depois do laço que a chama, e o
perfil ficou **plano**: nenhum item passa de 15 % do total. As 464.529 chamadas de `filme_tubo`
para 95.794 feixes dizem que o ponto fixo ainda faz ~4,85 passagens por estado — e essas
passagens são **necessárias**, porque no regime laminar/de transição h_i depende de L (Hausen,
Gz = Re·Pr·d/L).

P-003 é agora **89,1 %** de `avaliar()` (era 94,7 % no baseline, 92,6 % depois do R1).

Qualquer decisão seguinte deve ser tomada sobre **este** perfil.

## 6b. Suíte

**1.234 aprovados, cobertura 95,93 %.** São os 1.199 do R1 mais 35 testes novos, que prendem o
risco desta intervenção: reaproveitar através de estados diferentes.

A suíte inteira caiu de **14:19 para 8:25** — o dimensionamento do P-003 aparece em dezenas de
testes, e o ganho se propaga.

## 7. Conclusão da auditoria sobre as grades (registro, sem mudança)

Registrado como pedido, e **nada foi alterado**:

- **`n` é o número de tubos por passe**, a mesma variável física nos dois ramos;
- **fisicamente `n` é inteiro** — a granularidade que a física impõe é 1;
- **Δn = 5 é granularidade numérica, não restrição física.** A nota do parâmetro `n_step` diz
  isso com todas as letras: "passo 5 mantém a varredura legível";
- **cada grade está ancorada no seu próprio `n_min`** (`faixa_julia` gera `n_min + i·Δn`); o
  ramo conjunto usa `min_i(n_min,i)` e o ramo por caso usa o `n_min,i` daquele caso;
- **o desalinhamento explica a baixa coincidência** entre os ramos: 11,6 % dos pontos no P-003,
  28,8 % no P-002;
- **`per_case` não altera o projeto escolhido** — ele produz só o diagnóstico "este caso tem
  solução isolada?"; a escolha sai do envelope conjunto;
- **no envelope conjunto a discretização pode deslocar a solução em até quatro tubos** em
  relação à malha inteira, o que vale ~0,015 % de área (0,0187 % por passo da grade, medido em
  n = 7.521 / 7.526 / 7.531).

Uma política canônica única de discretização continua **proposta, não feita**: mudaria números,
e exige aprovação e nota própria.
