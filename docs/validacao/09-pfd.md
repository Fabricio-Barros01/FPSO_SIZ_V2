# F10b — balanço → entradas dos TAGs → envelopes

> **Histórico.** Registro de uma etapa anterior à consolidação arquitetural (2026-09-28): a alocação do PFD F1 do Julia (`--topologia-julia`), o óleo morto e as fixtures da F10b saíram; vale a P-46 e o óleo vivo. O funcionamento vigente está em [`../arquitetura/arquitetura-alvo.md`](../arquitetura/arquitetura-alvo.md).

Continuação da implementação aprovada em 2026-09-23. O comando `fpso-siz pfd` monta os
11 TAGs a partir dos 16 casos do BOT. Exporta um JSON por TAG e `planta.csv`, inclusive
quando há lacunas ou inviabilidade. O balanço preliminar e os oráculos permanecem intactos.

## Uso

```sh
uv run fpso-siz pfd --casos tests/fixtures/python_ref/design_cases_bot.json
uv run fpso-siz pfd --casos tests/fixtures/python_ref/design_cases_bot.json --saida saida/pfd
uv run fpso-siz pfd --casos design_cases_bot.json --ajustes ajustes_pfd.toml --saida saida/pfd
```

Sem `--saida`, mostra somente o resumo. `--premissa NOME=VALOR` altera uma premissa do
balanço antes de montar as entradas. Códigos de saída: **0** = todos os TAGs dimensionados
ou inativos; **1** = há lacuna ou inviabilidade; **2** = erro de entrada/configuração.

O arquivo de ajustes usa o TAG como tabela. Uma subtabela `caso` tem precedência sobre os
ajustes gerais daquele TAG. Exemplo de formato (valores ilustrativos, não recomendação):

```toml
["B-001"]
h_sucao = 8.0

["B-001".caso."3"]
h_sucao = 9.0
```

Não há edição interativa nesta fase; o menu Planta está previsto na F10c. Os ajustes
substituem entradas do dimensionamento, sem reescrever os resultados do balanço.

> **Atualização (F10c):** este formato continua aceito como legado (automático, sem
> revisões); o esquema 2, o fluxo por TAG e o `dimensionar --tag` estão em
> [`10-fluxo-tag.md`](10-fluxo-tag.md).

## Entradas e rastreabilidade

- `config/pfd/tags/*.toml`: método, correntes, regras, recomendações e critério de atividade.
- `config/pfd/metodos.toml`: defaults com fonte, escolhas de geometria e dicas das lacunas.
- `pfd/entradas.py`: precedência usuário → regra do TAG → recomendação → default com
  fonte → lacuna. Mantém unidade, faixa, origem, fonte e dependências ausentes.
- `pfd/planta.py`: um envelope independente por TAG, só com casos ativos. Rejeita balanço
  sem convergência e numeração de casos inconsistente. Não interpola entre casos.
- `output/pfd.py`: números finitos ou `null`, sem NaN/Infinity no JSON. Entradas,
  insumos de utilidade, propriedades, fontes, avisos, ajustes, versões ChEDL, varredura,
  cartão e rastros dos casos ficam no mesmo arquivo.

As recomendações usadas aparecem como **a confirmar**, com a fonte. Os parâmetros marcados
`escolha` são geometria de referência do método e precisam de revisão de projeto; não
são dados de processo obtidos do BOT.

## Propriedades e diferenças frente ao rascunho PFD F1

As fixtures em `tests/fixtures/julia/pfd/` são cópias integrais do repositório Julia no
commit `ab58fc631749aa81fdf7db566aa14a0cecd777c4`. O manifesto preservado contém os hashes
dos 11 TOMLs; os testes conferem cada hash, o SHA-256 do arquivo de casos e os 16 casos.

As **528 entradas compartilhadas**, incluindo T, P, vazão mássica, cp, rendimento e
vazão/densidade do óleo morto nos separadores/tratadores, são iguais bit a bit. Também
se verificam os volumes líquidos originais e o gás ideal do rascunho, antes de aplicar
as propriedades da F10a. Os valores novos de propriedades não são comparados como se
fossem a mesma grandeza do rascunho:

1. **Base de gás:** a Eq. 3.8b de Stewart & Arnold (2008), p. 116, define `Qg` em
   scmh. O rascunho F1 fornecia volume nas condições de operação. Os TAGs agora
   fornecem **Sm³/h**, pois T, P e Z já entram na equação. A EOS fornece Z, densidade
   e viscosidade na condição do vaso. A equação do método não foi alterada.
2. **Fase aquosa:** W + D é uma solução com a massa de NaCl de cada água, obtida de
   `S_W/rho_W` e `S_D/rho_D`. A fração mássica resultante alimenta Laliberté; não se
   calcula uma densidade média de duas soluções independentes. Volume = massa/ρ(T).
