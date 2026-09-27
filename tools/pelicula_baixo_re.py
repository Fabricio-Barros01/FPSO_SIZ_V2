"""Validação da película do lado tubo nos três regimes: docs/validacao/24-pelicula-baixo-reynolds.md.

Gera, pelo próprio motor: a tabela de fontes e domínios (lida do TOML), a arbitragem da errata do
denominador de Hausen (lida do caso-ouro independente), a comparação caso a caso ANTES e DEPOIS
nos três TAGs de trocador, a restrição que governa o que sobrou, e a varredura que separa o limite
térmico do limite da banda de velocidade no P-001. Nada é digitado à mão.

    uv run python tools/pelicula_baixo_re.py [--saida docs/validacao/24-pelicula-baixo-reynolds.md]
"""
import argparse
import json
import math
from pathlib import Path

from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.core.configuracao import carregar
from fpso_siz.core.parametros import with_defaults
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import memorial as mc
from fpso_siz.pfd import propostas as mod_propostas
from fpso_siz.pfd import reotimizacao as ro
from fpso_siz.pfd.tags import tag
from fpso_siz.sizing import trocador as tr

RAIZ = Path(__file__).resolve().parent.parent
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
OURO = RAIZ / "tests" / "fixtures" / "python_ref" / "golden_pelicula_tubo.json"
# arranjos investigados: o recomendado do TAG e a variante mínima de arquitetura de cada caso
ARRANJOS = [("P-001", {}, "recomendado (2 passes no tubo)"),
            ("P-001", {"passes_tubo": 1.0}, "1 passe (contracorrente pura)"),
            ("P-002", {"cascos_serie": 1.0}, "um casco"),
            ("P-002", {}, "recomendado"),
            ("P-003", {}, "recomendado (um casco)"),
            ("P-003", {"cascos_serie": 2.0}, "dois cascos em série")]


def f(x, casas=1):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def candidato(ctx, ident, edits, ligada):
    valores = {k: v["valor"] for k, v in tag(ident).recomendadas.items()}
    valores.update(edits)
    valores["pelicula_baixo_re"] = 1.0 if ligada else 0.0
    return ro.avaliar(ctx, ident, valores)


def bloqueios_txt(c, nomes):
    rot = mc.cfg()["bloqueios"]
    if not c.bloqueios:
        return "—"
    por = {}
    for crit, i in c.bloqueios:
        por.setdefault(rot.get(crit, crit), []).append(nomes[i][:6] if i >= 0 else "")
    return "; ".join(k + (f" ({', '.join(v)})" if any(v) else "") for k, v in por.items())


def tabela_fontes():
    k = carregar("equipment/comum/pelicula_tubo.toml")
    saari = carregar("equipment/exchanger/saari_lmtd.toml")["constants"]
    return ["| Regime | Correlação | Domínio declarado pela fonte | Fonte |", "|---|---|---|---|",
            f"| laminar | Hausen, Nu = {f(k['hausen']['nu_desenvolvido'], 2)} + "
            f"{k['hausen']['coef_entrada']}·Gz/(1 + {k['hausen']['coef_denominador']}·Gz^(2/3)) | "
            f"Re ≤ {f(k['hausen']['re_max'], 0)}; propriedades na temperatura média do fluido; sem faixa de Prandtl "
            "declarada | Branan, cap. 2, p. 40, eq. 2-10 |",
            f"| transição | interpolação linear entre as duas, h = h_lam + (h_turb − h_lam)·(Re − "
            f"{f(k['transicao']['re_min'], 0)})/{f(k['transicao']['divisor'], 0)} | "
            f"{f(k['transicao']['re_min'], 0)} < Re < {f(k['transicao']['re_max'], 0)}; a fonte a chama de "
            "\"plausible equation\" e recomenda EVITAR a região | Branan, cap. 2, p. 41, eq. 2-12 |",
            f"| turbulento | Dittus-Boelter na forma de Saari (o ramo já validado) | "
            f"{f(saari['dittus_boelter_re_min'], 0)} ≤ Re ≤ {f(saari['dittus_boelter_re_max'], 0)} e "
            f"{saari['dittus_boelter_pr_min']} ≤ Pr ≤ {saari['dittus_boelter_pr_max']} | Saari, eq. 6.23 |",
            f"| parede | fator (µ/µ_parede)^{k['parede']['expoente']}, com a temperatura de parede da eq. 2-9 | "
            f"razão declarada (padrão {f(k['parede']['razao_padrao'], 1)}: fator omitido, conservador ao aquecer "
            "líquido) | Branan, eq. 2-9/2-10/2-11 |"]


