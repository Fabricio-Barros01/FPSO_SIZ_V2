"""Cabeçalho do modo interativo, na tradição do banner do OpenFOAM (moldura de comentário,
logotipo à esquerda, identificação à direita, bloco Exec/Data/Host/PID abaixo) com o
acabamento dos CLIs de agentes (degradê no logotipo, linha de dicas).

O acrônimo do logotipo é o do próprio equipamento: Floating Production Storage and
Offloading.
"""
from fpso_siz.output.terminal.estilo import ajustar, largura

LARGURA = 79
LOGO = (
    ("=========", ""),
    ("\\\\      /", "Floating"),
    (" \\\\    / ", "Production"),
    ("  \\\\  /  ", "Storage and"),
    ("   \\\\/   ", "Offloading"),
)
COLUNA_BARRA = 28
DICAS = "Dicas: escolha pelo número · Enter aceita o [padrão] · 0 volta · Ctrl+C sai"


def _logo(i, estilo):
    traco, palavra = LOGO[i]
    if not palavra:
        return "  " + estilo.paleta(i, traco)
    # "F loating": a inicial destacada e separada, como o "F ield" do OpenFOAM
    return "  " + estilo.paleta(i, traco) + "  " + estilo.destaque(palavra[:1]) + " " + estilo.paleta(i, palavra[1:])


def cabecalho(direita, execucao, estilo, colunas=LARGURA):
    """Texto do cabeçalho. `direita`: até 5 linhas ao lado do logotipo; `execucao`:
    pares (rótulo, valor) do bloco de execução. Terminal estreito → versão compacta."""
    if colunas < LARGURA:
        titulo = direita[1] if len(direita) > 1 else ""
        return "\n".join([estilo.destaque("FPSO_Siz") + " " + titulo,
                          *(f"{k}: {v}" for k, v in execucao), estilo.fraco(DICAS), ""])
    borda = "-" * (LARGURA - 4)
    linhas = [estilo.fraco("/*" + borda + "*\\")]
    for i in range(len(LOGO)):
        esq = ajustar(_logo(i, estilo), COLUNA_BARRA)
        dir_ = direita[i] if i < len(direita) else ""
        linhas.append((esq + estilo.fraco("|") + (" " + dir_ if dir_ else "")).rstrip())
    linhas.append(estilo.fraco("\\*" + borda + "*/"))
    rot = max((largura(k) for k, _ in execucao), default=0)
    linhas += [f"{ajustar(k, rot)} : {v}" for k, v in execucao]
    linhas += [estilo.fraco("─" * LARGURA), estilo.fraco(DICAS), ""]
    return "\n".join(linhas)
