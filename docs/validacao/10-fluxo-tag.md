# F10c — fluxo por equipamento/TAG no terminal; PFD como atalho

Aprovada em 2026-09-23 ("execute o SPRINTS de onde parou; implemente as alterações feitas
nas documentações"). A aprovação cobre só a F10c: nenhuma revisão de física e nada da F11.
A unidade de trabalho passa a ser **um equipamento/TAG**; a Planta/PFD é o atalho que
percorre o mesmo fluxo para os 11 TAGs. Tudo continua no terminal (`fpso-siz`), sem
dependências novas.

## Uso

```sh
uv run fpso-siz                                   # interativo (num terminal); --ascii força ASCII
uv run fpso-siz interativo --casos design_cases_bot.json --ajustes ajustes_pfd.toml

# Um TAG, preenchido pelo balanço, com os ajustes daquele TAG:
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --auto-balanco \
    --ajustes ajustes_pfd.toml --saida saida/tag
# Um TAG salvo em modo manual (não usa o balanço para preenchê-lo):
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json --ajustes ajustes_pfd.toml --saida saida/tag
# A planta: mesmo serviço por TAG; respeita os modos salvos, automático nos demais:
uv run fpso-siz pfd --casos design_cases_bot.json --ajustes ajustes_pfd.toml --saida saida/planta
# Um equipamento avulso salvo na sessão:
uv run fpso-siz dimensionar --avulso ko --ajustes ajustes_pfd.toml --saida saida/ko
# A entrada avulsa no contrato do Julia continua como era (bytes idênticos aos da F7b):
uv run fpso-siz dimensionar --exemplo alves_komesu --saida saida/exemplo
```

Códigos de saída, iguais aos da F10b: **0** = dimensionado ou inteiramente inativo (na
planta: todos); **1** = lacuna ou inviabilidade (os arquivos são gravados mesmo assim);
**2** = erro de entrada, de uso ou de contexto. `--ascii` vale para `interativo`,
`dimensionar`, `pfd` e `balanco`.

## Arquitetura

```
pfd/equipamento.py  serviço por TAG: Contexto, preparar, dimensionar, executar (cache)
pfd/entradas.py     adaptador automático (F10b) e adaptador manual (montar_manual)
pfd/manual.py       arquivo/exemplo → valores importados; avulso; associação avulso→TAG
pfd/ajustes.py      estado da sessão (EstadoTAG/Ajustes), leitura v2 e legado, contexto
pfd/planta.py       percorre o serviço para os 11 TAGs
output/pfd.py       serializador por TAG (JSON + <TAG>_varredura.csv) e planta.csv
output/ajustes.py   escritor TOML determinístico do arquivo de ajustes
output/terminal/    esquema.py (desenhos da topologia), pfd.py (telas), sessao.py (menus)
```

- **Um serviço, três entradas.** `planta.dimensionar`, `dimensionar --tag` e a sessão
  chamam `equipamento.executar`, que monta as entradas (automático ou manual) e chama o
  motor. Testes espionam a delegação: a planta executa os 11 TAGs com **um** balanço; o
  TAG isolado executa só ele (um balanço, um envelope). Comandos e menus não importam o
  motor nem a montagem de entradas (teste de arquitetura).
- **Contexto.** Arquivo de casos, premissas, balanço e versões. O balanço é resolvido uma
  vez por contexto e só se algum TAG automático precisar; uma planta toda manual não o
  resolve. Resultados ficam em cache no contexto, pela forma canônica do estado do TAG:
  editar recalcula só aquele TAG; outro arquivo de casos ou outras premissas criam outro
  contexto e descartam tudo o que dependia do anterior.
- **Estados.** dimensionado / aguardando entrada / inviável / inativo, como na F10b.
  Revisão e avisos são informação adicional (`preliminar`), não estado.
- **Erro × inviabilidade.** Sintaxe, chave desconhecida, caso inexistente, sentido de
  troca térmica incompatível e contexto divergente são `ValueError` (código 2; no
  interativo, a edição é desfeita com a mensagem). Conta impossível com as entradas dadas
  (p.ex. gás mais denso que o líquido → raiz de negativo) é **inviabilidade com
  diagnóstico**: o serviço converte o erro de domínio em envelope inviável. O motor não
  foi alterado (paridade Julia).

## Adaptadores

| | Automático | Manual (digitado, arquivo ou exemplo) |
|---|---|---|
| Precedência | usuário (caso > geral) > regra do TAG > recomendada > default com fonte > lacuna | usuário > arquivo (caso > geral) > recomendada > default com fonte > lacuna |
| Balanço/ChEDL | sim (regras do TAG) | **não** (teste espiona `fluidos.*`) |
| Insumos do TAG (utilidades) | sim | não existem: as entradas finais do método são pedidas |
| Atividade | regras do TAG (vazão, carga térmica) | informada pelo usuário + regras de vazão sobre os valores informados; a de carga térmica depende do balanço e não se aplica |
| Faixas [mín, máx] | não | sim (viram cantos no envelope, como no Julia) |

- **Defaults sem fonte não entram.** O manual e o avulso só usam o catálogo com fonte
  (`config/pfd/metodos.toml`) e as recomendadas do TAG; o que falta é pendência. Por isso
  o exemplo `alves_komesu` importado como avulso pede `tr_oil`/`tr_water` (sem fonte no
  catálogo), e o `knockout` pede `tr_liquid`. O comando `dimensionar --exemplo` continua
  no contrato do Julia, com os defaults do método, e grava os mesmos bytes da F7b.
- **Importação.** Um `[[case]]` vale para todos os casos do TAG; vários são casados pelo
  **nome** com os casos do TAG (ex.: "BOT 01 — Early Life", o nome dos rascunhos PFD F1 do
  Julia). Valor não finito (a lacuna explícita dos rascunhos) não é importado e segue
  pendente. Chave que o método não declara é erro de entrada. `enabled = false` torna o
  caso inativo com o motivo "desativado em <arquivo>".
- **Avulso.** Equipamento fora da planta (tipo + método + casos próprios). O automático
  pede antes um TAG compatível. A associação a um TAG é explícita: um caso vira valor
  geral; vários são casados pelo nome; cada valor mantém a origem.

## Pendências, recomendações e revisões

- **Lacuna:** chave, rótulo, unidade, faixa do descritor, casos ativos afetados, dica e
  as entradas que dependem dela (`Lacuna.dependentes`). Enter adia; nunca vira zero.
- **Recomendada / default com fonte:** exigem revisão (`Valor.revisao = "pendente"`):
  origem `recomendada` ou `metodo` do tipo `fonte`/`escolha`. Grade de busca e parâmetro
  não usado não pedem revisão. Confirmar registra valor e fonte por campo × caso e preserva
  a origem; editar vira origem usuário e registra o que foi substituído (a primeira origem
  não-usuário, com fonte e valor). Revisão cujo valor ou fonte mudou volta como
  `desatualizada` e conta como pendente.
- **Origem na tela:** balanço, correlação (propriedade), premissa + id (P-xx),
  recomendada, default (método), usuário, arquivo, lacuna. O JSON mantém a classificação
  detalhada da F10b.
- **Sobrescrita de entrada final** (balanço/propriedade/premissa): a tela avisa que o
  balanço não muda; o rastro registra "substitui … sem alterar o balanço".

## Arquivo de ajustes (esquema 2)

Um único `ajustes_pfd.toml` serve ao TAG isolado, ao PFD e à sessão: contexto (esquema,
arquivo e SHA-256 do BOT, casos, premissas alteradas, versões do pacote e do ChEDL,
SHA-256 da configuração), e por TAG/avulso: modo, método, arquivo importado, entradas
gerais e por caso, importados, atividade, revisões e substituídos. Escrita determinística
(ordem do método, floats em `repr`, sem data nem caminho de saída); ida e volta byte a
byte. O legado F10b (`["TAG"]`, `["TAG".caso."n"]`) é lido como automático sem revisões.
Formato completo e migração: [`../esquemas/README.md`](../esquemas/README.md).

Contexto divergente: hash do BOT, números dos casos, premissas alteradas ou método de um
TAG **bloqueiam** o comando (código 2, "erro de contexto", nada é reaplicado) e pedem
reconciliação explícita no interativo (adotar as premissas do arquivo, aplicar ao
contexto atual descartando casos inexistentes, ou cancelar). Versões e configuração só
avisam. Sem arquivo de casos carregado, a identidade do BOT fica guardada e é conferida
quando ele for carregado.

## Terminal

- Menu principal, menus do TAG, da planta, da revisão e dos ajustes declarados em
  `config/interativo.toml` por id de ação; o código despacha pelo id
  (`sessao.DESPACHO`). Teste troca ordem e textos no TOML e a sessão acompanha. Ação
  indisponível aparece com o motivo (numeração estável).
- **Esquemas** a partir de `config/topologia_db.toml` (via `esquema.arestas`,
  `linhas_planta`, `vizinhos`): planta bloco a bloco na ordem declarada, com saídas de
  fronteira, reciclo ("retorno ao M-01") e os dois lados do trocador; esquema local do
  TAG com os blocos vizinhos. Testes releem as arestas desenhadas e comparam com a
  topologia, também com blocos/correntes renomeados e ordem invertida.
- **ASCII seguro** por `--ascii` ou pela codificação da saída; glifos dos desenhos por
  repertório e transliteração pela tabela `[ascii]`. Cor independente do conteúdo (teste
  compara a saída sem ANSI com a sem cor).
- **Tela estreita:** desenho quebra em linhas; tabelas têm colunas com prioridade e as que
  não cabem viram linhas de detalhe (fontes longas). TAG, corrente e chave de pendência
  nunca são cortados (teste a 40 colunas).
- **MC:** a tela do TAG informa que o memorial do equipamento é da F11; nenhuma ação
  aparenta gerá-lo. O `ResultadoTAG` já reúne entradas, revisões, fontes, propriedades,
  pendências e rastro para o gerador da F11.

## Decisões e desvios registrados

1. **`dimensionar --avulso NOME --ajustes A`** — forma não listada na proposta, necessária
   para que a exportação de um avulso imprima um comando que reproduz os mesmos bytes.
2. **Planta sem estado salvo** usa o automático; abrir um TAG pela planta cria o estado
   automático dele (o modo passa a constar do arquivo). Nada é aplicado a outros TAGs.
3. **Inviabilidade por erro de domínio** tratada no serviço, não no motor (paridade).
4. **Grade do catálogo em vasos pequenos:** com `d_min` = mínimo do descritor e passo de
   150 mm (F10b), o exemplo de knockout do Julia importado como avulso não tem diâmetro
   na banda de esbeltez 3–4 e sai inviável com diagnóstico; com passo informado de 50 mm,
   dimensiona (d = 900 mm). Não houve revisão da regra de grade: é física/catálogo, fora
   do escopo desta fase.
5. **JSON por TAG passa ao esquema 2** (campos `avulso`, `modo`, `preliminar`, `revisoes`,
   `ajustes` canônico; valores com `faixa`, `revisao`, `anterior`; lacunas com
   `dependentes`) e ganha `<TAG>_varredura.csv`. Os números não mudam (abaixo).

## Verificação

- Paridade com a F10b: `tests/fixtures/pfd/f10b_resultados.json`, gerado pelo código da
  F10b via `git archive`, confere estados, lacunas, hash dos valores de entrada,
  envelopes, folgas e `planta.csv` com e sem os ajustes sintéticos. Na comparação direta
  com a saída da F10b: 4.128 valores (com origem e rastro), 3 e 11 envelopes (resultado,
  casos, varredura, rastros) iguais; `planta.csv` idêntico byte a byte. As 528 entradas
  compartilhadas com o PFD F1 do Julia seguem bit a bit.
- `dimensionar --exemplo` para os 5 exemplos: bytes idênticos aos do commit anterior.
- Balanço, memoriais (`-m latex`) e fixtures do Julia (`-m julia`) inalterados e verdes.
- Sessões roteirizadas (`tests/test_fluxo_tag.py`, `tests/test_interativo.py`):
  automático, manual parcial com retomada, importação do rascunho Julia por nome, edição
  por caso, restauração, revisão (confirmar/editar/desatualizada), redimensionamento,
  equipamento → PFD → equipamento sem recalcular, troca de premissa e de BOT, ajustes com
  contexto divergente, legado, avulso (manual, exemplo, associação), exportação igual ao
  comando impresso — inclusive resultado parcial.
- `tests/pfd/test_cli_tag.py`: TAG isolado × planta com os mesmos bytes em modos mistos
  (manual parcial, automático com lacuna preenchida e recomendações não revisadas, revisão
  confirmada, premissa alterada), estado de outros TAGs sem efeito no artefato, erros de
  uso/contexto e `--ascii`.
- Snapshots em `tests/fixtures/terminal/` (regenerar com `FPSO_SNAPSHOTS=1`): menu,
  planta (Unicode, ASCII, estreita, filtro por caso), TAG nos quatro estados (Unicode,
  ASCII, estreita), entradas com Origem.
- Números finais: ver `SPRINTS.md` (F10c).
