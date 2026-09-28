# 38 — Recombinação da Nota 4: condição padrão × condição do FWKO

Comparação **diagnóstica**, sem alteração de física, código ou número produtivo. Decide, pela
consistência com o BOT, a condição de referência que a nota 35 deixou em aberto. β, x e y
continuam `nao_validada`; os casos com lift (9, 11, 15, 16) aparecem só para informação e
seguem fora de qualquer ativação.

Cálculo feito pela API pública (`balanco.modelo.resolver_todos` + `termo.flash_tp`), com o
fluido de poço por tipo (Tab. 2.2.2.4), a ρ do óleo pela API e V_M da condição padrão; nenhum
script foi versionado.

## 1. As duas candidatas

| | **S — condição padrão** | **F — condição do FWKO** |
|---|---|---|
| flash de referência de z₀ | 15,6 °C; 101,3 kPa(a) | 2.500 kPa(a) (§2.7.1.2) e T do caso (Tab. 2.2.2.3, nota 1) |
| "Produced Gas" significa | todo o gás de solução, na condição padrão | o gás que sai do 1º estágio (FWKO), sem recirculações |
| gás da recombinação | `ṅ_g = Q_g/V_M` com y do flash padrão | `ṅ_g = Q_g/V_M` com y do flash no FWKO |
| óleo da recombinação | `ṅ_o = Q_o·ρ_o/MW_x` (x padrão = óleo morto) | ṅ_L de x_FWKO tal que a série x_FWKO → padrão dá `Q_o` de óleo morto (Nota 2) |
| reproduz por construção | Q_o e Q_g na condição padrão | Q_g na saída do FWKO e Q_o como óleo morto |

As duas fecham exatamente o que prometem (conferido: razão 1,0000 em todos os casos).

## 2. O que cada uma implica para a outra grandeza

| caso | fluido | GOR do BOT | S: gás do FWKO / Q_g | F: gás padrão total / Q_g | S: entrada do compressor (MSm³/d) | F: entrada do compressor (MSm³/d) | "Total Gas" do BOT | F: efeito de usar T do estado no lugar de T do caso |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Early Life | 419,3 | 90,4 % | 108,6 % | 10,848 | 12,000 | 12,000 | 0,00 % |
| 2 | Early Life | 419,3 | 88,6 % | 110,4 % | 10,630 | 12,000 | 12,000 | 0,34 % |
| 3 | Early Life Blend | 324,9 | 86,4 % | 114,3 % | 8,039 | 9,300 | 9,300 | 0,53 % |
| 4 | Early Life | 241,9 | 81,8 % | 118,4 % | 0,736 | 0,900 | 0,900 | 0,00 % |
| 5 | Low CO2 | 185,0 | 74,8 % | 125,6 % | 0,673 | 0,900 | 0,900 | 0,00 % |
| 6 | Mid Life | 720,0 | 90,0 % | 109,7 % | 0,810 | 0,900 | 0,900 | 0,00 % |
| 7 | Mid Life | 349,4 | 90,7 % | 110,0 % | 11,070 | 12,000 | 12,000 | 0,00 % |
| 8 | Mid Life | 524,1 | 92,0 % | 108,7 % | 11,196 | 12,000 | 12,000 | 0,42 % |
| 9 | Mid Life (lift) | 533,3 | 92,6 % | 107,9 % | 11,410 | 12,000 | 12,000 | 0,36 % |
| 10 | Late Life | 652,2 | 96,4 % | 103,7 % | 9,227 | 9,500 | 9,500 | 0,01 % |
| 11 | Late Life (lift) | 880,5 | 95,2 % | 105,2 % | 10,667 | 11,000 | 11,000 | 0,39 % |
| 12 | Late Life | 1.117,7 | 97,8 % | 102,2 % | 9,305 | 9,500 | 9,500 | 0,00 % |
| 13 | High CO2 | 963,2 | 97,5 % | 102,4 % | 9,071 | 9,300 | 9,300 | 0,00 % |
| 14 | High CO2 | 1.242,9 | 98,1 % | 101,9 % | 11,770 | 12,000 | 12,000 | 0,00 % |
| 15 | Highest CO2 (lift) | 1.270,8 | 97,7 % | 102,3 % | 6,898 | 7,000 | 7,000 | 0,00 % |
| 16 | Highest CO2 (lift) | 1.271,0 | 97,7 % | 102,3 % | 6,886 | 7,000 | 7,000 | 0,00 % |

