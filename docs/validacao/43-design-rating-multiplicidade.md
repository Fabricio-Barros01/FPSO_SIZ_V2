# 43 — DESIGN × RATING e multiplicidade física

## Diagnóstico reproduzido com o trem atual

A reexecução de 2026-09-30 usa o caminho produtivo aprovado `Rs do trem → Beggs &
Robinson`, sem recuperar os números históricos como oráculo. O P-001 padrão continua
parando primeiro no fator F do arranjo 1–2. Com um passe, o bloqueio conhecido passa a
ser área/comprimento; isto é inviabilidade da geometria que tenta realizar todo o alvo,
não demonstra que toda recuperação parcial seja impossível.

Entradas atuais destacadas (valores do `ExchangerDuty`, unidades SI):

| BOT | ṁ tubo (kg/s) | ρ tubo (kg/m³) | μ tubo (Pa·s) | cp tubo (J/kgK) | T fria in→alvo (°C) | ṁ casco (kg/s) | μ casco (Pa·s) | T quente in (°C) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 02 | 319,449 | 894,205 | 0,003231 | 2.020,208 | 52,681→78,005 | 292,267 | 0,007944 | 90,479 |
| 03 | 319,158 | 890,403 | 0,002596 | 2.021,590 | 52,820→77,831 | 290,014 | 0,006335 | 90,481 |
| 05 | 52,816 | 885,150 | 0,002838 | 1.994,226 | 35,000→77,343 | 49,026 | 0,006668 | 90,484 |

Os dados mostram por que o diagnóstico antigo não pode ser transplantado: BOT 02/03 têm
viscosidades do tubo de 2,60–3,23 cP com o Rs do trem, enquanto BOT 05 está em 2,84 cP e
tem somente cerca de um sexto da vazão. O governante deve ser determinado pelo rating e
pelas restrições simultâneas, não pelo rótulo histórico do caso 5.

## Contratos implementados

- `sizing/rating.py`: rating limitado, fechamento dos dois lados, ausência de cruzamento,
  diagnóstico de convergência, `Q_rec_max`, `Q_rating`, `Q_real` e recuperação não realizada.
- `sizing/servico.py`: unidades físicas, política de turndown, totais extensivos, busca
  discreta e frente de Pareto física.
- `sizing/bombas_paralelo.py`: divisão de vazão e avaliação separada de potência/NPSH.

## Limitação declarada

A correlação de Beggs & Robinson não recebe composição do gás. O alto teor de CO₂ segue
como incerteza de aplicabilidade já documentada na nota 40. Não foi criado caminho
produtivo alternativo por Standing e nenhum fouling, condutividade ou limite foi alterado.

