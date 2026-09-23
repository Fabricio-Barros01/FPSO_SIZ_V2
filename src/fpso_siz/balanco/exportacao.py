"""Estruturas de dados das saídas do balanço (JSON e tabela de correntes).

Monta dados puros (dict/list de números e textos); serializar é papel de fpso_siz.output.
"""
from fpso_siz import __version__
from fpso_siz.balanco.balancos import balanco_global, balancos_por_bloco, topologia
from fpso_siz.balanco.dados import descritores_premissas
from fpso_siz.core.configuracao import carregar

ESQUEMA = 1


def colunas_correntes():
    return carregar("saida_correntes.toml")["colunas"]


def tabela_correntes(resultados):
    """Uma linha por caso × corrente, com as chaves de config/saida_correntes.toml."""
    linhas = []
    for r in resultados:
        for c in topologia()["correntes"]:
            s = r.streams[c["id"]]
            linhas.append({
                "caso": r.num, "corrente": c["id"], "nome": c["nome"], "fase": c["fase"],
                "T_C": r.T[c["id"]], "P_kPa": r.P[c["id"]],
                "m_O_kg_s": s["O"], "m_W_kg_s": s["W"], "m_D_kg_s": s["D"], "m_G_kg_s": s["G"],
                "m_total_kg_s": sum(s.values()),
                "Q_O_m3_d": r.vol(s, "O"), "Q_W_m3_d": r.vol(s, "W"), "Q_D_m3_d": r.vol(s, "D"),
                "Q_G_Sm3_d": r.vol(s, "G"),
            })
    return linhas


def _puro(v):
    """Converte mapeamentos imutáveis e tuplas do rastro em dict/list."""
    if hasattr(v, "items"):
        return {k: _puro(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_puro(x) for x in v]
    return v


def rastro(r):
    return [dict(equacao=p.equacao, escopo=p.escopo, valor=_puro(p.valor), entradas=_puro(p.entradas))
            for p in r.trace]


def estrutura_balanco(dados, prem, resultados, auditoria):
    """Resultado completo do balanço como dados puros (esquema em docs/esquemas/)."""
    base = {d["nome"]: d for d in descritores_premissas(dados)}
    return {
        "esquema": ESQUEMA,
        "gerador": {"pacote": "fpso-siz", "versao": __version__},
        "entrada": {"arquivo": dados.origem, "sha256": dados.sha256},
        "premissas": [dict(d, valor=prem[nome], alterada=prem[nome] != d["valor"]) for nome, d in base.items()],
        "casos": [{
            "num": r.num, "nome": r.caso.get("name", ""), "fluido": r.fluid, "poco": r.well, "api": r.api,
            "convergiu": r.convergiu, "iteracoes": r.iters, "residuo_reciclo": r.residuo_reciclo,
            "viscosidade_oleo_cP": {"valor": r.mu[0], "marcador": r.mu[1]},
            "BSW_chegada": r.BSW01, "BSW_FWKO": r.BSW_F,
            "rho": r.rho, "cp": r.cp, "gas_props": r.gp,
            "correntes": {sid: {"T_C": r.T[sid], "P_kPa": r.P[sid], "vazao_massica_kg_s": s}
                          for sid, s in r.streams.items()},
            "cargas": r.duties, "gas": r.gas,
            "balancos_bloco": balancos_por_bloco(r), "balanco_global": balanco_global(r),
            "rastro": rastro(r),
        } for r in resultados],
        "auditoria": auditoria,
    }
