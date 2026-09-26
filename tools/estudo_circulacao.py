"""Estudos da Etapa 2 dos alarmes: circulação fixa da utilidade e cascos em série no P-003.

Escreve docs/validacao/21-circulacao-cascos.md. Os dois estudos foram autorizados pelo usuário
em 2026-09-26 como ESTUDO: nada aqui muda o cálculo padrão, as recomendações dos TAGs ou a
regra do método. Determinístico e LENTO (quatro buscas completas na grade de
config/pfd/reotimizacao.toml; o P-003 tem 16 casos) — roda fora da suíte habitual.

Cada TAG é comparado em duas circulações (a original, ṁ = q/(cp·ΔT), e a fixa, pfd/circulacao.py)
e em duas divisões (um casco só, e a busca em série até o limite da política). A etapa de um
casco de cada busca É a comparação "sem divisão adicional": o resultado é reaproveitado, não
recalculado.

    uv run python tools/estudo_circulacao.py [--saida docs/validacao/21-circulacao-cascos.md]
"""
import argparse
import collections
import math
from pathlib import Path

from fpso_siz.pfd import circulacao
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import investigacao as inv
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd import reotimizacao as ro
from fpso_siz.balanco.dados import carregar_casos

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
PROPOSTAS = RAIZ / "src" / "fpso_siz" / "config" / "pfd" / "pendencias_propostas.toml"
# política de estudo do P-003: a decisão original previu cascos em série só no P-002
SERIE = {"divisao": "cascos_serie", "gatilho": "comprimento", "n_cascos_max": 3}
ROTULOS = {"comprimento": "comprimento de tubo > l_tubo_max", "casco": "casco > d_casco_max",
           "dittus_boelter": "fora da faixa de Dittus-Boelter", "v_max": "v > v_max", "v_min": "v < v_min",
           "v_min_projeto": "v < v_min no caso de projeto", "calculo": "cálculo do feixe não fecha",
           "lacuna": "entrada em lacuna", "preparacao": "caso não prepara"}


def f(x, casas=0):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def bloqueios_txt(c, nomes):
    grupos = collections.defaultdict(list)
    for crit, i in c.bloqueios:
        grupos[crit].append(nomes[i][:6] if i >= 0 else "")
    return "; ".join(f"{ROTULOS.get(k, k)}" + (f" ({', '.join(v)})" if any(v) else "") for k, v in grupos.items()) or "—"


def variante_de(ident):
    return inv.variante(f"{ident.lower().replace('-', '_')}_circulacao_fixa")


def buscar(ctx, ident, fixa):
    """[Etapa] da busca completa com a política de série (a etapa 1 é o "um casco só")."""
    return ro.buscar(ctx, ident, politica_estudo=SERIE, variante=variante_de(ident) if fixa else None)


def linha_config(rotulo, c, nomes):
    return (f"| {rotulo} | {'viável' if c.viavel else 'inviável'} | {f(c.valores.get('cascos_serie', 1.0))} | "
            f"{f(c.x)} | {f(c.y, 2)} | {f(c.area, 1)} | {bloqueios_txt(c, nomes)} |")


