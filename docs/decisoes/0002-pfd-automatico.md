# F10 (adiantada) — do balanço ao dimensionamento automático dos 11 TAGs

> **Atualização (2026-09-23, F10c aprovada e entregue).** A F10c deixou de ser "um menu
> Planta" e passou a ser o **fluxo por equipamento/TAG**, com a Planta/PFD como atalho do
> mesmo fluxo (proposta revisada no `SPRINTS.md`). Decidido e implementado:
> - um **serviço por TAG** (`pfd/equipamento.py`) usado pelo TAG isolado, pelo PFD e pelo
>   modo interativo; o balanço é resolvido uma vez por contexto;
> - **dois adaptadores** para o mesmo contrato de entradas: automático (balanço →
>   propriedades → ajustes) e manual (digitado, arquivo ou exemplo), sem consultar o
>   balanço nem o ChEDL; defaults sem fonte nunca completam um campo;
> - **recomendações e defaults com fonte** são confirmados explicitamente (revisão por
>   campo × caso, com valor e fonte); editar vira origem usuário e registra o substituído;
> - **um único `ajustes_pfd.toml` versionado** (esquema 2, com contexto), que lê o legado
>   da F10b; divergência de contexto bloqueia o comando e pede reconciliação no terminal;
> - `fpso-siz dimensionar --tag … [--auto-balanco] --ajustes …`, `--avulso` e `--ascii`.
>
> A seção "F10c — PFD no modo interativo" abaixo é o plano original, mantido como
> histórico. O entregue está em `docs/validacao/10-fluxo-tag.md`.

> **Atualização (2026-09-23, após o estudo de pacotes).** O usuário decidiu usar
> **thermo/chemicals (ChEDL, MIT) como dependência direta de runtime**, atrás da porta única
> `pfd/_chedl.py`. Isso muda a tabela de propriedades abaixo:
> - o Z do gás passa a vir de Peng-Robinson com a composição real, no lugar de
>   Redlich-Kwong;
> - a μ do gás sai do thermo (Brokaw);
> - ρ, μ e cp da salmoura saem de Laliberté (2009);
> - a água de diluição usa IAPWS.
>
> Continuam lacunas: k da salmoura (o banco de Magomedov não tem NaCl), k do óleo, óleo
> vivo e Bo. O estado entregue está em `docs/validacao/08-propriedades.md`. O restante do
> plano (F10b/c, F11) não muda.

> O plano geral F0–F12 continua em `SPRINTS.md`. Este arquivo planeja só a próxima etapa.
> O usuário decidiu **adiantar a F10** (antes do Pinch e do Song) e fazer a F11 (os MCs)
> logo em seguida. Cada subfase abaixo é aprovada separadamente com "aprovado, pode
> implementar".

## Contexto

**Visão do usuário:** o arquivo com os casos 1–16 alimenta o balanço de massa e energia
(que já está pronto e é bit a bit), e o balanço fornece **automaticamente** as entradas do
dimensionamento de cada equipamento. O usuário só informa algo se quiser (input extra).
Quando o balanço preliminar não bastar, o programa detalha mais por conta própria. Esse
detalhamento fica **oculto no balanço**, mas é **exposto no MC do equipamento** como
entrada da modelagem.

**Onde o Julia parou (F1 do PFD, `../FPSO_Siz/docs/validacao/10-pfd-casos-bot.md`):**
existem 11 TOMLs de rascunho, `DRAFT_MISSING_INPUTS`, com `nan` nas lacunas L01–L12. Não há
correlação de propriedade nenhuma: gás com Z = 1 e óleo morto limitado a 70 °C. O
mapeamento TAG → método → correntes já foi decidido lá e será reaproveitado:

| TAG | Método | Correntes |
|---|---|---|
| SG-001 | separador 3F | C-03 → C-04/05/06 |
| V-001 / V-002 | knockout | C-08 / C-16 (na P do vaso: 700 / 200 kPa) |
| TO-001 / TO-002 | tratador | C-10 / C-18 |
| P-001 | trocador | tubo C-06→07, casco C-22→23 |
| P-002 / P-003 | trocador | tubo C-07→08 / C-23→24; casco = utilidade |
| B-001 / B-002 / B-003 | bomba | C-21→22 / C-12→13 / C-19→20 |

Os blocos M-0x, MED-001 e DWH-001 ficam sem dimensionamento, e isso é listado.

**Decisões do usuário (2026-09-23):**
- **Ordem:** adiantar a F10.
- **Propriedades:** correlações clássicas, com coeficientes e fontes em TOML e rastro no MC.
  Restrição posterior do usuário: **só o que tem fonte no acervo**; o resto não é suposto.
- **Lacunas:** premissa por TAG, com **valor recomendado apresentado na CLI** e só o
  **mínimo necessário** perguntado.
