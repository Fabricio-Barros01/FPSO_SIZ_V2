"""Resumo da planta: TAGs, estado, lacunas e recomendações com suas fontes."""
from fpso_siz.output.terminal.estilo import num, tabela
from fpso_siz.output.terminal.relatorio import cfg, quebrar, titulo


def resumo(planta, estilo, colunas):
    out = titulo("Planta — balanço → equipamentos", estilo, colunas)
    out.append(f"  {planta.dados.origem} · sha256 {planta.dados.sha256[:12]}… · {len(planta.tags)} TAGs")
    rot = cfg()["pfd"]
    linhas = []
    for t in planta.tags:
        r, e = t.resultado, t.entradas
        campos = [f for f in e.metodo.result_fields(r) if f.highlight] if r is not None and r.feasible else []
        principal = "; ".join(f"{f.label}: {num(f.value, f.digits)} {f.unit}" for f in campos)
        linhas.append([t.tag.tag, rot["estados"][t.status], str(sum(c.ativo for c in e.casos)),
                       principal or "—", r.driver_case if r is not None and r.feasible else "—"])
    out += tabela(rot["colunas"], linhas, estilo)
    for t in planta.tags:
        e, r = t.entradas, t.resultado
        out += ["", estilo.negrito(f"  {t.tag.tag} — {t.tag.nome}")]
        for l in e.lacunas:
            out += quebrar(f"Falta: {l.chave} — {l.rotulo} [{l.unidade}]; casos: "
                           + ", ".join(str(n) for n in l.casos), colunas)
        if r is not None and r.message:
            out += quebrar(r.message, colunas)
        inativos = [str(c.num) for c in e.casos if not c.ativo]
        if inativos:
            out += quebrar("Casos inativos: " + ", ".join(inativos), colunas)
        for k, rec in t.tag.recomendadas.items():
            if any(c.ativo and c.valores[k].origem == "recomendada" for c in e.casos):
                out += quebrar(f"A confirmar: {e.specs[k].label} = {num(rec['valor'])} {e.specs[k].unit}; "
                               + rec["fonte"], colunas)
        if e.avisos():
            out += quebrar(f"{len(e.avisos())} aviso(s) de propriedades/faixas; detalhes no JSON do TAG.", colunas)
    out += ["", "  Blocos sem dimensionamento: " + ", ".join(planta.sem_dimensionamento)]
    return out
