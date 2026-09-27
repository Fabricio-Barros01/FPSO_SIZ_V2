# FPSO_Siz_V2

Um programa que calcula **o tamanho dos equipamentos** que separam petróleo, água e gás a bordo
de um navio-plataforma, e que entrega essa conta em forma auditável: cada número com a equação
que o gerou e a fonte bibliográfica que autoriza a equação.

Esta página é para quem **não é da área**. Não é necessário saber engenharia química para
entender o que o software faz e como ele funciona.

---

## 1. O problema, em linguagem comum

Um **FPSO** é um navio-plataforma que fica parado sobre um campo de petróleo no mar. Ele produz,
trata e armazena o óleo até um navio aliviador levá-lo embora. A sigla vem do inglês: *Floating
Production, Storage and Offloading*.

O que sobe do poço **não é petróleo pronto**. É uma mistura suja e quente de três coisas:

- **óleo** — o produto que se quer vender;
- **água salgada** — vem do próprio reservatório, junto com o óleo;
- **gás** — dissolvido no óleo, sai quando a pressão cai.

Antes de guardar o óleo no tanque do navio, é preciso separar os três e entregar o óleo dentro de
uma **especificação** contratual: no máximo tanto de água, no máximo tanto de sal. Isso não
acontece sozinho. Exige uma sequência de equipamentos — vasos onde a mistura descansa e se separa
por gravidade, aquecedores que reduzem a viscosidade do óleo para a água conseguir descer,
resfriadores que devolvem o óleo à temperatura de estocagem, bombas que empurram a água retirada.

Alguém precisa decidir **de que tamanho** cada um desses equipamentos tem de ser. Um vaso curto
demais não dá tempo para a água separar; um vaso grande demais é aço, peso e espaço que o navio
não tem. É essa decisão que este programa calcula.

### Por que não basta uma conta só

Um FPSO não opera sempre igual. Ao longo dos anos de vida do campo, a vazão cai, a proporção de
água sobe, o gás muda de composição. O projeto precisa funcionar em **todos** esses regimes — no
dia de maior vazão e no dia de menor vazão.

Por isso o programa não recebe uma condição de operação: recebe **16 casos de projeto**, tirados
de um documento técnico público da Petrobras (a especificação `I-ET-3010.2K-1200-941-P4X-001_C`,
tabelas 2.2.2.3 e 2.2.2.4). O equipamento escolhido tem de atender aos 16 — ou o programa diz,
explicitamente, qual caso ele não atende e por quê.

---

## 2. O que o programa entrega

Da **mesma** conta saem três coisas, e essa é uma decisão de projeto do software:

| Saída | Para quem serve |
|---|---|
| **Memória de cálculo** (documento PDF) | o engenheiro que assina o projeto. Traz cada equação, cada número intermediário e a referência bibliográfica de onde a equação veio |
| **JSON** | outro programa que vá consumir os resultados |
| **CSV** | planilha, para conferir número a número |

Uma **memória de cálculo** é o documento que registra a conta de engenharia de forma que outra
pessoa possa repeti-la e discordar dela. Não é um relatório de resultados: é a prova do caminho.

As três saídas vêm do mesmo registro interno de cálculo — o programa não recalcula nada para
gerar o PDF. Se o número mudar no JSON, ele muda no PDF junto, por construção.

---

## 3. Como funciona, em quatro passos

**Passo 1 — Os casos entram.** Um arquivo descreve os 16 casos de projeto: vazões, temperaturas,
pressões, composição do fluido.

**Passo 2 — Balanço de massa e energia.** Antes de dimensionar qualquer equipamento, o programa
resolve para onde vai cada quilo e cada joule: quanto de óleo, água e gás passa em cada ponto da
planta, e quanto calor cada aquecedor e resfriador tem de trocar. É a contabilidade da planta —
nada é criado nem destruído, e o programa verifica isso.

**Passo 3 — Dimensionamento por envelope.** Aqui está a ideia central do software. Para cada
equipamento, o programa varre uma dimensão — por exemplo, o diâmetro de um vaso, milímetro a
milímetro — e, para cada valor, pergunta: *este tamanho atende a todos os casos ativos?* A
resposta é uma faixa de tamanhos admissíveis, o **envelope**. O programa então escolhe o menor
tamanho dentro dele, porque no mar peso e espaço custam.

**Passo 4 — As três saídas.** O registro do cálculo vira memória de cálculo, JSON e CSV.

---

## 4. A planta: onze equipamentos

Cada equipamento tem um **TAG**, que é o código que o identifica no diagrama da planta (é a
convenção da indústria: quem lê o desenho encontra o equipamento pelo TAG).

