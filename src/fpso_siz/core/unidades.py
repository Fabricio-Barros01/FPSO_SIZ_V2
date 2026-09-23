"""Fatores de conversão EXATOS. Único módulo autorizado a conter literais numéricos
fora de {0, 1, 2, 10} (invariante 2); tudo que é aproximado vive em TOML."""

SEGUNDOS_POR_DIA = 86400
SEGUNDOS_POR_HORA = 3600
HORAS_POR_DIA = 24
POR_CENTO = 100
PPM_POR_UNIDADE = 1e6
ZERO_CELSIUS_K = 273.15


def c_para_k(t_c):
    return t_c + ZERO_CELSIUS_K


def c_para_f(t_c):
    """°C → °F na mesma ordem de operações do script de referência (T·9/5 + 32)."""
    return t_c * 9 / 5 + 32


def c_para_f_linear(t_c):
    """°C → °F na forma T·1,8 + 32 (a da auditoria independente do original)."""
    return t_c * 1.8 + 32


def m3h_para_m3s(q):
    return q / 3600.0


def cp_para_pas(mu):
    return mu / 1000.0


def kpa_para_pa(p):
    return p * 1000.0
