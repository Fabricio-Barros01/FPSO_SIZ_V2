# 35 — O que os 16 casos do BOT representam (etapa A do laço pressão → flash)

> **Situação (release do TCC, 2026-09-29):** decisão **tomada**. A recombinação da Nota 4 foi
> adotada na referência do FWKO (nota 38, aprovada em 2026-09-28) e está no caminho produtivo nos
> 12 casos sem gás de lift (nota 39). O texto abaixo é o registro da análise que a precedeu.

Nota de decisão (na data, pendente de aprovação do usuário). Não altera física nem número: registra a
leitura da fonte e a decisão que ela exige. Fonte: `docs/bot/I-ET-3010.2K-1200-941-P4X-001_C.pdf`
(rev. C), folhas 10–13 e 23.

## 1. Evidência da fonte

| item | texto (resumo fiel) | o que diz sobre os casos |
|---|---|---|
| §2.2.2.1–2.2.2.3 | o SELLER projeta "com as composições dadas abaixo" e simula "os premissas da Tab. 2.2.2.3 (regime permanente)" | os casos são **premissas de simulação**, não análises de fluido |
| Tab. 2.2.2.3 | 16 linhas: poço/fluido, T a jusante do choke, óleo, líquido, gás total, produzido, lift, transferido, modo de operação | cada caso combina **vazões + condição + tipo de fluido**; Total = Produzido + Lift + Transferido em todas as linhas |
| Tab. 2.2.2.4 | **sete** composições, uma por tipo de fluido (Early Life, Low CO2, Blend, Mid, Late, High CO2, Highest CO2), mais as propriedades dos C20+ (nota 3) | a composição é por **tipo de fluido**, não por caso |
| Nota 2 | "Oil flowrates are dead oil conditions"; Sm³ a 15,6 °C e 101,3 kPa(a) (§1.4.2) | a vazão de óleo é de óleo morto na condição padrão |
| **Nota 4** | "In order to achieve the desired GOR for each design case, simulation **may be adjusted** by subjecting Well Fluids through a series of flashes, and **recombining the gas and oil rates** to match the flowrates indicated in Table 2.2.2.3" | o próprio BOT **prevê** que a composição da Tab. 2.2.2.4 não reproduz o GOR de cada caso, e **autoriza** (não obriga) flash + recombinação para ajustá-la |
| Nota 3 | "Gas Flow rate at inlet Main Gas Compressor. Any recirculation of gas streams shall be added onto this Gas Flow Rate." | a nota **não está ancorada** em coluna nenhuma da tabela (conferido na imagem da folha 10); pela soma, casa com "Total Gas" |
| Tab. 2.5.2, nota 1 | capacidade de 12.000.000 Sm³/d "at outlet of first stage separation (FWKO)", recirculações somadas à parte | o teto dos casos (12 MSm³/d) é gás **na saída do FWKO** |

Medida que a F5.1 já fez (docs/validacao/34, §1): mesmo tipo de fluido em casos com GOR
diferente — Early Life em 419 (casos 1–2) e 242 Sm³/Sm³ (caso 4); Mid Life em 720, 349, 524 e 533
(casos 6–9). A razão GOR(flash de z₀)/GOR(BOT) vai de 0,62 a 2,16.

## 2. Interpretação

**Resposta: C — uma combinação.** Os casos são casos de projeto (envelopes: vazões, temperatura,
modo de operação e gás de lift/transferido combinados) construídos sobre **sete** composições de
base; o estado composicional de cada caso **não é dado**, mas o BOT dá o **procedimento** para
obtê-lo (Nota 4). O procedimento é subdeterminado em dois pontos, que a fonte não fecha:

1. **condição de referência da recombinação** — as "series of flashes" não têm pressão nem
   temperatura na fonte;
