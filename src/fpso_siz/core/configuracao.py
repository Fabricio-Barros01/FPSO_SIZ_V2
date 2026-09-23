"""Leitura dos TOML de dados do modelo, resolvidos em runtime dentro do pacote."""
import tomllib
from functools import cache
from importlib.resources import files


@cache
def carregar(nome):
    """Devolve o TOML `fpso_siz/config/<nome>` como dict (cacheado; não mutar)."""
    texto = files("fpso_siz.config").joinpath(nome).read_text(encoding="utf-8")
    return tomllib.loads(texto)
