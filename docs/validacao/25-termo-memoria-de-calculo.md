# 25 — O termo adotado é "memória de cálculo"

**Decisão do usuário, 2026-09-27.** O termo correto do documento é **memória de cálculo**, não
"memorial de cálculo". A troca vale para o programa inteiro: cabeçalhos, interface, ajuda da CLI,
documentação e o corpo do documento do balanço. O usuário autorizou explicitamente relaxar, neste
ponto, a paridade byte a byte do **texto** com o script de referência.

## O que mudou

| Onde | De | Para |
|---|---|---|
| Cabeçalho SENAI do documento por TAG | `MEMORIAL DE CÁLCULO -- EQUIPAMENTO / DIAGNÓSTICO / AGUARDANDO ENTRADA` | `MEMÓRIA DE CÁLCULO -- …` |
| Cabeçalho SENAI do balanço e do balanço por caso | `MEMORIAL DE CÁLCULO -- DIAGRAMA DE BLOCOS` / `-- BALANÇO POR CASO` | `MEMÓRIA DE CÁLCULO -- …` |
| Capa e cabeçalho do layout `original` | `MEMORIAL PRELIMINAR DE CÁLCULO`; `Memorial preliminar do diagrama de blocos` | `MEMÓRIA DE CÁLCULO PRELIMINAR`; `Memória de cálculo preliminar do diagrama de blocos` |
| Corpo do documento do balanço | 21 trechos em 10 templates | ver a tabela de divergência |
| Interface interativa, ajuda da CLI, docstrings, README, CLAUDE.md | "memorial de cálculo" | "memória de cálculo" |

A concordância foi feita **caso a caso**, porque "memorial" é masculino e "memória" é feminino:
`Este memorial converteu` → `Esta memória de cálculo converteu`; `é um \textbf{memorial
preliminar de cálculo…}` → `é uma \textbf{memória de cálculo preliminar…}`; `o memorial de
cálculo definitivo` → `a memória de cálculo definitiva`; `O memorial foi gerado` → `A memória de
cálculo foi gerada`.

## O que NÃO mudou

**Identificadores não são o termo.** Continuam como estão, porque renomeá-los não muda nada para
quem lê o documento e quebraria referências:

- variáveis de template: `premissas_memorial`, `envelopes_memorial`, `criticos_memorial`;
- estilo LaTeX `\fancypagestyle{memorial}` / `\pagestyle{memorial}`;
- nomes de arquivo reais: `gerar_memorial.py` (o script de referência, citado como arquivo no
  texto), `memorial_balanco.toml`, `memorial_tag.toml`, os módulos `memorial.py`;
- o subcomando `fpso-siz memorial` (renomear é quebra de interface; fica pendente de decisão).

## Como a paridade foi relaxada sem perder a garantia

O contrato do projeto diz que refatoração não muda número e que o balanço tem paridade com o
oráculo. O relaxamento foi **cirúrgico**, e a mecânica é esta:

1. **`tests/fixtures/python_ref/main_ref.tex` não foi editado.** Ele é o artefato do script de
   referência (`references/Balanço_Preliminar.py`, que nunca é editado), e o SHA-256 dele é a
   proveniência registrada no oráculo — `tests/balanco/test_oraculo.py::test_stdout_e_main_tex`
   confere hash e tamanho. Editá-lo apagaria esse rastro.
2. A divergência ficou **declarada em dados**, em
   `tests/fixtures/python_ref/lexico_memoria_calculo.toml`: 21 pares `de`/`para`, com a
   justificativa e a data no cabeçalho do arquivo.
3. O teste de paridade aplica essas substituições ao texto **de referência** e só então compara o
   documento inteiro. Logo, o que se tolera é exatamente o termo: um número diferente, uma casa
   decimal, uma vírgula fora de lugar continuam reprovando.
4. O teste também reprova se uma substituição ficar **obsoleta** — se o trecho deixar de existir
   no texto de referência —, para a tabela não apodrecer em silêncio.
5. Os dois testes de robustez, que executam o script de referência ao vivo com outros dados e
   outras premissas, recebem o mesmo tratamento: o termo entra como divergência declarada, não
   como diferença de resultado.
6. `tools/comparar_memorial.py` aplica a mesma tabela, para a conferência template a template
   continuar valendo.

**A paridade dos números não foi relaxada.** Ela é verificada pelo `oraculo_balanco.json`, que
não tem texto corrido, e pela regressão da regra padrão do FWKO
(`regressao_eficiencia.json`).

## Verificação

| Verificação | Resultado |
|---|---|
| `tools/comparar_memorial.py` (template a template, layout `original`) | **IDÊNTICO** |
| `tests/test_memorial.py` | 13 aprovados |
| `tests/balanco/` (oráculo do balanço, hash do `main_ref.tex`) | aprovados |
| `tests/test_memorial_caso.py`, `tests/test_mc_exportacao.py`, `tests/pfd/test_memorial_tag.py` | aprovados |
| Snapshots de tela | regenerados; o diff é só o termo, nas três variantes (larga, estreita e ASCII) |
| `pytest -m latex` | ver o registro da fase no `SPRINTS.md` |
