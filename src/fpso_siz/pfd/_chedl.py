"""Porta única para o ecossistema ChEDL (thermo/chemicals, licença MIT).

Decisão do usuário (2026-09-23): thermo e chemicals são dependências diretas de runtime.
Como numpy/scipy em `_num.py`, só este módulo os importa, para que a troca (port a C/Java)
seja uma única camada. A importação é preguiçosa: thermo leva ~1 s para carregar e a
montagem das constantes do gás ~2 s, então nada disso acontece ao abrir a CLI, e as
constantes ficam em cache por conjunto de componentes.

Tudo aqui está em SI (K, Pa, kg/m³, Pa·s, W/(m·K), J/(kg·K)); a conversão para as
unidades do projeto é de `pfd/fluidos.py`.
"""
from functools import cache


def versoes():
    import chemicals
    import thermo
    return {"thermo": thermo.__version__, "chemicals": chemicals.__version__}


@cache
def _flash_gas(ids, eos, kij):
    import thermo
    from thermo.interaction_parameters import IPDB

    consts, props = thermo.ChemicalConstantsPackage.from_IDs(list(ids))
    classe = getattr(thermo, f"{eos}MIX")
    kw = dict(Tcs=consts.Tcs, Pcs=consts.Pcs, omegas=consts.omegas,
              kijs=IPDB.get_ip_asymmetric_matrix(kij, consts.CASs, "kij"))
    gas = thermo.CEOSGas(classe, kw, HeatCapacityGases=props.HeatCapacityGases)
    liq = thermo.CEOSLiquid(classe, kw, HeatCapacityGases=props.HeatCapacityGases)
    return thermo.FlashVL(consts, props, liquid=liq, gas=gas), props


def estado_gas(ids, zs, T, P, eos, kij):
    """Flash (T, P) da mistura e propriedades da fase vapor. `VF` < 1 indica que a EOS prevê
    condensação na condição (informativo: o gás de um vaso sai no ponto de orvalho)."""
    flash, props = _flash_gas(tuple(ids), eos, kij)
    r = flash.flash(T=T, P=P, zs=list(zs))
    g = r.gas
    if g is None:
        raise ValueError(f"a EOS não prevê fase vapor a T = {T} K e P = {P} Pa")
    return dict(Z=g.Z(), VF=r.VF, mu=g.mu(), k=g.k(), MW=g.MW(), cp=g.Cp_mass(),
                metodo_mu=props.ViscosityGasMixture.method, metodo_k=props.ThermalConductivityGasMixture.method,
                metodo_mu_puros=sorted({v.method for v in props.ViscosityGases}))


def agua_iapws(T, P):
    """Água pura: IAPWS-95 (ρ), IAPWS 2008 (μ) e IAPWS 2011 (k)."""
    from chemicals.iapws import iapws95_rho
    from chemicals.thermal_conductivity import k_IAPWS
    from chemicals.viscosity import mu_IAPWS

    rho = iapws95_rho(T=T, P=P)
    return dict(rho=rho, mu=mu_IAPWS(T, rho), k=k_IAPWS(T, rho))


def agua_saturada_iapws(T):
    """Água pura como líquido saturado a T (IAPWS-95; μ IAPWS 2008; k IAPWS 2011). Para
    circuitos cuja pressão não é conhecida: o efeito da pressão sobre o líquido é
    desprezado, sem arbitrar um valor para ela."""
    from chemicals.iapws import iapws95_rhol_sat
    from chemicals.thermal_conductivity import k_IAPWS
    from chemicals.viscosity import mu_IAPWS
    from thermo.electrochem import iapws95_Cpl_mass_sat

    rho = iapws95_rhol_sat(T)
    return dict(rho=rho, mu=mu_IAPWS(T, rho), k=k_IAPWS(T, rho), cp=iapws95_Cpl_mass_sat(T))


# blocos de colunas do banco de Laliberté (2009) no thermo: faixa de validade por propriedade
_FAIXAS_LALIBERTE = {"rho": "", "mu": ".1", "cp": ".2"}


def salmoura_laliberte(T, w, cas):
    """Solução aquosa de um sal (fração mássica w): ρ, μ e cp de Laliberté (2009), com a
    faixa de validade de cada correlação (T em °C, w) lida do próprio banco."""
    from thermo import electrochem as ec

    ws, cass = [w], [cas]
    valores = dict(rho=ec.Laliberte_density(T, ws, cass), mu=ec.Laliberte_viscosity(T, ws, cass),
                   cp=ec.Laliberte_heat_capacity(T, ws, cass))
    linha = ec.Laliberte_data.loc[cas]
    faixas = {p: (float(linha["Min T" + s]), float(linha["Max T" + s]), float(linha["Max w" + s]))
              for p, s in _FAIXAS_LALIBERTE.items()}
    return valores, faixas


# ------------------------------------------------------------------ serviço termodinâmico (F3)
# As funções abaixo servem `pfd/estado_termodinamico.py`. Elas NÃO substituem as de cima: as
# antigas continuam como estão, porque o PFD depende delas e a paridade é bit a bit.

def flash_vle(ids, zs, T, P, eos, kij):
    """Flash (T, P) completo: TODAS as fases previstas, com composição, fração e propriedades.

    Diferente de `estado_gas`, que devolve só a fase vapor, aqui volta o equilíbrio inteiro —
    é o que um serviço consumível pelo processo precisa entregar. Levanta ValueError se o
    backend não convergir; quem chama decide o que fazer (o serviço transforma em estado)."""
    flash, props = _flash_gas(tuple(ids), eos, kij)
    r = flash.flash(T=T, P=P, zs=list(zs))
    fases = []
    for nome, fase, beta, beta_m in _fases_de(r):
        fases.append(dict(nome=nome, fracao_molar=beta, fracao_massica=beta_m,
                          composicao=list(fase.zs), Z=fase.Z(), MW=fase.MW(),
                          rho=fase.rho_mass(), h=fase.H_mass(), cp=fase.Cp_mass(),
                          mu=fase.mu(), k=fase.k()))
    return dict(VF=r.VF, fases=fases, h=r.H_mass(),
                metodos=dict(mu_gas=props.ViscosityGasMixture.method,
                             k_gas=props.ThermalConductivityGasMixture.method,
                             mu_liquido=props.ViscosityLiquidMixture.method,
                             k_liquido=props.ThermalConductivityLiquidMixture.method))


def _fases_de(r):
    """[(nome, fase, fração molar, fração mássica)] do resultado, na ordem vapor → líquidos."""
    betas, betas_m = list(r.betas), list(r.betas_mass)
    out, i = [], 0
    if r.gas is not None:
        out.append(("vapor", r.gas, betas[i], betas_m[i]))
        i += 1
    for j, liq in enumerate(r.liquids):
        nome = "liquido" if j == 0 else f"liquido{j}"
        out.append((nome, liq, betas[i], betas_m[i]))
        i += 1
    return out


def agua_iapws_completa(T, P):
    """Água pura pela fase IAPWS-95 do thermo: acrescenta cp e h ao que `agua_iapws` já dá.

    rho, mu e k saem numericamente IGUAIS aos de `agua_iapws` (mesma norma; conferido por
    teste), então o serviço não introduz uma segunda verdade para a água."""
    from thermo.phases import IAPWS95Liquid

    ph = IAPWS95Liquid(T=T, P=P, zs=[1.0])
    return dict(rho=ph.rho_mass(), mu=ph.mu(), k=ph.k(), cp=ph.Cp_mass(), h=ph.H_mass(),
                MW=ph.MW())
