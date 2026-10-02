#!/usr/bin/env python3
"""Busca discreta de layout do pré-aquecedor, com o conjunto integrado verificado
(ADR 0005; docs/validacao/43).

    uv run python tools/buscar_layout_trocador.py --estagio 1 --processos 4
    uv run python tools/buscar_layout_trocador.py --estagio 2 --processos 4
    uv run python tools/buscar_layout_trocador.py --geometria   # só a geometria selecionada

A física é toda de `fpso_siz.pfd.layout` (eixos, avaliação do candidato, frente de Pareto e
regra de seleção declarada); aqui ficam só a paralelização, a ordenação da impressão e os
arquivos. `multiprocessing` é desta ferramenta, não do pacote: cada candidato é uma avaliação
INDEPENDENTE do serviço por TAG, e `Pool.imap` preserva a ordem, de modo que a rodada paralela
dá o MESMO resultado da sequencial — paralelizar não muda número.

## Por que a busca é em dois estágios

O empacotamento (cascos em série × comprimento máximo por casco) entra na conta só pelo
PRODUTO `cascos_serie · l_tubo_max`, que é o caminho total de tubo que o candidato tem direito
a usar: o comprimento por casco é `L_total/cascos_serie`, a perda de carga é proporcional ao
caminho total e a área total não depende de como o caminho é dividido. Logo:

- **estágio 1** varre os eixos TÉRMICOS (diâmetro e passo do tubo, arranjo e espaçamento de
  chicana, passes, trens em paralelo) com o empacotamento mais permissivo que os eixos
  declaram, porque ampliar o caminho permitido só aumenta o conjunto admissível e, com ele, só
  pode reduzir a área escolhida;
- **estágio 2** pega a frente do estágio 1 e varre, nela, TODOS os empacotamentos declarados —
  é aí que se vê com quantos cascos e com que comprimento de tubo cada geometria se realiza.

A seleção final é sobre a união dos dois estágios, pela regra declarada em
`pfd/layout.selecionar`.
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import fpso_siz.sizing  # noqa: F401,E402  (registra os métodos)
from fpso_siz.balanco.dados import carregar_casos  # noqa: E402
from fpso_siz.core.configuracao import carregar  # noqa: E402
from fpso_siz.pfd import equipamento as servico  # noqa: E402
from fpso_siz.pfd import layout  # noqa: E402
from fpso_siz.pfd import propostas as mod_propostas  # noqa: E402

SAIDA = Path("saida/layout_trocador")
_CTX = {}


def _limpo(obj):
    """NaN/Inf → null, recursivamente: JSON estrito, a mesma regra de `output/pfd.py`."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _limpo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_limpo(v) for v in obj]
    return obj


def _gravar(obj, caminho):
    caminho.write_text(json.dumps(_limpo(obj), indent=2, ensure_ascii=False, allow_nan=False),
                       encoding="utf-8")
    return caminho


def _contexto(arquivo, propostas):
    ctx = servico.Contexto(carregar_casos(arquivo), propostas=propostas)
    ctx.balanco  # noqa: B018  (resolve uma vez por processo, não por candidato)
    return ctx


def _abrir(arquivo, propostas):
    _CTX["ctx"] = _contexto(arquivo, propostas)


def _avaliar(par):
    esp, conf = par
    av = layout.avaliar(_CTX["ctx"], esp, conf)
    return _resumo(av)