"Entrada do compressor" = gás do FWKO + lift + transferido, a grandeza que a Nota 3 atribui ao
gás da tabela. A diferença entre S e F é o gás que sai **depois** do FWKO (degaseificadores e
tanque): de 2 % (alto GOR) a 25 % (caso 5, baixo GOR) do gás do caso.

## 3. Critérios de consistência com o BOT

| critério (fonte) | S | F |
|---|---|---|
| **"Total Gas" = entrada do compressor principal** (Tab. 2.2.2.3, Nota 3; Total = Produzido + Lift + Transferido em todas as linhas) | falha: a entrada fica 2–25 % abaixo do "Total Gas" | **exato** nos 16 casos, por construção |
| **Capacidade de 12 MSm³/d "at outlet of first stage separation (FWKO)"** (Tab. 2.5.2, nota 1) | nenhum caso atinge a capacidade declarada (máx. 11,77, caso 14) | casos 1, 2, 7, 8, 9 e 14 atingem exatamente 12,000 — o teto dos casos coincide com o teto declarado |
| **Recirculações somadas por fora** (Nota 3; Tab. 2.5.2 nota 1; §2.7.1.6; VRU → compressor) | o gás da VRU já estaria dentro do "Produced Gas" — dupla contagem se somado | o gás dos degaseificadores é adicional, como o BOT manda somar |
| **Separador de teste** (§2.2.3.3: dimensionado para o gás a 2.500 kPa(a); Tab. 2.2.3.1b) | — | as vazões de gás de teste são de separador a 2.500 kPa(a), com os mesmos GOR dos casos (Low CO2: 185,0 = caso 5; Early Life: 241 ≈ caso 4, 242) |
| **"a series of flashes"** (Nota 4, plural) | um flash basta | a série é necessária: FWKO → padrão para levar o líquido a óleo morto |
| **Óleo em "dead oil conditions"** (Nota 2) | natural | respeitado explicitamente (série até a condição padrão) |
| **GOR como razão de tanque** (convenção usual, **não** escrita no BOT) | natural | não é o GOR de tanque; o GOR de tanque sai 2–26 % maior |
| **Referência fixa, independente das variáveis de decisão** | sim | sim, **com T do caso** (Tab. 2.2.2.3). Com a T do estado (C-04) dependeria do reciclo e de η_F; a diferença é ≤ 0,53 % do gás, logo T do caso não custa precisão |

Sm³ não decide a questão: é unidade (15,6 °C, 101,3 kPa, §1.4.2) para qualquer corrente, não o
lugar da medição.

## 4. Recomendação

**F — recombinar na condição do FWKO: 2.500 kPa(a) e a temperatura do caso da Tab. 2.2.2.3**,
com o óleo levado a óleo morto pela série FWKO → condição padrão.

Fundamento: é a única leitura em que as quatro grandezas de gás que o BOT amarra entre si
fecham ao mesmo tempo — "Total Gas" (Nota 3), a capacidade de 12 MSm³/d na saída do FWKO
(Tab. 2.5.2), a regra de somar recirculações por fora e o dimensionamento do separador de
teste a 2.500 kPa(a). S só tem a seu favor a convenção de GOR de tanque, que o BOT não escreve,
e contradiz as três primeiras.

Grau de confiança: **médio-alto**. A Nota 3 está solta na tabela (docs/validacao/35, §1); a
recomendação se apoia no conjunto das evidências, não nela sozinha.

## 5. Consequências (para a próxima etapa, se aprovada)

1. O gás do SG-001 passa a ser o "Produced Gas" do BOT na condição do FWKO — próximo do que o
   balanço já põe em C-04; o gás dos degaseificadores sai do flash e é **adicional** (2–26 %
   do caso), em vez de ser subtraído do FWKO como hoje.
2. A massa de hidrocarboneto de entrada sobe 3–4 % em relação à C-01 atual (S subiria 1–2,5 %):
   o balanço usa hoje, para o gás, o MW do corte leve, não o do vapor de equilíbrio. A
   ativação muda a C-01; isso terá de ser justificado em `docs/validacao/` e rever a regressão.
3. A base molar do trem fica única (fim da discordância de 0,7–116 %).
4. O teto de P_D2 pela TVP (nota 37) tem de ser **recalculado** com z_F antes de qualquer uso.
5. β, x e y **não** são promovidos por esta nota: a promoção é o passo seguinte, depois de
   aprovada a recombinação.
6. Casos 9, 11, 15 e 16: fora da ativação (lift sem composição).
7. A capacidade da VRU (§2.7.3.8.9) não discrimina as leituras: o gás máximo dos
   degaseificadores (P-18/P-19 atuais) é de 1,20 MSm³/d em S e 1,13 em F.
