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

## Integração no caminho produtivo

O serviço `pfd/equipamento.py` materializa uma única geometria do P-001 (comprimento físico
limitado pelo método e número fixo de tubos por passe), chama a busca discreta e executa o
rating para os 16 `EstadoProcesso`. O resultado guarda `Q_Pinch`, `Q_real`, ambas as
temperaturas de saída, cargas residuais de P-002/P-003 e diagnóstico numérico de cada caso.

`pfd/planta.py` substitui no estado produtivo `Q_pre`, `Q_H`, `Q_C`, `T_C07` e `T_C23`
antes de preparar P-002 e P-003. O JSON, o CSV de operação, o memorial por TAG e o gate de
auditoria recebem esse mesmo objeto; não há API de operação paralela. O teste
`tests/arquitetura/test_p001_integrado.py` instrumenta o PFD normal e falha se a busca, o
rating ou a propagação deixarem de ser alcançados.

## Busca discreta e seleção reproduzível

O domínio está em `config/pfd/p_001_busca.toml`, junto da fonte: 50–400 tubos por passe
(passo 25), tubos de 6,0–9,0 m (passo 1,5 m), diâmetro externo 19,05 mm, um passe,
razão de passo 1,25, layouts 30°/45°, corte de chicana 25 % e espaçamento 40 % do casco.
São comparadas as filosofias 2 × 100 % (1 duty + 1 standby) e 3 × 50 % (2 duty + 1
standby); em ambas a reserva instalada da ET permanece fisicamente separada do duty.

Cada ponto materializa **uma** geometria antes de avaliar os 16 casos. Em cada iteração do
rating são reconstruídas as restrições do método para as temperaturas de saída correntes;
da mesma física de `trocador.py`, `pelicula.py` e `bell_delaware.py` saem Reynolds, filmes,
U, F, LMTD, diâmetro de casco e velocidade. Candidato que não converge ou viola a validade
das correlações, velocidade, comprimento ou diâmetro em qualquer caso obrigatório é
descartado. Perda de carga ainda aparece como `NaN`: o acervo tem Darcy–Weisbach para tubos,
mas não tem uma correlação de perda no casco; inventar a segunda parcela contrariaria a regra
das fontes. Portanto ela é diagnóstico explícito, não uma restrição silenciosamente suposta.

A frente não dominada maximiza recuperação e minimiza área instalada e soma das utilidades.
O alvo Pinch é teto (`Q_Pinch`), não restrição de recuperação integral. Dentro da frente, o
desempate lexicográfico é: utilidades, área instalada, instaladas, duty, tubos por passe,
comprimento, diâmetro, passes, layout, razão de passo, corte e espaçamento de chicana. A
fixture `tests/fixtures/pfd/p001_busca_regressao.json` congela tanto essa ordem quanto a
seleção atual: **3 instaladas, 2 duty, 1 standby; 400 tubos/passe; 9,0 m; 19,05 mm; um
passe; layout 45°; razão 1,25; corte 0,25; espaçamento 0,40**, área unitária
215,45042418318803 m².

## Limitação declarada

A correlação de Beggs & Robinson não recebe composição do gás. O alto teor de CO₂ segue
como incerteza de aplicabilidade já documentada na nota 40. Não foi criado caminho
produtivo alternativo por Standing e nenhum fouling, condutividade ou limite foi alterado.
