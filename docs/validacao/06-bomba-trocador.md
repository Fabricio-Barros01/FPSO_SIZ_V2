# 06 — Bomba centrífuga (Moran) e trocador casco-e-tubos (Saari + Bell-Delaware) (F7)

Data: 2026-09-23. **Estado: entregue.**

## Port (FPSO_Siz Julia @ `ab58fc6`)
| Python | Julia | Conteúdo |
|---|---|---|
| `sizing/base.py` | — | `MetodoTOML`: config, rótulo, referência, descritores e corrente reescrita (comum a vasos, bomba e trocador) |
| `sizing/hidraulica.py` | `sizing/pump/hydraulics.jl` | Reynolds, Colebrook-White, regime (laminar/transição/turbulento), Darcy-Weisbach, perdas localizadas, Antoine |
| `sizing/bomba.py` | `sizing/pump/moran.jl` | DN na série da Fig. 3; H = h_est + h_atrito; banda de velocidade, NPSH e validade da correlação **por caso**; menor DN |
| `sizing/bell_delaware.py` | `sizing/exchanger/bell_delaware.jl` | h_ideal·Jc·Jl·Jb·Js·Jr; Tabelas 2-5/2-6/2-7 de Branan |
| `sizing/trocador.py` | `sizing/exchanger/shell_and_tube.jl` | LMTD, F 1-2, Dittus-Boelter, U em série, ε-NTU, ponto fixo L ↔ h_o; tubos por passe; menor área |
| `core/ieee.py` | aritmética IEEE do Julia | `div()`: x/0 = ±Inf, 0/0 = NaN |
| `config/equipment/{pump,exchanger}/*.toml` | idem | **cópia literal** do snapshot |
| `config/equipment/comum/{hidraulica,trocador}.toml` | literais do código Julia | Colebrook (3,7, 2,51, 2), Dittus-Boelter 0,8, Colburn 0,14/1,33, expoente 2/3 do Prandtl, (µ/µw)^0,14, tolerâncias das singularidades removíveis, defaults de iteração |
| `config/equipment/pump/moran_corrente.toml` | `_AJUSTES_BOMBA` | rótulos, defaults e notas da corrente da bomba |

## Paridade com o Julia (`tests/sizing/test_paridade_julia.py`)
Mesma comparação estrutural dos vasos. **O ponto escolhido (x, y, caso governante) é
idêntico bit a bit** nos dois exemplos; cartão, resumo, colunas, blocos, descritores e
constantes também.

| Equipamento | Números que diferem | Desvio máximo | Origem |
|---|---|---|---|
| bomba (DN 250, H = 15,855 m) | 5 | 2,5e-16 | `log10` no Colebrook-White |
| trocador (75 tubos/passe, L = 5,7166 m) | 846 | 4,8e-16 | `pow`/`acos`/`exp`/`cbrt` no Bell-Delaware, propagados pelo laço L ↔ h_o |

São diferenças de 1 a 2 ulp entre a `libm` do Julia e a do sistema. A tolerância de teste
é 1e-13.

## Casos-ouro portados (`tests/sizing/test_golden_bomba_trocador.py`)
- **Moran:**
  - Antoine (Tabela 3, água a 30 °C, e 100 °C ≈ 1 atm);
  - Colebrook-White (satisfaz a própria equação, limites liso e rugoso, monotonicidade, Re
    inválido);
  - regimes, com f = 64/Re no laminar;
  - Figura 3 (25 mm a 1 m/s ≈ 6 m/100 m);
  - k-values da Tabela 1 e potência;
  - o menor DN admissível e o fechamento H = h_est + h_atrito;
  - carga estática negativa;
  - cavitação e transição como diagnóstico;
  - o memorial credita Hagen ou Colebrook conforme o regime.
- **Saari / Branan:**
  - Exemplo 4.1 inteiro, com o erratum da vazão;
  - LMTD ≡ ε-NTU;
  - limites da Eq. 4.6 e do fator F (R = 1 removível, simetria entre correntes);
  - U em série com a razão de áreas;
  - faixa de Dittus-Boelter;
  - Tabelas 2-5, 2-6 e 2-7;
  - Eq. 2-26 com o ângulo inteiro (o fator 2 que a fonte perde) e Eq. 2-24 com o meio
    ângulo;
  - os cinco fatores nas faixas declaradas;
  - Jl nunca amplifica (0,44, e não os 0,044 impressos);
  - Bell-Delaware desligado devolve o h do formulário;
  - área de célula por layout (Eq. 2-13 e 2-14);
  - casco = feixe + 2·d_o, com o teto conferido contra o casco;
  - 9 inviabilidades com mensagem.

## Achado: divisão por zero
No Julia, `x/0` dá `Inf`/`NaN`, que se propaga até uma checagem e vira mensagem. Com
`k_tubo = 0`, por exemplo, o Prandtl dá `Inf` e sai "Prandtl inválido". No Python, a
divisão levanta `ZeroDivisionError`. Foram duas correções:
1. `core/ieee.div` nos pontos em que o Julia depende disso para diagnosticar: Prandtl do
   tubo e do casco, P efetivo do arranjo 1-2 e Antoine com T + C = 0, que dá Pv = 0 como
   no Julia. O estouro de `10^x` volta como `Inf`, como no Julia.
2. **Rede de segurança no motor.** `size_single` e `size_envelope` convertem qualquer
   `ArithmeticError` não previsto em inviabilidade explícita ("Erro numérico no
   cálculo…"), nunca em exceção. Isso preserva o contrato do projeto.

## Invariantes
- Regra de literais: 8 entra como estrutural (área do segmento circular d²/8). As casas
  decimais de apresentação (`digits=`) não são física e ficam fora da regra.
- Todos os coeficientes que o Julia deixava no código estão nos TOMLs comuns.

Testes: 449 (+2 `-m latex`, +1 `-m julia`), cobertura de 98 %.
