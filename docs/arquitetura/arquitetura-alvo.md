# Arquitetura alvo

Uma implementação produtiva por responsabilidade; comparações e estudos ficam fora do
caminho, em `tools/`, chamando a mesma API. Inventário que motivou cada decisão:
[`inventario.md`](inventario.md).

## Caminho produtivo

```
CasoProjeto (arquivo do BOT + premissas)
    │  balanco/dados.py
    ▼
ModeloProcesso            balanco/modelo.py   resolver_caso / resolver_todos
    │  correlações de processo: balanco/propriedades.py (Standing, tabelas do BOT, splits)
    │  trem SG-001 → V-001 → V-002: balanco/trem.py (parte do estado, avaliado sob demanda)
    ▼
EstadoProcesso            balanco/estado.py   correntes, T, P, cargas, potências, FWKO,
    │                                         composição, proveniência, rastro, trem
    ▼
Entradas dos TAGs         pfd/entradas.py     lê o EstadoProcesso; propriedades pela API de termo/
    │  termo/servico.py   API única: propriedades de fase e flash_tp / flash_poco
    │  termo/backend.py   única porta do ChEDL
    ▼
Dimensionamento           pfd/equipamento.py → core/motor.py → sizing/*
    ▼
Objetivos e restrições    pfd/otimizacao.py   (mesmo Contexto, mesmo resolvedor, mesma planta)
    ▼
Otimização                _otim.py            (porta única do pymoo)
    ▼
Output / Memorial         output/*, pfd/memorial.py   só LEEM o que o motor e o processo produziram
    ▼
Gate                      tools/auditar_saida_pfd.py
```

Fora do caminho, lendo o mesmo estado: `pfd/pinch.py` (rede do pré-aquecedor), `pfd/investigacao.py`
(variantes dos alarmes, disparadas só por ferramenta), `tools/*`.

## Dependências permitidas

```
core ← termo ← balanco ← pfd ← output ← cli
          ↑       ↑        ↑
        sizing ───┴────────┘        (sizing depende só de core; pfd liga sizing ao processo)
tools → API pública de qualquer camada; nada de src/ importa tools/
```

- só `termo/backend.py` importa `thermo`/`chemicals`; fora de `termo/`, só `termo/servico.py`
  (e `termo/proveniencia.py`) são importados;
- `sizing/` não importa `balanco/`, `pfd/` nem `termo/`: recebe entradas prontas;
- `output/` e `pfd/memorial.py` não chamam `sizing_constraints` nem hooks de física: leem o
  resultado do motor.

## Contratos públicos que sobrevivem

### Processo — `balanco/modelo.py`, `balanco/estado.py`

```python
resolver_caso(caso, dados, prem=None) -> EstadoProcesso
resolver_todos(dados, prem=None) -> list[EstadoProcesso]
```

`EstadoProcesso` é o **único** estado oficial. Campos: `streams` (kg/s por componente O/W/D/G),
`T`, `P`, `duties` (cargas e potências), `gas` (vazão de gás por estágio), `rho`, `cp`, `gp`
(propriedades do gás do corte leve), `fwko` (regra de eficiência, η), `composicao` (z₀ do
fluido, z_base do BOT), `mws_plus`, `trace` (rastro das equações), `proveniencia` (o que o
balanço consumiu naquele caso, por propriedade), `trem` (a recombinação da Nota 4 e a cascata
SG-001 → V-001 → V-002, resolvidas dentro do balanço; ou o motivo de o caso não ser avaliável) e
`gas_padrao` (Sm³/d do gás de cada corrente no caso avaliável; `q(corrente, componente)` lê). Há **uma** regra de FWKO — a de eficiência (P-43); a regra do script de
referência saiu com o seu oráculo.

### Trem de separação — `balanco/trem.py`

`z_base --Nota 4--> z_caso → SG-001 → x_F → V-001 → x₁ → V-002 → x₂`, com `ṅ_V = β·ṅ_F` e
`ṅ_L = (1−β)·ṅ_F`. A composição e a base molar do caso vêm da recombinação da Nota 4 na
referência do FWKO (premissa de modelagem, `docs/validacao/38`): reproduzem o `produced_gas_sm3d`
no FWKO e o `oil_sm3d` de óleo morto. Fechamento:

