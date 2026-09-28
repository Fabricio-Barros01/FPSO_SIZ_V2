"""Estruturas de dados das saídas do balanço (JSON e tabela de correntes).

Monta dados puros (dict/list de números e textos); serializar é papel de fpso_siz.output.
"""
from fpso_siz import __version__
from fpso_siz.balanco.balancos import balanco_global, balancos_por_bloco, topologia
from fpso_siz.balanco.dados import descritores_premissas
from fpso_siz.core.configuracao import carregar



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
                "Q_O_m3_d": r.q(c["id"], "O"), "Q_W_m3_d": r.q(c["id"], "W"), "Q_D_m3_d": r.q(c["id"], "D"),
                "Q_G_Sm3_d": r.q(c["id"], "G"),
            })
    return linhas


def _puro(v):
    """Converte mapeamentos imutáveis e tuplas do rastro em dict/list."""
    if hasattr(v, "items"):
        return {k: _puro(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_puro(x) for x in v]
    return v


def cargas(r):
    """Cargas do caso para o balanco.json (config/saida_balanco.toml): Q_H = Σ Q_in e Q_C =
    Σ Q_out dos blocos (utilidades), um campo por trocador pelo TAG, na ordem da topologia,
    e as potências das bombas."""
    recuperado = carregar("saida_balanco.toml")["recuperado"]
    blocos = topologia()["blocos"]
    trocadores = {b["id"]: (r.duties[recuperado[b["id"]]] if b["id"] in recuperado
                            else sum(r.duties[k] for k in [*b["Q_in"], *b["Q_out"]]))
                  for b in blocos if b["id"] in recuperado or b["Q_in"] or b["Q_out"]}
    return {"Q_H": sum(r.duties[k] for b in blocos for k in b["Q_in"]),
            "Q_C": sum(r.duties[k] for b in blocos for k in b["Q_out"]),
            **trocadores, **{k: r.duties[k] for b in blocos for k in b["W"]}}


def termodinamica(r):
    """Avaliabilidade do caso, composição do BOT (z_base) e do caso (Nota 4) e os estágios do trem."""
    tr, rec = r.trem, r.recombinacao
    return {
        "avaliavel": r.avaliavel, "motivo": tr.motivo if tr is not None else "", "z_base": dict(r.composicao),
        "z_caso": dict(rec.z_caso) if rec else None,
        "recombinacao": None if rec is None else {
            "T_ref_C": rec.T_ref_C, "P_ref_kPa": rec.P_ref_kPa, "n_gas_kmol_d": rec.n_gas_kmol_d,
            "n_liquido_kmol_d": rec.n_liquido_kmol_d, "massa_kg_d": rec.massa_kg_d,
            "q_gas_fwko_Sm3_d": rec.reproducao.q_gas_fwko_sm3d, "q_oleo_tanque_m3_d": rec.reproducao.q_oleo_tanque_m3d,
            "erro_gas_rel": rec.reproducao.erro_gas_rel, "erro_oleo_rel": rec.reproducao.erro_oleo_rel},
        "estagios": [] if rec is None else [
            {"ponto": e.ponto, "corrente_gas": e.corrente_gas, "T_C": e.T_C, "P_kPa": e.P_kPa, "beta": e.beta,
             "n_vapor_kmol_d": e.n_vapor_kmol_d, "Q_G_Sm3_d": e.q_vapor_sm3d, "m_vapor_kg_d": e.m_vapor_kg_d,
             "MW_v": e.vapor.MW, "Z_v": e.vapor.Z, "rho_v_kg_m3": e.vapor.rho, "y": e.y, "x": e.x}
            for e in tr.estagios],
    }


def rastro(r):
    return [dict(equacao=p.equacao, escopo=p.escopo, valor=_puro(p.valor), entradas=_puro(p.entradas))
            for p in r.trace]


def estrutura_balanco(dados, prem, resultados, auditoria):
    """Resultado completo do balanço como dados puros (esquema em docs/esquemas/)."""
    base = {d["nome"]: d for d in descritores_premissas(dados)}
    return {
        "esquema": carregar("saida_balanco.toml")["esquema"],
        "gerador": {"pacote": "fpso-siz", "versao": __version__},
        "entrada": {"arquivo": dados.origem, "sha256": dados.sha256},
        "premissas": [dict(d, valor=prem[nome], alterada=prem[nome] != d["valor"]) for nome, d in base.items()],
        "casos": [{
            "num": r.num, "nome": r.caso.get("name", ""), "fluido": r.fluid, "poco": r.well, "api": r.api,
            "convergiu": r.convergiu, "iteracoes": r.iters, "residuo_reciclo": r.residuo_reciclo,
            "viscosidade_oleo_cP": {"valor": r.mu[0], "marcador": r.mu[1]},
            "BSW_chegada": r.BSW01, "BSW_FWKO": r.BSW_F, "FWKO": dict(r.fwko),
            "rho": r.rho, "cp": r.cp, "gas_props": r.gp,
            "correntes": {sid: {"T_C": r.T[sid], "P_kPa": r.P[sid], "vazao_massica_kg_s": s}
                          for sid, s in r.streams.items()},
            "cargas": cargas(r), "gas": r.gas, "termodinamica": termodinamica(r),
            "balancos_bloco": balancos_por_bloco(r), "balanco_global": balanco_global(r),
            "rastro": rastro(r),
        } for r in resultados],
        "auditoria": auditoria,
    }
