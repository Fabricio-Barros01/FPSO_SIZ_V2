# 03 — Memorial LaTeX do balanço (F4)

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): o layout `original` (reprodução do memorial do script de referência) saiu; o memorial vigente é o layout SENAI. O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Data: 2026-09-23. **Estado: entregue.**

## Uso
```
fpso-siz memorial --casos <json> --saida <pasta> [--layout original|senai] [--premissa NOME=VALOR ...] [--pdf]
```
`--pdf` compila com latexmk se ele estiver instalado (código de saída 3 se a compilação falhar).

## Arquitetura
- **Núcleo, `balanco/indicadores.py`.** Concentra as grandezas derivadas que o memorial
  exibe e que o original calculava dentro da geração do texto: vazões por fase, vazão real
  de gás (Z = 1), vazões molares de CO₂ e H₂S, BSW, eficiências, Standing do exemplo,
  máximos entre casos (com a regra de empate), envelopes, críticos, fechamento, resíduos
  por componente, sensibilidade, verificação de normalização (k_f) e propriedades por
  fluido. Os limiares estão em `constantes.toml [criterios]` e `[bot]`, as variações de
  sensibilidade em `sensibilidade_balanco.toml` e as percentagens do BOT para k_f em
  `composicao_bot.toml`.
- **Saída, `output/latex/`.** `formatacao.py` implementa `br`, `mb`, `sci`, `esc` e `ids`,
  idênticas às do original, mais `mbn`. `ambiente.py` configura o Jinja2 com delimitadores
  `<< >>`, `<% %>` e `<# #>`, que não colidem com LaTeX. `compilacao.py` chama o latexmk.
- **Templates, `output/latex/balanco/templates/`.** Há um template por seção (41), mais
  `_bomba.tex.j2`, compartilhado pelas três bombas. Foram gerados **fatiando o `main.tex`
  de referência** e trocando só os trechos dinâmicos, de modo que o texto estático é exato
  por construção.
- **Conteúdo documental em TOML**, na camada de saída: a tabela de premissas
  (`premissas_memorial.toml`, cujos valores são expressões avaliadas no contexto), os
  textos dos envelopes e dos críticos e as definições de fechamento.
- **Metadados** (número, data, revisão, responsáveis, caso de demonstração): em
  `config/memorial_balanco.toml`.

## Layouts
| Layout | Preâmbulo e capa | Uso |
|---|---|---|
| `original` | os do script de referência | paridade: `main.tex` **idêntico byte a byte** ao original |
| `senai` | template SENAI CETIQT: moldura, cabeçalho com logo, "folha x de N", folha de rosto com índice de revisões, rodapé de propriedade | entrega |

O corpo (seções 1–18 e apêndices) é o mesmo nos dois layouts, e há teste para isso. No
`senai`, os tipos de coluna `L`/`R` do template (colunas X, sem argumento) foram
substituídos pelos do corpo (`L{largura}`/`R{largura}`); `C` e `M` do template continuam.
O logotipo foi copiado do template para `output/latex/balanco/recursos/`.

## Verificações (tests/test_memorial.py)
1. **Paridade:** o layout `original` é idêntico ao `main_ref.tex` do oráculo F1.
2. **Robustez a dados:** o script original e o `fpso-siz` rodam sobre um arquivo de casos
   perturbado (FWKO a 2.350 kPa, óleo ×1,07, líquido ×1,04, T −3 °C, gás ×0,93). Toda
   linha diferente precisa estar na lista branca `LITERAIS_DO_ORIGINAL`, e nenhuma outra
   difere. Isso prova que nenhum número do caso base ficou fixo num template.
3. **Robustez a premissas:** idem, com 15 premissas alteradas numa cópia temporária do
   script original (a referência não é tocada).
4. **Bijeção equação↔memorial (invariante 3):** as 26 equações do catálogo têm âncoras
   (`memorial = [...]`) que existem como `\label` no documento. Todo `\label{eq:*}` do
   documento é âncora de uma equação ou uma das 4 definições de fechamento
   (`rastro_memorial.toml`).
5. **Críticos:** valores e casos iguais ao oráculo F1, e textos iguais aos do original.
6. **Compilação** (`uv run pytest -m latex`, fora da rodada padrão por ser lenta): os dois
   layouts compilam do zero com latexmk/MiKTeX, sem erro nem referência indefinida, em
   cerca de 17 s. O original tem 71 páginas e o SENAI, 68.

## Literais fixos do original que agora acompanham dados e premissas
O script de referência escrevia à mão, no texto, valores que dependem de dado ou de
premissa. No caso base eles coincidem, por isso a paridade se mantém; com outros dados, o
original ficaria desatualizado. Agora eles vêm do dado:
- **pressão do FWKO "2.500":** 10 lugares, entre eles F-02, a descrição do DB, M-01,
  SG-001, P-001, M-03 e a linha "Maior pressão";
- **BSW nas frações:** `0,01/0,99` (TO-001) e `0,005/0,995` (TO-002);
- **diluição:** `285/0,005` e `240.000` (DWH-001, TO-002);
- **outros valores de premissa:** `2,0 kg/m³` (C_OiW), `ΔT_app = 10` (P-001), `max(90; …)`
  (P-002), `c_p,D = 4,18`, `T − 40` (P-003), `0,5 %` (MED-001) e `2.600 → 2.500`
  (válvula de reciclo).

Para essas premissas escritas no texto, usa-se `mbn`, que não arredonda (0,015 não vira
0,01).

## Pontos do conteúdo original registrados, não alterados (paridade)
- **γ_g sem definição escrita.** A definição γ_g = MW/MW_ar é avaliada no motor, mas o
  memorial só usa γ_g em `eq:standing`. É uma lacuna herdada, anotada no catálogo
  (`nota_memorial`).
- **"Maior pressão".** A linha "Maior pressão (igual em todos os casos; não discrimina)"
  reporta P_FWKO, mas a maior pressão do módulo é a descarga das bombas de reciclo
  (P_rec = 2.600 kPa).
- **Autoria no texto.** O texto de reprodutibilidade (no layout `original`) ainda atribui a
  geração ao `gerar_memorial.py`. O layout `senai` atribui ao `fpso-siz` na folha de
  identificação.

## Ferramenta
`tools/comparar_memorial.py [-v]` compara o layout `original` com a referência, template a
template, e mostra a primeira diferença. É usada durante a edição dos templates.
