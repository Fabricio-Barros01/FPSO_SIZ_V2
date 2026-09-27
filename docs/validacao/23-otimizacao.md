# F15 — otimização multiobjetivo do módulo (estudo)

Gerado por `tools/otimizar.py`; a frente sai do NSGA-II/III pela porta única `fpso_siz/_otim.py`, e cada avaliação é o mesmo serviço por TAG do `pfd` — a otimização não fala com o motor.

## Aviso de pré-condição

O documento `docs/decisoes/0003-otimizacao-pymoo.md` exige **nenhum alarme aberto** antes da primeira rodada. Os alarmes do P-001, P-002 e P-003 **continuam abertos** (`docs/validacao/14-alarmes.md`): falta a correlação laminar/de transição do lado tubo, cuja fonte já existe no acervo mas ainda não tem exemplo numérico para o caso-ouro (`docs/validacao/20-correlacao-tubo-laminar.md`). O usuário autorizou a implementação da F15 mesmo assim, em 2026-09-26; **toda rodada aqui é estudo, e nenhum ponto da frente é recomendação de projeto.**

## Rodada 1 — problema completo (diagnóstico)

Todas as variáveis, os três objetivos e os onze TAGs. Esta rodada existe para MOSTRAR o efeito dos alarmes abertos, não para recomendar projeto.

### O que a rodada pôde mexer

| Variável | Tipo | Limites | Origem dos limites |
|---|---|---|---|
| η_padrão do SG-001 (P-43) (`eta_F`) | real | 0,800 – 0,900 | faixa de 80–90 % declarada pelo usuário para a P-43 (F10w); não há valor suposto |
| número de trens do SG-001 (`trens_sg`) | inteiro | 1,000 – 3,000 | divisão da vazão por um número inteiro de vasos iguais (mesma variante dos alarmes, trens_2/trens_3); arranjo, não valor suposto |
| passes no tubo do P-002 (`passes_p002`) | inteiro | 1,000 – 2,000 | faixa do descritor passes_tubo (Saari: 1 contracorrente §4.2.1; 2 no arranjo 1-2, Fig. 4.3) |
| passes no tubo do P-003 (`passes_p003`) | inteiro | 1,000 – 2,000 | faixa do descritor passes_tubo (Saari) |

| Objetivo | Unidade | Como é somado | Fonte |
|---|---|---|---|
| volume total dos vasos (`volume_vasos`) | m³ | soma de `volume` em SG-001, V-001, V-002, TO-001, TO-002 | proxy de peso e área de convés (0003); o volume é o derivado que os métodos de vaso já emitem |
| carga de aquecimento (`carga_aquecimento`) | kW | Q_H + Q_D (maximo_entre_casos) | utilidade de aquecimento do módulo (BOT 3.4): P-002 (Q_H) e DWH-001 (Q_D); o dimensionamento da utilidade responde ao caso de maior carga |
| área total de troca (`area_trocadores`) | m² | soma de `area_total` em P-001, P-002, P-003 | área de troca é o proxy de custo dos trocadores (0003); com cascos divididos vale a área total (derivados_v2) |

Recorte: **completo**. TAGs restringidos: SG-001, V-001, V-002, TO-001, TO-002, P-001, P-002, P-003, B-001, B-002, B-003.

Algoritmo **NSGA-II** (pymoo 0.6.2), população 24, 8 gerações, semente 1, 192 avaliações.

### O ponto do projeto atual

| Variáveis | Objetivos | Violações | Estado |
|---|---|---|---|
| eta_F = 0,8500 · trens_sg = 1 · passes_p002 = 2 · passes_p003 = 1 | volume_vasos = 2.327,8 · carga_aquecimento = 9.769,7 · area_trocadores = — | P-001 1,000, P-002 0,091, P-003 1,000 | inviável |

Critério de validação 1 do 0003: o avaliador reproduz o ponto do projeto atual — os estados por TAG são os mesmos que o `fpso-siz pfd` publica hoje.

### Frente de Pareto

Nenhum indivíduo viável: com os alarmes dos trocadores abertos, todo ponto do espaço de decisão tem pelo menos um TAG inviável, e a frente é vazia. **Isto é o resultado da rodada**, e é exatamente a razão da pré-condição do 0003 — otimizar sobre um modelo que ainda dá "nenhum equipamento atende" seria otimizar um erro.

A rodada continua útil como diagnóstico: a coluna de violações mostra qual TAG barra cada ponto e quanto falta, e a violação do P-002 cai com os passes no tubo.

## Rodada 2 — subproblema do SG-001 (validação)

