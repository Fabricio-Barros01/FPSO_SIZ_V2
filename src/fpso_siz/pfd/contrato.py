"""Contrato das propriedades de fluido (F13): config/pfd/contrato_propriedades.toml.

Declara, por grandeza, a regra do TAG que a produz, a unidade, a condição, a função de
pfd/fluidos.py, a fonte e a validade. `conferir()` prova que o contrato descreve o código
(regra existe, função existe, fonte citada existe em fluidos.toml, unidade é a do descritor
do método que a consome); nenhum número é recalculado.
"""
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd import fluidos
from fpso_siz.pfd.entradas import REGRAS, especificacoes
from fpso_siz.pfd.tags import tags


def descritores():
    return carregar("pfd/contrato_propriedades.toml")


def _fonte(chave):
    secao, campo = chave.split(".")
    return fluidos.cfg()[secao][campo]


def fonte_de(grandeza):
    """Texto das referências da grandeza, lido de fluidos.toml."""
    return [_fonte(c) for c in descritores()[grandeza]["fonte"]]


def conferir():
    """Lista de divergências entre o contrato e o código (vazia = contrato válido)."""
    erros = []
    desc = descritores()
    for nome, d in desc.items():
        if d["regra"] not in REGRAS:
            erros.append(f"{nome}: regra {d['regra']!r} não existe")
        if not callable(getattr(fluidos, d["funcao"], None)):
            erros.append(f"{nome}: função fluidos.{d['funcao']} não existe")
        for f in d["fonte"]:
            try:
                _fonte(f)
            except KeyError:
                erros.append(f"{nome}: fonte {f!r} não está em fluidos.toml")
    por_regra = {d["regra"]: nome for nome, d in desc.items()}
    for t in tags():
        _, _, specs = especificacoes(t)
        for chave, regra in t.entradas.items():
            nome = por_regra.get(regra["regra"])
            if nome is None:
                continue
            if specs[chave].unit != desc[nome]["unidade"]:
                erros.append(f"{t.tag}.{chave}: o método espera {specs[chave].unit!r}, o contrato "
                             f"{nome} entrega {desc[nome]['unidade']!r}")
    return erros


def regras_de_propriedade():
    """Regras do TAG que produzem propriedade de fluido (as que o contrato deve cobrir)."""
    return sorted(r for r in REGRAS if r.startswith(("densidade", "viscosidade", "compressibilidade",
                                                     "condutividade", "cp_utilidade", "pressao_vapor")))
