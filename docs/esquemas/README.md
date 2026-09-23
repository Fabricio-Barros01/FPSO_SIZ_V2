# Esquemas das saídas do balanço (`fpso-siz balanco`)

`fpso-siz balanco --casos <arquivo.json> --saida <pasta>` grava dois arquivos em `<pasta>`.
Ambos são UTF-8. Os números são floats em `repr` exato, com ponto decimal, e a leitura de
volta dá o mesmo valor bit a bit.

## `balanco.json`
Validado por [`balanco.schema.json`](balanco.schema.json) (JSON Schema 2020-12). Conteúdo:

- `entrada`: nome e SHA-256 do arquivo de casos (rastreabilidade).
- `premissas`: cada premissa com id P-xx/F-xx, valor usado, unidade, origem e
  `alterada` (se foi mudada por `--premissa`).
- `casos[]`: para cada caso, convergência do reciclo (`convergiu`, `iteracoes`,
  `residuo_reciclo`), propriedades (`rho`, `cp`, `gas_props`), as 26 `correntes` (T em °C,
  P em kPa abs, vazão mássica O/W/D/G em kg/s), `cargas` (kW), `gas` (Sm³/d; `Dv` em m³/d),
  balanços por bloco e global e o `rastro` (CalcTrace: equação, escopo, valor, entradas;
  catálogo em `src/fpso_siz/config/equacoes_balanco.toml`).
- `auditoria[]`: as verificações independentes, com o maior |desvio| absoluto nos casos
  (catálogo em `src/fpso_siz/config/auditoria.toml`).

## `correntes.csv`
Uma linha por caso × corrente (16 × 26 = 416 linhas no BOT). O cabeçalho usa os ids
abaixo; a ordem e as unidades vêm de `src/fpso_siz/config/saida_correntes.toml`.

| Coluna | Unidade | Descrição |
|---|---|---|
| `caso` | - | Número do caso de projeto (BOT) |
| `corrente` | - | Identificador da corrente no diagrama de blocos (C-01 … C-26) |
| `nome` | - | Descrição da corrente |
| `fase` | - | Fase ou natureza da corrente |
| `T_C` | °C | Temperatura |
| `P_kPa` | kPa abs | Pressão |
| `m_O_kg_s` | kg/s | Vazão mássica de óleo |
| `m_W_kg_s` | kg/s | Vazão mássica de água produzida |
| `m_D_kg_s` | kg/s | Vazão mássica de água de diluição |
| `m_G_kg_s` | kg/s | Vazão mássica de gás |
| `m_total_kg_s` | kg/s | Vazão mássica total |
| `Q_O_m3_d` | m³/d (padrão) | Vazão volumétrica de óleo na condição padrão |
| `Q_W_m3_d` | m³/d (padrão) | Vazão volumétrica de água produzida na condição padrão |
| `Q_D_m3_d` | m³/d (padrão) | Vazão volumétrica de água de diluição na condição padrão |
| `Q_G_Sm3_d` | Sm³/d | Vazão de gás na condição padrão (Z = 1) |

## Saídas de `fpso-siz pfd` (versão 1)

Com `--saida`, grava `TAG.json` para cada um dos 11 equipamentos e `planta.csv`.
Sem `--saida`, não grava arquivos. Todos são UTF-8 e determinísticos para os mesmos
dados, premissas, ajustes, configuração e versões das dependências.

Cada JSON contém:

- `schema_version`, `proveniencia` (arquivo, hash, versões), `tag` (mapeamento declarativo);
- `status`: `aguardando_entrada`, `dimensionado`, `inviavel` ou `inativo`;
- `premissas`, `ajustes`, `descritores`, `limitacoes`, `fontes_propriedades` e
  `blocos_sem_dimensionamento`;
- `lacunas[]`: chave, rótulo, unidade, faixa, dica e números dos casos dependentes;
- `casos[]`: número, nome, atividade/motivo, `valores`, `insumos`, `rastro` e `avisos`;
- cada valor: `valor`, `origem`, `fonte`, `tipo` e `pendente`;
- `envelope`: entrada, resultado, cartão, casos, varredura e rastros do dimensionamento;
  é `null` quando o TAG aguarda entrada ou está inteiramente inativo.

NaN e Inf são `null`. Consulte origem/estado para distinguir uma lacuna de uma grandeza
sem limite finito. `pendente` lista as entradas que impedem o cálculo de um valor.

`planta.csv` tem uma linha por TAG, com as colunas:
`tag,equipamento,x,eixo_x,y,unidade_y,caso_governante,status`. `eixo_x` traz o rótulo e a
unidade da primeira coluna da varredura do método (por exemplo `d (mm)`); `y` usa
`unidade_y`. Valores indisponíveis ficam vazios. A definição de x/y pertence ao método.

Formato dos ajustes, limitações e comparação com os oráculos:
[`../validacao/09-pfd.md`](../validacao/09-pfd.md).
