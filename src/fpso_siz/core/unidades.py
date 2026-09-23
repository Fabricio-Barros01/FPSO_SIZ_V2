"""Fatores de conversão EXATOS. Único módulo autorizado a conter literais numéricos
fora de {0, 1, 2, 10} (invariante 2); tudo que é aproximado vive em TOML."""

SEGUNDOS_POR_DIA = 86400
ZERO_CELSIUS_K = 273.15


def c_para_k(t_c):
    return t_c + ZERO_CELSIUS_K


def c_para_f(t_c):
    """°C → °F na mesma ordem de operações do script de referência (T·9/5 + 32)."""
    return t_c * 9 / 5 + 32
