"""F8 na planta: a rede térmica do pré-aquecedor, montada do balanço (config/pfd/pinch.toml).

O balanço já cruza duas correntes no P-001 — o óleo vivo que sai do SG-001, que precisa ser
aquecido até a temperatura de tratamento, e o óleo tratado que vai para o cargo tank, que
precisa ser resfriado até a temperatura de estocagem. A Análise Pinch responde, sobre essas
mesmas correntes, **quanto de utilidade quente e fria a rede exige no mínimo** — e a comparação
com as cargas que o balanço realizou (Q_pre, Q_H, Q_C) diz se o arranjo do BOT alcança o alvo.

Duas decisões que fazem a pergunta ser honesta:

- o DESTINO de cada corrente é a premissa (T_trat, T_store), não a temperatura que o balanço
  realizou: usar a realizada embutiria o arranjo na resposta;
- o ΔTmin é a própria premissa P-32 (`dT_app`) do pré-aquecedor, e não um valor novo: com outro
  ΔTmin as duas coisas comparadas seriam redes diferentes.

Nada aqui é física nova nem número suposto: as capacidades e temperaturas vêm do balanço, os
alvos vêm de `analysis/pinch.py`, e nenhuma corrente é nomeada no código — as correntes, os
destinos e as cargas comparadas são declarados no TOML.
"""
import math
from dataclasses import dataclass

from fpso_siz.analysis import pinch as pa
from fpso_siz.core.configuracao import carregar
from fpso_siz.pfd.entradas import cfg as cfg_pfd


def cfg():
    return carregar("pfd/pinch.toml")


SENTIDOS = {"aquecer": 1.0, "resfriar": -1.0}


@dataclass(frozen=True)
class RedeCaso:
    """A rede de um caso do balanço: as correntes, o ΔTmin e os alvos, mais as cargas que o
    balanço realizou naquele caso."""
    num: int
    nome: str
    streams: tuple
    omitidas: tuple             # ((rótulo, motivo), ...) correntes sem exigência neste caso
    dt_min: float
    tabela: object              # PinchResult (inviável se a rede não se aplica ao caso)
    curvas: object              # CompositeCurves
    realizado: dict             # {papel: carga do balanço, em kW}

    @property
    def aplicavel(self):
        return self.tabela.feasible


def correntes_do_caso(r, prem):
    """([ThermalStream], [(rótulo, motivo)]) do caso: entrada do balanço → destino da premissa,
    com o CP do balanço. Corrente cuja exigência JÁ está atendida no caso (o destino é piso para
    quem aquece e teto para quem resfria) não entra na rede: entra na lista de omitidas, com o
    motivo declarado. Inverter o seu sentido inventaria uma carga que o processo não pede."""
    out, omitidas = [], []
    for c in cfg()["corrente"]:
        t_in = r.T[c["entrada"]]
        t_out = float(prem[c["destino_premissa"]])
        sentido = SENTIDOS[c["sentido"]]
        if sentido * (t_out - t_in) <= 0:
            omitidas.append((c["rotulo"], c["motivo_omissao"]))
            continue
        out.append(pa.corrente(c["rotulo"], t_in, t_out, r.C(r.streams[c["capacidade"]])))
    return out, omitidas


def rede(r, prem):
    """RedeCaso do caso do balanço `r`. Caso em que uma corrente não tem o que trocar (vazão
    nula, ou já na temperatura de destino) volta como tabela INVIÁVEL com a mensagem do núcleo —
    é estado, não exceção, e não há alvo inventado."""
    dt_min = float(prem[cfg()["dt_min_premissa"]])
    streams, omitidas = correntes_do_caso(r, prem)
    realizado = {papel: float(r.duties[chave]) for papel, chave in cfg()["comparacao"].items()}
    nome = cfg_pfd()["nome_caso"].format(num=r.num, nome=r.caso.get("name", r.fluid))
    if omitidas:
        # Sem os dois lados não há integração a calcular: é recusa declarada, com o motivo de cada
        # corrente ausente, e não um alvo de zero disfarçado.
        motivos = "; ".join(f"{rotulo}: {motivo}" for rotulo, motivo in omitidas)
        return RedeCaso(r.num, nome, tuple(streams), tuple(omitidas), dt_min,
                        pa.pinch_infeasible(f"rede incompleta neste caso — {motivos}", dt_min),
                        pa.composite_curves(streams, pa.pinch_infeasible("", dt_min)), realizado)
    tabela = pa.problem_table(streams, dt_min)
    return RedeCaso(r.num, nome, tuple(streams), (), dt_min, tabela,
                    pa.composite_curves(streams, tabela), realizado)


def redes(balanco, prem):
    return [rede(r, prem) for r in balanco]


def folgas(rc):
    """Quanto o arranjo do balanço deixa na mesa, por papel, em kW (NaN se a rede não se aplica):
    utilidade acima do alvo é desperdício de utilidade; recuperação abaixo do alvo é calor que o
    pré-aquecedor poderia ter trocado e não trocou."""
    if not rc.aplicavel:
        return {papel: math.nan for papel in rc.realizado}
    alvo = {"utilidade_quente": rc.tabela.q_h_min, "utilidade_fria": rc.tabela.q_c_min,
            "recuperacao": rc.curvas.q_rec}
    return {papel: rc.realizado[papel] - alvo[papel] if papel != "recuperacao"
            else alvo[papel] - rc.realizado[papel] for papel in rc.realizado}


def alvos(rc):
    """{papel: alvo em kW} do caso (NaN se a rede não se aplica)."""
    if not rc.aplicavel:
        return {papel: math.nan for papel in rc.realizado}
    return {"utilidade_quente": rc.tabela.q_h_min, "utilidade_fria": rc.tabela.q_c_min,
            "recuperacao": rc.curvas.q_rec}