2. **o que "Produced Gas" mede** — (i) todo o gás de solução na condição padrão (GOR de tanque;
   leitura que o balanço usa hoje: G_F + G_D1 + G_D2 = G_in), ou (ii) o gás na saída do FWKO,
   sem as recirculações (leitura sustentada pela Nota 3 órfã e pela nota 1 da Tab. 2.5.2). A
   diferença entre as leituras é o gás dos degaseificadores: pelo flash de z₀ com P-18/P-19
   atuais, 0,1–1,2 MSm³/d, isto é, até ~10 % do gás do caso.

Portanto: **nem A** (a composição do caso não é dada e a de base não o reproduz), **nem D**
(a fonte diz explicitamente o que os casos são e como ajustá-los) — é **C com subdeterminação
declarada** da composição por caso.

## 3. Implicação para o flash

- Flashar z₀ (tipo de fluido) direto — o que o trem faz hoje — **não** é o estado de nenhum caso;
  é por isso que as duas bases molares possíveis discordam de 0,7 % a 116 %.
- Com a recombinação da Nota 4 **numa condição de referência fixa** (ainda a escolher, §5), a composição do caso
  `z_caso = (ṅ_g·y_ref + ṅ_o·x_ref)/(ṅ_g + ṅ_o)`, com `ṅ_g = Q_g/V_M` e `ṅ_o = Q_o·ρ_o/MW_x`,
  reproduz os dois volumes do BOT **por construção**, e a base molar fica única (a discordância
  0,7–116 % desaparece). Recombinar não é otimizar componentes: é a regra de mistura de duas
  fases de um mesmo flash, na proporção que o BOT fixa.
- A condição de referência **não pode** ser o próprio trem (P_D1, P_D2): a composição de
  alimentação passaria a depender das variáveis de decisão. Tem de ser fixa.

## 4. Implicação para os 16 casos

| grupo | casos | situação termodinâmica com a recombinação |
|---|---|---|
| sem lift | 1–8, 10, 12, 13, 14 | **avaliáveis** (12 casos) |
| com lift | 9, 11, 15, 16 | **não avaliáveis termodinamicamente com os dados disponíveis** na corrente C-01 inteira: o fluido produzido é recombinável, o gás de lift (20–31 % do gás de entrada) não tem composição (§2.3.3 só dá especificação) |
| gás transferido | 7–13, 15 | não entra no módulo de óleo (vai à planta de gás); sem efeito no trem |

Os 16 casos continuam sendo o **envelope de projeto** dos equipamentos pelo caminho vigente;
nenhum caso sai do dimensionamento por esta nota.

## 5. Decisão recomendada para o modelo (requer aprovação)

1. **Adotar a Nota 4 como regra declarada**, sem escolher ainda a condição de referência. Há duas
   candidatas, nenhuma prescrita pelo BOT:
   - **condição padrão** (15,6 °C; 101,3 kPa(a)) — coerente com a base Sm³ e com o óleo morto
     (Nota 2, §1.4.2), leitura (i) de "Produced Gas"; não prescrita pelo BOT;
   - **condição do FWKO** (2.500 kPa(a), T do caso) — alternativa compatível com a leitura (ii),
     em que "Produced Gas" é o gás do primeiro estágio; muda a partição do gás, e com ela o SG-001.

   A próxima etapa deve **testar a consistência das duas interpretações** (volumes do BOT
   reproduzidos, partição por estágio, efeito no envelope) **antes de qualquer ativação
   produtiva**. A escolha é premissa nova do usuário, com fonte (Nota 4) e parâmetro escolhido
   (a condição) — não é dado do BOT.
2. Casos 9, 11, 15 e 16: fluido produzido recombinado; o lift fica **fora** do flash e a
   lacuna continua declarada. Tratar o lift como gás que sai inteiro no SG-001 seria
   premissa nova — não adotada aqui.
3. Se a recombinação não for aprovada, a alternativa coerente com a fonte é separar
   **16 casos → envelope** de **casos representativos → estudo pressão/flash**, escolhidos
   onde z₀ já reproduz o caso (razão de GOR entre 0,95 e 1,15: casos 3, 4, 5, 6, 12, 13, 15, 16).
   Essa escolha é mais fraca: os representativos excluiriam os casos de maior vazão (1, 2, 7).
