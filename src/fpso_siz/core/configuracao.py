"""Leitura dos TOML de dados do modelo, resolvidos em runtime dentro do pacote."""
import tomllib
from functools import cache
from importlib.resources import files


@cache
def carregar(nome):
    """Devolve o TOML `fpso_siz/config/<nome>` como dict (cacheado; não mutar)."""
    texto = files("fpso_siz.config").joinpath(nome).read_text(encoding="utf-8")
    return tomllib.loads(texto)


def listar(pasta):
    """Nomes dos TOML de `fpso_siz/config/<pasta>/`, em ordem alfabética."""
    return sorted(p.name for p in files("fpso_siz.config").joinpath(pasta).iterdir() if p.name.endswith(".toml"))


PREFIXO_EXEMPLO = "exemplo_"


@cache
def exemplos():
    """{nome: dict} dos arquivos de casos de exemplo (`config/exemplos/exemplo_<nome>.toml`,
    cópia literal dos exemplos do Julia), em ordem alfabética."""
    pasta = files("fpso_siz.config").joinpath("exemplos")
    nomes = sorted(p.name for p in pasta.iterdir() if p.name.startswith(PREFIXO_EXEMPLO) and p.name.endswith(".toml"))
    return {n.removeprefix(PREFIXO_EXEMPLO).removesuffix(".toml"): carregar(f"exemplos/{n}") for n in nomes}