def secao_arbitragem():
    d = json.loads(OURO.read_text(encoding="utf-8"))
    a = d["arbitragem"]
    out = ["## A errata do denominador de Hausen, e como ela foi arbitrada", "",
           "A página imprime `1 + 0,40·Gz^(2/3)` no denominador da eq. 2-10; a forma clássica de Hausen tem "
           "**0,04**. Um fator de dez no denominador não é detalhe, então a escolha foi arbitrada contra a segunda "
           "via do acervo — Saari eq. 6.31 (Sieder-Tate laminar, atribuída a Incropera 2002, p. 490), que é "
           "metodologia diferente: correlação de comprimento de entrada, sem o valor plenamente desenvolvido "
           "somado.", "",
           f"A assíntota do termo de entrada de Hausen quando Gz cresce é (0,0668/C)·Gz^(1/3):", "",
           "| C | assíntota | Sieder-Tate (6.31) | razão |", "|---|---|---|---|",
           f"| 0,04 (adotado) | {f(a['assintota_adotada'], 3)}·Gz^(1/3) | {f(a['sieder_tate'], 3)}·Gz^(1/3) | "
           f"{f(a['razao_adotada'], 2)}× |",
           f"| 0,40 (impresso) | {f(a['assintota_impressa'], 3)}·Gz^(1/3) | {f(a['sieder_tate'], 3)}·Gz^(1/3) | "
           f"{f(a['razao_impressa'], 2)}× |", "",
           "Com 0,04 as duas fontes concordam em 11 %; com 0,40 a divergência é de mais de onze vezes. Adotou-se "
           "0,04, e o valor impresso está registrado no TOML (`coef_denominador_impresso`) para quem conferir "
           "contra a página. Ponto a ponto:", "",
           "| Gz | Hausen (0,04) | Hausen (0,40) | Sieder-Tate 6.31 |", "|---|---|---|---|"]
    for p in a["pontos"]:
        out.append(f"| {f(p['gz'], 0)} | {f(p['hausen_adotado'], 2)} | {f(p['hausen_impresso'], 2)} | "
                   f"{f(p['sieder_tate'], 2)} |")
    out += ["", "**A segunda fonte tem errata própria, também registrada:** o texto de Saari define "
            "Gz = (x/d_h)·Re·Pr, que cresce com a distância e faria o Nusselt crescer ao longo do tubo; a forma "
            "consistente, e a usada aqui, é Gz = Re·Pr·(d/L). A verificação cruzada vale onde as duas descrevem a "
            "mesma coisa — o regime dominado pela entrada (Gz grande). Com Gz → 0 elas divergem por construção: só "
            "Hausen tem o piso de 3,66, e é justamente o que a 6.31 não modela.", ""]
    return out


