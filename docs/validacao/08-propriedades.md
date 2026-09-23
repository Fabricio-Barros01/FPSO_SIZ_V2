# 08 — Propriedades na condição do equipamento (F10a)

Data: 2026-09-23. **Estado: entregue.**

## O que é e por que existe
O balanço preliminar trabalha na condição padrão: gás ideal (premissa P-39), óleo morto
(P-40) e densidades de premissa. O dimensionamento precisa das propriedades na condição
**do vaso, da bomba e do trocador**. A F10a acrescenta essa camada **a jusante** do
balanço (`src/fpso_siz/pfd/`), que fica oculta no balanço e exposta no MC do equipamento
(F11). O balanço não muda, e a paridade bit a bit continua verde.

## Decisões do usuário
- **Regra das fontes:** "para as referências sem fonte não suponha nada, complete o que é
  possível". Sem fonte citável, é **lacuna** (NaN, anotada), nunca um número suposto.
- **thermo e chemicals (ChEDL, MIT) como dependência direta de runtime.** Ficam atrás de
  uma porta única, `pfd/_chedl.py`, como numpy/scipy em `_num.py`. O teste de arquitetura
  proíbe importá-los em outro lugar, e o port a C/Java troca só essa camada. A importação é
  preguiçosa: a CLI não paga o ~1 s de import nem os ~2 s da montagem das constantes do gás.

## O que cada propriedade usa

| Propriedade | Método | Fonte |
|---|---|---|
| Z do gás | Peng-Robinson com a composição do balanço (corte N2–nC4, P-03) e kij do ChemSep; flash (T, P) com `thermo.FlashVL`, fase vapor | Peng & Robinson (1976), ref. [1] de `thermo.PRMIX` |
| ρ do gás | P·MW/(Z·R·T), com MW e R do balanço, para ṁ/ρ ficar coerente com a massa do balanço | Stewart & Arnold, eq. 1.8 (PV = ZnRT) |
| μ e k do gás | puros por ajuste REFPROP; mistura por Brokaw (μ) e Lindsay-Bromley (k) | thermo 0.6.1; regra de gás diluído, sem correção de pressão (declarado) |
| Água de diluição | IAPWS-95 (ρ), IAPWS 2008 (μ), IAPWS 2011 (k) | Wagner & Pruß (2002); Huber et al. (2009; 2012), via chemicals |
| Salmoura (ρ, μ, cp) | NaCl com w = S_W/ρ_W; faixas de validade lidas do banco | Laliberté (2009), via thermo.electrochem |
| **k da salmoura** | **lacuna** | o banco de Magomedov do thermo não tem NaCl |
| μ do óleo | tabela de óleo morto do BOT, log-linear, valor do extremo fora dela | BOT Tab. 2.2.1.2 + P-40 (a mesma regra do balanço) |
| ρ do óleo | padrão, pelo API | balanço (P-07); sem correção por T e Bo, por falta de fonte |
| **k do óleo** | **lacuna** | sem fonte no acervo nem no ChEDL |
| μ de emulsão | Zanker, com as faixas de validade da página | Branan (2012), p. 406, eq. 27-4 |
| Pv na sucção | líquido no ponto de bolha: Pv = P do vaso | Branan (2012), p. 116, Ex. 5-2 |

As duas equações do Branan foram **conferidas na página renderizada do PDF**, não só no
texto extraído. Os coeficientes e as faixas estão em `config/fluidos.toml`.

## Validação (`tests/pfd/test_fluidos.py`)
- **Exemplos das docstrings do ChEDL,** que citam a fonte primária:
  - `Laliberte_viscosity`, `_density` e `_heat_capacity` (planilha do autor);
  - `mu_IAPWS(298,15; 998) = 889,7351 µPa·s`.
- **Duas fontes independentes concordam.** Laliberté a 15,6 °C dá ρ = 1156,7 kg/m³ para a
  salmoura de 240.000 mg/L; a premissa P-08 do balanço é 1154 (0,23 %).
- **Comparação com outra biblioteca,** feita no estudo e fora da suíte. A 90 °C:
  - salmoura: μ = 0,526 cP (Laliberté) contra 0,529 cP (Spivey/McCain, pyrestoolbox);
  - gás do caso 8: Z = 0,937 (PR) contra 0,947–0,953 (DAK/HY com correção de CO₂) e 0,942
    (Redlich-Kwong do Branan com Kay).
