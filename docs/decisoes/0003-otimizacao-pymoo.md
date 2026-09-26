# 0003 — Otimização multiobjetivo do módulo com `pymoo` (planejamento, F15)

Estado: **proposta de planejamento**; nada implementado, nenhuma dependência instalada. A
implementação é outra fase, com aprovação própria.

## Pré-condição: nenhum alarme aberto

Otimizar sobre um modelo que ainda dá "nenhum equipamento atende" é otimizar um erro. Pela
diretriz do usuário (a unidade do BOT é um projeto básico real), os alarmes de
`docs/validacao/14-alarmes.md` (SG-001, trocadores com óleo laminar no tubo, bombas com
faixa de vazão entre casos) precisam ser resolvidos — premissa corrigida com fonte, ou modelo
estendido — antes da primeira rodada. A otimização não pode "resolver" um alarme escolhendo
uma premissa sem fonte.

## Variáveis de decisão (só com limite de origem declarada)

| Variável | Onde entra | Limites | Origem dos limites |
|---|---|---|---|
| η_padrão do SG-001 (P-43) | balanço | 0,80–0,90 | faixa declarada pelo usuário (F10w) |
| nº de trens do SG-001 | TAG (vazão ÷ N) | inteiro 1–3 | escolha de arranjo; sem valor suposto |
| tempo de retenção do óleo no SG-001 | método | 7,5–10 min (×2–4 com emulsão) | S&A Tab. 4.1 e nota |
| esbeltez-alvo dos vasos | método | dentro da banda de cada método | S&A §3.8.5 / §4.9 |
| passes no tubo dos trocadores | método | 1–2 | descritor `passes_tubo` (Saari) |
| DN das linhas de bomba | método | série comercial do TOML | Moran (2016) Fig. 3 |
| T de tratamento | balanço | ≥ F-05 (BOT 2.7.1.4) e ≤ 99 °C (BOT 2.7.1.10) | BOT |

Valores propostos (`status = "proposto"`) não viram variável de decisão sem confirmação.

## Objetivos

1. Volume total dos vasos (SG-001, V-001/002, TO-001/002), m³ — proxy de peso e área de convés.
2. Carga de aquecimento Q_H = P-002 + DWH-001, kW (utilidade de aquecimento, BOT 3.4).
3. Área total de troca dos trocadores, m².

Potência das bombas e carga de resfriamento entram como restrição ou como 4º objetivo; com mais
de três objetivos troca-se o algoritmo (abaixo).

## Restrições

- As do contrato de dimensionamento, como estado: cada TAG viável (`feasible = True`); um
  envelope inviável vira violação g > 0 (proporcional à distância ao admissível, por exemplo
  x_min_banda − teto no SG-001), nunca exceção.
- Balanço convergido; BSW e temperaturas nas especificações do BOT (F-06, F-07, F-08, F-09).
- Nenhum alarme novo: a solução não pode ter TAG inviável.

## Algoritmo

- **NSGA-II** (`pymoo.algorithms.moo.nsga2`) para 2–3 objetivos, com variáveis mistas
  (inteiras: trens, passes, DN; contínuas: η, retenção, T). Justificativa: frente de Pareto sem
  pesos arbitrários, tratamento nativo de restrições por violação, e avaliação cara (cada
  indivíduo roda o balanço e 11 envelopes) compatível com populações de 40–100.
- **NSGA-III** se entrarem 4 ou mais objetivos (direções de referência de Das–Dennis).
- Semente fixa e registro de versão, para reprodutibilidade.

## Arquitetura

- Porta única `fpso_siz/_otim.py` (como `_num.py` e `pfd/_chedl.py`): só ela importa `pymoo`,
  com teste de arquitetura; o núcleo expõe um avaliador puro
  `avaliar(dados, premissas, ajustes) → (objetivos, restrições, estados)` que chama o serviço
  por TAG — a otimização não fala com o motor diretamente.
- A saída é uma frente de Pareto em JSON/CSV e um relatório em `docs/validacao/`; cada ponto da
  frente pode ser reproduzido pelos comandos existentes (`pfd --ajustes`), com MC.

## Critério de validação

1. O ponto do projeto atual (se viável depois dos alarmes) é reproduzido exatamente pelo
   avaliador.
2. Num subproblema pequeno (ex.: η × nº de trens do SG-001), a frente do NSGA-II coincide com a
   de uma varredura exaustiva da mesma grade.
3. Mesma semente → mesma frente (bytes do JSON).
4. Cobertura ≥ 90 % no núcleo; nenhuma mudança no balanço padrão nem na paridade.

## Dependência

`pymoo` (Apache-2.0) só depois de aprovada; versão fixada no `uv.lock`.