- `FechamentoTrem.ok` exige o trem **completo** (os três estágios) **e** o fechamento global e
  por componente;
- `FechamentoTrem.ok_parcial` cobre só os estágios executados.

**O trem é produtivo nos casos termodinamicamente avaliáveis** (sem gás de lift): o gás de cada
estágio que o balanço e o dimensionamento consomem é o do flash (β, y, x, MW_v, Z_v, ρ_v), e a
proveniência de cada caso diz isso (`docs/validacao/39`). Nos casos com gás de lift (9, 11, 15,
16) a composição do lift não existe na fonte: eles são "não avaliáveis termodinamicamente para
integração completa" e seguem no envelope do BOT por Standing. É um caminho só, com a classe do
caso como dado — não dois modelos.

### Termodinâmica — `termo/servico.py`

Uma API pública:

```python
flash_tp(T, P, z, fluido) -> EstadoTermodinamico
flash_poco(T, P, z, mws_plus) -> EstadoTermodinamico
mw_mistura(z, mws_plus) -> float
pressao_bolha(T, z, mws_plus) -> float          # leitura do mesmo flash (TVP, diagnóstico)
conferir(estado) -> Fechamento
gas(...), gas_cp(...), agua(...), agua_saturada(...), salmoura_fracao(...), fracao_sal(...),
oleo(...), oleo_vivo(...), emulsao(...), pressao_vapor_saturado(...), versoes()
```

`Fechamento.ok` inclui a coerência molar × mássica (é invariante, não diagnóstico).

### Proveniência — `termo/proveniencia.py` + `config/termo/proveniencia.toml`

Dois conceitos **independentes**:

- `validade`: `validada` | `nao_validada` | `ausente`;
- `origem`: `BOT` | `Standing` | `BeggsRobinson` | `PengRobinson` | `IAPWS` | `Laliberte` |
  `premissa` | outra declarada.

Cada propriedade declara origem, validade e **consumidores reais**. Propriedade com
`consumidores = []` é diagnóstico: existe, tem validade declarada, e ninguém a consome.
`EstadoProcesso.proveniencia` e cada entrada de TAG derivada de propriedade (`Valor.propriedade`)
apontam para o contrato; a proveniência nunca diz que um valor veio do flash se o cálculo usou
outra origem.

### Dimensionamento — `core/contrato.py`, `core/motor.py`

Inalterado no que decide o equipamento. Acréscimos estruturados:

- `campos_nao_aplicaveis(r)` (já existe) e `mecanismos_nao_aplicaveis()`: o método declara, por
  **código**, os mecanismos que tornam um critério não aplicável a um caso — o gate lê o código,
  nunca o texto do rótulo;
- `EnvelopeResult` guarda a preparação de cada caso (`preparo`: entrada, restrições, parâmetros),
  os parâmetros do envelope (`p_env`, `pcs`) e o método; `core/memoria.py` calcula a partir disso
  o que o memorial mostra (governante por caso, bordas, perfil T × Q, parcelas de 1/U, curva do
  sistema, feixe mais próximo), e a saída só lê.

### Contexto — `pfd/equipamento.py`

`Contexto(dados, prem=None, alteracoes=None, balanco=None, propostas=None)`. Sem `oleo_vivo`,
sem `topologia_julia`. As propostas ficam: são capacidade de produto (preencher lacunas com
valor proposto, ou deixá-las abertas), não compatibilidade.

### Otimização

`vetor x → premissas/ajustes → Contexto → resolver_todos → planta → objetivos/restrições`. Uma
variável é uma entrada de `config/pfd/otimizacao.toml`. `P_D1`/`P_D2` entram com
`destino = "premissa"` e uma faixa com fonte — configuração, não reescrita; o trem as lê do
estado (`P` das correntes C-09 e C-17).

## Regressões que ficam

- `regressao_eficiencia.json` — o balanço produtivo;
- `tests/fixtures/julia/*.json` — os métodos de equipamento (sem modo nenhum);
- `golden_pelicula_tubo.json` — a película do lado tubo (caso-ouro independente);
- instantâneo bit a bit da planta produtiva (11 TAGs) — critério de toda mudança;
- o gate de sanidade.
