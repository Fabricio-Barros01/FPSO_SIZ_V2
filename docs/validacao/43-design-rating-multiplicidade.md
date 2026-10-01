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

## Acoplamento produtivo entregue na fase 2

O adaptador `rating_saari` transforma uma geometria unitária congelada (tubos por passe e
comprimento) em `UA(Q)` e `F(Q)`: em cada avaliação ele reconstrói temperaturas, Bell–Delaware,
película do tubo, Reynolds, coeficientes e área da geometria instalada. O comprimento não é
obtido novamente da carga. Assim, um caso off-design não redimensiona o equipamento.

O resolvedor `balanco/integracao_energetica.py` é o único laço de acoplamento. Ele conserva as
correntes mássicas, substitui a carga idealizada por `Q_real`, atualiza C-07 e C-23 e recalcula
P-002 e P-003. Tolerância, máximo de iterações, convergência e resíduo são explícitos. O serviço
por TAG permite ativá-lo mediante `rating_p001`, sempre com a mesma geometria instalada.

A filosofia física também passou a integrar o descritor declarativo de TAG. P-001 declara um
**domínio de busca**, não uma configuração escolhida. P-002, P-003 e B-001/2/3 declaram a
filosofia duty/standby como lacuna: não se inferiu `2×50%`, `2×100%` ou standby a partir do nome.

## Resultado de engenharia ainda aberto

Nenhuma fonte do projeto identifica a geometria instalada ou a filosofia duty/standby do
P-001. Portanto esta mudança não promove arbitrariamente um candidato a projeto. O caminho
produtivo anterior permanece como baseline quando `rating_p001` não é fornecido; quando uma
geometria é fornecida, o mesmo PFD passa pelo rating e propaga suas utilidades. A seleção final
do layout continua bloqueada por decisão de projeto documentada, e não por falta de conexão
entre o rating e o balanço.

## Limitação declarada

A correlação de Beggs & Robinson não recebe composição do gás. O alto teor de CO₂ segue
como incerteza de aplicabilidade já documentada na nota 40. Não foi criado caminho
produtivo alternativo por Standing e nenhum fouling, condutividade ou limite foi alterado.
