# Fase 4 — caracterização do fluido de poço (pseudo-componentes)

Gerado por `tools/caracterizacao_poco.py`.

> **Nada foi integrado ao processo.** O balanço, o dimensionamento e os relatórios não passam por aqui; a integração é a Fase 5.

## Por que é necessário

O fluido do BOT tem 31 componentes com fração não nula. Só dois **não são aceitos** pelo backend (`C20+` e `C20++`) — mas o problema é maior que isso: os cortes **C6–C19 são frações SCN**, e o backend resolve o rótulo `C7` como **n-heptano puro**. Aceitar essa resolução seria trocar um corte com iso-parafinas, naftênicos e aromáticos por uma parafina normal, em silêncio.

Fonte da caracterização: Riazi, M. R.; Al-Sahhaf, T. A. Physical properties of heavy petroleum fractions and crude oils. Fluid Phase Equilibria 117 (1996) 217-224 (`references/riazi1996.pdf`).

**Conferência da transcrição:** transcrição conferida contra as duas verificações internas do próprio artigo (p. 220): a eq. 2 com os coeficientes de Pc dá 1,013 bar em M = 1382, e Tbr dá 0,996; calculados 1,0087 bar e 0,9959.

**Limitação da fonte:** as Tabelas 4 e 5 do artigo (valores tabelados de Katz-Firoozabadi e 'recommended values') estão ilegíveis no escaneamento do acervo; TODAS as propriedades aqui são calculadas pelas equações, nenhuma é valor tabelado.

## A regra da transformação

**Não há transformação de composição.** Cada componente mantém a sua fração molar exatamente; o que muda é a propriedade atribuída a ele — de "procure este nome no banco" para "use este Tc, Pc e ω". Logo, por construção: fechamento preservado, nenhuma fração negativa criada, e a quantidade atribuída a cada tipo é exatamente a que já estava lá.

| classe | componentes | caracterização |
|---|---|---|
| real | N2, CO2, H2S, C1–C3, iC4/nC4, iC5/nC5, BTEX | identificador do banco (chemicals) |
| SCN | C6–C19 | Riazi & Al-Sahhaf, de Nc |
| plus | C20+, C20++ | Riazi & Al-Sahhaf, do **MW do BOT** |

## Caracterização dos pseudo-componentes

| pseudo | tipo | MW (g/mol) | Tb (K) | SG | Tc (K) | Pc (bar) | ω |
|---|---|---|---|---|---|---|---|
| C6 | SCN | 80,0 | 335,61 | 0,7000 | 512,56 | 38,460 | 0,2471 |
| C7 | SCN | 94,0 | 365,19 | 0,7264 | 546,92 | 33,650 | 0,2997 |
| C8 | SCN | 108,0 | 392,31 | 0,7479 | 577,31 | 29,836 | 0,3498 |
| C9 | SCN | 122,0 | 417,36 | 0,7660 | 604,48 | 26,732 | 0,3979 |
| C10 | SCN | 136,0 | 440,65 | 0,7813 | 628,96 | 24,156 | 0,4443 |
| C11 | SCN | 150,0 | 462,41 | 0,7947 | 651,19 | 21,983 | 0,4892 |
| C12 | SCN | 164,0 | 482,82 | 0,8064 | 671,48 | 20,125 | 0,5329 |
| C13 | SCN | 178,0 | 502,04 | 0,8168 | 690,09 | 18,519 | 0,5756 |
| C14 | SCN | 192,0 | 520,18 | 0,8261 | 707,24 | 17,117 | 0,6172 |
| C15 | SCN | 206,0 | 537,35 | 0,8345 | 723,09 | 15,884 | 0,6581 |
| C16 | SCN | 220,0 | 553,65 | 0,8422 | 737,80 | 14,790 | 0,6981 |
| C17 | SCN | 234,0 | 569,14 | 0,8492 | 751,48 | 13,815 | 0,7375 |
| C18 | SCN | 248,0 | 583,90 | 0,8556 | 764,23 | 12,941 | 0,7762 |
| C19 | SCN | 262,0 | 597,98 | 0,8615 | 776,15 | 12,152 | 0,8144 |
| C20+ | plus | **570,0** | 801,40 | 0,9323 | 920,53 | 4,424 | 1,5634 |
| C20++ | plus | **468,0** | 750,99 | 0,9165 | 890,10 | 5,848 | 1,3293 |

