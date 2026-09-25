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

## Saídas por TAG e da planta (esquema 2, F10c)

`fpso-siz pfd --saida D` grava, para cada um dos 11 TAGs, `TAG.json` e
`TAG_varredura.csv`, e mais `planta.csv`. `fpso-siz dimensionar --tag T --saida D` (e a
exportação do TAG no modo interativo) grava os mesmos dois arquivos daquele TAG, **com os
mesmos bytes** para o mesmo contexto e os mesmos ajustes; o estado dos outros TAGs não
entra no artefato. `dimensionar --avulso A` grava `A.json` e `A_varredura.csv`. Sem
`--saida`, nada é gravado. UTF-8, determinísticos para os mesmos dados, premissas,
ajustes, configuração e versões das dependências.

Cada JSON contém:

- `schema_version` (2), `proveniencia` (arquivo e hash do BOT — `null` no avulso —,
  versões), `tag` (descritor; no avulso, `bloco` vazio), `avulso`, `modo`
  (`automatico`/`manual`);
- `status`: `aguardando_entrada`, `dimensionado`, `inviavel` ou `inativo`; `preliminar`:
  há recomendação/default sem revisão nos casos ativos (não é um estado);
- `premissas` (`null` no avulso), `ajustes` (a forma canônica do estado do TAG, a mesma do
  arquivo de ajustes), `descritores`, `limitacoes`, `fontes_propriedades` e
  `blocos_sem_dimensionamento`;
- `lacunas[]`: chave, rótulo, unidade, faixa, dica, casos dependentes e `dependentes`
  (entradas que só se calculam com ela);
- `revisoes[]`: recomendações/defaults em aberto — chave, valor, fonte, origem, tipo,
  `estado` (`pendente`/`desatualizada`) e casos;
- `casos[]`: número, nome, atividade/motivo, `valores`, `insumos`, `rastro` e `avisos`;
- cada valor: `valor`, `origem` (balanco, propriedade, premissa, recomendada, metodo,
  usuario, arquivo, lacuna, nao_aplicavel), `fonte`, `tipo`, `pendente`, `faixa` (`[mín, máx]` quando a
  entrada é uma faixa, com `valor` nulo), `revisao` (`""`, `pendente`, `confirmada`,
  `desatualizada`) e `anterior` (o que a entrada do usuário substituiu: origem, fonte e
  valor; `null` se não houver registro);
- `envelope`: entrada, resultado, cartão, casos, varredura e rastros; `null` quando o TAG
  aguarda entrada ou está inteiramente inativo.
- `nao_aplicavel` (F10v, premissa P-42): num caso sem vazão de água e com óleo, as entradas
  usadas só pelos critérios da fase aquosa do separador e do tratador (`dm_water`, `dm_oil`,
  `tr_water`, e `rho_water`/`mu_water` quando não vêm do balanço) têm `valor` nulo, `fonte`
  citando a P-42, sem `pendente` nem `revisao`. O `mecanismo_teto` do caso é
  `sem_fase_aquosa` (teto infinito, que não governa o envelope). A lista está em
  `config/pfd/metodos.toml [<método>.fase_aquosa]`.

NaN e Inf são `null`. `TAG_varredura.csv` tem as colunas da varredura do método e
`governante,caso_governante,admissivel` (só o cabeçalho quando não há envelope).
`planta.csv` tem uma linha por TAG: `tag,equipamento,x,eixo_x,y,unidade_y,caso_governante,status`.

Mudança do esquema 1 (F10b) para o 2: acrescentados `avulso`, `modo`, `preliminar`,
`revisoes`, os campos `faixa`/`revisao`/`anterior` dos valores e `dependentes` das
lacunas; `ajustes` passou a ser a forma canônica do estado; o CSV de varredura por TAG é
novo. Nenhum valor numérico mudou (ver `docs/validacao/10-fluxo-tag.md`).

## Arquivo de ajustes `ajustes_pfd.toml` (esquema 2)