O recorte do critério de validação 2 do 0003: pequeno o bastante para a frente ser conferida contra uma varredura exaustiva da mesma grade.

### O que a rodada pôde mexer

| Variável | Tipo | Limites | Origem dos limites |
|---|---|---|---|
| η_padrão do SG-001 (P-43) (`eta_F`) | real | 0,800 – 0,900 | faixa de 80–90 % declarada pelo usuário para a P-43 (F10w); não há valor suposto |
| número de trens do SG-001 (`trens_sg`) | inteiro | 1,000 – 3,000 | divisão da vazão por um número inteiro de vasos iguais (mesma variante dos alarmes, trens_2/trens_3); arranjo, não valor suposto |

| Objetivo | Unidade | Como é somado | Fonte |
|---|---|---|---|
| volume total dos vasos (`volume_vasos`) | m³ | soma de `volume` em SG-001, V-001, V-002, TO-001, TO-002 | proxy de peso e área de convés (0003); o volume é o derivado que os métodos de vaso já emitem |
| carga de aquecimento (`carga_aquecimento`) | kW | Q_H + Q_D (maximo_entre_casos) | utilidade de aquecimento do módulo (BOT 3.4): P-002 (Q_H) e DWH-001 (Q_D); o dimensionamento da utilidade responde ao caso de maior carga |

Recorte: **sg_001**. TAGs restringidos: SG-001, V-001, V-002, TO-001, TO-002, B-001, B-002, B-003.

Algoritmo **NSGA-II** (pymoo 0.6.2), população 24, 8 gerações, semente 1, 192 avaliações.

### O ponto do projeto atual

| Variáveis | Objetivos | Violações | Estado |
|---|---|---|---|
| eta_F = 0,8500 · trens_sg = 1 | volume_vasos = 2.327,8 · carga_aquecimento = 9.769,7 | — | viável |

Critério de validação 1 do 0003: o avaliador reproduz o ponto do projeto atual — os estados por TAG são os mesmos que o `fpso-siz pfd` publica hoje.

### Frente de Pareto

| Variáveis | Objetivos | Violações | Estado |
|---|---|---|---|
| eta_F = 0,8992 · trens_sg = 3 | volume_vasos = 1.857,8 · carga_aquecimento = 9.345,8 | — | viável |

A frente tem **um ponto só**, e isso é resultado, não falha da rodada: neste recorte os dois objetivos melhoram na mesma direção (mais trens reduzem o volume por vaso, e η maior reduz a carga de aquecimento), então não há troca a mostrar — o conjunto de Pareto degenera num ponto.

### Conferência contra varredura exaustiva (critério 2 do 0003)

Grade declarada em `config/pfd/otimizacao.toml`: 18 pontos; 15 viáveis, 1 não dominados.

| Variáveis | Objetivos | Violações | Estado |
|---|---|---|---|
| eta_F = 0,8800 · trens_sg = 3 | volume_vasos = 1.862,9 · carga_aquecimento = 9.506,6 | — | viável |

Nenhum ponto da varredura domina um ponto da frente do algoritmo.

#### Fronteira de viabilidade encontrada na grade

3 dos 18 pontos da grade são **inviáveis**, e quem os barra é: B-002. Isto é resultado da rodada: a otimização encontrou uma fronteira de viabilidade DENTRO de uma faixa que a fonte declara admissível, e ela é pendência de decisão do usuário, não algo que a otimização possa resolver escolhendo um valor.

| Variáveis | Objetivos | Violações | Estado |
|---|---|---|---|
| eta_F = 0,9000 · trens_sg = 1 | volume_vasos = 2.294,2 · carga_aquecimento = 9.339,1 | B-002 0,583 | inviável |
| eta_F = 0,9000 · trens_sg = 2 | volume_vasos = 1.966,8 · carga_aquecimento = 9.339,1 | B-002 0,583 | inviável |
| eta_F = 0,9000 · trens_sg = 3 | volume_vasos = 1.857,6 · carga_aquecimento = 9.339,1 | B-002 0,583 | inviável |

## Arquivos

- `23-otimizacao-frente.json`: por rodada, a frente, o ponto do projeto e os metadados (algoritmo, versão do pymoo, semente).
- `23-otimizacao-frente-completo.csv`: as 192 avaliações da rodada `completo`, uma por linha, para reproduzir qualquer ponto com `fpso-siz pfd --ajustes`.
- `23-otimizacao-frente-sg_001.csv`: as 210 avaliações da rodada `sg_001`, uma por linha, para reproduzir qualquer ponto com `fpso-siz pfd --ajustes`.