- **Input extra:** no **modo interativo**.

## Arquitetura

O pacote novo `src/fpso_siz/pfd/` é núcleo: não imprime e não formata.

```
pfd/fluidos.py    correlações puras, cada uma anota um Rastro (bloco "propriedades")
pfd/tags.py       carrega config/pfd/<tag>.toml (equipamento, método, correntes, regras, premissas)
pfd/entradas.py   ResultadoCaso[16] + premissas do TAG + ajustes → CaseSet por TAG,
                  com a ORIGEM de cada valor (balanço Cxx | correlação | premissa recomendada |
                  default do método | usuário) e o rastro das propriedades por caso
pfd/planta.py     roda os 11 envelopes (reusa core.motor.size_envelope) → ResultadoPlanta
config/fluidos.toml   coeficientes das correlações + fonte
config/pfd/*.toml     um arquivo por TAG (declarativo; a interface só itera)
```

Pontos reaproveitados:
- `balanco.modelo.resolver_todos` / `ResultadoCaso`: `streams`, `T`, `P`, `rho`, `cp`, `gp`
  (`y`, `MW`, `gamma`), `vol()`, `C()`.
- `balanco.propriedades`: `standing_rs`, `mu_interp` (a tabela do poço), `poco_do_fluido`.
- `balanco.indicadores.q_real_gas`.
- `core.casos.Case/CaseSet`, `core.motor.size_envelope`, `core.registro.resolver`.
- `output/dimensionamento.py` (JSON/CSV) e `output/terminal/*` (tabelas, sessão).

**O balanço não muda.** O detalhamento é uma camada a jusante, então a paridade bit a bit
e o memorial do balanço ficam intactos (regra "refatoração não muda número").

### Detalhamento oculto — só o que tem fonte no acervo

**Regra do usuário (2026-09-23): "para as referências sem fonte não suponha nada, complete
o que é possível".** Fiz uma varredura do texto de todos os PDFs de `references/`. O
resultado:
- Entra só o que tem fonte **no acervo**: equação ou tabela citável, ou uma premissa já
  documentada do balanço.
- O que não tem fonte vira **lacuna de entrada**, sem valor recomendado. O usuário
  informa no modo interativo; sem essa entrada o TAG fica "aguardando entrada" e não é
  dimensionado.
- Nenhum número é digitado de memória. Na F10a, cada item marcado ✓ é conferido no PDF
  antes de ir para o código.

| Grandeza (condição do equipamento) | Tratamento | Fonte no acervo |
|---|---|---|
| Vazões, ṁ, cp, T, P das correntes | direto do balanço | balanço (bit a bit) |
| Pressão de sucção e de recalque da bomba | P do vaso a montante; P da corrente de descarga | balanço |
| Pv na sucção da bomba | líquido saturado no vaso: Pv = P do vaso, NPSHa = elevação − atrito | ✓ Branan cap. 5, Ex. 5-2 ("liquid at boiling point") |
| Z e ρ do gás | Redlich-Kwong (eqs. 27-10/27-11), ρ = P·MW/(Z·R·T) | ✓ Branan cap. 27. Tc/Pc dos componentes: S&A Tab. 1.2. A regra de mistura das pseudocríticas **precisa ser achada no acervo na F10a**; se não houver, fica o Z = 1 da premissa P-39 do balanço, sinalizado |
| μ do óleo | tabela de óleo morto do poço; acima de 70 °C vale o extremo, como no balanço | ✓ BOT Tab. 2.2.1.2 + premissa P-40. Sem correção de óleo vivo (Beggs-Robinson e Bo não estão no acervo; a limitação é declarada) |
| ρ do óleo | API do poço, na condição padrão | ✓ balanço (API, P-07). Sem correção por T e Bo (sem fonte) |
| μ de emulsão (bombas, trocadores, BOT nota 1: "pressure loss due to emulsified oil viscosity") | Zanker, eq. 27-4, com a faixa de validade verificada | ✓ Branan cap. 27 |
| ρ da água | premissa rho_W (salmoura) | ✓ balanço P-08 |
| **μ da água** | **lacuna, entrada do usuário** | sem fonte (IAPWS citada no Branan só como planilha VBA) |
| **μ do gás** | **lacuna, entrada do usuário**; o MC aponta S&A Fig. 1.9 (GPSA) para leitura | só gráfico |
| **k (condutividade) nos trocadores** | **lacuna, entrada do usuário** | sem fonte |
| Tempo de retenção, knockout | recomendado 5 min, porque os fluidos têm alto CO₂ | ✓ S&A Tab. 3.2 e nota ("high CO2: minimum 5-min") |
| Tempo de retenção, trifásico e tratador | óleo pela API; água 10 min | ✓ S&A Tab. 4.1 e §4 ("10 min recommended") |
| Gotículas, grade, esbeltez | default do método, com a fonte citada | ✓ S&A / Alves-Komesu (TOMLs do método) |
| **Gotícula pós-coalescência do tratador** | **lacuna**, salvo se a F10a achar a fonte | a confirmar |
| Rendimento da bomba | premissa eta_pump | ✓ balanço P-22 |
| **Geometria da linha da bomba** (desnível, comprimentos, Σk, nível de sucção) e **NPSHr** | **lacuna, entrada do usuário** | sem fonte (projeto) |
| Utilidade do P-002 (água quente) | **T de entrada e de saída: lacuna**; o limite de 120 °C é verificado; a vazão sai de Q/(cp·ΔT) | ✓ BOT 2.7.1.4 e 2.7.3.7.16 (limite e meio) |
| Utilidade do P-003 (água de resfriamento, circuito fechado) | **T de entrada e de saída: lacuna** | BOT 3.3.2 (meio); temperaturas no METOCEAN, que não está no acervo |
| Geometria de Bell-Delaware | default do método (exemplo de Saari), marcado "a confirmar" | ✓ Saari |

