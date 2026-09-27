# F13/Etapa 1 — correlação do lado tubo fora da faixa de Dittus-Boelter: fontes localizadas

Corrige o diagnóstico registrado na F10x/F13. A afirmação anterior era **"falta, no acervo,
correlação laminar do lado tubo com fonte"**. Ela está errada: o acervo tem duas vias
independentes, com equação, faixa de validade e correção de viscosidade na parede. O que
falta é o **exemplo numérico resolvido** exigido pelo aceite do projeto para virar caso-ouro.

Diagnóstico correto: **fonte encontrada; validação e implementação pendentes.** Nenhum ramo
novo foi implementado nesta entrega, e o `P-001` continua alarme aberto.

## 1. Branan — via primária (unidades de engenharia, projeto preliminar)

*Rules of Thumb for Chemical Engineers*, cap. 2 "Heat Exchangers", **pp. 40–41**. As quatro
equações formam um procedimento fechado para `h_i`, do laminar ao turbulento:

| Eq. | Página | Conteúdo | Faixa declarada |
|---|---|---|---|
| 2-9 | 40 | `T_w = t + (U_i/h_i)·(T − t)` — temperatura média da parede interna | — (iterativa) |
| 2-10 | 40 | **Hausen**: `h_i = (k/d_i)·[3,66 + 0,0668·N_Re·N_Pr·(d_i/L) / (1 + 0,40·[N_Re·N_Pr·(d_i/L)]^(2/3))]·(µ/µ_w)^0,14` | `N_Re ≤ 2000` |
| 2-11 | 41 | **Sieder-Tate**: `h_i = 0,023·(k/d_i)·N_Re^0,8·N_Pr^(1/3)·(µ/µ_w)^0,14` | `N_Re ≥ 10.000` |
| 2-12 | 41 | **Transição** (interpolação): `(h_i)_T = h_i,lam + (h_i,turb − h_i,lam)·(N_Re − 2000)/8000` | `2000 < N_Re < 10.000` |

Pontos que o texto fixa e que a implementação precisa respeitar:

- As propriedades de 2-10 são avaliadas na **temperatura média do fluido**, e `µ_w` na
  **temperatura de parede** — daí a 2-9 e o laço: o texto manda supor `h_i` (chute inicial
  "cerca de 2.000 W/m²·°C ou 400 Btu/ft²·°F"), calcular `T_w`, reavaliar `µ_w` e iterar
  "uma ou duas vezes" até o valor suposto igualar o calculado.
- Em 2-10, `L` é o comprimento **do caminho de um tubo**, não o do feixe: o texto é
  explícito ("se há 10 tubos por passe, `L` é o comprimento total dividido por 10").
- A 2-12 é declarada como *"a plausible equation"*, e o item 4 recomenda **evitar** a região
  de transição (coeficiente imprevisível, possibilidade de oscilação de escoamento). Ela
  serve de limite, não de garantia: o texto diz que o coeficiente de transição é
  **limitado** pelo laminar e pelo turbulento.
- Fonte primária das três correlações, citada pelo Branan como referência [2]:
  Bell K., Mueller A., *Wolverine Engineering Data Book*, Wolverine Tube, Huntsville.
  Está **fora** do acervo local.

## 2. Saari — via secundária (livro-texto, mesma origem de `golden_saari`)

*Heat Exchanger Dimensioning*, §6.3, **pp. 68–72**. Confirma a mesma física por outro
caminho e é a fonte já usada pelo método casco-e-tubos do projeto:

