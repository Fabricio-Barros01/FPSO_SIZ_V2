"""Entradas do balanço: arquivo de casos (JSON do BOT), constantes, poços e premissas."""
import hashlib
import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

from fpso_siz.core.configuracao import carregar

CHAVES_CASOS = ("standard_conditions", "fwko_pressure_kPa", "cases", "fluid_compositions",
                "h2s_ppmv", "c20_pseudo")
CHAVES_CASO = ("num", "fluid_type", "T_C", "oil_sm3d", "liquid_sm3d", "produced_gas_sm3d",
               "lift_gas_sm3d", "total_gas_sm3d", "transferred_gas_sm3d")


@dataclass(frozen=True)
class DadosCasos:
    """Conteúdo do arquivo de casos, validado. `bruto` preserva o JSON original."""
    bruto: dict
    sha256: str
    origem: str

    @property
    def T_std_C(self):
        return self.bruto["standard_conditions"]["T_C"]

    @property
    def P_std_kPa(self):
        return self.bruto["standard_conditions"]["P_kPa"]

    @property
    def P_FWKO_kPa(self):
        return self.bruto["fwko_pressure_kPa"]

    @property
    def casos(self):
        return self.bruto["cases"]

    @property
    def composicoes(self):
        return self.bruto["fluid_compositions"]

    @property
    def c20(self):
        return self.bruto["c20_pseudo"]

    @property
    def h2s_ppmv(self):
        return self.bruto["h2s_ppmv"]

    def caso(self, num):
        for c in self.casos:
            if c["num"] == num:
                return c
        raise KeyError(f"caso {num} não existe em {self.origem}")


def carregar_casos(caminho):
    caminho = Path(caminho)
    bruto = caminho.read_bytes()
    d = json.loads(bruto)
    faltam = [k for k in CHAVES_CASOS if k not in d]
    if faltam:
        raise ValueError(f"{caminho.name}: faltam as chaves {faltam}")
    for c in d["cases"]:
        faltam = [k for k in CHAVES_CASO if k not in c]
        if faltam:
            raise ValueError(f"{caminho.name}: caso {c.get('num', '?')} sem {faltam}")
        if c["fluid_type"] not in d["fluid_compositions"]:
            raise ValueError(f"{caminho.name}: caso {c['num']} usa fluido sem composição: {c['fluid_type']}")
    return DadosCasos(d, hashlib.sha256(bruto).hexdigest(), caminho.name)


@dataclass(frozen=True)
class Standing:
    a: float
    b: float
    c_api: float
    c_T: float
    expoente: float
    kPa_por_psia: float
    Sm3_Sm3_por_scf_bbl: float


@dataclass(frozen=True)
class Constantes:
    R: float
    MW_ar: float
    T_ref_C: float
    api_a: float
    api_b: float
    rho_agua_15_6C: float
    standing: Standing
    MW: MappingProxyType
    cp0: MappingProxyType
    numerico: MappingProxyType


@cache
def constantes():
    t = carregar("constantes.toml")
    s = t["standing"]
    return Constantes(
        R=t["gas"]["R"], MW_ar=t["gas"]["MW_ar"], T_ref_C=t["referencia"]["T_C"],
        api_a=t["api"]["a"], api_b=t["api"]["b"], rho_agua_15_6C=t["api"]["rho_agua_15_6C"],
        standing=Standing(*(s[k] for k in ("a", "b", "c_api", "c_T", "expoente",
                                           "kPa_por_psia", "Sm3_Sm3_por_scf_bbl"))),
        MW=MappingProxyType(dict(t["componentes"]["MW"])),
        cp0=MappingProxyType(dict(t["componentes"]["cp0"])),
        numerico=MappingProxyType({k: v for k, v in t["numerico"].items() if k != "fonte"}),
    )


@dataclass(frozen=True)
class Poco:
    api: float
    viscosidade: tuple  # ((T °C, mu cP), ...), T crescente


@cache
def pocos():
    return MappingProxyType({
        nome: Poco(api=e["api"], viscosidade=tuple(tuple(par) for par in e["viscosidade"]))
        for nome, e in carregar("pocos.toml").items()
    })


def premissas(dados, **alteracoes):
    """Dicionário de premissas (equivalente ao PREM original), com P_FWKO do arquivo de
    casos. `alteracoes` sobrescreve valores (sensibilidade); chave desconhecida é erro."""
    p = {"P_FWKO": dados.P_FWKO_kPa}
    for nome, e in carregar("premissas.toml").items():
        if "valor" in e:
            p[nome] = e["valor"]
        else:  # carry: composto por conversões, na ordem do original
            p[nome] = e["gal_por_MMscf"] * e["m3_por_gal"] / e["m3_por_MMscf"]
    desconhecidas = set(alteracoes) - set(p)
    if desconhecidas:
        raise KeyError(f"premissas desconhecidas: {sorted(desconhecidas)}")
    p.update(alteracoes)
    return p
