# F10x.6 — banda de velocidade das bombas pelo caso de projeto (P-44, P-44b)

O usuário aprovou em 2026-09-26 ("a proposta da bomba pode prosseguir como aprovada"). Este
documento justifica a mudança de resultado, como exige o CLAUDE.md.

## O problema (alarmes B-001/B-002/B-003 da F13)

A velocidade na linha é v = Q/A, então ela já depende da vazão de cada caso. O que não
fechava era a regra do envelope: a banda de Moran (2016), 1,0 ≤ v ≤ 1,5 m/s, era exigida
**em todos os 16 casos** de **uma mesma linha**. A vazão varia 23× no B-001, 10× no B-002 e
8× no B-003. Assim, o DN que põe o caso de maior vazão na banda deixa os de menor vazão
abaixo do piso, e nenhum DN atende a todos.

## A premissa

- **P-44** (`piso_caso_projeto = 1`): a linha é dimensionada pelo **caso de projeto**, o de
  maior vazão volumétrica. Nele vale a banda inteira. Nos demais (turndown), vale só o teto
  `v_max`, que no mesmo DN fica automaticamente atendido, porque o caso de projeto tem a maior
  velocidade.
- **Piso só para água:** Moran (2016) dá o piso de 1 m/s para "water-like fluids with
  settleable solids". O B-001 (óleo tratado, líquido limpo) recebe `v_min = 0`. O B-002 e o
  B-003 (água produzida, que pode levar sólidos) mantêm o piso no caso de projeto.
- **P-44b** (`transicao_turndown = 1`, **a confirmar**): num caso de turndown a linha larga
  pode ficar na zona de transição laminar-turbulento (Re entre 2.300 e 4.000), onde nenhuma
  correlação da implementação vale. Ali o fator de Colebrook-White é aceito como **limite
  superior**:
  - o teste verifica f ≥ 64/Re em toda a zona, para tubo liso e rugoso;
  - a perda de carga fica superestimada e o NPSH disponível, subestimado (lado seguro);
  - o caso de projeto continua exigindo correlação válida.

## Implementação

- **Motor:** hook genérico `envelope_case_params(conss, p_env)` em `core/contrato.py`. O padrão
  devolve os parâmetros do envelope para todos os casos, que é a regra do Julia. O motor não
  cita grandeza.
- **Bomba** (`sizing/bomba.py`):
  - dois descritores de extensão em `moran_extensoes.toml`, ambos com default 0 (regra do Julia, paridade mantida);
  - `envelope_case_params`: tira o piso fora do caso de projeto e, com a P-44b, aceita a transição;
  - `operacao_por_caso`: tabela do MC com v, Re, regime, H, folga de NPSH e potência por caso.
- **TAGs:** `[recomendadas]` de `b_001/2/3.toml`, com fonte P-44 e revisão pendente. O usuário
  pode editar no modo interativo.
- **Estudo:** a variante `sem_p44` (`config/pfd/alarmes.toml`) reproduz o estado anterior, e o
  relatório `14-alarmes.md` compara os dois.

## Resultado (16 casos do BOT, com as propostas)

| TAG | Caso de projeto | Q_max/Q_min | DN | H (m) | P no caso governante (kW) | P máxima entre os casos (kW) |
|---|---|---|---|---|---|---|
| B-001 | 2 (1.198 m³/h, v = 1,18 m/s) | 23,0 | 600 | 75,1 | 310 | 310 |
| B-002 | 11 (180 m³/h, v = 1,02 m/s) | 10,2 | 250 | 183,4 | 14 | 140 |
| B-003 | 3 (46 m³/h, v = 1,05 m/s) | 8,2 | 125 | 252,2 | 45 | 45 |

- Só o caso 6 do B-001 (52 m³/h, 4 % da vazão de projeto, Re ≈ 3.460 em DN 600) usa a P-44b.
- A **potência de eixo do resultado** é a do caso que governa a carga, que é a regra do motor
  do Julia. No B-002 esse caso é de baixa vazão (18 m³/h), e a potência a especificar é a maior
  entre os casos. O MC agora mostra as duas (tabela "Operação de cada caso").

## Limitações (no MC de cada bomba)

- Uma bomba não opera numa faixa de 23×. A vazão mínima contínua é dado do fabricante (fora do
  acervo), e os casos de menor vazão podem exigir bombas em paralelo ou recirculação de mínimo
  fluxo. Isso não é modelado.
- A P-44b é juízo de engenharia (limite superior), não correlação de transição. Fica a
  confirmar.

## Paridade

- A fixture do Julia (`tests/fixtures/julia/bomba-centrifuga.json`) e o PFD F1 continuam
  iguais, porque os defaults são a regra do Julia.
- A regressão F10b roda com a P-44 desligada (`tests/pfd/test_servico.py::_sem_p44`), do mesmo
  modo que a P-42.
- Testes novos: `tests/sizing/test_banda_caso_projeto.py` e
  `tests/pfd/test_alarmes_contrato.py::test_p44_*`.