MW das frações plus em negrito: é **dado do BOT**, usado exatamente como veio. Todas as demais colunas são calculadas pelas correlações; nenhuma é valor tabelado da fonte.

### Densidade contra o dado do BOT

| pseudo | SG × 999 (kg/m³) | ρ do BOT (kg/m³) | desvio |
|---|---|---|---|
| C20+ | 931,3 | 957,2 | -2,70 % |
| C20++ | 915,6 | 938,1 | -2,40 % |

É a verificação mais direta disponível: a correlação reproduz a densidade que o próprio BOT declara para o pseudo-componente, dentro de ~2,5 %.

## Composição, antes e depois

| componente | z (Early Life) | classe | vai ao backend como |
|---|---|---|---|
| H2S | 0,000120 | real | identificador do banco |
| N2 | 0,002400 | real | identificador do banco |
| CO2 | 0,175696 | real | identificador do banco |
| C1 | 0,444191 | real | identificador do banco |
| C2 | 0,065899 | real | identificador do banco |
| C3 | 0,044899 | real | identificador do banco |
| iC4 | 0,007600 | real | identificador do banco |
| nC4 | 0,018100 | real | identificador do banco |
| iC5 | 0,005600 | real | identificador do banco |
| nC5 | 0,009300 | real | identificador do banco |
| C6 | 0,012500 | scn | Tc=512,6 K, Pc=38,46 bar, ω=0,247 |
| C7 | 0,010300 | scn | Tc=546,9 K, Pc=33,65 bar, ω=0,300 |
| C8 | 0,019300 | scn | Tc=577,3 K, Pc=29,84 bar, ω=0,350 |
| C9 | 0,012200 | scn | Tc=604,5 K, Pc=26,73 bar, ω=0,398 |
| C10 | 0,014300 | scn | Tc=629,0 K, Pc=24,16 bar, ω=0,444 |
| C11 | 0,012200 | scn | Tc=651,2 K, Pc=21,98 bar, ω=0,489 |
| C12 | 0,011100 | scn | Tc=671,5 K, Pc=20,12 bar, ω=0,533 |
| C13 | 0,011200 | scn | Tc=690,1 K, Pc=18,52 bar, ω=0,576 |
| C14 | 0,009400 | scn | Tc=707,2 K, Pc=17,12 bar, ω=0,617 |
| C15 | 0,009100 | scn | Tc=723,1 K, Pc=15,88 bar, ω=0,658 |
| C16 | 0,007100 | scn | Tc=737,8 K, Pc=14,79 bar, ω=0,698 |
| C17 | 0,005700 | scn | Tc=751,5 K, Pc=13,82 bar, ω=0,737 |
| C18 | 0,006300 | scn | Tc=764,2 K, Pc=12,94 bar, ω=0,776 |
| C19 | 0,005500 | scn | Tc=776,2 K, Pc=12,15 bar, ω=0,814 |
| C20+ | 0,070499 | plus | Tc=920,5 K, Pc=4,42 bar, ω=1,563 |
| Benzene | 0,004300 | real | identificador do banco |
| Toluene | 0,000500 | real | identificador do banco |
| Ethylbenzene | 0,000900 | real | identificador do banco |
| o-Xylene | 0,000800 | real | identificador do banco |
| m-Xylene | 0,001500 | real | identificador do banco |
| p-Xylene | 0,001500 | real | identificador do banco |

**Balanço da transformação:** soma antes = 1.0; soma depois = 1.0; diferença = 0.0. Idêntica, porque a regra é a identidade.

## Flash no domínio dos casos de projeto

Os 7 fluidos do BOT nas condições dos 16 casos (T do caso; P do FWKO, do vaso e da condição padrão). **Não é um ponto só.**