def tabela_casos(c, estudo, aprox):
    """Operação de cada caso no feixe escolhido, com o que o estudo resolveu e a P-32."""
    res = {r.num: r for r in (estudo.resolucoes if estudo else ())}
    op = ro.operacao(c)
    ap = {a["caso"]: a for a in aprox}
    cab = ["| Caso | Papel | Carga (kW) | ṁ utilidade (kg/s) | T saída utilidade (°C) | v (m/s) | Re | "
           "Dittus-Boelter | ΔT₁ (K) | ΔT₂ (K) | P-32 | L exigido (m) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    nums = [n for n, _ in c.rt.entradas.case_set().expand()]
    numeros = [caso.num for caso in c.rt.entradas.casos if caso.ativo]
    for (o, num) in zip(op, numeros):
        r = res.get(num)
        a = ap.get(o["caso"], {})
        cab.append(f"| {o['caso']} | {o['papel']} | {f(o['q'] / 1000)} | {f(r.vazao, 2) if r else '—'} | "
                   f"{f(r.t_saida, 2) if r else '—'} | {f(o['v'], 2)} | {f(o['re'])} | "
                   f"{'sim' if o['nu_valido'] else 'NÃO'} | {f(a.get('dt1'), 2)} | {f(a.get('dt2'), 2)} | "
                   f"{('atende' if a.get('atende') else 'NÃO atende') if a else '—'} | {f(o['l'], 2)} |")
    return cab


def secao(ctx, ident, dt_app):
    etapas_base = buscar(ctx, ident, fixa=False)
    etapas_fixa = buscar(ctx, ident, fixa=True)
    nomes = [n for n, _ in ro.escolhido(etapas_base).rt.entradas.case_set().expand()]
    # a etapa de 1 casco é o "sem divisão adicional"; o escolhido é o melhor de todas as etapas
    um_base, um_fixa = etapas_base[0].melhor, etapas_fixa[0].melhor
    esc_base, esc_fixa = ro.escolhido(etapas_base), ro.escolhido(etapas_fixa)
    out = [f"## {ident}", "",
           f"Busca completa na grade de `config/pfd/reotimizacao.toml` ({len(etapas_base[0].candidatos)} candidatos "
           f"por etapa), com `divisao = \"cascos_serie\"`, gatilho `comprimento` e até "
           f"{SERIE['n_cascos_max']} cascos. Os limites `l_tubo_max` (6 m) e `d_casco_max` (2.500 mm) não foram "
           "alterados.", "",
           "| Configuração | Estado | Cascos | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |",
           "|---|---|---|---|---|---|---|",
           linha_config("circulação original, um casco", um_base, nomes),
           linha_config("circulação original, busca em série", esc_base, nomes),
           linha_config("circulação fixa, um casco", um_fixa, nomes),
           linha_config("circulação fixa, busca em série", esc_fixa, nomes), ""]
    for rotulo, c, fixa in (("circulação original", esc_base, False), ("circulação fixa", esc_fixa, True)):
        estudo = None
        if fixa:
            e = servico.estado_inicial(ident)
            for chave, valor in c.valores.items():
                e.editar(chave, float(valor), None, {})
            _, estudo = circulacao.executar(ctx, ident, variante_de(ident), e)
        aprox = circulacao.aproximacoes(c.rt, dt_app)
        out += [f"### {ident} — {rotulo}: operação por caso no feixe escolhido", ""]
        if fixa and estudo is not None:
            out += [f"Caso de projeto pela P-45 na **configuração-base**: **{estudo.nome_projeto}**; circulação "
                    f"fixada em {f(estudo.vazao_fixa, 2)} kg/s — a vazão desse caso, com origem no rastro.", "",
                    "Achado do estudo: com a circulação fixa a vazão volumétrica no tubo fica praticamente igual em "
                    "todos os casos, e o critério da P-45 **degenera** dentro do método — a coluna "
                    "\"Papel\" passa a rotular como projeto o caso de maior temperatura de retorno (menor "
                    "densidade), não o de maior carga. Como a velocidade é a mesma em todos os casos, a escolha "
                    "não muda o feixe; mas é mais uma razão para a variante não ser promovida a padrão sem "
                    "decisão: a P-45 foi escrita para a circulação proporcional à carga.", ""]
        out += tabela_casos(c, estudo, aprox) + [""]
        if not estudo:
            out += [f"A coluna de vazão e de temperatura de saída da utilidade fica vazia: na circulação original "
                    f"elas são as do cálculo padrão (ΔT fixo pelos insumos).", ""]
    return out


def gerar():
    dados = carregar_casos(CASOS)
    ctx = servico.Contexto(dados, propostas=mod_propostas.carregar(PROPOSTAS))
    dt_app = float(ctx.prem["dT_app"])
    out = ["# F13/Etapa 2 — circulação fixa da utilidade e cascos em série (estudos)", "",
           "Gerado por `tools/estudo_circulacao.py`; todos os números saem do motor e do rastro.", "",
           "Os dois estudos foram autorizados pelo usuário em 2026-09-26 **como estudo**. O cálculo padrão não "
           "muda: a vazão da utilidade continua proporcional à carga (ṁ = q/(cp·ΔT), com o ΔT fixo pelos insumos "
           "`t_agua_in`/`t_agua_out`), a política de divisão em cascos do P-003 continua a de cascos em paralelo, e "
           "as recomendações dos TAGs continuam as da reotimização F10x.7 "
           "(`docs/validacao/18-trocadores.md`). Nada aqui é promovido a premissa ou a padrão.", "",
           "**Circulação fixa:** a bomba da utilidade mantém a vazão do caso de projeto (critério da P-45: maior "
           "vazão volumétrica no tubo) em todos os casos, e o ΔT varia com a carga. A temperatura de saída de cada "
           "caso é **resolvida** por bisseção sobre o mesmo fechamento de energia do cálculo padrão "
           "(ṁ_fixa = q/(cp(T̄)·|ΔT|)), com cp, ρ, μ e k da água reavaliados na temperatura média resultante (IAPWS); "
           "a saída resolvida entra no próprio insumo `t_agua_out`, e a grade de tubos por passe é preparada outra "
           "vez com a vazão fixa e a densidade reavaliada. Critérios numéricos em "
           "`config/pfd/circulacao.toml`; nenhum valor físico é suposto.", "",
           f"**Condição do estudo (P-32):** as duas aproximações terminais de cada caso ativo são conferidas contra "
           f"o ΔT de aproximação do balanço (P-32 = {f(dt_app, 1)} K). É exigência destes estudos, registrada por "
           "caso; a regra padrão do método continua sem impô-la.", "",
           "**Casos inativos continuam inativos** (motivo do TAG, carga nula). Lacuna continua lacuna: falha física "
           "ou de convergência volta como inviabilidade com mensagem, nunca número suposto.", ""]
    for ident in ("P-002", "P-003"):
        out += secao(ctx, ident, dt_app)
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=RAIZ / "docs" / "validacao" / "21-circulacao-cascos.md")
    a = ap.parse_args()
    a.saida.write_text(gerar(), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