| TAG | O que é | O que faz, em linguagem comum |
|---|---|---|
| **SG-001** | Separador trifásico de água livre | O primeiro estágio. A mistura desacelera e, por gravidade, o gás sobe, a água desce e o óleo fica no meio |
| **P-001** | Pré-aquecedor óleo/óleo | Aproveita o calor do óleo já tratado, que está saindo quente, para aquecer o óleo que está entrando frio. Economia de energia |
| **P-002** | Aquecedor de óleo | Aquece o óleo com água quente, para baixar a viscosidade e a água conseguir se separar |
| **V-001**, **V-002** | Vasos desgaseificadores | Tiram o gás que ainda restava dissolvido no óleo |
| **TO-001** | Desidratador (pré-tratador eletrostático) | Usa campo elétrico para fazer as gotinhas de água se juntarem até ficarem pesadas o bastante para descer |
| **TO-002** | Dessalinizador | Mesmo princípio, um estágio depois: injeta-se água doce para lavar o sal, e o campo elétrico separa de novo |
| **P-003** | Resfriador de óleo | Devolve o óleo tratado à temperatura em que ele pode ser estocado no tanque |
| **B-001** | Bomba de transferência de óleo | Empurra o óleo tratado até o tanque de carga |
| **B-002**, **B-003** | Bombas de água produzida | Levam embora a água retirada nos dois tratadores |

---

## 5. Três regras que explicam o comportamento do programa

Estas três decisões explicam quase tudo o que o software faz — e o que ele **se recusa** a fazer.

### Nenhum número sem fonte

Todo coeficiente, toda faixa de validade, toda premissa fica num arquivo de configuração **com a
citação bibliográfica ao lado** — livro, capítulo, página, equação. Não há número solto no código.

A consequência é incomum e deliberada: se falta um dado, o programa **não estima**. Ele marca
aquela entrada como **lacuna** e diz o que precisa receber. Um valor inventado que parece
razoável é pior que uma lacuna declarada, porque atravessa o projeto sem ninguém notar.

### "Inviável" é uma resposta, não um erro

Quando nenhum tamanho de equipamento atende a todos os casos, o programa **não quebra** e não
força um resultado. Ele responde: *não há solução*, e diz **qual restrição impediu** e por quanto.

Isso é um resultado de engenharia legítimo. Dizer "este trocador de calor não cabe no navio" é
informação de projeto; entregar um número que não atende é defeito.

### Refatoração não muda número

O programa é a reescrita, em Python, de uma versão anterior escrita em outra linguagem (Julia).
Os resultados daquela versão ficaram congelados como **oráculo**: um conjunto de arquivos de
referência que os testes comparam a cada mudança, número por número. Melhorar a organização do
código é permitido; mudar um resultado sem justificativa escrita, não.

Existem hoje **1.177 testes automatizados**, e mudar um número exige documentar por quê em
`docs/validacao/`.

---

## 6. Em que ponto o projeto está

Dos onze equipamentos, **dez estão dimensionados**.

O que falta é o **P-001**, o pré-aquecedor óleo/óleo — e a razão é física, não do programa. Ele
troca calor entre dois óleos viscosos, e óleo viscoso escoando devagar é um mau condutor de calor:
nos casos de baixa vazão a capacidade de troca do equipamento satura (cerca de 25 W por metro
quadrado e por grau de diferença de temperatura) muito abaixo do que o serviço pedido exige. Para
dar conta, o equipamento precisaria de uma área de troca absurda — o cálculo pede tubos de 434
metros de comprimento, contra um limite prático de seis metros.

O programa **diz isso com número**, em vez de entregar um equipamento que não funcionaria. Essa é
exatamente a regra da seção anterior em funcionamento.

---

## 7. Como rodar

O ambiente é declarado no repositório (Nix + uv), então não há lista de dependências para
instalar à mão:

```bash
nix develop          # entra no ambiente com tudo o que o programa precisa
uv sync              # instala as bibliotecas Python
```

Depois:

```bash
# assistente interativo: pergunta o que você quer e conduz
uv run fpso-siz

# balanço de massa e energia dos 16 casos
uv run fpso-siz balanco --casos design_cases_bot.json --saida saida/

# dimensiona a planta inteira, TAG por TAG
uv run fpso-siz pfd --casos design_cases_bot.json --saida saida/pfd

# um equipamento só, com memória de cálculo em PDF
uv run fpso-siz dimensionar --tag V-001 --casos design_cases_bot.json \
    --auto-balanco --saida saida/tag --mc --pdf

# lista as premissas do projeto com a fonte de cada uma
uv run fpso-siz premissas
```

Rodar os testes:

```bash
uv run pytest -n 4 --dist loadscope     # cerca de dez minutos
```

---

## 8. Onde ler mais

| Arquivo | O que tem |
|---|---|
| [`SPRINTS.md`](SPRINTS.md) | o estado real do projeto, fase por fase, com o que foi decidido e por quê. É a fonte de verdade |
| [`docs/validacao/`](docs/validacao/) | um documento por verificação feita: de onde veio cada correlação, como foi conferida, que números deu |
| [`docs/decisoes/`](docs/decisoes/) | as decisões de arquitetura, registradas com a alternativa que foi descartada |
| [`CLAUDE.md`](CLAUDE.md) | o contrato técnico para quem for mexer no código: invariantes, regras de processo, comandos |

Os equipamentos são dimensionados por métodos da literatura técnica (Stewart & Arnold para vasos
de separação, Arnold para tratadores eletrostáticos, Moran para bombas, Saari com o método de
Bell-Delaware para trocadores de calor, Kemp para análise Pinch). Cada um está citado no ponto do
código que o usa.