| fluido | T (°C) | P (kPa) | conv. | VF molar | VF mássica | Z vapor | ρ vapor | MW líq | ρ líq (PR) | ρ líq (mist. ideal) | razão |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Early Life | 35,0 | 2.500 | sim | 0,6233 | 0,1847 | 0,9188 | 26,824 | 184,49 | 474,03 | 814,17 | 0,582 |
| Early Life | 35,0 | 700 | sim | 0,7304 | 0,2313 | 0,9735 | 7,576 | 243,00 | 473,39 | 858,84 | 0,551 |
| Early Life | 35,0 | 200 | sim | 0,7743 | 0,2595 | 0,9913 | 2,249 | 279,60 | 470,63 | 876,07 | 0,537 |
| Early Life | 35,0 | 101 | sim | 0,7902 | 0,2733 | 0,9953 | 1,171 | 295,17 | 468,50 | 881,52 | 0,531 |
| Early Life | 45,0 | 2.500 | sim | 0,6410 | 0,1929 | 0,9246 | 26,216 | 191,63 | 471,17 | 820,28 | 0,574 |
| Early Life | 45,0 | 700 | sim | 0,7395 | 0,2376 | 0,9752 | 7,431 | 249,47 | 470,67 | 861,98 | 0,546 |
| Early Life | 45,0 | 200 | sim | 0,7816 | 0,2665 | 0,9918 | 2,216 | 286,20 | 467,67 | 878,28 | 0,532 |
| Early Life | 45,0 | 101 | sim | 0,7974 | 0,2813 | 0,9955 | 1,157 | 302,38 | 465,30 | 883,59 | 0,527 |
| Early Life | 50,0 | 2.500 | sim | 0,6490 | 0,1967 | 0,9273 | 25,926 | 195,05 | 469,75 | 823,05 | 0,571 |
| Early Life | 50,0 | 700 | sim | 0,7438 | 0,2407 | 0,9760 | 7,364 | 252,64 | 469,29 | 863,44 | 0,544 |
| Early Life | 50,0 | 200 | sim | 0,7852 | 0,2702 | 0,9920 | 2,201 | 289,56 | 466,15 | 879,35 | 0,530 |
| Early Life | 50,0 | 101 | sim | 0,8011 | 0,2855 | 0,9956 | 1,150 | 306,11 | 463,66 | 884,63 | 0,524 |
| Early Life | 55,0 | 2.500 | sim | 0,6565 | 0,2005 | 0,9299 | 25,646 | 198,38 | 468,34 | 825,67 | 0,567 |
| Early Life | 55,0 | 700 | sim | 0,7480 | 0,2439 | 0,9767 | 7,300 | 255,77 | 467,89 | 864,84 | 0,541 |
| Early Life | 55,0 | 200 | sim | 0,7888 | 0,2739 | 0,9922 | 2,187 | 292,97 | 464,60 | 880,41 | 0,528 |
| Early Life | 55,0 | 101 | sim | 0,8047 | 0,2899 | 0,9957 | 1,145 | 309,94 | 461,98 | 885,67 | 0,522 |
| Early Life | 60,0 | 2.500 | sim | 0,6635 | 0,2041 | 0,9323 | 25,376 | 201,62 | 466,92 | 828,13 | 0,564 |
| Early Life | 60,0 | 700 | sim | 0,7521 | 0,2471 | 0,9774 | 7,240 | 258,88 | 466,47 | 866,19 | 0,539 |
| Early Life | 60,0 | 200 | sim | 0,7924 | 0,2778 | 0,9924 | 2,174 | 296,44 | 463,01 | 881,46 | 0,525 |
| Early Life | 60,0 | 101 | sim | 0,8084 | 0,2944 | 0,9958 | 1,140 | 313,87 | 460,27 | 886,71 | 0,519 |
| Early Life | 65,0 | 2.500 | sim | 0,6702 | 0,2076 | 0,9346 | 25,116 | 204,79 | 465,51 | 830,47 | 0,561 |
| Early Life | 65,0 | 700 | sim | 0,7561 | 0,2503 | 0,9781 | 7,183 | 261,98 | 465,03 | 867,49 | 0,536 |
| Early Life | 65,0 | 200 | sim | 0,7959 | 0,2818 | 0,9926 | 2,163 | 299,97 | 461,40 | 882,50 | 0,523 |
| Early Life | 65,0 | 101 | sim | 0,8121 | 0,2990 | 0,9959 | 1,136 | 317,90 | 458,54 | 887,76 | 0,517 |
| Early Life | 75,0 | 2.500 | sim | 0,6826 | 0,2144 | 0,9389 | 24,629 | 210,93 | 462,66 | 834,78 | 0,554 |
| Early Life | 75,0 | 700 | sim | 0,7638 | 0,2569 | 0,9793 | 7,079 | 268,15 | 462,10 | 869,97 | 0,531 |
| Early Life | 75,0 | 200 | sim | 0,8031 | 0,2902 | 0,9929 | 2,143 | 307,28 | 458,10 | 884,57 | 0,518 |
| Early Life | 75,0 | 101 | sim | 0,8194 | 0,3087 | 0,9960 | 1,128 | 326,24 | 454,99 | 889,88 | 0,511 |
| Early Life | 90,0 | 2.500 | sim | 0,6991 | 0,2243 | 0,9445 | 23,977 | 219,71 | 458,31 | 840,50 | 0,545 |
| Early Life | 90,0 | 700 | sim | 0,7749 | 0,2673 | 0,9808 | 6,949 | 277,48 | 457,54 | 873,46 | 0,524 |
| Early Life | 90,0 | 200 | sim | 0,8139 | 0,3037 | 0,9933 | 2,121 | 318,85 | 452,95 | 887,70 | 0,510 |
| Early Life | 90,0 | 101 | sim | 0,8303 | 0,3241 | 0,9962 | 1,120 | 339,49 | 449,51 | 893,11 | 0,503 |
| Low CO2 | 35,0 | 2.500 | sim | 0,5353 | 0,1177 | 0,9227 | 21,914 | 178,94 | 506,68 | 794,79 | 0,638 |
| Low CO2 | 90,0 | 101 | sim | 0,7717 | 0,2510 | 0,9958 | 1,033 | 309,20 | 489,93 | 882,35 | 0,555 |
| Early Life Blend | 35,0 | 2.500 | sim | 0,6853 | 0,2472 | 0,9194 | 26,135 | 163,27 | 523,90 | 793,71 | 0,660 |
| Early Life Blend | 90,0 | 101 | sim | 0,8619 | 0,4002 | 0,9965 | 1,067 | 296,37 | 497,43 | 878,29 | 0,566 |
| Mid Life | 35,0 | 2.500 | sim | 0,8183 | 0,4347 | 0,9118 | 29,621 | 162,09 | 487,38 | 800,75 | 0,609 |
| Mid Life | 90,0 | 101 | sim | 0,9370 | 0,5805 | 0,9968 | 1,086 | 346,87 | 449,87 | 894,50 | 0,503 |
| Late Life | 35,0 | 2.500 | sim | 0,8837 | 0,5594 | 0,9078 | 32,087 | 178,76 | 472,19 | 822,11 | 0,574 |
| Late Life | 90,0 | 101 | sim | 0,9594 | 0,6620 | 0,9972 | 1,095 | 392,51 | 436,83 | 904,90 | 0,483 |
| High CO2 | 35,0 | 2.500 | sim | 0,8702 | 0,5316 | 0,9060 | 33,525 | 183,85 | 471,70 | 830,55 | 0,568 |
| High CO2 | 90,0 | 101 | sim | 0,9519 | 0,6334 | 0,9972 | 1,141 | 388,48 | 437,54 | 904,22 | 0,484 |
| Highest CO2 | 35,0 | 2.500 | sim | 0,8812 | 0,6318 | 0,8920 | 38,674 | 152,85 | 498,57 | 817,09 | 0,610 |
| Highest CO2 | 90,0 | 101 | sim | 0,9644 | 0,7432 | 0,9968 | 1,279 | 355,36 | 449,13 | 896,70 | 0,501 |

