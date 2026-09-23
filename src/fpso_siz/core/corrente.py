"""StreamState: a corrente trifásica na entrada de um equipamento, em SI
(port de src/types/stream.jl). Adaptador comum: todo método consome só isto."""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.parametros import parameter_specs
from fpso_siz.core.unidades import c_para_k, cp_para_pas, kpa_para_pa, m3h_para_m3s

STREAM_KEYS = ("q_oil", "q_water", "q_gas", "rho_oil", "rho_water", "rho_gas",
               "mu_oil", "mu_water", "mu_gas", "pressure", "temperature", "z")


@dataclass(frozen=True)
class PhaseProps:
    volumetric_flow: float  # m³/s
    density: float          # kg/m³
    viscosity: float        # Pa·s


@dataclass(frozen=True)
class StreamState:
    oil: PhaseProps
    water: PhaseProps
    gas: PhaseProps
    pressure: float         # Pa
    temperature: float      # K
    z_factor: float


def stream_from_field(*, q_oil_m3h, q_water_m3h, q_gas_m3h, rho_oil, rho_water, rho_gas,
                      mu_oil_cp, mu_water_cp, mu_gas_cp, p_kpa, t_celsius, z):
    return StreamState(PhaseProps(m3h_para_m3s(q_oil_m3h), rho_oil, cp_para_pas(mu_oil_cp)),
                       PhaseProps(m3h_para_m3s(q_water_m3h), rho_water, cp_para_pas(mu_water_cp)),
                       PhaseProps(m3h_para_m3s(q_gas_m3h), rho_gas, cp_para_pas(mu_gas_cp)),
                       kpa_para_pa(p_kpa), c_para_k(t_celsius), z)


def stream_parameters():
    """Descritores de corrente (config/stream.toml), comuns a todos os equipamentos."""
    return parameter_specs(carregar("stream.toml"))


def stream_from_case(vals, required=STREAM_KEYS):
    """Corrente a partir do dicionário de um caso expandido. Fase não exigida vira NaN
    (não zero: zero é valor plausível e esconderia o uso indevido)."""
    faltam = [k for k in required if k not in vals]
    if faltam:
        raise ValueError("caso sem as entradas de corrente: " + ", ".join(faltam))
    v = {k: float(vals[k]) if k in required else math.nan for k in STREAM_KEYS}
    return stream_from_field(q_oil_m3h=v["q_oil"], q_water_m3h=v["q_water"], q_gas_m3h=v["q_gas"],
                             rho_oil=v["rho_oil"], rho_water=v["rho_water"], rho_gas=v["rho_gas"],
                             mu_oil_cp=v["mu_oil"], mu_water_cp=v["mu_water"], mu_gas_cp=v["mu_gas"],
                             p_kpa=v["pressure"], t_celsius=v["temperature"], z=v["z"])
