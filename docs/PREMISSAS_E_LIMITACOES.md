# Premissas e limitações do FPSO_SIZ_V2

Documento de referência do TCC. Diz o que o software assume, o que ele não sabe e o que ele não
pretende representar. Baseline: `b638c19` (congelado para a release). Detalhes em
`docs/validacao/` (notas citadas entre parênteses).

## 1. Escopo do software

- Balanço de massa e energia do **módulo de separação de óleo** de um FPSO: separador de água
  livre (SG-001), dois desgaseificadores (V-001, V-002), dois tratadores eletrostáticos (TO-001,
  TO-002), três trocadores (P-001, P-002, P-003) e três bombas (B-001, B-002, B-003).
- Dimensionamento **preliminar** desses 11 equipamentos por envelope sobre os 16 casos de projeto,
  com métodos da literatura (Stewart & Arnold, Arnold, Saari + Bell-Delaware, Moran).
- Termodinâmica do trem SG-001 → V-001 → V-002 por flash Peng-Robinson com pseudo-componentes, nos
  casos em que a composição é conhecida.
- Um **subproblema de otimização** das pressões dos desgaseificadores (nota 42).
- Saídas rastreáveis: memória de cálculo (LaTeX), JSON e CSV do mesmo rastro, e um gate de
  sanidade.

## 2. Dados de entrada

| dado | origem |
|---|---|
| 16 casos (vazões, T, modo de operação, gás de lift e transferido) | BOT I-ET-3010.2K-1200-941-P4X-001 rev. C, Tab. 2.2.2.3 |
| 7 composições por tipo de fluido, propriedades de C20+ | BOT Tab. 2.2.2.4 |
| API e viscosidade de óleo morto dos poços | BOT Tab. 2.2.1.2 |
| especificações (BSW, salinidade, TVP, T de estocagem e de tratamento) | BOT §2.3.1.1, §2.7.1 |
| **arquivo auditado** | `tests/fixtures/python_ref/design_cases_bot.json` (sha256 `ca3dfe559b32…`, 16 casos) |

## 3. Premissas principais

| premissa | valor | natureza |
|---|---|---|
| P do FWKO (F-02) | 2.500 kPa(a) | BOT |
| **P-18** P do V-001/TO-001 | **700 kPa** | **cenário-base (premissa inicial)** |
| **P-19** P do V-002/TO-002 | **200 kPa** | **cenário-base (premissa inicial) — NÃO CONFORME à TVP** (§11) |
| T de tratamento / de estocagem | 90 °C / 40 °C | BOT |
| referência da recombinação da Nota 4 | FWKO: 2.500 kPa(a), T do caso | premissa de modelagem sustentada pelo BOT, não prescrita (nota 38) |
| casos avaliáveis termodinamicamente | os 12 sem gás de lift | regra declarada (`trem.toml`) |

A tabela completa (55 linhas F-xx/P-xx, com justificativa e classe) está no memorial do balanço
(`output/latex/balanco/premissas_memorial.toml`); os valores, em `config/premissas.toml`.

### Cenário-base × subproblema otimizado

| | P_D1 | P_D2 | onde é usado | TVP nos 12 casos avaliáveis |
|---|---|---|---|---|
| **CENÁRIO-BASE** | 700 kPa | 200 kPa | todos os resultados produtivos (balanço, 11 TAGs, memoriais, gate) | **93,1–110,8 kPa — NÃO CONFORME** ao limite de 70 kPa |
| **SUBPROBLEMA OTIMIZADO** | ≈ 510–540 kPa | ≈ 134 kPa | só a nota 42 | ≤ 70 kPa (no limite) |

O resultado otimizado é **resultado do subproblema de otimização de pressões dentro do domínio de
estudo**. Não é pressão definitiva de projeto, nem premissa final da planta, nem condição
validada industrialmente: o piso de P_D2 não tem fonte, a TVP só foi avaliada nos 12 casos sem
lift e o subproblema não representa a planta inteira. A planta **não** foi redimensionada com ele.