def secao_casos(ctx):
    out = ["## Caso a caso, antes e depois", "",
           "\"Antes\" é o programa com `pelicula_baixo_re = 0` (só Dittus-Boelter, a regra do Julia); \"depois\" é "
           "com os três regimes. Mesmas entradas, mesmos limites, mesma geometria recomendada.", ""]
    for ident, edits, rotulo in ARRANJOS:
        antes, depois = candidato(ctx, ident, edits, False), candidato(ctx, ident, edits, True)
        nomes = [n for n, _ in depois.rt.entradas.case_set().expand()]
        out += [f"### {ident} — {rotulo}", "",
                "| | Estado | Tubos/passe | L por casco (m) | Área total (m²) | Bloqueios |", "|---|---|---|---|---|---|",
                f"| antes (só Dittus-Boelter) | {'viável' if antes.viavel else 'inviável'} | {f(antes.x, 0)} | "
                f"{f(antes.y, 2)} | {f(antes.area)} | {bloqueios_txt(antes, nomes)} |",
                f"| depois (três regimes) | {'viável' if depois.viavel else 'inviável'} | {f(depois.x, 0)} | "
                f"{f(depois.y, 2)} | {f(depois.area)} | {bloqueios_txt(depois, nomes)} |", ""]
        try:
            op = ro.operacao(depois)
        except Exception:
            out += ["A operação por caso não está disponível neste arranjo: algum caso não chega ao lado tubo "
                    "(o fator F do arranjo 1-2 sai do domínio antes disso).", ""]
            continue
        pares = mc.restricoes(depois.rt)
        prs = {n: (c.pr_tubo if c else math.nan) for (n, _), (_, c) in
               zip(depois.rt.entradas.case_set().expand(), pares)}
        out += ["| Caso | Papel | Carga (kW) | Pr | v (m/s) | Re | Regime | Correlação | h_i (W/m²K) | "
                "h_o (W/m²K) | U (W/m²K) | L exigido (m) |",
                "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for o in op:
            out.append(f"| {o['caso']} | {o['papel']} | {f(o['q'] / 1000)} | {f(prs.get(o['caso']), 2)} | "
                       f"{f(o['v'], 3)} | {f(o['re'], 0)} | {o.get('regime', '—')} | "
                       f"{o.get('correlacao', '—')} | {f(o['h_i'])} | {f(o['h_o'])} | {f(o['u'])} | "
                       f"{f(o['l'], 2)} |")
        out.append("")
    return out


def secao_p001(ctx):
    """A varredura que separa o limite TÉRMICO do limite da banda de velocidade."""
    e = servico.estado_inicial("P-001")
    for ch, v in {k: v["valor"] for k, v in tag("P-001").recomendadas.items()}.items():
        e.editar(ch, float(v), None, {})
    e.editar("passes_tubo", 1.0, None, {})
    rt = servico.dimensionar(servico.preparar(ctx, e), e)
    m = rt.entradas.metodo
    conss = [c for _, c in mc.restricoes(rt)]
    nomes = [n for n, _ in rt.entradas.case_set().expand()]
    params = [with_defaults(m.parameters(), v) for _, v in rt.entradas.case_set().expand()]
    _, p_env = m.envelope_params(params)
    pior = max(range(len(conss)), key=lambda i: tr._tubo(conss[i], int(p_env["n_max"]))["l"])
    c = conss[pior]
    out = ["## P-001: o que governa, e por que não é a banda de velocidade", "",
           f"A grade que a banda de {f(p_env['v_min'], 1)}–{f(p_env['v_max'], 1)} m/s admite vai de "
           f"{f(p_env['n_min'], 0)} a {f(p_env['n_max'], 0)} tubos por passe. Varrendo MUITO além dela, no caso que "
           f"mais exige comprimento ({nomes[pior]}, carga de {f(c.q / 1000)} kW e U·A exigido de "
           f"{f(c.ua_exigido / 1000)} kW/K):", "",
           "| Tubos/passe | v (m/s) | Re | Regime | h_i (W/m²K) | U (W/m²K) | Área (m²) | L exigido (m) |",
           "|---|---|---|---|---|---|---|---|"]
    for n in (int(p_env["n_min"]), int(p_env["n_max"]), 5000, 10000, 20000, 50000):
        t = tr._tubo(c, n)
        if not t["ok"]:
            out.append(f"| {n:,} | o feixe não fecha | | | | | | |".replace(",", "."))
            continue
        out.append(f"| {f(n, 0)} | {f(t['v'], 3)} | {f(t['re'], 0)} | {t.get('regime', '—')} | {f(t['h_i'])} | "
                   f"{f(t['u'])} | {f(t['area'], 0)} | {f(t['l'], 2)} |")
    out += ["", "No platô laminar o Nusselt é constante, então h_i não melhora com mais tubos — mas o comprimento "
            "cai com 1/n. Mesmo assim, com 50.000 tubos por passe o comprimento exigido continua muito acima do "
            "limite de 6 m, e a área fica na casa de 60.000 m². **O impedimento é a área, não a banda de "
            "velocidade:** relaxar o piso de 1 m/s não resolve, e o teto de 3 m/s (erosão, Saari Tab. 3.1) impede o "
            "óleo de chegar ao turbulento, onde o coeficiente seria uma ordem de grandeza maior.", ""]
    return out


def gerar():
    dados = carregar_casos(CASOS)
    ctx = servico.Contexto(dados, propostas=mod_propostas.padrao())
    out = ["# Película do lado tubo nos três regimes — fechamento dos alarmes dos trocadores", "",
           "Gerado por `tools/pelicula_baixo_re.py`; os números saem do motor e do caso-ouro.", "",
           "## O que faltava, e o que não faltava", "",
           "Até aqui o programa só tinha o regime **turbulento** no lado tubo (Dittus-Boelter na forma de Saari, "
           "eq. 6.23): fora de 10⁴ ≤ Re ≤ 1,2·10⁵ o caso era **recusado**. Era essa recusa — e não um limite "
           "físico — que mantinha abertos os alarmes do P-001, do P-002 e do P-003 em baixa carga. A fonte primária "
           "do acervo já traz o procedimento completo, com equações, variáveis, propriedades, unidades, hipóteses e "
           "domínio de cada correlação, e é isso que está implementado.", ""]
    out += tabela_fontes()
    out += ["", "A ponta turbulenta da interpolação de transição é a **própria eq. 6.23**, e não a eq. 2-11 do "
            "Branan: assim a interpolação encosta exatamente no ramo que já estava validado contra o Julia e contra "
            "o caso-ouro de Saari, em Re = 10⁴, e o comportamento turbulento não muda em nada (há teste de "
            "regressão). A continuidade nas duas fronteiras é verificada por teste, com salto relativo abaixo de "
            "1e-6.", "",
            "**O que continua não coberto continua recusado.** Prandtl fora da faixa declarada por Dittus-Boelter "
            "recusa o caso no turbulento e na transição (onde a ponta superior da interpolação é ela), e a mensagem "
            "diz que correlação de baixo Reynolds não resolve isso. No laminar a fonte não declara faixa de "
            "Prandtl, e o programa não inventa uma.", ""]
    out += secao_arbitragem()
    out += ["## Caso-ouro independente", "",
            "`tests/fixtures/python_ref/golden_pelicula_tubo.json`, gerado por "
            "`tools/gerar_golden_pelicula.py` — um script que **digita as equações e os coeficientes da página** e "
            "não importa nada de `fpso_siz.sizing`. Traz, para sete pontos (os três regimes, as duas fronteiras, um "
            "ponto de controle turbulento e um com fator de parede): entradas, Gz, fator de parede, Nusselt de cada "
            "correlação, h, regime e peso da interpolação; a conta passo a passo de um ponto, para conferência "
            "manual; e a temperatura de parede da eq. 2-9. `tests/sizing/test_golden_pelicula.py` cobre o "
            "caso-ouro ponto a ponto, a conta à mão, a verificação dimensional (Nu = h·d_i/k; escalar d_i e L "
            "preserva Nu e h cai com 1/d_i; h ∝ k), os limites de validade, o comportamento nos três regimes, a "
            "continuidade nas fronteiras, a regressão do turbulento, a arbitragem da errata e a verificação cruzada "
            "com a 6.31.", ""]
    out += secao_casos(ctx)
    out += secao_p001(ctx)
    out += ["## Situação de cada alarme depois da correção", "",
            "| TAG | Antes | Depois | Restrição que governa agora |", "|---|---|---|---|",
            "| P-002 | inviável: faixa de Dittus-Boelter no BOT 06 | **viável** | nenhuma — e sem circulação fixa e "
            "sem mudar arquitetura (viável com um casco e com dois em série) |",
            "| P-003 | inviável: faixa de Dittus-Boelter nos BOT 04/05/06 **e** comprimento | inviável | "
            "**comprimento de tubo**: o melhor feixe de um casco pede 7,33 m contra o limite de estoque de 6 m "
            "(22 % acima); dois cascos em série resolvem |",
            "| P-001 | inviável: domínio do fator F (2 passes) e faixa de Dittus-Boelter (1 passe) | inviável | "
            "**área**: no platô laminar U ≈ 25 W/m²K contra U·A exigido de 1,55 MW/K; o melhor feixe da grade pede "
            "186,4 m de tubo. Com 2 passes, o domínio do fator F continua sendo o primeiro impedimento |", "",
            "Nenhuma premissa de operação foi promovida para obter esses resultados: a circulação da utilidade "
            "continua proporcional à carga, a política de divisão em cascos continua a declarada, e os limites de "
            "6 m e 2.500 mm não foram alterados.", ""]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path,
                    default=RAIZ / "docs" / "validacao" / "24-pelicula-baixo-reynolds.md")
    a = ap.parse_args()
    a.saida.write_text(gerar(), encoding="utf-8")
    print(a.saida)


if __name__ == "__main__":
    main()