- Cada função recebe (P, T, dados do caso), devolve o valor e anota o rastro (bloco
  "propriedades") com equação, variáveis e **fonte**.
- JSON, terminal e MC (F11) saem desse rastro.
- As lacunas ficam listadas por TAG, com a unidade e, quando houver, a figura do acervo que
  ajuda a estimar o valor.

### Mapeamento e lacunas (`config/pfd/<tag>.toml`)

`[entradas]` declara uma regra por chave, de um vocabulário fixo em `pfd/entradas.py`:
`vazao_oleo_real`, `vazao_agua`, `vazao_gas_real`, `rho_gas_real`, `mu_oleo_vivo`,
`pressao_da_corrente`, `vazao_massica`, `cp_da_corrente` etc., cada uma com a corrente de
origem.

As entradas que o balanço não resolve ficam em `[premissas.<chave>]`, de um de dois tipos:
- **recomendada:** tem `valor` e `fonte` do acervo. O modo interativo pergunta só se
  `perguntar = true`, com o valor já no padrão [Enter aceita]. É o caso dos tempos de
  retenção.
- **lacuna:** sem valor e sem fonte. É **sempre perguntada** e só aceita número dentro da
  faixa do descritor. Sem ela o TAG fica "aguardando entrada".

O **mínimo necessário** é exatamente o conjunto de lacunas da tabela acima, mais as
recomendadas que mais pesam no resultado (os tempos de retenção). Todo o resto usa o
recomendado ou o default do método e aparece listado no MC.

**Casos sem vazão no TAG** (L06: B-002/B-003 sem água nos casos 1 e 4–7) ficam inativos
nesse TAG, com o motivo informado e nunca com uma vazão mínima fictícia.

**Faixas de descritor excedidas** (L07: salmoura a 1154 kg/m³ contra o máximo de 1050)
são tratadas com um override de faixa em `*_corrente.toml`, com justificativa. O TOML do
Julia não é alterado.

**NPSH das bombas.** O líquido sai saturado do vaso a montante, então Pv = P do vaso
(Branan, Ex. 5-2). Para isso a bomba ganha uma entrada opcional `pv_informada`: `nan` usa
Antoine. As fixtures do Julia seguem idênticas, com teste que garante isso.

## Subfases (cada uma aprovada separadamente)

### F10a — Propriedades na condição real
- Entregas: `pfd/fluidos.py`, `config/fluidos.toml`, `tests/pfd/test_fluidos.py`.
- **Aceite:**
  - cada correlação reproduz um exemplo numérico publicado na sua fonte, dentro da
    tolerância citada;
  - limites físicos: Z → 1 quando P → 0; Walther passa pelos pontos da tabela do poço;
    Bo = 1 com Rs = 0; μ_emulsão = μ_óleo com BSW = 0;
  - invariante 2 (literais em TOML) e cobertura ≥ 90 %.
- **Escopo:** só as linhas ✓ da tabela. Cada coeficiente e cada Tc/Pc é conferido no PDF
  e citado com página e equação no TOML.
- Se a regra de pseudocríticas não estiver no acervo, o Z fica em 1 (P-39), sinalizado.
- Se o usuário acrescentar PDFs ao `references/` depois (McCain, Lee-Gonzalez-Eakin,
  Beggs-Robinson, METOCEAN), as lacunas correspondentes viram correlação numa fase
  seguinte, sem mudar a arquitetura.

### F10b — Mapeamento balanço → TAG e `fpso-siz pfd`
- Entregas: `pfd/{tags,entradas,planta}.py`, os 11 `config/pfd/*.toml`, os ajustes da
  bomba (`pv_informada`) e da faixa de descritor, e o subcomando
  `fpso-siz pfd --casos X [--saida D] [--ajustes A.toml]`.
