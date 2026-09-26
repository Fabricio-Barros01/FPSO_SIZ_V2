# Valores propostos

O arquivo de valores propostos para as entradas sem fonte técnica mudou para dentro do pacote:
[`src/fpso_siz/config/pfd/pendencias_propostas.toml`](../../src/fpso_siz/config/pfd/pendencias_propostas.toml).
Ele é carregado por padrão pela CLI e pelo modo interativo (decisão do usuário, 2026-09-26);
todo item tem `status = "proposto"`, origem "proposta do usuário" e fica em revisão pendente
até ser confirmado ou editado (modo interativo → TAG → "Revisar recomendações e defaults").
`--propostas ARQ` usa outro arquivo; `--sem-propostas` desliga.