**Convergência: 224 de 224 condições** (100,0 %), cobrindo 7 composições × 8 temperaturas (35–90 °C) × 4 pressões (101–2.500 kPa). A tabela mostra um recorte; a contagem é do domínio inteiro.

## Composição das fases

Early Life a 35,0 °C e 2.500 kPa:

| componente | z | y (vapor) | x (líquido) | z recomposto |
|---|---|---|---|---|
| H2S | 0,000120 | 0,000130 | 0,000103 | 0,000120 |
| N2 | 0,002400 | 0,003663 | 0,000310 | 0,002400 |
| CO2 | 0,175696 | 0,221401 | 0,100056 | 0,175696 |
| C1 | 0,444191 | 0,644462 | 0,112748 | 0,444191 |
| C2 | 0,065899 | 0,076586 | 0,048212 | 0,065899 |
| C3 | 0,044899 | 0,035692 | 0,060136 | 0,044899 |
| iC4 | 0,007600 | 0,003875 | 0,013764 | 0,007600 |
| nC4 | 0,018100 | 0,007807 | 0,035133 | 0,018100 |
| iC5 | 0,005600 | 0,001341 | 0,012648 | 0,005600 |
| nC5 | 0,009300 | 0,001856 | 0,021620 | 0,009300 |
| C6 | 0,012500 | 0,001594 | 0,030549 | 0,012500 |
| C7 | 0,010300 | 0,000527 | 0,026473 | 0,010300 |
| C8 | 0,019300 | 0,000385 | 0,050602 | 0,019300 |
| C9 | 0,012200 | 0,000094 | 0,032234 | 0,012200 |
| C10 | 0,014300 | 0,000043 | 0,037895 | 0,014300 |
| C11 | 0,012200 | 0,000014 | 0,032367 | 0,012200 |
| C12 | 0,011100 | 0,000005 | 0,029461 | 0,011100 |
| C13 | 0,011200 | 0,000002 | 0,029732 | 0,011200 |
| C14 | 0,009400 | 0,000001 | 0,024955 | 0,009400 |
| C15 | 0,009100 | 0,000000 | 0,024159 | 0,009100 |
| C16 | 0,007100 | 0,000000 | 0,018850 | 0,007100 |
| C17 | 0,005700 | 0,000000 | 0,015133 | 0,005700 |
| C18 | 0,006300 | 0,000000 | 0,016726 | 0,006300 |
| C19 | 0,005500 | 0,000000 | 0,014602 | 0,005500 |
| C20+ | 0,070499 | 0,000000 | 0,187172 | 0,070499 |
| Benzene | 0,004300 | 0,000432 | 0,010702 | 0,004300 |
| Toluene | 0,000500 | 0,000019 | 0,001296 | 0,000500 |
| Ethylbenzene | 0,000900 | 0,000015 | 0,002364 | 0,000900 |
| o-Xylene | 0,000800 | 0,000011 | 0,002105 | 0,000800 |
| m-Xylene | 0,001500 | 0,000022 | 0,003947 | 0,001500 |
| p-Xylene | 0,001500 | 0,000023 | 0,003945 | 0,001500 |