| Eq. | Página | Conteúdo | Faixa declarada |
|---|---|---|---|
| 6.26 | 69 | Gnielinski (versão simplificada, propriedades em `T_b`) | `Re ≥ 3000`, ± 10 % |
| 6.27 | 69 | Média ponderada laminar/turbulento, `γ = 1,33 − Re/6000` (Shah 2003, p. 481) | regime de transição |
| 6.28 | 70 | Laminar plenamente desenvolvido, tubo circular: `Nu = 4,36` (q" constante) ou `3,66` (T_s constante) | laminar, fora do comprimento de entrada |
| Tab. 6.2 | 70–71 | `Nu` laminar de geometrias não circulares (Holman 1989) | — |
| 6.31 | 71 | **Sieder-Tate laminar**: `Nu_x = 1,86·Gz^(1/3)·(µ/µ_s)^0,14`, `Gz = (x/d_h)·Re·Pr` (Incropera 2002, p. 490) | `T_s` constante, comprimento de entrada |
| 6.32 | 71 | Bhatti & Shah: `Nu = C·(C_f·Re)^(1/3)·Gz^(1/3)`, `C` na Tab. 6.3 (Shah 2003, p. 503) | `C_f` do escoamento desenvolvido conhecido |

O §6.3.1 também registra que a correlação de Gnielinski, embora útil abaixo do alcance
usual, **superestima `Nu` no regime de transição** — a razão pela qual Saari oferece a
6.27. Como na 2-10 do Branan, a 6.31 avalia as propriedades em `T_b` e `µ_s` na temperatura
de **superfície**: as duas vias exigem a temperatura de parede, não a dispensam.

### Errata aparente da 6.27 (a conferir na implementação)

Impressa como `Nu = γ·Nu_lam + (γ − 1)·Nu_turb`. Com `γ = 1,33 − Re/6000`, o segundo termo
seria **negativo** em toda a faixa de interesse (`γ < 1` para `Re > 1.980`), e o resultado
cairia abaixo do laminar. A forma consistente é `(1 − γ)`: aí a ponderação vale `Nu_lam` em
`Re ≈ 1.980` e `Nu_turb` em `Re ≈ 7.980`, faixa praticamente igual à da 2-12 do Branan
(2.000 a 10.000). Fica registrada como as erratas de Stewart & Arnold, de Saari e de Kemp
já registradas no projeto: quem conferir o teste contra o livro precisa saber por quê.

## 3. O que ainda falta para o aceite

Nenhuma das duas fontes publica **exemplo numérico resolvido** dessas equações:

- Branan remete o cálculo à planilha que acompanha o livro (aba **"Tubes htc"**, célula D7
  para o `h_i` suposto, D44 para o calculado) — a planilha não está no acervo.
- Saari não fecha exemplo numérico, o mesmo buraco já documentado em `golden_saari`.

Pelo aceite do projeto (caso-ouro com números impressos na fonte, como `golden_kemp` e
`golden_moran`), **a correlação não entra sem esse exemplo**. Referências autorizadas pelo
usuário (2026-09-26) para suprir a lacuna, a incorporar ao acervo quando chegarem:

1. Serth & Lestina, *Process Heat Transfer: Principles, Applications and Rules of Thumb* —
   exemplos resolvidos de Seider-Tate/Hausen com correção de viscosidade na parede.
2. Planilha suplementar do Branan (aba "Tubes htc") — valida exatamente as eq. 2-9 a 2-12,
   incluindo o laço da temperatura de parede.

## 4. Onde isso morde os alarmes

| TAG | Bloqueio | Re dos casos bloqueados | Faixa que cobriria |
|---|---|---|---|
| P-001 | óleo/óleo, lado tubo fora de Dittus-Boelter (após resolver o domínio de F com 1 passe) | 1.661 a 4.947 | 2-10 (laminar, parte dos casos) **e** 2-12 (transição) |
| P-002 | turndown profundo, BOT 06 (263 kW = 3,6 % da carga de projeto) | ≈ 4.200 | 2-12 (transição) |
| P-003 | baixa carga, BOT 04/05/06 (1.148, 498 e 129 kW contra 26.506 kW) | < 10⁴ | 2-12 (transição), e 2-10 se algum caso cair em `Re ≤ 2000` |

O P-001 é o único que atravessa a fronteira `Re = 2000`: precisa dos **dois** ramos.
O comprimento de tubo do P-003 (14,1 m no melhor feixe, contra 6 m) **não** é resolvido por
correlação nenhuma — é bloqueio de geometria, tratado no estudo de cascos em série.

## 5. Requisitos registrados para a futura implementação

Quando o exemplo numérico existir, a implementação precisa (nenhum destes pontos é opcional):

1. **Ramo próprio do método**, não extrapolação de Dittus-Boelter. Os três regimes são
   selecionados por `Re` com as fronteiras da fonte (2.000 e 10.000), nunca por ajuste.
2. **Temperatura de parede pela eq. 2-9**, com o laço do texto. É proibido assumir
   `(µ/µ_w) = 1` em silêncio: sem `T_w` não há `µ_w`, e sem `µ_w` a correlação não está
   avaliada — isso é lacuna de entrada ou inviabilidade com mensagem, não fator unitário.
3. **Faixas não cobertas continuam não cobertas.** Fora de `Re ≤ 2000`, `2000 < Re < 10⁴` e
   `Re ≥ 10⁴` com as demais faixas da fonte (`Pr`, `x/d_h`, `C_f` conhecido), o caso volta
   como inviabilidade com mensagem — nunca número.
4. **A transição é declarada imprevisível pela própria fonte.** Se o resultado do TAG passar
   a depender da 2-12, isso é registrado no rastro e no MC como tal, com a recomendação do
   item 4 da p. 41 (evitar a região), e não como projeto fechado.
5. `L` da eq. 2-10 é o caminho de um tubo (comprimento total ÷ tubos por passe), coerente com
   a geometria do candidato da varredura.
6. O caso-ouro cita página e número de equação, como os demais do projeto, e a errata da
   6.27 fica no cabeçalho do teste.

## 6. Efeito desta correção nos documentos

- `config/pfd/alarmes.toml`: os textos de P-001, P-002 e P-003 deixam de afirmar ausência de
  fonte e passam a citar Branan pp. 40–41 e Saari pp. 70–72, com a pendência do exemplo
  numérico.
- `docs/validacao/14-alarmes.md`: regenerado por `tools/investigar_alarmes.py` (o texto vem
  do TOML; nada é digitado no relatório).
- `docs/validacao/19-trocadores-premissas.md`: a pendência 3 muda de "depende de fonte em
  `references/`" para "depende de exemplo numérico para o caso-ouro".
- O estado do P-001 continua **lacuna metodológica**: a fonte não fecha o alarme; a
  implementação validada fecha.
