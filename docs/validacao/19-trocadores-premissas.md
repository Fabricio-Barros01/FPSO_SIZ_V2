# F10x.7 — trocadores: P-45, P-46, cascos em série e paralelo, P-001 como lacuna metodológica

Decisões do usuário em 2026-09-26. Este documento justifica as mudanças de resultado, como exige
o CLAUDE.md. Os números vêm de `docs/validacao/18-trocadores.md`, gerado pela ferramenta.

## Premissas

- **P-46 — topologia do P-002 e do P-003** (premissa de projeto destes dois equipamentos, não
  regra geral de trocadores): o óleo, o fluido mais viscoso, vai no **casco**, e a água de
  utilidade vai nos **tubos**.
  - Arquivos: `config/pfd/tags/p_002.toml` e `p_003.toml`.
  - A alocação do PFD F1 do Julia (óleo no tubo) está em `config/pfd/variantes/*_oleo_tubo.toml`
    e é usada com `topologia_julia=True` / `--topologia-julia` (fixtures do PFD F1 e regressão
    F10b).
  - As propostas de k e de incrustação foram trocadas de lado junto com os fluidos.
- **P-45 — velocidade nos tubos**, específica de trocadores (`banda_caso_projeto`, extensão em
  `equipment/exchanger/saari_extensoes.toml`; não reutiliza a P-44 das bombas):
  1. o teto `v_max` vale em todos os casos;
  2. a banda inteira vale no caso de projeto, o de maior vazão volumétrica no tubo (para a
     utilidade, ṁ = q/(cp·ΔT), é o de maior carga térmica);
  3. no turndown, v < v_min é **alerta** de operabilidade/incrustação (`casos_abaixo_v_min`,
     marcado no MC), não reprovação;
  4. Dittus-Boelter continua exigido dentro da faixa **em cada caso**.
- **Cascos em série e paralelo** (`cascos_serie`, `cascos_paralelo`; default 1, que é a regra
  do Julia):
  - **Série:** vazões inteiras e 1/N do U·A em cada casco. O F é o do arranjo 1-2 com as
    temperaturas do conjunto, o que é conservador.
  - **Paralelo:** 1/N das vazões dos dois lados e da carga em cada casco.
  - Os limites `l_tubo_max` = 6 m e `d_casco_max` = 2.500 mm **não** foram alterados.
- **Reotimização discreta** (`pfd/reotimizacao.py`, `config/pfd/reotimizacao.toml`,
  `tools/reotimizar_trocadores.py`):
  - **Grade:** d_externo, passes, passo, arranjo e espaçamento de chicana, cada lista dentro da
    faixa da fonte do descritor. O número de tubos continua varrido pelo método.
  - **Divisão em cascos:** só se o bloqueio que a justifica estiver no melhor candidato
    (comprimento → série no P-002; casco → paralelo no P-003).
  - **Registro:** o escolhido entra no TAG como `[recomendadas]` com fonte, revisáveis.
- **P-001 — lacuna metodológica:** não se implementou Sieder-Tate nem outra correlação laminar
  sem referência rastreável em `references/`. Quando houver fonte, a correlação entra como ramo
  próprio do método, sem extrapolar Dittus-Boelter.

## Resultado e o que continua governando

| TAG | Configuração | Governante |
|---|---|---|
| P-002 | 2 cascos em série; d_o 19,05 mm, 2 passes, passo 1,25, arranjo 90°, chicana 0,2·Ds; 308 tubos por passe; L = 5,29 m por casco; área total 389,9 m² | **Dittus-Boelter no caso BOT 06** (carga 263 kW = 3,6 % da de projeto): v ≈ 0,08 m/s, Re ≈ 4.200 < 10⁴. O comprimento deixa de bloquear com 2 cascos em série; os demais nove casos ficam dentro da faixa. |
| P-003 | 1 casco; d_o 25,4 mm, 1 passe, passo 1,25, arranjo 90°, chicana 0,2·Ds; 1.210 tubos por passe | **Dittus-Boelter nos casos BOT 04, 05 e 06** (1.148, 498 e 129 kW contra 26.506 kW no de projeto) e **comprimento** (14,1 m no melhor feixe, contra 6 m). O casco fica abaixo de 2.500 mm, então os cascos em paralelo não se aplicam. Eles reduziriam o Re por casco. |
| P-001 | — | lacuna metodológica (óleo laminar no tubo) |

Os dois trocadores seguem **inviáveis**: são alarmes abertos, com as hipóteses em
`config/pfd/alarmes.toml`. O MC de cada um mostra o feixe mais próximo de atender, os bloqueios
por critério e caso e a operação de cada caso.

## Pendências para decisão do usuário

1. **Vazão da utilidade no turndown.** Hoje ṁ = q/(cp·ΔT), com o ΔT da utilidade fixo pelos
   insumos. Com a circulação mantida (e ΔT menor no turndown) o Re dos casos de baixa carga
   subiria. É uma premissa de operação, sem fonte no acervo.
2. **Comprimento do P-003.** A decisão previu cascos em série só no P-002.
3. **Correlação laminar/de transição do lado tubo** (P-001 e turndown do P-002/P-003):
   depende de fonte em `references/`.

## Paridade

- Com os defaults das extensões, o envelope é o do Julia (`test_paridade_julia`, com
  `derivados_v2` fora da comparação e o cartão Julia conferido com ele vazio).
- As fixtures do PFD F1 e a regressão F10b rodam com `topologia_julia=True`, óleo morto e as
  extensões desligadas.
