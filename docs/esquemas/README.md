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
