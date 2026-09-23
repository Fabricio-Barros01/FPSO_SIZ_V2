# 07 — CLI interativa e subcomando `dimensionar` (F7b)

Data: 2026-09-23. **Estado: entregue.** Fase extra, pedida pelo usuário depois da F7.

## O que o usuário vê
`fpso-siz` sem argumentos, num terminal, ou `fpso-siz interativo [--casos X]` abre o
modo interativo.

1. **Cabeçalho.** Segue a tradição do OpenFOAM: moldura de comentário `/*--- ---*\`,
   logotipo em barras e a identificação à direita. No lugar de *Field Operation And
   Manipulation* entra o acrônimo do próprio equipamento, *Floating Production Storage and
   Offloading*. Abaixo vem o bloco Exec/Data/Host/PID/Pasta/Casos. Dos CLIs de agentes vêm o
   degradê ANSI no logotipo e a linha de dicas. Em terminal com menos de 79 colunas, o
   cabeçalho sai compacto.
2. **Contexto.** Mostra arquivo, sha256, fonte (BOT), casos, fluidos e a condição padrão.
   Se houver `design_cases_bot.json` na pasta corrente, ele é carregado automaticamente.
3. **Menu.** Balanço, equipamento, premissas e casos.
4. **Resumo antes de exportar.**
   - **Balanço:** convergência, premissas alteradas e o caso que maximiza cada critério de
     dimensionamento. Dá para ver também a auditoria independente e as correntes de um caso.
   - **Equipamento:** a tabela de entradas (só as informadas, uma coluna por caso), o cartão
     de resultados com status ✓/✗, o resumo de governança e, por caso, o que ele escolheria
     sozinho e a folga no envelope. Dá para ver também a varredura, com a linha escolhida
     marcada, e o rastro de cálculo de cada caso.
5. **Exportar é opcional.** O usuário escolhe o formato e a pasta. A sessão grava e
   imprime o **comando equivalente** (`fpso-siz balanco|memorial|dimensionar …`, com as
   `--premissa` alteradas na sessão).

## Garantias (tests/test_interativo.py)
- **O comando impresso reproduz a sessão.** O teste apaga o que a sessão gravou, executa
  o comando impresso e compara os bytes:
  - no balanço: JSON, CSV e `main.tex`, com premissa alterada;
  - nos 5 exemplos de equipamento e num arquivo TOML: JSON e CSV.
- Erros viram aviso e a sessão continua:
  - arquivo ilegível;
  - premissa desconhecida ou valor não numérico;
  - formato ou layout inválido;
  - caso inexistente;
  - TOML de outro equipamento;
  - caso inviável.
- EOF (Ctrl+D) encerra com 0 e Ctrl+C com 130. Sem argumentos e fora de um terminal, a
  CLI mantém o erro de uso (2) de antes.
- **Cor:** só em TTY, com `NO_COLOR`/`FORCE_COLOR`/`TERM=dumb` respeitados. Sem os códigos
  ANSI, o cabeçalho colorido é idêntico ao sem cor.
- Os exemplos em `config/exemplos/` são idênticos, byte a byte, a
  `tests/fixtures/julia/casos/`.

## Invariantes
- **Invariante 4.** O teste de arquitetura cobre `cli.py`, `output/terminal/*.py` e
  `output/dimensionamento.py`. Nenhum desses módulos contém como texto o nome de premissa,
  equação, verificação, coluna, campo de `ResultadoCaso`, parâmetro de método registrado ou
  chave de corrente. Colunas, rótulos, unidades e casas decimais vêm de
  `config/interativo.toml`; o cartão, a varredura e o rastro vêm dos hooks do método.
- **Invariante 1.** Tudo fica em `output/`, e o núcleo não imprime. Entraram no núcleo só
  duas funções puras: `configuracao.exemplos()` e `registro.resolver()`.
- **Sem dependência nova.** Tudo usa a biblioteca padrão: `input`, ANSI e `readline`
  quando disponível.

## Limites conhecidos
- **Largura das tabelas.** A tabela de correntes (~80 colunas mais a descrição) e a de
  casos críticos passam de 80 colunas. A descrição fica por último para não desalinhar os
  números.
- **Arquivos de casos.** O modo interativo não edita casos de equipamento. Ele lê
  exemplos embutidos ou um TOML do usuário, e a edição fica para uma fase futura, se for
  pedida.