def _resumo(av):
    """O que trafega de volta do processo filho: números, não objetos do motor."""
    g = av.geometria
    return {
        "especificacao": dict(av.especificacao.valores),
        "servico": {"instaladas": av.configuracao.instaladas, "duty": av.configuracao.duty_projeto,
                    "standby": av.configuracao.standby},
        "viavel": av.viavel, "motivo": av.motivo,
        "ponto_fixo": {"iteracoes": av.ponto_fixo[0] if av.ponto_fixo else None,
                       "convergiu": av.ponto_fixo[1] if av.ponto_fixo else None,
                       "desvio_K": av.ponto_fixo[2] if av.ponto_fixo else None},
        "geometria": None if g is None else {
            "tubos_por_passe": g.tubos_por_passe, "comprimento_por_casco": g.comprimento_por_casco,
            "cascos_serie": g.cascos_serie, "diametro_casco": g.diametro_casco,
            "area_por_trem": g.area_unitaria,
            "residuais": {t: {"status": rt.status,
                              "x": rt.resultado.x if rt.resultado and rt.resultado.feasible else None,
                              "y": rt.resultado.y if rt.resultado and rt.resultado.feasible else None,
                              "area": (rt.resultado.derivados.get("area")
                                       if rt.resultado and rt.resultado.feasible else None),
                              "dp": (rt.resultado.derivados.get("dp")
                                     if rt.resultado and rt.resultado.feasible else None)}
                          for t, rt in (g.residuais or {}).items()}},
        "area_instalada": av.area_instalada, "area_operacional": av.area_operacional,
        "cascos_instalados": av.cascos_instalados,
        "recuperacao_alvo": av.recuperacao_alvo, "recuperacao_realizada": av.recuperacao_realizada,
        "fracao_realizada": av.fracao_realizada,
        "utilidade_quente": av.utilidade_quente, "utilidade_fria": av.utilidade_fria,
        "dp_maximo": av.dp_maximo, "casos_abaixo_v_min": list(av.casos_abaixo_v_min),
        "verificacoes": [{"rotulo": v.rotulo, "corrente": v.corrente, "premissa": v.premissa,
                          "pior": v.pior, "limite": v.limite, "atende": v.atende}
                         for v in av.verificacoes],
        "casos": [{"num": c.num, "nome": c.nome, "ativo": c.ativo, "estado": c.estado,
                   "q_alvo": c.q_alvo, "q_realizado": c.q_realizado,
                   "utilidade_quente": c.utilidade_quente, "utilidade_fria": c.utilidade_fria,
                   "dp": c.dp, "v": c.v, "re": c.re, "u": c.u, "abaixo_v_min": c.abaixo_v_min}
                  for c in av.casos],
        "avisos": list(av.avisos),
    }


# ------------------------------------------------------------------ candidatos de cada estágio
def _empacotamentos():
    eixos = layout.eixos()
    return [(s, l) for s in eixos["cascos_serie"] for l in eixos["l_tubo_max"]]


def _especificacao_registrada():
    """A especificação que o catálogo do TAG já registra, para conferir a geometria vigente.

    Eixo que o TAG não declara em `[recomendadas]` fica com o default do descritor do método —
    é exatamente o que o serviço usaria, e por isso a conferência vê a mesma geometria."""
    from fpso_siz.pfd.tags import tag
    t = tag(layout.cfg()["tag"])
    specs = servico.especificacoes_de(t.equipamento, t.metodo)
    rec = {k: float(v["valor"]) for k, v in t.recomendadas.items()}
    return layout.Especificacao(tuple((k, rec.get(k, specs[k].default)) for k in layout.eixos()))


def _permissivo():
    """O empacotamento de maior caminho total de tubo entre os declarados."""
    return max(_empacotamentos(), key=lambda p: p[0] * p[1])


def _com_empacotamento(esp, serie, l_max):
    d = dict(esp.valores)
    d["cascos_serie"], d["l_tubo_max"] = float(serie), float(l_max)
    return layout.Especificacao(tuple((k, d[k]) for k, _ in esp.valores))


def candidatos_estagio1():
    """Eixos térmicos, com o empacotamento mais permissivo e a reserva que a ET exige.

    O número de trens de RESERVA não muda nada do que o estágio 1 compara: ele entra na área
    instalada e na contagem de cascos, não no rating nem nas utilidades. Varrê-lo aqui dobraria
    o trabalho sem acrescentar informação — quanto a reserva custa é medido no fim, sobre o
    candidato selecionado."""
    serie, l_max = _permissivo()
    minimo = layout.reserva_exigida()
    vistos, out = set(), []
    for esp, conf in layout.candidatos():
        if conf.standby < minimo:
            continue
        novo = _com_empacotamento(esp, serie, l_max)
        if (novo, conf) in vistos:
            continue
        vistos.add((novo, conf))
        out.append((novo, conf))
    return out


