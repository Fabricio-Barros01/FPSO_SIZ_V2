# ADR 0005 — DESIGN, RATING e multiplicidade de unidades físicas

Data: 2026-09-30. Revisada e **conectada ao caminho produtivo** em 2026-10-02.
Estado: aceito e implementado (ver `docs/validacao/43-design-rating-multiplicidade.md`).

## Contexto

O P-001 tratava o alvo de recuperação da Análise Pinch como carga obrigatória de uma
mesma geometria em todos os casos. O envelope existente é um cálculo de **DESIGN**:
calcula área e comprimento exigidos. Usá-lo como off-design redimensiona implicitamente
o equipamento — num serviço com turndown de até ~24× em capacidade térmica, os casos de
baixa vazão caem no laminar, o U despenca e o envelope passa a pedir uma área que o caso de
projeto não precisa. Era essa a causa do alarme: `docs/validacao/36`, alternativa **A5** da
árvore de alternativas. Além disso, os cascos internos do método eram a única noção de
paralelo; não existia representação de unidades físicas duty/standby.

## Decisão

1. Pinch continua inalterado e fornece `Q_rec_max`, limite TERMODINÂMICO. O balanço
   preliminar continua escrevendo esse alvo, e segue congelado pela regressão.
2. O rating recebe geometria fixa e resolve numericamente
   `Q = UA(Q) F(Q) ΔTlm(Q)`, com as temperaturas de saída calculadas pelo próprio Q,
   bisseção limitada a `[0, Q_rec_max]` e bloqueio de cruzamento. `UA` e `F` são
   **callbacks reavaliados em cada iteração**: o U não é congelado no ponto de projeto.
3. O rating declara o seu ESTADO (`sizing/rating.py`): `limitado_pelo_alvo`,
   `limitado_pela_area`, `sem_forca_motriz` ou `nao_avaliavel`. **`UA` não avaliável devolve
   NaN com motivo, nunca carga zero** — zero afirmaria que a geometria não troca calor, o que
   não foi calculado (invariante 5).
4. No envelope, só o caso de PROJETO dimensiona a geometria; os demais são CLASSIFICADOS
   nela. O motor ganha um hook de contrato (`envelope_constraints`) que não sabe o que a
   marca significa: quem marca é o método. O default devolve as mesmas restrições, e aí a
   física é a do Julia.
5. A recuperação não realizada propaga às utilidades (`pfd/integracao_termica.py`): o
   destino de cada lado é a PREMISSA (temperatura de tratamento, de estocagem), e o aquecedor
   e o resfriador são **dimensionados pela carga residual**. As propriedades são reavaliadas na
   temperatura média REALIZADA, por ponto fixo.
6. A integração **não reabre o balanço**, e isso é verificado caso a caso: enquanto a
   temperatura de destino de cada lado não muda (o piso de tratamento e o teto de estocagem
   são o que o balanço propaga adiante), o reciclo não é tocado. Caso em que isso deixe de
   valer sai com aviso declarado.
7. Multiplicidade física é um contrato de serviço separado de cascos em série/paralelo
   e passes. Instaladas, duty, standby, fração nominal e mínimo de ativas são dados
   explícitos; sufixos A/B/C não têm semântica implícita. A **reserva instalada que a ET
   exige** entra na área instalada e não recebe carga operacional.
8. A busca discreta (`pfd/layout.py`, `tools/buscar_layout_trocador.py`) executa DESIGN uma
   vez por candidato, RATING em todos os casos, **redimensiona o aquecedor e o resfriador pelas
   cargas residuais** e só então declara viabilidade. Sem dados econômicos, a seleção expõe a
   frente de Pareto de área instalada, utilidade quente e utilidade fria, e a regra de
   preferência é declarada (recuperação, área instalada, número de cascos).
9. A perda de carga do lado tubo é calculada (Darcy-Weisbach com as correlações e as
   fronteiras que a bomba já usa, Moran 2016) e verificada contra a premissa P-17 **onde a
   premissa se aplica** — no P-001, cujo lado tubo é o processo. No P-002 e no P-003 o lado
   tubo é a utilidade e a P-17 é do lado do processo (o casco): ali a perda é reportada, não
   aprovada, e a do lado casco é lacuna declarada (sem fator de atrito de feixe no acervo).

## Consequências

- Área operacional e área instalada passam a ser grandezas diferentes.
- Standby entra no total instalado, mas não recebe vazão/carga operacional.
- Turndown pode operar com menos unidades, elevando velocidade e Reynolds sem alterar a
  geometria instalada.
- **O P-002 e o P-003 mudam de número**: passam a ser dimensionados pela carga residual, que é
  maior que a preliminar nos casos em que a geometria do P-001 não realiza o alvo. A mudança
  está justificada e tabelada em `docs/validacao/43`.
- Ausência de curva, vazão mínima ou NPSHr continua sendo lacuna; o algoritmo não inventa
  dados de fabricante.
- **Multiplicidade de BOMBAS não é entrega desta ADR.** O contrato de serviço existe e é
  exercitado pela busca de layout do trocador; nenhum TAG de bomba o usa, e isso está
  declarado como pendência no `SPRINTS.md`. O módulo que havia sem consumidor
  (`sizing/bombas_paralelo.py`) foi removido: contrato sem caminho produtivo é dívida, não
  entrega.
