"""Sensibilidade da viscosidade de óleo vivo ao Rs do trem (Beggs & Robinson) e o seu efeito nos
vasos que decantam (SG-001, TO-001).

Não é um segundo caminho: o caminho produtivo é um só (Rs do trem → Beggs & Robinson, decisão do
usuário de 2026-09-28). Aqui o Rs de cada caso é multiplicado por fatores declarados, a μ
resultante é calculada pela MESMA função do serviço (`termo.oleo`) e entra no TAG como ajuste do
usuário (`EstadoTAG.editar`, a capacidade de sobrepor uma entrada que o produto já tem). O TAG é
dimensionado pelo mesmo serviço (`pfd/equipamento.executar`). Referências fora da faixa: óleo morto
(Rs abaixo da correlação, o limite conservador) e o Rs de Standing, só para comparação.

    uv run python tools/sensibilidade_viscosidade.py [--casos ARQ] [--saida saida/sensibilidade_viscosidade.md]
"""
import argparse
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos, constantes, pocos
from fpso_siz.balanco.propriedades import poco_do_fluido, standing_rs
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.unidades import sm3sm3_para_scf_stb
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import propostas
from fpso_siz.pfd.tags import tag
from fpso_siz.termo import servico as termo

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "design_cases_bot.json"
FIXTURE = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"


def n(x, casas=2):
    return "—" if x is None or x != x else f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cfg():
    return carregar("pfd/sensibilidade_viscosidade.toml")


def rs_do_trem(r, corrente):
    """Rs [Sm³/Sm³] da corrente no estado: gás dissolvido / óleo, em volume padrão."""
    return r.q(corrente, "G") / r.q(corrente, "O")


def mu(r, dados, T, rs_sm3):
    """μ do óleo pela função do serviço: com Rs (óleo vivo) ou sem (óleo morto)."""
    poco = pocos()[poco_do_fluido(dados, r.fluid)]
    rs = None if rs_sm3 is None else sm3sm3_para_scf_stb(rs_sm3)
    return termo.oleo(poco, r.rho["O"], T, None, rs).mu


def rs_standing(r, dados, prem):
    """ΔRs de Standing no FWKO (a entrada que o caminho anterior dava a Beggs & Robinson), só
    como referência de comparação."""
    const = constantes()
    ks = const.standing
    return (standing_rs(prem["P_FWKO"], r.T["C-04"], r.gp["gamma"], r.api, ks)
            - standing_rs(dados.P_std_kPa, const.T_ref_C, r.gp["gamma"], r.api, ks))


def dimensionar(ctx, ident, chave, valores):
    """Envelope do TAG com a μ sobreposta caso a caso (None = regra do TAG, sem sobreposição)."""
    estado = servico.estado_inicial(ident)
    for num, v in (valores or {}).items():
        estado.editar(chave, v, [num], {})
    return servico.executar(servico.Contexto(ctx.dados, balanco=ctx.balanco, propostas=ctx.propostas), estado)


def gerar(dados):
    c = cfg()
    ctx = servico.Contexto(dados, propostas=propostas.padrao())
    aval = [r for r in ctx.balanco if r.avaliavel]
    out = ["# Sensibilidade da μ de óleo vivo ao Rs do trem", "",
           "Gerado por `tools/sensibilidade_viscosidade.py`. Caminho produtivo: Rs do trem → Beggs & Robinson "
           "(decisão do usuário, 2026-09-28). Os fatores multiplicam o Rs do trem; a μ sai da mesma função do "
           "serviço e entra no TAG como ajuste do usuário; o TAG é dimensionado pelo mesmo serviço.", ""]
    for alvo in c["alvo"]:
        t = tag(alvo["tag"])
        cond = t.condicao
        fatores = c["fatores_rs"]
        out += [f"## {alvo['tag']} — `{alvo['chave']}` (Rs de {alvo['corrente_rs']}, T de {cond})", "",
                "| caso | Rs do trem (Sm³/Sm³) | Rs Standing (ref.) | μ óleo morto (cP) | "
                + " | ".join(f"μ ×{n(f, 2)} Rs" for f in fatores) + " | μ com Rs Standing |",
                "|---:|---:|---:|---:|" + "---:|" * len(fatores) + "---:|"]
        base = servico.preparar(ctx, servico.estado_inicial(alvo["tag"]))
        por_fator = {f: {} for f in fatores}
        morto, stand = {}, {}
        for r in aval:
            T = r.T[cond]
            rs = rs_do_trem(r, alvo["corrente_rs"])
            rs_s = rs_standing(r, dados, ctx.prem) if alvo["corrente_rs"] == "C-06" else None
            regra = base.caso(r.num).valores[alvo["chave"]].valor
            assert abs(mu(r, dados, T, rs) - regra) <= c["tolerancia_reproducao"] * regra, (alvo["tag"], r.num)
            for f in fatores:
                por_fator[f][r.num] = mu(r, dados, T, rs * f)
            morto[r.num] = mu(r, dados, T, None)
            stand[r.num] = mu(r, dados, T, rs_s) if rs_s is not None else None
            out.append(f"| {r.num} | {n(rs, 1)} | {n(rs_s, 1)} | {n(morto[r.num], 3)} | "
                       + " | ".join(n(por_fator[f][r.num], 3) for f in fatores)
                       + f" | {n(stand[r.num], 3)} |")
        out += ["", f"### Efeito no dimensionamento de {alvo['tag']}", "",
                "| μ usada | diâmetro (mm) | Leff (m) | governante | caso governante | teto (mm) | mecanismo do teto |",
                "|---|---:|---:|---|---|---:|---|"]
        cenarios = [("regra do TAG (Rs do trem)", None)]
        cenarios += [(f"Rs do trem ×{n(f, 2)}", por_fator[f]) for f in fatores if f != 1]
        cenarios += [("óleo morto (limite conservador)", morto)]
        if alvo["corrente_rs"] == "C-06":
            cenarios += [("Rs de Standing (referência, não produtivo)", stand)]
        for rotulo, valores in cenarios:
            res = dimensionar(ctx, alvo["tag"], alvo["chave"], valores).resultado
            out.append(f"| {rotulo} | {n(res.x, 0)} | {n(res.y, 3)} | {res.governing} | {res.driver_case} | "
                       f"{n(res.ceiling, 0)} | {res.ceiling_mechanism} |")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--casos", type=Path, default=CASOS if CASOS.exists() else FIXTURE)
    ap.add_argument("--saida", type=Path, default=RAIZ / "saida" / "sensibilidade_viscosidade.md")
    a = ap.parse_args()
    a.saida.parent.mkdir(parents=True, exist_ok=True)
    a.saida.write_text(gerar(carregar_casos(a.casos)), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