def candidatos_estagio2(resumos):
    """O EMPACOTAMENTO mínimo de cada geometria térmica da frente do estágio 1, por comprimento
    máximo de tubo declarado.

    O caminho total de tubo (`cascos_serie × comprimento por casco`) é o que a física fixou no
    estágio 1; aqui só se divide esse caminho. Para cada comprimento máximo por casco do eixo,
    o número MÍNIMO de cascos em série é `ceil(caminho / comprimento máximo)` — qualquer número
    maior é mais equipamento para a mesma troca, e por isso não entra. Cada par resultante é
    AVALIADO de verdade (não é conta no papel): é a avaliação que confirma que o comprimento por
    casco cabe no limite e que o resto continua atendido."""
    chaves = [k for k, _ in layout.especificacoes()[0].valores]
    eixo = layout.eixos()
    teto_serie = max(eixo["cascos_serie"])
    vistos, out = set(), []
    for r in resumos:
        e, g = r["especificacao"], r["geometria"]
        if g is None or not g["cascos_serie"] or not g["comprimento_por_casco"]:
            continue
        caminho = g["cascos_serie"] * g["comprimento_por_casco"]
        for l_max in sorted(eixo["l_tubo_max"]):
            serie = math.ceil(caminho / l_max - 1e-9)
            if serie < 1 or serie > teto_serie:
                continue
            d = {**e, "cascos_serie": float(serie), "l_tubo_max": float(l_max)}
            esp = layout.Especificacao(tuple((k, d[k]) for k in chaves))
            for conf in layout.configuracoes_de_servico(d["cascos_paralelo"]):
                if conf.standby != r["servico"]["standby"] or (esp, conf) in vistos:
                    continue
                vistos.add((esp, conf))
                out.append((esp, conf))
    return out


# ------------------------------------------------------------------ execução
def _resultados(pares, arquivo, propostas, processos):
    """Resumos na ordem dos pares (sequencial ou em processos; `imap` preserva a ordem)."""
    if processos <= 1:
        _abrir(arquivo, propostas)
        yield from (_avaliar(par) for par in pares)
        return
    import multiprocessing
    ctx = multiprocessing.get_context("forkserver")
    ctx.set_forkserver_preload(["fpso_siz.pfd.layout"])
    with ctx.Pool(processos, initializer=_abrir, initargs=(arquivo, propostas)) as pool:
        yield from pool.imap(_avaliar, pares, chunksize=1)


def rodar(pares, arquivo, propostas, processos, parcial=None):
    """[resumo] de cada candidato. Cada avaliação é gravada em JSONL assim que chega: uma
    rodada de horas não pode perder tudo por um erro na escrita do arquivo final."""
    out = []
    linhas = parcial.open("w", encoding="utf-8") if parcial is not None else None
    try:
        for i, r in enumerate(_resultados(pares, arquivo, propostas, processos), 1):
            out.append(r)
            if linhas is not None:
                linhas.write(json.dumps(_limpo(r), ensure_ascii=False, allow_nan=False) + "\n")
                linhas.flush()
            if i % 25 == 0 or i == len(pares):
                print(f"  {i}/{len(pares)} avaliados ({sum(x['viavel'] for x in out)} viáveis)", flush=True)
    finally:
        if linhas is not None:
            linhas.close()
    return out


def _area_especifica(r):
    rec, area = r["recuperacao_realizada"], r["area_instalada"]
    if rec is None or area is None or not rec > 0:
        return math.inf
    return area / rec


def _chaves():
    """As mesmas regras declaradas de `pfd/layout.REGRAS`, sobre os resumos (dicionários)."""
    return {
        "area_especifica": lambda r: (_area_especifica(r), r["cascos_instalados"] or math.inf,
                                      -(r["recuperacao_realizada"] or 0.0)),
        "maior_recuperacao": lambda r: (-(r["recuperacao_realizada"] or 0.0),
                                        r["area_instalada"] or math.inf,
                                        r["cascos_instalados"] or math.inf),
    }


