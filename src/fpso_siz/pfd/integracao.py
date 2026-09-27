"""Fase 5 — integração do serviço termodinâmico ao processo, em MODO SOMBRA.

O flash do fluido de poço roda **em paralelo** nos pontos onde o equilíbrio deveria ser usado
(SG-001, V-001, V-002), e o resultado é registrado e comparado com o caminho legado. O processo
continua consumindo o legado: nada da planta muda nesta fase.

Três coisas moram aqui:

1. **o mapa de proveniência** (`config/pfd/integracao_termodinamica.toml`), que diz de onde vem
   cada propriedade hoje, de onde poderia vir, quem a consome e se está liberada;
2. **o guarda**: `exigir_liberada` recusa consumir propriedade bloqueada. Não é documentação —
   é erro em tempo de execução, para que nada entre em silêncio;
3. **os fechamentos**: para cada flash, z_i = β·y_i + (1−β)·x_i componente a componente, soma
   das composições, balanço molar e mássico, e desaparecimento de fase no monofásico. O erro é
   registrado **numericamente**, não só aprovado ou reprovado.

Nada aqui apresenta o estado como produzido por um modelo só: `proveniencia()` devolve, para
cada propriedade, a origem efetiva.
"""
import math
from dataclasses import dataclass, field

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import c_para_k, kpa_para_pa
from fpso_siz.pfd import estado_termodinamico as et

LIBERADA = "liberada"
SOMBRA = "sombra"
BLOQUEADA = "bloqueada"


def cfg():
    return carregar("pfd/integracao_termodinamica.toml")


def mapa():
    """{id da propriedade: declaração} — o mapa de proveniência, como está no TOML."""
    return {p["id"]: p for p in cfg()["propriedade"]}


def pontos():
    return cfg()["ponto"]


def status(propriedade):
    m = mapa()
    if propriedade not in m:
        raise ValueError(f"propriedade não mapeada: {propriedade!r}; mapeadas: {sorted(m)}")
    return m[propriedade]["status"]


def exigir_liberada(propriedade):
    """O guarda. Consumir propriedade não liberada é erro, não aviso.

    É isto que impede a substituição silenciosa: quem for ligar uma propriedade nova ao
    processo tem de passar por aqui e, para passar, tem de mudar o `status` no mapa — o que
    deixa rastro na revisão."""
    s = status(propriedade)
    if s != LIBERADA:
        d = mapa()[propriedade]
        raise ValueError(
            f"propriedade {propriedade!r} está {s.upper()} e não pode ser consumida pelo processo. "
            f"Origem atual: {d['origem_atual']}. Motivo: {d['motivo']}")
    return True


def proveniencia():
    """{propriedade: origem efetiva} — o que o processo realmente usa hoje.

    Existe para que nenhum relatório apresente um conjunto híbrido como se viesse de um modelo
    termodinâmico único."""
    return {i: (d["origem_proposta"] if d["status"] == LIBERADA else d["origem_atual"])
            for i, d in mapa().items()}


# ------------------------------------------------------------------ fechamentos
@dataclass(frozen=True)
class Fechamento:
    """Os erros de fechamento de um flash, em número. `ok` é derivado das tolerâncias."""
    erro_componente_max: float      # máx |z_i − (β·y_i + (1−β)·x_i)|
    componente_pior: str
    erro_soma_z: float              # |Σz − 1|
    erro_soma_y: float
    erro_soma_x: float
    erro_balanco_molar: float       # |Σβ − 1|
    erro_balanco_massico: float     # |Σβ_massica − 1|
    erro_recomposicao: float        # máx |z_i recomposto − z_i| (idem ao de componente)
    coerencia_molar_massica: float  # |β_massica − β·MW_v/MW_mistura|
    monofasico: bool
    fases: int

    @property
    def ok(self):
        c = cfg()["fechamento"]
        return (self.erro_componente_max <= c["tolerancia_componente"]
                and max(self.erro_soma_z, self.erro_soma_y, self.erro_soma_x) <= c["tolerancia_soma"]
                and max(self.erro_balanco_molar, self.erro_balanco_massico) <= c["tolerancia_soma"])


def conferir(estado):
    """Fechamento de um `EstadoTermodinamico` bifásico ou monofásico."""
    z = estado.z
    v, li = estado.vapor, estado.liquido
    soma_z = abs(sum(z.values()) - 1.0)
    if v is None or li is None:
        unica = v or li
        soma_u = abs(sum(unica.composicao.values()) - 1.0) if unica else 1.0
        # monofásico: a composição da fase é a global, e a fração é 1
        pior, erro = "", 0.0
        if unica:
            for k in z:
                e = abs(unica.composicao.get(k, 0.0) - z[k])
                if e > erro:
                    pior, erro = k, e
        return Fechamento(erro, pior, soma_z, soma_u if v else 0.0, soma_u if li else 0.0,
                          abs((unica.fracao_molar if unica else 0.0) - 1.0),
                          abs((unica.fracao_massica if unica else 0.0) - 1.0),
                          erro, 0.0, True, len(estado.fases))
    b = v.fracao_molar
    pior, erro = "", 0.0
    for k in z:
        rec = b * v.composicao.get(k, 0.0) + (1.0 - b) * li.composicao.get(k, 0.0)
        e = abs(rec - z[k])
        if e > erro:
            pior, erro = k, e
    mw_mist = b * v.MW + (1.0 - b) * li.MW
    coer = abs(v.fracao_massica - b * v.MW / mw_mist) if mw_mist > 0 else math.nan
    return Fechamento(erro, pior, soma_z, abs(sum(v.composicao.values()) - 1.0),
                      abs(sum(li.composicao.values()) - 1.0),
                      abs(v.fracao_molar + li.fracao_molar - 1.0),
                      abs(v.fracao_massica + li.fracao_massica - 1.0),
                      erro, coer, False, len(estado.fases))


# ------------------------------------------------------------------ modo sombra
@dataclass(frozen=True)
class Sombra:
    """Um ponto de equilíbrio avaliado em paralelo, sem alterar o processo."""
    caso: int
    ponto: str
    corrente: str
    T_C: float
    P_kPa: float
    estado: object
    fechamento: object = None
    legado: dict = field(default_factory=dict)


def _condicoes(r, ponto, prem):
    """(T em °C, P em kPa) do ponto de equilíbrio, lidos do próprio resultado do balanço."""
    sid = ponto["corrente_gas"]
    return r.T[sid], prem[ponto["pressao"]]


def rodar(resultados, dados, prem, composicoes=None, mws_plus=None):
    """[Sombra] de todos os casos × pontos de equilíbrio. Não toca em `resultados`."""
    comp = composicoes if composicoes is not None else dados.composicoes
    out = []
    for r in resultados:
        z = {k: v for k, v in comp[r.fluid].items() if v > 0}
        for ponto in pontos():
            t_c, p_kpa = _condicoes(r, ponto, prem)
            try:
                e = et.flash_poco(c_para_k(t_c), kpa_para_pa(p_kpa), z, mws_plus)
            except ValueError as err:
                out.append(Sombra(r.num, ponto["id"], ponto["corrente_gas"], t_c, p_kpa, None,
                                  None, {"erro": str(err)}))
                continue
            f = conferir(e) if e.ok else None
            out.append(Sombra(r.num, ponto["id"], ponto["corrente_gas"], t_c, p_kpa, e, f,
                              {"gas_legado_kg_s": r.streams[ponto["corrente_gas"]]["G"]}))
    return out
