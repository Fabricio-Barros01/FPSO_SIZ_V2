"""Termodinâmica preliminar (F14): o que o balanço simplifica, comparado caso a caso com
propriedades de fonte citável do ChEDL, sem alterar o balanço nem a paridade.

O balanço preliminar usa cp constante por pseudo-componente (P-10 a P-12; gás ideal a
25 °C, constantes.toml) e gás seco sem calor de flash. Aqui:

- fase aquosa de cada corrente: cp do balanço (média mássica de W e D) × cp de Laliberté
  (2009) na T da corrente e com o sal real de W e D (mesma regra de pfd/entradas.py);
- gás de cada vaso: cp do balanço × cp da fase vapor pela EOS de Peng-Robinson na T e P da
  corrente, e o Z (o balanço usa gás ideal nos índices, P-39);
- efeito na carga do P-002: parcela aquosa de m·(cp_ref − cp_bal)·ΔT no aquecimento de C-07 a
  C-08 (estimativa de sensibilidade, não correção do balanço).

Não entra aqui o que não tem fonte: flash do fluido de poço, óleo vivo, Bo/Rs pela EOS e
calor de flash exigem Tc, Pc e ω do pseudo-componente C20+, e o BOT só dá MW e densidade (as
correlações do ChEDL para petróleo pedem o ponto de ebulição). Fica como lacuna de
caracterização (`lacunas()`).
"""
import math
from dataclasses import dataclass

from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import kj_para_j, w_para_kw
from fpso_siz.pfd import fluidos


def cfg():
    return carregar("pfd/termodinamica.toml")


@dataclass(frozen=True)
class Comparacao:
    caso: int
    corrente: str
    grandeza: str
    balanco: float      # valor do balanço preliminar
    referencia: float   # valor da correlação de fonte citável
    unidade: str
    fonte: str

    @property
    def desvio(self):
        """(balanço − referência)/referência: positivo = balanço acima da referência."""
        return self.balanco / self.referencia - 1


def _cp_aquoso_balanco(r, sid):
    s = r.streams[sid]
    m = {c: s[c] for c in ("W", "D")}
    total = sum(m.values())
    return sum(m[c] * r.cp[c] for c in m) / total if total > 0 else math.nan


def _fracao_sal(r, sid, prem):
    sal = carregar("pfd/pfd.toml")["sal"]
    s = r.streams[sid]
    massa = {c: s[c] for c in ("W", "D")}
    w = {c: fluidos.fracao_sal(prem[sal[c][0]], prem[sal[c][1]]) for c in massa}
    total = sum(massa.values())
    return sum(massa[c] * w[c] for c in massa) / total


def aquosas(r, prem):
    out = []
    for sid in cfg()["correntes_aquosas"]:
        s = r.streams[sid]
        if not s["W"] + s["D"] > 0:
            continue
        ref = fluidos.salmoura_fracao(r.T[sid], _fracao_sal(r, sid, prem))
        out.append(Comparacao(r.num, sid, "cp da fase aquosa", kj_para_j(_cp_aquoso_balanco(r, sid)), ref.cp,
                              "J/(kg·K)", fluidos.cfg()["salmoura"]["fonte"]))
    return out


def gases(r):
    out = []
    for sid in cfg()["correntes_gas"]:
        if not r.streams[sid]["G"] > 0:
            continue
        g = fluidos.gas_cp(r.gp["y"], r.T[sid], r.P[sid])
        fonte = fluidos.cfg()["gas"]["fonte_eos"]
        out.append(Comparacao(r.num, sid, "cp do gás", kj_para_j(r.cp["G"]), g["cp"], "J/(kg·K)", fonte))
        out.append(Comparacao(r.num, sid, "Z do gás", 1.0, g["Z"], "–", fonte))
    return out


def efeito_carga_aquecedor(r, prem):
    """(ΔQ [kW], Q do P-002 [kW]) se a parcela aquosa de C-07 → C-08 usasse o cp de Laliberté
    na temperatura média; estimativa de sensibilidade (o balanço não muda)."""
    e, s = cfg()["aquecedor"], r.streams
    ent, sai = e["entrada"], e["saida"]
    m = s[ent]["W"] + s[ent]["D"]
    if not m > 0 or not r.duties[e["carga"]] > 0:
        return None
    t_media = (r.T[ent] + r.T[sai]) / 2
    ref = fluidos.salmoura_fracao(t_media, _fracao_sal(r, ent, prem)).cp
    dq = w_para_kw(m * (ref - kj_para_j(_cp_aquoso_balanco(r, ent))) * (r.T[sai] - r.T[ent]))
    return dq, r.duties[e["carga"]]


def lacunas():
    return cfg()["lacunas"]


def comparar(resultados, prem):
    """Todas as comparações dos casos (sem alterar `resultados`)."""
    out = []
    for r in resultados:
        out += aquosas(r, prem) + gases(r)
    return out
