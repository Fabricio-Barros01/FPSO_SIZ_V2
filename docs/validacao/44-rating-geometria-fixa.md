# 44 — Rating termo-hidráulico de geometria fixa

## Mudança física

O rating do P-001 agora avalia o comprimento e o número de chicanas **instalados** em cada
ponto da raiz. Antes, embora as restrições fossem reconstruídas, o cálculo interno voltava a
resolver o comprimento requerido pelo `UA` tentativo; isso não era um rating estrito de
geometria fixa. O avaliador novo atualiza temperaturas médias, consulta os fornecedores de
propriedades permitidos, refaz `Re`, `Pr`, películas, resistências, `U`, `F`, velocidades e
perdas de carga, e entrega o diagnóstico do mesmo ponto usado no resíduo.

No P-001, `k` do óleo continua sendo uma proposta declarada, pois o serviço termodinâmico não
tem uma condutividade líquida validada. Portanto não se promove uma propriedade proibida.
Serviços com água fornecem ao avaliador um adaptador de `termo.servico.agua_saturada` e passam a observar
a dependência térmica das propriedades durante a raiz; a inversão preserva a fronteira arquitetural que
entrega propriedades prontas ao módulo de dimensionamento.

## Efeito na regressão

A geometria selecionada e o critério de desempate não mudaram. O uso do número real de
chicanas instalado alterou apenas casos limitados por `UA`, em aproximadamente 1e-6 kW nos
menores desvios observados. A fixture `p001_busca_regressao.json` foi revista de propósito
para registrar a física corrigida. Teste sintético com propriedades fortemente dependentes
de temperatura prova que `U` varia entre avaliações e que o calor convergido difere do caso
artificial com propriedades congeladas.