- **Limites e identidades:**
  - Z → 1 quando P → 0, e ρ = ideal/Z;
  - a μ do óleo reproduz a tabela do BOT nos nós;
  - Zanker com δ_D = 0 dá μ_C;
  - fora das faixas (Laliberté, Zanker, tabela do óleo), o resultado vem com **aviso**, sem
    bloquear;
  - condensação prevista pela EOS também gera aviso.

## Resultado nos 16 casos (thermo 0.6.1, chemicals 1.5.2)
Gás na saída de cada vaso (C-04: SG-001 a 2500 kPa; C-09: V-001 a 700 kPa; C-17: V-002 a
200 kPa), salmoura em C-12 (90 °C) e óleo em C-10 (90 °C):

| Caso | Fluido | Z C-04 | ρ C-04 / ideal | μ_g C-04 (cP) | Z C-09 | Z C-17 | μ salmoura C-12 (cP) | μ óleo C-10 (cP) |
|---|---|---|---|---|---|---|---|---|
| 1 | Early Life | 0.9324 | 1.0725 | 0.01319 | 0.9849 | 0.9957 | 0.526 | 7.90 |
| 2 | Early Life | 0.9260 | 1.0799 | 0.01289 | 0.9849 | 0.9957 | 0.526 | 7.90 |
| 3 | Early Life Blend | 0.9279 | 1.0777 | 0.01274 | 0.9852 | 0.9957 | 0.526 | 6.30 |
| 4 | Early Life | 0.9165 | 1.0912 | 0.01248 | 0.9849 | 0.9957 | 0.526 | 7.90 |
| 5 | Low CO2 | 0.8986 | 1.1128 | 0.01083 | 0.9834 | 0.9952 | 0.526 | 6.30 |
| 6 | Mid Life | 0.9085 | 1.1008 | 0.01258 | 0.9852 | 0.9957 | 0.526 | 7.90 |
| 7 | Mid Life | 0.9402 | 1.0637 | 0.01406 | 0.9852 | 0.9957 | 0.526 | 7.90 |
| 8 | Mid Life | 0.9373 | 1.0669 | 0.01389 | 0.9852 | 0.9957 | 0.526 | 7.90 |
| 9 | Mid Life | 0.9382 | 1.0658 | 0.01395 | 0.9852 | 0.9957 | 0.526 | 7.90 |
| 10 | Late Life | 0.9484 | 1.0544 | 0.01519 | 0.9852 | 0.9957 | 0.525 | 7.90 |
| 11 | Late Life | 0.9298 | 1.0755 | 0.01405 | 0.9852 | 0.9957 | 0.526 | 7.90 |
| 12 | Late Life | 0.9484 | 1.0545 | 0.01519 | 0.9852 | 0.9957 | 0.525 | 7.90 |
| 13 | High CO2 | 0.9472 | 1.0558 | 0.01552 | 0.9849 | 0.9957 | 0.525 | 7.90 |
| 14 | High CO2 | 0.9471 | 1.0558 | 0.01552 | 0.9849 | 0.9956 | 0.525 | 7.90 |
| 15 | Highest CO2 | 0.9396 | 1.0642 | 0.01614 | 0.9829 | 0.9951 | 0.526 | 7.90 |
| 16 | Highest CO2 | 0.9396 | 1.0642 | 0.01614 | 0.9829 | 0.9951 | 0.526 | 7.90 |

Leitura:
- **FWKO.** A premissa de gás ideal subestima a massa específica do gás em **5–11 %**; nos
  desgaseificadores, em 0,4–1,7 %. É o ganho principal do detalhamento para o bloco de
  gás do separador.
- **Aviso único nos 16 casos:** "viscosidade do óleo limitado a 70 °C" nos tratadores
  (90 °C). A tabela do BOT termina em 70 °C, e não há fonte para extrapolar; o MC mostra o
  aviso.

## Ambiente
No NixOS, o numpy do venv precisa do `LD_LIBRARY_PATH` do flake (`direnv allow` ou
`.direnv/flake-profile-*.rc`). Até a F7b o projeto não importava numpy de fato; o thermo
importa. Em Linux, Windows e macOS comuns as wheels funcionam sem isso.
