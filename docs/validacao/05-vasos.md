# 05 — Vasos: separador trifásico, knockout, tratador eletrostático (F6)

Data: 2026-09-23. **Estado: entregue.**

## Port (FPSO_Siz Julia @ `ab58fc6`)
| Python | Julia | Conteúdo |
|---|---|---|
| `sizing/vasos.py` | `sizing/constraints.jl` | `VesselConstraints`, `PhaseLayer`, `MetodoVaso`: grade, exigência max(gás, líquido), teto, Lss/SR/volume, banda de esbeltez, `envelope_params` (grade-união × banda-interseção), mensagens, cartão, colunas, blocos, rastro da seleção, seção transversal |
| `sizing/capacidade_gas.py` | `sizing/gas_capacity.jl` | bloco A, o mesmo nos vasos (Eq. 14 ≡ Eq. 3.8b), numeração citada por método |
| `sizing/arrasto.py` | `sizing/separator/drag.jl` | C_D sub-relaxado, V_t, Re, Souders-Brown |
| `sizing/beta.py` | `sizing/separator/beta.jl` | segmento circular por bisseção: β (vaso meio cheio), h/d (vaso cheio), Eq. 18 |
| `sizing/separador.py` | `sizing/separator/stewart_arnold.jl` | blocos A, B, C; variante geométrica "Eq. 21*" só registrada |
| `sizing/knockout.py` | `sizing/knockout/two_phase.jl` | A + C, sem teto; Lss = maior dos dois (livro); fase líquida reetiquetada |
| `sizing/tratador.py` | `sizing/treater/electrostatic.jl` | vaso cheio (α = 1), sem bloco A; ganho do campo (d_m/500)² |
| `core/grade.py` | `collect(a:passo:b)` | a grade de diâmetros nos MESMOS floats do Julia (`rat` + caminho racional) |
| `core/corrente.field_units` | `field_units` | único ponto SI → unidades de campo |
| `config/equipment/{separator,knockout,treater}/*.toml` | idem | **cópia literal** do snapshot |
| `config/equipment/comum/stewart_arnold.toml` | literais de `drag.jl`/`beta.jl` | coeficientes do arrasto e passos da bisseção, agora dados (invariante 2) |
| `config/equipment/*/*_corrente.toml` | `_ROTULOS_LIQUIDO`, `_AJUSTES_TRATADOR` | rótulos, defaults e notas que o método reescreve na corrente |

## Paridade com o Julia (`tests/sizing/test_paridade_julia.py`)
Comparação estrutural de **tudo** que as fixtures guardam: envelope, varredura, folgas,
casos individuais com varredura e rastro (bloco, equação, variável, fórmula, valor,
unidade), cartão de resultados, resumo de governança, colunas, blocos do memorial,
descritores (inclusive os reetiquetados), constantes e rótulos.

| Vaso | Resultado |
|---|---|
| knockout-2f | **idêntico bit a bit** |
| vaso-eletrostatico | **idêntico bit a bit** |
| separador-3f | idêntico, exceto 11 números da cadeia de β, com desvio máximo de **1,25e-15** relativo |

A diferença do separador é de `libm`: β sai de uma bisseção sobre `acos`, e o `acos` do
Julia (openlibm) e o do sistema divergem no último ulp em alguns argumentos. A tolerância
do teste para o separador é 1e-13, com folga de duas ordens de grandeza sobre o medido.

A grade do knockout do livro (passo 6 × 25,4 = 152,39999999999998) só sai igual com o
algoritmo de faixa do Julia; as 8 faixas de `tests/core/test_grade.py` foram conferidas
no Julia 1.12.6.

## Casos-ouro portados (`tests/sizing/test_golden.py`)
- **Alves & Komesu (2025):**
  - Tabela 3 (6 diâmetros, ≤ 0,5 %) e Tabela 2 (o gás não governa);
  - teto não restritivo e Tabela 4 (5500 mm admissível), com desvio < 10 % do vaso
    instalado;
  - o 4,12×10⁴ impresso seria reprovado;
  - equações citadas no memorial;
  - a variante geométrica da Eq. 21 é registrada e não decide; sem água livre, ela é
    omitida.
- **Stewart & Arnold, Exemplo 3.2 (knockout):**
  - sem teto;
  - C_D ≈ 0,851;
  - Tabela 3.4, com o erratum 39,85 × 55,04 in·ft;
  - 34,5 × equivalente exato do 420 (+0,87 %);
  - bloco de gás idêntico ao trifásico, com numeração própria;
  - Lss = maior dos dois;
  - envelope multi-caso.
- **Tratador:**
  - coeficiente 0,033 (e não 0,0033) e 1320 (e não 1520);
  - retenção 21000 ≈ C_meio-cheio/2;
  - Eq. 4.17 exata e simétrica;
  - sem bloco de gás, vaso cheio e β > 0,5;
  - o campo elétrico é operativo: sem coalescência, o teto cai 4×;
  - inviabilidades com mensagem.
- **β e arrasto:** Figura 3, Eq. 18, os dois regimes de C_D, ponto fixo, relaxação e não
  convergência como mensagem.

## Decisões e divergências mantidas (idênticas ao Julia)
1. **Eq. 22:** 4,2152×10⁴ (forma de campo) no lugar do 4,12×10⁴ impresso.
2. **µ_g da Tabela 1:** 0,6 cP é viscosidade de líquido; µ_g é entrada explícita.
3. **Eq. 21:** segue o texto publicado (divide por β). A variante geométrica, 0,5 − β, é
   emitida no rastro como `Eq. 21*` e não decide.
4. **Lss:** do bloco que governa no separador (artigo); o maior dos dois no knockout e no
   tratador (livro).

## Invariantes
- A regra de literais passou a admitir 0,5 (vaso meio cheio, média) e 4 (área πd²/4,
  casas decimais), além de {0, 1, 2, 10}. Coeficientes empíricos continuam proibidos no
  código.
- `core/grade.py` fica isento da regra, como `formato_julia.py`: ambos emulam regras de
  representação numérica do Julia, não física.

Cobertura do pacote: 98,5 % (364 testes).