def _chave_ordem(r):
    return _chaves()[layout.cfg()["selecao"]["regra"]](r)


def frente_de_resumos(resumos):
    """Frente de Pareto (área instalada, utilidade quente, utilidade fria) entre os viáveis."""
    viaveis = [r for r in resumos if r["viavel"]]

    def domina(a, b):
        va = (a["area_instalada"], a["utilidade_quente"], a["utilidade_fria"])
        vb = (b["area_instalada"], b["utilidade_quente"], b["utilidade_fria"])
        return all(x <= y for x, y in zip(va, vb)) and any(x < y for x, y in zip(va, vb))

    return sorted((r for r in viaveis if not any(domina(o, r) for o in viaveis if o is not r)),
                  key=_chave_ordem)


def tabela_candidatos(resumos, limite=20):
    cab = (f"{'d_o':>6} {'passo':>5} {'lay':>4} {'chic':>5} {'pas':>4} {'par':>4} {'sér':>4} "
           f"{'Lmax':>5} {'rsv':>4} | {'n/passe':>7} {'L':>5} {'Dcasco':>7} {'A_inst':>8} "
           f"{'Σcascos':>7} {'Qrec':>8} {'frac':>6} {'ΣQH':>8} {'ΣQC':>9} {'ΔPmax':>6} | estado")
    linhas = [cab, "-" * len(cab)]
    for r in resumos[:limite]:
        e, g, s = r["especificacao"], r["geometria"], r["servico"]
        if g is None:
            linhas.append(f"{e['d_externo']:6.3f} {e['razao_passo']:5.2f} {e['layout_tubos']:4.0f} "
                          f"{e['espacamento_chicana']:5.2f} {e['passes_tubo']:4.0f} "
                          f"{e['cascos_paralelo']:4.0f} {e['cascos_serie']:4.0f} {e['l_tubo_max']:5.1f} "
                          f"{s['standby']:4.0f} | {'—':>7} " + " " * 54 + f"| {r['motivo'][:60]}")
            continue
        linhas.append(
            f"{e['d_externo']:6.3f} {e['razao_passo']:5.2f} {e['layout_tubos']:4.0f} "
            f"{e['espacamento_chicana']:5.2f} {e['passes_tubo']:4.0f} {e['cascos_paralelo']:4.0f} "
            f"{e['cascos_serie']:4.0f} {e['l_tubo_max']:5.1f} {s['standby']:4.0f} | "
            f"{g['tubos_por_passe']:7.0f} {g['comprimento_por_casco']:5.2f} {g['diametro_casco']:7.0f} "
            f"{r['area_instalada']:8.0f} {r['cascos_instalados']:7.0f} {r['recuperacao_realizada']:8.0f} "
            f"{r['fracao_realizada']:6.4f} {r['utilidade_quente']:8.0f} {r['utilidade_fria']:9.0f} "
            f"{r['dp_maximo']:6.1f} | {'VIÁVEL' if r['viavel'] else r['motivo'][:60]}")
    return "\n".join(linhas)


def _n(x, largura, casas=1):
    """Número da tabela; ausente sai como travessão (JSON estrito grava null)."""
    return f"{x:{largura}.{casas}f}" if isinstance(x, (int, float)) else f"{'—':>{largura}}"