A última coluna é β·y + (1−β)·x: fecha com z componente a componente (há teste).

## O que NÃO é confiável para o processo

| grandeza | situação | consequência |
|---|---|---|
| cp de gás ideal (Cp_ig) dos pseudo-componentes | BLOQUEADO — propriedade ausente, não estimada | h e cp das fases do fluido de poço ficam indisponíveis POR CONSTRUÇÃO: o pacote é montado sem Cp_ig, e o backend não expõe H_mass nem Cp_mass. VLE, Z, densidade, frações de fase e composições das fases não dependem de Cp_ig e estão disponíveis. |
| faixa de validade das Tabelas 1-3 (S e I) acima de ~C20 | extrapolação declarada | nenhuma sobre as propriedades entregues |
| densidade da fase LÍQUIDA do fluido de poço | retornada pelo backend, porém NÃO validada para uso de engenharia | rho da fase líquida do fluido de poço fica BLOQUEADA para consumo pelo processo. Z e rho da fase VAPOR não têm esse problema. A correção usual é a translação de volume de Péneloux, que exige um parâmetro de deslocamento por componente — outra entrada com fonte própria. |
| flash de componente PURO | não suportado pelo caminho atual | o serviço devolve estado com ok = False e a mensagem do backend, nunca exceção (há teste). Misturas, inclusive com traço de 1e-12 de pseudo-componente, funcionam. |

A distinção pedida, explicitamente:

- **propriedade ausente** — `h` e `cp`: não existem no pacote, porque não há Cp_ig com fonte. Não é um zero nem uma estimativa;
- **calculada dentro do domínio validado** — VLE, frações de fase, composições das fases, Z e ρ da fase **vapor**; e a caracterização (Tc, Pc, ω, SG), conferida contra as verificações internas do artigo e contra a densidade do BOT;
- **retornada pelo backend, porém extrapolada / não validada** — ρ da fase **líquida** (PR sem translação de volume, razão 0,541 contra a mistura ideal) e, no serviço de hidrocarboneto, `k` da fase líquida. Ficam expostas com o método ao lado e com aviso, e **não podem ser promovidas a propriedade de projeto**.