## 4. Premissas do autor

Valores escolhidos pelo autor, identificados como premissa (não são dado de fonte):

- ΔT de aproximação do pré-aquecedor P-32 = 10 K — decide a inviabilidade do P-001 (nota 36);
- η padrão de remoção de água livre do FWKO P-43 = 0,85;
- cp constante por componente (óleo 2,0; água produzida 3,35; diluição 4,18 kJ/kg·K; P-10 a P-12);
- ΔP de trocador e de resfriador (P-17), descarga das bombas (P-20, P-21), rendimento das bombas
  (P-22), temperaturas da água de diluição (P-31);
- tempos de retenção recomendados (Stewart & Arnold, com o valor adotado dentro da faixa da fonte);
- premissas de projeto dos trocadores P-44/P-44b/P-45/P-46 (decisões do usuário registradas).

## 5. Valores propostos

**43 entradas de TAG não têm fonte técnica** — nem no acervo, nem no BOT, nem em norma citável.
Receberam um **valor proposto pelo autor** (`config/pfd/pendencias_propostas.toml`, status
`proposto`) para que o fluxo rode, com a justificativa física de cada um:

- bombas: desnível, nível de sucção, comprimentos e Σk das linhas, NPSHr e margem;
- trocadores: condutividades (óleo, parede), incrustações, temperaturas das utilidades;
- tratadores: diâmetro de gota pós-coalescência (1.000 µm).

Eles aparecem como **proposta** em todas as saídas e **nunca** como valor validado. Sem elas
(`--sem-propostas`) os TAGs correspondentes ficam "aguardando entrada".

**Filosofia de fontes do software:**

- dado ou correlação com fonte → fonte registrada ao lado do valor;
- premissa do autor → identificada como premissa;
- proposta sem fonte → identificada como proposta, nunca apresentada como validada;
- lacuna não preenchida → permanece lacuna (o TAG fica "aguardando entrada").

## 6. Limitações termodinâmicas

- **Sem entalpia nem cp dos pseudo-componentes** (sem Cp de gás ideal com fonte): o balanço de
  energia usa cp constante por componente e não tem calor latente (nota 30).
- **ρ da fase líquida pela PR não validada** (sem translação de volume/Péneloux; razão 0,541):
  a ρ do óleo vem da API na condição padrão, sem correção de T nem de Bo.
- **μ do gás** pelo corte leve N2–nC4, não pela composição de equilíbrio y (sem método de
  transporte validado para pseudo-componentes).
- **k da fase líquida de hidrocarboneto** não validada (proposta de 0,13 W/m·K nos trocadores).
- **μ do óleo vivo** por Beggs & Robinson com o Rs do trem: a correlação não tem variável de
  composição do gás, e a aplicabilidade a gás rico em CO2 não é demonstrada pela fonte (nota 40).
- A composição do caso é validada **por consistência com o BOT** (reproduz Q_G e Q_O a
  ≤ 1,2·10⁻⁹), **sem PVT medido**.

## 7. Limitações de equipamentos

- **P-001 inviável**: resultado legítimo do modelo, não defeito. Com P-32 = 10 K a troca é quase
  balanceada, o óleo viscoso fica laminar no turndown e o casco 1-2 sai do domínio de F; o
  menor comprimento de tubo na grade é 186 m contra 6 m (nota 36). Nenhuma alternativa (A1–A9)
  foi adotada.
- Dimensionamento preliminar: sem projeto mecânico, espessuras, bocais, internos, controle.
- Grades dos trocadores desalinhadas entre caso e envelope (nota 33); revisar muda número.
- Bombas com geometria de linha proposta (§5), sem isométrico nem curva de fabricante.
- Avisos de faixa de descritores ficam registrados no JSON e no MC (p. ex. vazão de gás do SG-001
  acima de 500.000 Sm³/h em três casos, por ruído de reconvergência ou T real do FWKO).