- Saídas: um JSON por TAG com entradas, origem, rastro de propriedades e envelope, mais
  `planta.csv` (TAG, equipamento, x, y, caso governante, status).
- **Oráculo cruzado:** copiar o `manifesto.json` e os 11 TOMLs do PFD F1 do Julia para
  `tests/fixtures/julia/pfd/` (só leitura). Todo valor que o Julia derivou do balanço
  (vazões padrão, ṁ, cp, T, P e ρ_gás com Z = 1 como função auxiliar) tem de sair igual,
  bit a bit.
- **Aceite:**
  - sem lacunas preenchidas, cada TAG sai como "aguardando entrada" com a lista exata do
    que falta;
  - com um arquivo de ajustes de teste que preenche as lacunas, os 11 envelopes são
    calculados, cada um com caso governante;
  - toda entrada tem origem registrada (balanço, correlação com fonte, recomendada com
    fonte, default do método ou usuário), e nenhuma vem de valor sem fonte;
  - invariante 4: a CLI itera `config/pfd` e as regras;
  - cobertura ≥ 90 %.

### F10c — PFD no modo interativo (plano original; substituído, ver a atualização no topo)
Novo item de menu: **"Planta: dimensionar os equipamentos a partir do balanço"**.
1. Roda o balanço com as premissas da sessão e deriva as entradas dos 11 TAGs.
2. **Entradas mínimas, agrupadas por TAG:**
   - **lacunas:** sem padrão; pede o valor com unidade e faixa e cita a figura do acervo
     quando houver (p.ex. S&A Fig. 1.9 para μ do gás). Um valor dado para um TAG pode ser
     aplicado a todos os casos ou a um caso específico.
   - **recomendadas:** mostra valor e fonte, e Enter aceita. Há a opção "aceitar todas as
     recomendadas".
   - Os TAGs com lacuna em aberto aparecem como "aguardando entrada".
3. Dimensiona os 11 TAGs e mostra uma tabela-resumo: TAG, equipamento, resultado
   principal, caso governante e ✓/✗.
4. Detalhe de um TAG: entradas por caso com a coluna **Origem**, cartão, varredura e o
   rastro, incluindo o bloco de propriedades. Dá para **editar uma entrada** (input
   extra) e redimensionar.
5. Exportar: grava os JSONs, `planta.csv` e `ajustes_pfd.toml` (o que o usuário mudou) e
   mostra o comando `fpso-siz pfd --casos … --ajustes …`. O teste confere que esse
   comando grava os mesmos bytes.

- **Aceite:** sessões roteirizadas; aceitar recomendações; editar e redimensionar;
  exportar reproduzível; cobertura ≥ 90 %.

### F11 — MC LaTeX por TAG (logo em seguida)
Um memorial A4 por TAG, com o pipeline da F4 (jinja2):
- as entradas com a origem de cada valor;
- **o detalhamento de propriedades exposto** (equações, fontes, valores por caso);
- as premissas recomendadas, marcadas "a confirmar" quando não foram revisadas;
- o envelope e o rastro do método.

É o lugar onde o que ficou oculto no balanço vira documentação. **Aceite:** compila; há
bijeção rastro ↔ MC.

## Arquivos críticos
- **Novos:**
  - `src/fpso_siz/pfd/{__init__,fluidos,tags,entradas,planta}.py`
  - `src/fpso_siz/config/fluidos.toml`, `src/fpso_siz/config/pfd/*.toml`
  - `tests/pfd/`, `tests/fixtures/julia/pfd/`
  - `docs/validacao/08-propriedades.md`, `09-pfd.md`
- **Alterados:**
  - `sizing/bomba.py` (`pv_informada`, com paridade preservada)
  - `config/equipment/*/*_corrente.toml` (faixas)
  - `cli.py` (`pfd`), `output/terminal/{sessao,relatorio}.py`, `config/interativo.toml`
  - `tests/arquitetura/test_invariantes.py` (o pacote `pfd/` entra nas regras de literais
    e de impressão)
  - `SPRINTS.md` (reordenar: F10a/b/c ← ATUAL, F11, depois F8/F9)

## Verificação
- `uv run pytest --cov=fpso_siz --cov-fail-under=90`: a paridade do balanço e do Julia
  continua verde.
- `uv run fpso-siz pfd --casos tests/fixtures/python_ref/design_cases_bot.json --saida /tmp/x`:
  mostra 11 envelopes e as lacunas listadas.
- Sessão real: `uv run fpso-siz` → Planta → aceitar recomendações → detalhe de um TAG →
  exportar → rodar o comando impresso e comparar os bytes.
- F11: `uv run pytest -m latex` compila os MCs por TAG.