Estado único da sessão, lido por `pfd --ajustes`, `dimensionar --tag/--avulso --ajustes` e
`interativo --ajustes`, e gravado pela sessão (Exportar ou Abrir/salvar ajustes). Escrita
determinística: TAGs na ordem do catálogo, avulsos por nome, chaves na ordem do método,
floats em `repr` (ida e volta exata), sem data, hora nem caminho de saída.

```toml
[contexto]
esquema = 2
casos_arquivo = "design_cases_bot.json"   # nome, sem pasta
casos_sha256 = "ca3dfe55…"
casos = [1, 2, 3]                          # números dos casos do BOT
fpso_siz = "0.1.0"
configuracao = "…"                         # SHA-256 dos TOML do modelo (sem os de tela)

[contexto.premissas]                       # só as alteradas (--premissa)
eta_pump = 0.8

[contexto.propriedades]                    # versões do ChEDL
chemicals = "1.5.2"
thermo = "0.6.1"

[tag."TO-001"]
modo = "automatico"                        # ou "manual"
equipamento = "treater"
metodo = "arnold_electrostatic"

[tag."TO-001".entradas]                    # usuário, todos os casos
dm_water = 800.0

[tag."TO-001".caso."3".entradas]           # usuário, só o caso 3 (prevalece)
tr_oil = 25.0

[[tag."TO-001".revisao]]                   # confirmação: campo × casos, valor e fonte
chave = "tr_water"
casos = [1, 2, 3]
valor = 10.0
fonte = "Stewart & Arnold (2008) §4.7.4: …"

[[tag."TO-001".substituido]]               # o que a entrada do usuário substituiu
chave = "tr_oil"
casos = [3]
origem = "recomendada"
fonte = "Stewart & Arnold (2008) Tab. 4.1: …"
valor = 20.0

[tag."V-001"]
modo = "manual"
equipamento = "knockout"
metodo = "stewart_arnold_2f"
arquivo = "casos_bot_1_a_16_v_001.toml"    # origem dos importados

[tag."V-001".caso."5"]
inativo = "parada programada"              # atividade: só no manual

[tag."V-001".caso."5".importados]          # valores do arquivo, por caso (ou [tag."X".importados])
q_oil = 1192.53

[avulso.ko]
modo = "manual"
equipamento = "knockout"
metodo = "stewart_arnold_2f"
arquivo = "exemplo:knockout"
casos = ["Exemplo 3.2 — projeto"]          # nomes; o número é a posição

[avulso.ko.caso."1".importados]
q_oil = 13.2489
```

Valores: número; `[mín, máx]` só no modo manual/avulso. Caso prevalece sobre geral;
usuário prevalece sobre importado. Revisões e substituídos agrupam os casos com os mesmos
campos. Chave que o método não declara, caso inexistente, modo inválido, atividade no
automático ou avulso com nome de TAG são erro de entrada (código 2).

**Contexto.** Divergência de `casos_sha256`, `casos`, `premissas` ou do método de um TAG
bloqueia o comando ("erro de contexto", código 2; nada é reaplicado) e pede reconciliação
explícita no interativo. `fpso_siz`, `configuracao` e `propriedades` só geram aviso: os
valores são recalculados e revisões cujo valor/fonte mudou voltam a pendentes.
`--avulso` não confere o BOT nem as premissas (o avulso não os usa).

**Migração do legado F10b.** O leitor aceita o formato da F10b (`["TAG"]` com entradas e
`["TAG".caso."n"]`) como ajustes automáticos, sem contexto nem revisões registrados; com
`--tag`, o legado implica o modo automático. O escritor sempre grava o esquema 2 (abrir e
salvar pela sessão faz a migração).

Formato dos ajustes da F10b, limitações da modelagem e comparação com os oráculos:
[`../validacao/09-pfd.md`](../validacao/09-pfd.md); fluxo por TAG e reprodução:
[`../validacao/10-fluxo-tag.md`](../validacao/10-fluxo-tag.md).
