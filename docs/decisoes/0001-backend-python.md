# ADR 0001 — Backend em Python, com o Julia como oráculo

Data: 2026-09-23. Estado: aceito.

## Contexto
O FPSO_Siz Julia está maduro (7 aplicações, 5.327 testes de núcleo, memoriais A4), mas o
sprint 10 dele, "artefato distribuível", esbarra no custo de distribuir Julia a terceiros:
sysimage, latência de compilação e instalação. Três outras motivações pesam: um port
posterior a C ou Java, que é mais direto a partir de Python; a familiaridade com o
ecossistema Python; e o fato de o balanço preliminar de referência já estar em Python
(`Balanço_Preliminar.py`), com port para Julia nunca feito.

## Decisão
Reescrever o backend em Python, como núcleo + CLI, sem HTTP nem GUI nesta fase:
1. primeiro o balanço preliminar, com paridade numérica contra o script original;
2. depois os 7 equipamentos, validados contra os casos-ouro e fixtures do Julia.

A arquitetura pode divergir do Julia. Quatro invariantes são mantidas (ver `CLAUDE.md`).
Java e C serão avaliados só por documento (F12), com PyInstaller/Nuitka como baseline.

## Consequências
- O Julia permanece como oráculo somente leitura até a paridade completa. A substituição
  como entregável do TCC é decidida depois da F10.
- numpy/scipy são permitidos, mas isolados em `_num.py`. O Julia usa só a stdlib, e cada
  ponto numpy/scipy vira um item de custo no port para C/Java.
- Os memoriais passam todos a ser LaTeX. No Julia, os de equipamento eram HTML/MathML.
