# 37 — Faixas de P_D1 e P_D2: o que a fonte fixa e o que falta (etapa C)

> **Atualização (2026-09-28):** a TVP foi recalculada com a composição recombinada (nota 38) e o
> trem produtivo, a 40 °C (estocagem): P_D2 em que a TVP atinge 70 kPa entre 133,4 e 157,3 kPa(a)
> — `39-trem-produtivo.md` §9. Os números de §2 abaixo (z_base, 37,8 °C) ficam como registro;
> nenhum dos dois é bound de otimização.

Investigação **sem alteração de física**. Fonte: BOT rev. C (`docs/bot/`). O acervo local
`references/` não estava disponível nesta sessão: nada dele é citado aqui.

## 1. O que o BOT diz

| item | texto | efeito sobre P_D1 / P_D2 |
|---|---|---|
| §2.7.1.2 | FWKO "operating at 2,500 kPa(a)" | teto físico do trem |
| §2.7.1.1, Fig. 2.7.1.17 | "degasser, electrostatic pre-treater, **degasser for RVP/TVP specification**, electrostatic treater"; gás dos dois degaseificadores "To Vapor Recovery" | o 2º degaseificador existe **para especificar RVP/TVP**; os dois descarregam na VRU |
| §2.3.1.1 | RVP < 68,9 kPa(a) a 37,8 °C (estocagem); RVP 34 kPa (medição, reavaliável); **TVP máx. 70 kPa** na temperatura de medição fiscal | critério do óleo estabilizado |
| §2.7.1.10 | TVP na estocagem acima do §2.3.1.1 ou separação acima de 99 °C "will not be accepted" | o critério vale na estocagem; T_D ≤ 99 °C |
| §2.7.3.9.20.1 | compressor principal: "Inlet pressure = 2,200 kPa(a) (estimated…)" | gás a ≥ 2.200 kPa(a) não precisaria de VRU |
| §2.7.3.8.9 | VRU: 1º estágio ≥ 420.000 Sm³/d; 2º estágio ≥ 960.000 Sm³/d (saída de simulação + 20 %) | capacidade, não pressão; **não** dá a pressão de sucção da VRU |
| §2.2.3.2 | separador de teste "from low pressure up to" 2.500 kPa(a) | não se aplica aos degaseificadores |

O BOT **não** dá pressão de nenhum degaseificador, nem a sucção/descarga dos estágios da VRU.

## 2. A especificação de TVP indica um teto para P_D2 (diagnóstico)

O líquido do V-002 sai no ponto de bolha em (P_D2, T_D2). Pelo trem existente
(`balanco/trem.resolver` + `termo.flash_tp`; bolha por bisseção em β = 0), a TVP a 37,8 °C do
líquido final é, com P_D1 = 700 kPa:

| P_D2 (kPa(a)) | TVP a 37,8 °C, caso 1 | caso 5 | caso 13 |
|---:|---:|---:|---:|
| 101,3 | 43,7 | 40,6 | 49,4 |
| **200 (P-19 atual)** | **98,3** | **90,2** | **107,6** |
| 300 | 159,1 | 147,2 | 169,7 |

Com o modelo diagnóstico atual, usando a composição-base ainda não reconciliada (Tab. 2.2.2.4,
por tipo de fluido, sem a recombinação da Nota 4) e `x` classificado como `nao_validada`,
P_D2 = 200 kPa resulta em TVP estimada de 89,7–107,6 kPa nos 16 casos. Portanto, 200 kPa é
incompatível com o limite de 70 kPa **dentro desse modelo**, mas isso ainda não constitui
verificação de projeto: a P-19 segue "a validar", não invalidada.

**Teto diagnóstico preliminar inferido pelo flash atual:** o maior P_D2 com TVP estimada ≤ 70 kPa
vai, por caso, de 137 kPa(a) (casos 13 e 14) a 162 kPa(a) (caso 6); P_D1 muda isso pouco
(P_D1 = 1.500 kPa: +3–4 kPa de TVP).

> **NÃO UTILIZAR COMO LIMITE DE P_D2 NA OTIMIZAÇÃO** antes da recombinação da Nota 4 e da
> validação da composição (`docs/validacao/35-casos-bot.md`).

Classe da estimativa: **(c) da invariante 5** — sai de x do flash (`nao_validada`), com a
composição por tipo de fluido. Espera-se que seja pouco sensível à interpretação dos casos em
primeira ordem (o líquido está na bolha em P_D2 por definição), mas isso não foi verificado e
não é número de projeto. A RVP (V/L = 4) não foi calculada.

## 3. Faixas possíveis

| variável | valor atual | limite inferior possível | limite superior possível | fonte | natureza do limite | confiança |
|---|---|---|---|---|---|---|
| **P_D2** | 200 kPa (P-19, "a validar") | **nenhum com fonte**; ~101,3 kPa(a) só por prática (sem vácuo na sucção da VRU) | critério **TVP ≤ 70 kPa** na estocagem; teto diagnóstico preliminar inferido pelo flash atual ≈ 137–162 kPa(a) — **não usar como limite na otimização** (§2) | BOT §2.3.1.1, §2.7.1.1, §2.7.1.10 (critério); flash diagnóstico (valor) | superior: **especificação de produto**, ainda sem avaliação validada; inferior: operacional, sem fonte | critério: **média** (com fonte); valor: **baixa** (classe c, composição não reconciliada); inferior: **baixa** |
| **P_D1** | 700 kPa (P-18, "a validar") | P_D1 > P_D2 + ΔP de transferência (o líquido do TO-001 segue ao V-002 sem bomba) | < 2.200 kPa(a) (sucção do compressor principal, estimada) e < P(C-08) = 2.500 − 2·100 = 2.300 kPa (P-17) | BOT §2.7.1.2, §2.7.3.9.20.1, Fig. 2.7.1.17; P-17 | topológico e de destino do gás (VRU) | **baixa**: faixa larga, extremos sem margem de controle com fonte |

## 4. O que falta para uma faixa com fonte

1. **Pressões de sucção e de descarga dos estágios da VRU** (o 1º recebe o V-002, o 2º o V-001;
   `config/memorial_tag.toml`): fixariam o piso de P_D2 e o par P_D1/P_D2 pela razão de
   compressão. Fora do BOT; sairiam de folha de dados de VRU ou de uma fonte de estágios de
   separação no acervo (a conferir: seção de separação em estágios de Arnold & Stewart).
2. **ΔP mínimo de transferência** entre os vasos (válvula de nível/misturadora da água de
   diluição, §2.7.1.7): premissa de projeto.
3. **Temperatura da medição fiscal** (define onde a TVP de 70 kPa é aplicada); a estocagem de
   40 °C é o que o §2.7.1.10 amarra.

## 5. Consequência para o modelo atual

No balanço vigente (Standing), **P_D2 não muda vazão de gás nenhuma**: `G_D2 = ΔRs(P_D1, T_D1)·Q_o`
libera todo o gás restante até a condição padrão, e `G_D1 + G_D2 = ΔRs(P_FWKO)·Q_o` não depende
de P_D1. P_D2 só entra na potência das bombas. Tornar P_D1/P_D2 variáveis sem o flash no
caminho produtivo daria à otimização uma variável sem efeito físico na separação.
