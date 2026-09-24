"""Gravação do arquivo de ajustes (`ajustes_pfd.toml`, esquema 2) a partir da forma
canônica de pfd/ajustes.py. TOML determinístico: ordem dada pela forma canônica, floats em
`repr` (ida e volta exata), sem data, hora nem caminho de saída. A biblioteca padrão só lê
TOML; este escritor cobre o subconjunto do esquema (tabelas, listas de tabelas, strings,
números, booleanos e listas)."""
import math
import re
from pathlib import Path

from fpso_siz.pfd import ajustes as modelo
from fpso_siz.pfd.equipamento import ordem_chaves

NOME = "ajustes_pfd.toml"
CABECALHO = (
    "# fpso-siz — ajustes de entradas por equipamento/TAG (esquema 2).",
    "# Estado da sessão: modo de cada TAG, entradas do usuário (caso prevalece sobre geral),",
    "# valores importados, revisões e o que cada entrada substituiu. Gerado pelo fpso-siz;",
    "# pode ser editado. Formato: docs/esquemas/README.md.",
)
_BARE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_ESCAPES = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\t": "\\t", "\n": "\\n", "\f": "\\f", "\r": "\\r"}


def _chave(k):
    return k if _BARE.fullmatch(k) else _string(k)


def _string(s):
    out = []
    for ch in s:
        if ch in _ESCAPES:
            out.append(_ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _valor(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError(f"valor não finito {v!r} não pode ser gravado nos ajustes")
        return repr(v)
    if isinstance(v, str):
        return _string(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_valor(x) for x in v) + "]"
    raise TypeError(f"tipo não gravável nos ajustes: {type(v).__name__}")


def _lista_de_tabelas(v):
    return isinstance(v, list) and bool(v) and all(isinstance(x, dict) for x in v)


def _tabela(caminho, d, linhas):
    escalares = [(k, v) for k, v in d.items() if not isinstance(v, dict) and not _lista_de_tabelas(v)]
    for k, v in escalares:
        linhas.append(f"{_chave(k)} = {_valor(v)}")
    for k, v in d.items():
        if isinstance(v, dict):
            sub = [*caminho, k]
            # tabela que só agrupa subtabelas fica implícita; vazia precisa do cabeçalho
            if not v or any(not isinstance(x, dict) for x in v.values()):
                linhas += ["", "[" + ".".join(_chave(x) for x in sub) + "]"]
            _tabela(sub, v, linhas)
    for k, v in d.items():
        if _lista_de_tabelas(v):
            sub = [*caminho, k]
            for item in v:
                linhas += ["", "[[" + ".".join(_chave(x) for x in sub) + "]]"]
                _tabela(sub, item, linhas)


def texto(canonico):
    linhas = list(CABECALHO)
    _tabela([], canonico, linhas)
    return "\n".join(linhas) + "\n"


def forma_canonica(ajustes, contexto):
    ordens = {e.id: ordem_chaves(e) for e in ajustes.todos()}
    return modelo.canonico(ajustes, contexto.identidade(), ordens)


def gravar(ajustes, contexto, caminho):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto(forma_canonica(ajustes, contexto)), encoding="utf-8")
    return caminho
