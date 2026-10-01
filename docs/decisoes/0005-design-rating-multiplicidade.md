# ADR 0005 — DESIGN, RATING e multiplicidade de unidades físicas

Data: 2026-09-30. Estado: aceito.

## Contexto

O P-001 tratava o alvo de recuperação da Análise Pinch como carga obrigatória de uma
mesma geometria em todos os casos. O envelope existente é um cálculo de **DESIGN**:
calcula área e comprimento exigidos. Usá-lo como off-design redimensiona implicitamente
o equipamento. Além disso, os cascos internos do método eram a única noção de paralelo;
não existia representação de unidades físicas duty/standby.

## Decisão

1. Pinch continua inalterado e fornece `Q_rec_max`, limite termodinâmico.
2. O rating recebe geometria fixa e resolve numericamente
   `Q = UA(Q) F(Q) ΔTlm(Q)`, com as temperaturas de saída calculadas pelo próprio Q,
   bisseção limitada a `[0, Q_rec_max]` e bloqueio de cruzamento.
3. O balanço realizado usa `Q_real = min(Q_rec_max, Q_rating)` e recalcula as utilidades
   residuais a partir das temperaturas realizadas.
4. Multiplicidade física é um contrato de serviço separado de cascos em série/paralelo
   e passes. Instaladas, duty, standby, fração nominal e mínimo de ativas são dados
   explícitos; sufixos A/B/C não têm semântica implícita.
5. A busca discreta executa DESIGN uma vez por candidato, RATING em todos os casos e
   rejeita qualquer candidato que viole seu método. Sem dados econômicos, a seleção
   expõe a frente de Pareto de área instalada, utilidade quente e utilidade fria.
6. Bombas usam o mesmo contrato de multiplicidade, mas avaliação hidráulica própria:
   vazão por unidade, head, potência, eficiência, NPSH e limites informados.
7. Uma geometria Saari instalada é imutável no rating: número de tubos por passe e
   comprimento determinam a área, enquanto películas, U e F são reavaliados com Q.
8. O acoplamento ao processo ocorre somente em `balanco/integracao_energetica.py`; sem
   geometria aprovada o baseline é preservado e a ausência continua sendo lacuna.

## Consequências

- Área operacional e área instalada passam a ser grandezas diferentes.
- Standby entra no total instalado, mas não recebe vazão/carga operacional.
- Turndown pode operar com menos unidades, elevando velocidade e Reynolds sem alterar a
  geometria instalada.
- Ausência de curva, vazão mínima ou NPSHr continua sendo lacuna; o algoritmo não inventa
  dados de fabricante.