def tabela_casos(r):
    cab = (f"{'BOT':>3} {'ativo':>5} {'estado do rating':>19} {'Q_Pinch':>9} {'Q_real':>9} {'frac':>6} "
           f"{'ΣQH':>8} {'ΣQC':>9} {'v':>5} {'Re':>8} {'U':>7} {'ΔP':>6} {'v<vmin':>6}")
    linhas = [cab, "-" * len(cab)]
    for c in r["casos"]:
        alvo, real = c["q_alvo"], c["q_realizado"]
        frac = (real / alvo if isinstance(real, (int, float)) and alvo else 1.0) if alvo is not None else None
        linhas.append(f"{c['num']:3d} {str(c['ativo']):>5} {c['estado']:>19} {_n(alvo, 9)} "
                      f"{_n(real, 9)} {_n(frac, 6, 4)} {_n(c['utilidade_quente'], 8)} "
                      f"{_n(c['utilidade_fria'], 9)} {_n(c['v'], 5, 2)} {_n(c['re'], 8, 0)} "
                      f"{_n(c['u'], 7)} {_n(c['dp'], 6)} {str(c['abaixo_v_min']):>6}")
    return "\n".join(linhas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--casos", type=Path,
                    default=Path(carregar("interativo.toml")["arquivo_casos_padrao"]))
    ap.add_argument("--estagio", type=int, choices=(1, 2), default=1)
    ap.add_argument("--processos", type=int, default=1)
    ap.add_argument("--saida", type=Path, default=SAIDA)
    ap.add_argument("--limite", type=int, default=20, help="linhas da tabela impressa")
    ap.add_argument("--geometria", action="store_true",
                    help="não busca: avalia só a geometria já registrada no TAG e imprime a tabela dos casos")
    a = ap.parse_args(argv)
    propostas = mod_propostas.padrao()
    a.saida.mkdir(parents=True, exist_ok=True)

    if a.geometria:
        ctx = _contexto(a.casos, propostas)
        esp = _especificacao_registrada()
        # o duty é o número de trens em paralelo que o próprio catálogo registra
        conf = next(c for c in layout.configuracoes_de_servico(esp.dict["cascos_paralelo"])
                    if c.standby >= layout.reserva_exigida())
        r = _resumo(layout.avaliar(ctx, esp, conf))
        print(tabela_candidatos([r], 1), "\n")
        print(tabela_casos(r))
        print("\ngravado:", _gravar(r, a.saida / "geometria_registrada.json"))
        return 0 if r["viavel"] else 1

    if a.estagio == 1:
        pares = candidatos_estagio1()
    else:
        anterior = json.loads((a.saida / "estagio1.json").read_text(encoding="utf-8"))
        pares = candidatos_estagio2(frente_de_resumos(anterior["resumos"]))
        if not pares:
            print("estágio 1 não deixou candidato viável: nada a empacotar", file=sys.stderr)
            return 2
    print(f"estágio {a.estagio}: {len(pares)} candidatos, {a.processos} processo(s)", flush=True)
    resumos = rodar(pares, a.casos, propostas, a.processos, a.saida / f"estagio{a.estagio}.jsonl")
    f = frente_de_resumos(resumos)
    arq = _gravar({"resumos": resumos, "frente": f}, a.saida / f"estagio{a.estagio}.json")
    print(f"\nviáveis: {sum(r['viavel'] for r in resumos)}/{len(resumos)}; frente: {len(f)}")
    print("\n== frente de Pareto (área instalada × utilidade quente × utilidade fria) ==")
    print(tabela_candidatos(f, a.limite))
    if f:
        regra = layout.cfg()["selecao"]["regra"]
        limite = layout.cfg()["selecao"].get("l_tubo_max_com_fonte")
        com_fonte = [r for r in f if limite is None
                     or r["especificacao"].get("l_tubo_max", limite) <= limite] or f
        for rotulo, conjunto in (("com fonte no acervo (vai ao catálogo)", com_fonte),
                                 ("faixa inteira pedida pelo usuário", f)):
            for nome, chave in _chaves().items():
                escolhido = min(conjunto, key=chave)
                marca = " <- REGISTRADO" if (nome == regra and conjunto is com_fonte) else ""
                print(f"\n== {rotulo} · regra '{nome}'{marca} "
                      f"(área específica {_area_especifica(escolhido):.4f} m²/kW) ==")
                print(tabela_candidatos([escolhido], 1))
        print("\n== tabela dos 16 casos do candidato REGISTRADO ==")
        print(tabela_casos(min(com_fonte, key=_chaves()[regra])))
    print(f"\ngravado: {arq}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
