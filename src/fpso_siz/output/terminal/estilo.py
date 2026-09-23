"""Estilo de terminal: cor ANSI opcional, números pt-BR e tabelas alinhadas.

Cor só quando a saída é um terminal (ou FORCE_COLOR), nunca com NO_COLOR ou TERM=dumb:
arquivo, pipe e teste recebem texto puro.
"""
import math
import os
import re

from fpso_siz.output.latex.formatacao import br

ANSI = re.compile(r"\x1b\[[0-9;]*m")
TRAVESSAO = "—"
# degradê ciano → violeta (paleta de 256 cores), uma cor por linha do logotipo
GRADIENTE = (51, 45, 39, 33, 69, 105, 141)
SIMBOLO = {"ok": "✓", "erro": "✗", "neutro": " "}


class Estilo:
    def __init__(self, cor=False):
        self.cor = cor

    @classmethod
    def para(cls, stream, env=None):
        env = os.environ if env is None else env
        if env.get("NO_COLOR"):
            return cls(False)
        if env.get("FORCE_COLOR"):
            return cls(True)
        tty = getattr(stream, "isatty", lambda: False)()
        return cls(bool(tty) and env.get("TERM") != "dumb")

    def _sgr(self, codigo, s):
        return f"\x1b[{codigo}m{s}\x1b[0m" if self.cor and s else s

    def negrito(self, s):
        return self._sgr("1", s)

    def fraco(self, s):
        return self._sgr("2", s)

    def ok(self, s):
        return self._sgr("32", s)

    def erro(self, s):
        return self._sgr("31", s)

    def aviso(self, s):
        return self._sgr("33", s)

    def destaque(self, s):
        return self._sgr("1;36", s)

    def paleta(self, i, s):
        return self._sgr(f"38;5;{GRADIENTE[i % len(GRADIENTE)]}", s)

    def status(self, st):
        """Símbolo colorido do status de um ResultField (ok | erro | neutro)."""
        s = SIMBOLO.get(st, " ")
        return self.ok(s) if st == "ok" else self.erro(s) if st == "erro" else s


def largura(s):
    return len(ANSI.sub("", s))


def ajustar(s, n, direita=False):
    falta = max(n - largura(s), 0)
    return " " * falta + s if direita else s + " " * falta


def num(v, casas=2):
    """Número pt-BR com casas fixas; texto passa direto; None/NaN/Inf viram travessão."""
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return TRAVESSAO
    return br(v, casas)


def sig(v, n=6):
    """Número com n algarismos significativos, vírgula decimal (rastro de cálculo)."""
    if isinstance(v, str):
        return v
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return TRAVESSAO
    return f"{v:.{n}g}".replace(".", ",")


def _numerico(s):
    t = ANSI.sub("", s).strip()
    return bool(t) and bool(re.fullmatch(r"[-+]?[\d.,]+(e[-+]?\d+)?|—", t))


def tabela(cabecalho, linhas, estilo, recuo="  "):
    """Linhas de texto de uma tabela alinhada; colunas numéricas à direita."""
    colunas = list(zip(cabecalho, *linhas)) if linhas else [(c,) for c in cabecalho]
    larg = [max(largura(c) for c in col) for col in colunas]
    direita = [bool(linhas) and all(_numerico(c) for c in col[1:]) for col in colunas]
    sep = "  "
    out = [recuo + estilo.negrito(sep.join(ajustar(c, w, d) for c, w, d in zip(cabecalho, larg, direita)).rstrip()),
           recuo + estilo.fraco(sep.join("─" * w for w in larg))]
    out += [recuo + sep.join(ajustar(c, w, d) for c, w, d in zip(li, larg, direita)).rstrip() for li in linhas]
    return out
