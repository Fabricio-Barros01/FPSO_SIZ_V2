# F10x.5 — viscosidade de óleo vivo (Beggs & Robinson) na camada do PFD

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): o óleo vivo é o único modelo; a comparação com o modo de óleo morto é registro. O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Pedido do usuário (2026-09-26): "Corrija a viscosidade para o valor real". Este documento
justifica a mudança de resultado exigida pelo CLAUDE.md ("mudar um resultado exige
justificativa escrita em `docs/validacao/`").

## O que estava errado

O BOT (Tab. 2.2.1.2) só mede a viscosidade do **óleo morto** (sem gás). Até a F13 a camada do
PFD usava esse valor (regra P-40) para todo óleo, inclusive o óleo que sai do FWKO a ~10 bar,
ainda com gás dissolvido. O gás dissolvido reduz a viscosidade, e a decantação de água no óleo
é inversamente proporcional a ela ((h_o)max ∝ 1/µ_o, S&A §4.7.2). Por isso o teto do SG-001
ficava subestimado, e essa era a primeira hipótese de premissa do alarme
(`docs/validacao/14-alarmes.md`).

## O que mudou

- **Correlação:** Beggs, H. D.; Robinson, J. R. *Estimating the Viscosity of Crude Oil
  Systems*. JPT 27(9), p. 1140–1141, 1975.
  µ_o = A·µ_od^B, A = 10,715 (Rs + 100)^−0,515, B = 5,44 (Rs + 150)^−0,338 (Rs em scf/STB,
  µ em cP). Coeficientes e faixa de dados em `config/fluidos.toml [oleo_vivo]`. A referência
  **não está no acervo local** (`references/`), do mesmo modo que a correlação de Standing do
  balanço, e está marcada "a conferir".
- **µ_od:** o óleo morto do BOT na temperatura do TAG, com a regra P-40 (sem mudança).
- **Rs:** o gás dissolvido na corrente de líquido que o balanço já calcula (Standing, P-23):
  Rs = Q_G/Q_O na condição padrão da corrente, convertido de Sm³/Sm³ para scf/STB pelos fatores
  exatos de `core/unidades.py` (`sm3sm3_para_scf_stb`). Nenhum valor novo foi suposto.
- **Corrente:** a própria corrente da regra `viscosidade_fase`. No SG-001 a regra usa a saída
  de óleo (`rs = "C-06"`), porque a entrada C-03 leva também o gás livre.
- **Faixa:** a correlação só é aplicada dentro da faixa de Rs dos dados (20–2070 scf/STB).
  Abaixo dela o óleo morto medido é mantido, com aviso quando Rs arredondado for > 0. Com os
  coeficientes arredondados, A(0) = 0,99998 e B(0) = 1,00018: extrapolada para Rs → 0, a
  correlação daria um óleo "vivo" 0,04 % mais viscoso que o morto, o que não tem sentido
  físico. Fora das faixas de API (16–58) e de T (70–295 °F) há só aviso.
- **Rastro/MC:** para cada TAG com óleo vivo o rastro mostra µ_od (BOT/P-40), Rs e µ_o (Beggs &
  Robinson), e a fonte da entrada diz "óleo vivo, Beggs & Robinson (1975); Rs de C-xx". A
  limitação de óleo no JSON e no MC depende do modo.

## Modos e paridade

| Modo | Como | Uso |
|---|---|---|
| óleo vivo (padrão) | `Contexto(..., oleo_vivo=True)` | CLI, interativo, MC |
| óleo morto | `--oleo-morto` (CLI `dimensionar`, `pfd`, `interativo`); `oleo_vivo=False` | paridade |

O balanço não muda: a paridade bit a bit com o oráculo e a regressão F10w continuam iguais. As
fixtures do PFD F1 do Julia e a regressão F10b usam o modo óleo morto
(`tests/pfd/conftest.py::planta_referencia`, `test_servico.py::plantas_f10b`), porque foram
geradas assim. O estudo do alarme da F13 fica reprodutível em `planta_oleo_morto`. Um TAG em
modo manual nunca recebe a correção.

## Efeito (16 casos do BOT, regra de eficiência do FWKO)

### SG-001: µ do óleo na saída (C-06)

| Caso | Rs C-06 [scf/STB] | µ_od [cP] | µ_o vivo [cP] | µ_o/µ_od |
|---|---|---|---|---|
| 1 | 60,6 | 9,11 | 5,62 | 0,617 |
| 2 | 64,3 | 13,28 | 7,67 | 0,577 |
| 3 | 63,8 | 10,01 | 5,99 | 0,598 |
| 4 | 66,8 | 17,45 | 9,60 | 0,550 |
| 5 | 62,9 | 18,45 | 10,37 | 0,562 |
| 6 | 73,6 | 26,00 | 12,98 | 0,499 |
| 7 | 60,4 | 7,90 | 4,96 | 0,627 |
| 8 | 64,2 | 9,61 | 5,76 | 0,600 |
| 9 | 62,7 | 8,40 | 5,16 | 0,614 |
| 10 | 59,8 | 7,90 | 4,97 | 0,630 |
| 11 | 69,8 | 10,68 | 6,11 | 0,572 |
| 12 | 59,9 | 7,90 | 4,97 | 0,629 |
| 13 | 62,5 | 7,90 | 4,89 | 0,619 |
| 14 | 62,5 | 7,90 | 4,89 | 0,619 |
| 15 | 71,6 | 7,90 | 4,63 | 0,587 |
| 16 | 71,5 | 7,90 | 4,64 | 0,587 |

Rs, API (27,5–28,2) e T ficam todos dentro da faixa da correlação.

### Por TAG

| TAG | Óleo morto | Óleo vivo | Observação |
|---|---|---|---|
| SG-001 | inviável: teto 3.612 mm (caso 2) | **D = 6.050 mm**, L_eff = 17,87 m, L_ss = 23,82 m, SR = 3,94; teto 6.257 mm (caso 2); governa o caso 12 | alarme explicado: hipótese de premissa confirmada |
| P-002 | inviável: Re no tubo 1.137–3.385, Pr 249 | inviável: Re 1.876–5.588, Pr 150,9 | óleo C-07 com Rs ≈ 60; mais perto, mas ainda fora de Dittus-Boelter; µ_od limitado ao valor de 70 °C (P-40), logo conservador |
| TO-001 | D = 5.550 mm | igual | C-10 com Rs ≈ 9–13 scf/STB, abaixo da faixa: óleo morto mantido, com aviso |
| TO-002, P-001, P-003, B-001/2/3 | — | iguais | correntes já desgaseificadas (Rs ≈ 0) |
| V-001, V-002 | D = 4.700 mm | igual | critério de gás, sem µ_o |

O SG-001 viável tem folga de só 207 mm (3 %) entre o diâmetro escolhido e o teto do caso 2.
O resultado continua sensível a µ_o, ao critério de 500 µm e à P-43 (hipóteses 2 e 3, que
seguem registradas em `config/pfd/alarmes.toml`).

## Limitações (declaradas no JSON e no MC)

- A correlação é bibliográfica, fora do acervo local, e não substitui um PVT medido (µ_o na
  pressão de saturação). Se o BOT ou o PVT do campo derem µ de óleo vivo, esse valor tem
  precedência (é entrada de usuário, com a sua fonte).
- Rs vem de Standing (balanço), não de flash pela EOS: o C20+ não tem Tc/Pc/ω
  (`docs/validacao/15-termodinamica.md`).
- Sem correção de Bo: a densidade do óleo segue a padrão do balanço.

## Testes

`tests/pfd/test_fluidos.py` (forma da correlação, redução monotônica, faixa, rastro, SG-001
com o Rs de C-06), `tests/pfd/test_alarmes_contrato.py` (alarme explicado; a variante herda o
modo), `tests/pfd/test_entradas.py` (teto de 3.612 mm preservado no modo óleo morto) e a
paridade F10b/Julia no modo óleo morto.