## 8. Limitações dos casos com lift

Casos **9, 11, 15 e 16**: o gás de lift entra em C-01, mas **não tem composição na fonte** (BOT
§2.3.3 só dá especificação). Eles são "não avaliáveis termodinamicamente para integração
completa": seguem no envelope de dimensionamento por Standing, **sem TVP e sem recuperação de óleo
verificadas**. Nenhuma composição foi suposta.

## 9. Limitações da otimização

- Subproblema de **pressão e separação**: só P_D1 e P_D2; só SG-001, V-001 e V-002 restringidos;
  P-001, P-002, P-003, TO-001, TO-002 e bombas fora.
- Domínio de **estudo** (P_D1 200–2.000 kPa, P_D2 110–250 kPa, região da nota 41), não faixa de
  projeto; o piso de P_D2 não tem fonte.
- TVP verificada só nos 12 casos avaliáveis.
- Carga da VRU é vazão de vapor, não potência de compressor (sem modelo de compressor).
- Os dois objetivos não conflitam no domínio: a frente degenera num ponto, limitado pela TVP.
- A frente foi conferida contra uma grade de 195 pontos na resolução da própria grade.

## 10. Aproximação trem × balanço (T1)

**Classificação: ACEITO COM LIMITAÇÃO / APROXIMAÇÃO DO MODELO.**

- O trem de flashes trabalha sobre a **alimentação recombinada** (C-01).
- O balanço inclui pequenas remoções e retornos que o trem não vê: o óleo que sai na água do
  FWKO (P-25), o arraste de líquido no gás (P-26) e o óleo que volta no reciclo de água.
- Essas alterações **não são realimentadas composicionalmente** estágio a estágio: os vapores de
  V-001 e V-002 são calculados sobre o líquido do trem, não sobre o líquido do balanço.
- A **massa global continua fechando** (as correntes de líquido do balanço são obtidas por
  diferença; O e G conservados).
- **Impacto máximo medido: 0,55 %** na base de óleo (caso 12); abaixo de 0,001 % nos casos sem
  reciclo de água (1, 4–7).

## 11. Pendências de projeto

1. **P-001 inviável** — decisão de projeto (P-32, arranjo, modo de operação ou tipo de trocador).
2. **Cenário-base não conforme à TVP**: com P-19 = 200 kPa a TVP do óleo é 93,1–110,8 kPa nos 12
   casos avaliáveis, contra 70 kPa do BOT. A não conformidade é declarada, não corrigida: a
   release mantém 700/200 como premissas iniciais.
3. Piso de P_D2 (sucção da VRU) e ΔP de transferência entre vasos — sem fonte.
4. As 43 propostas (§5) dependem de dados de projeto (isométricos, fabricantes, laboratório).

## 12. Trabalhos futuros

- Composição do gás de lift (integraria os 4 casos restantes).
- h/cp dos pseudo-componentes; translação de volume (Péneloux) com parâmetro de fonte própria;
  k da fase líquida; μ do gás pela composição de equilíbrio.
- Solução do P-001 (alternativas da nota 36).
- Realimentação composicional do balanço no trem (eliminaria T1).
- Revisão da discretização das grades dos trocadores (nota 33).
- Pressões da VRU e modelo de compressor, para um objetivo de energia.
- Otimização da planta inteira depois de resolvido o P-001.

## 13. O que o software NÃO pretende representar

- Não é simulador de processo comercial nem substitui um projeto básico ou de detalhamento.
- Não representa dinâmica, controle, partida ou transientes: só regime permanente por caso.
- Não dá pressões de projeto definitivas: a otimização é um estudo num domínio declarado.
- Não valida propriedades contra PVT de laboratório.
- Não dimensiona a planta de gás, a VRU, o tratamento de água, a estocagem ou utilidades.
- Não faz projeto mecânico, custo, peso ou layout.
- Não apresenta valor proposto como valor com fonte.