3. **Líquido misto:** volumes de óleo e solução aquosa aditivos. μ de emulsão por Zanker,
   com fase contínua declarada em TOML. Avisos de extrapolação ficam no JSON; μ de óleo
   fora da tabela só gera aviso se essa viscosidade for usada.
4. **Utilidades:** água pura de circuito fechado, IAPWS como líquido saturado à
   temperatura média. A pressão do circuito não é informada; essa aproximação fica
   explícita. As duas temperaturas são lacunas e aparecem juntas. A vazão fecha
   `Q/(cp·|ΔT|)`; ΔT zero ou sentido incompatível é erro de entrada. Acima de 120 °C
   no meio de aquecimento, há aviso do limite BOT 2.7.1.4.
5. **Bombas:** `pv_informada` em kPa absolutos substitui Antoine. No PFD, Pv = pressão
   do vaso de sucção (Branan, Ex. 5-2); o default NaN mantém Antoine e a paridade do
   método isolado. A nova entrada fica em um TOML de extensão; o TOML Julia não muda.
6. **Faixas:** descritores do PFD admitem salmoura até 1500 kg/m³, com justificativa.
   Isso amplia o formulário, sem impor densidade e sem mudar os descritores do oráculo.
7. **Knockouts:** retenção recomendada de 5 min, pela nota de alto CO₂ na Tab. 3.2 de
   Stewart & Arnold, conforme o plano aprovado. Os 3 min deixados no trabalho parcial
   foram corrigidos antes da entrega.

Continuam explícitos os limites: óleo morto, ausência de Bo e volume de gás dissolvido
não modelado no líquido. Nenhuma propriedade faltante recebe valor arbitrário.

## Estado com os dados reais, sem ajustes

| TAG | Estado / entradas faltantes |
|---|---|
| B-001/002/003 | Aguardam desnível, nível de sucção, comprimentos e Σk das duas linhas, NPSHr e margem |
| P-001 | Aguarda k dos dois fluidos, k da parede e incrustação dos dois lados |
| P-002/003 | Aguardam k do processo, k da parede, incrustação dos dois lados e as duas temperaturas da utilidade |
| TO-001/002 | Aguardam tamanho da gotícula de água após coalescência |
| SG-001 | Entradas completas, envelope inviável com o método/premissas atuais (F10v: agora pelo caso 2, ver `11-verificacao-balanco.md`) |
| V-001 | Dimensionado: d = 4850 mm; governa BOT 08 |
| V-002 | Dimensionado: d = 4700 mm; governa BOT 03 |

B-002/003 ficam inativos nos casos 1 e 4–7. P-001/002 ficam inativos nos casos 10 e
12–16. A ausência de vazão em todas as fases também inativa os vasos. Uma lacuna ou
valor não finito nunca é interpretado como vazão zero.

**SG-001:** o teto governante de 1634,579 mm vem do caso 6, sem fase aquosa livre, e
entra em conflito com a esbeltez 3–5. O método portado ainda avalia a restrição de
decantação nesse limite. A hipótese do histórico de desabilitar automaticamente essa
restrição **não foi implementada**: exige revisão física do método e do oráculo, separada
da ligação de entradas. Mesmo os casos com água podem impor tetos restritivos. O
diagnóstico é preservado, sem declarar um dimensionamento viável artificialmente.

## Verificação

- `uv run pytest --cov=fpso_siz --cov-fail-under=90`: resultado registrado no SPRINTS.
- Testes de paridade do balanço, memoriais de texto e métodos Julia continuam ativos.
- `tests/pfd/`: lacunas exatas, inatividade, precedência por caso, conservação da massa
  de sal e energia da utilidade, Pv, erros de ajustes, exportação estrita e determinismo.
- `tests/fixtures/pfd/ajustes_sinteticos.toml` calcula **11 envelopes viáveis com caso
  governante**. É exclusivamente teste: além de preencher lacunas, modifica gotículas,
  viscosidades, número de passes, faixas e limites. Os valores não representam projeto.
- Exportar pela API e pelo comando com os mesmos dados produz os mesmos bytes.
- O teste do registro de métodos foi isolado: antes ele esvaziava o registro global
  e fazia os testes seguintes dependerem da ordem de execução.

> **Atualização (F10v, 2026-09-25):** com a premissa P-42 (sem fase aquosa), os casos
> sem água (1, 4–7) não impõem teto de decantação nem pedem entradas aquosas; o teto do
> SG-001 passou do caso 6 (1634,579 mm) para o caso 2 (4434,5 mm), e o TAG segue
> inviável. Ver [`11-verificacao-balanco.md`](11-verificacao-balanco.md).

Próxima fase: F10c, sujeita à aprovação prevista em `CLAUDE.md`.
