"""F10c — telas de terminal: snapshots (Unicode, ASCII, estreito, sem cor; os quatro
estados), cor independente do conteúdo e esquemas validados contra a topologia — as
arestas desenhadas são relidas e comparadas com config/topologia_db.toml, também com
blocos/correntes renomeados e em outra ordem.

Para regenerar os snapshots depois de uma mudança intencional de tela:
    FPSO_SNAPSHOTS=1 uv run pytest tests/test_terminal_pfd.py
"""
import copy
import os
import re
from pathlib import Path

import pytest

from fpso_siz.balanco.balancos import topologia
from fpso_siz.balanco.dados import carregar_casos
from fpso_siz.output.terminal import esquema
from fpso_siz.output.terminal import pfd as tela
from fpso_siz.output.terminal.estilo import ANSI, Estilo, largura
from fpso_siz.pfd import ajustes as A
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import planta as mod_planta
from fpso_siz.pfd.tags import tags
from roteiro import CASOS, op, rodar

SNAP = Path(__file__).resolve().parent / "fixtures" / "terminal"
UNI, ASC = Estilo(False, True), Estilo(False, False)


@pytest.fixture(autouse=True)
def metodos_registrados():
    import fpso_siz.sizing
    fpso_siz.sizing.registrar()


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    """Sessões roteirizadas rodam numa pasta temporária: um roteiro desalinhado nunca
    grava no repositório."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="module")
def ctx():
    return servico.Contexto(carregar_casos(CASOS))


@pytest.fixture(scope="module")
def planta(ctx):
    return mod_planta.dimensionar(contexto=ctx)


@pytest.fixture(scope="module")
def planta_morto():
    """--oleo-morto: o SG-001 inviável (alarme) para a tela desse estado."""
    return mod_planta.dimensionar(contexto=servico.Contexto(carregar_casos(CASOS), oleo_vivo=False))


@pytest.fixture(scope="module")
def inativo(ctx):
    """B-001 com vazão zero informada em todos os casos: TAG inteiro inativo."""
    e = servico.estado_inicial("B-001")
    e.editar("q_oil", 0.0)
    return servico.executar(ctx, e)


def confere(nome, linhas):
    texto = "\n".join(linhas) + "\n"
    arq = SNAP / f"{nome}.txt"
    if os.environ.get("FPSO_SNAPSHOTS"):
        arq.parent.mkdir(parents=True, exist_ok=True)
        arq.write_text(texto, encoding="utf-8")
    assert arq.is_file(), f"snapshot ausente: {arq.name} (rode com FPSO_SNAPSHOTS=1)"
    assert texto == arq.read_text(encoding="utf-8"), arq.name


# ------------------------------------------------------------------ snapshots
def test_snapshot_menu_principal():
    rc, out, s = rodar("0")
    bloco = out[out.index("O que você quer fazer?"):out.index("Até logo.")].rstrip().splitlines()
    confere("menu_principal", bloco)


@pytest.mark.parametrize("nome, estilo, colunas, caso", [
    ("planta", UNI, 100, None), ("planta_ascii", ASC, 100, None), ("planta_estreita", UNI, 48, None),
    ("planta_caso1", UNI, 100, 1),
])
def test_snapshot_planta(planta, nome, estilo, colunas, caso):
    linhas = tela.resumo(planta, estilo, colunas, caso)
    confere(nome, linhas)
    assert all(largura(li) <= colunas for li in tela.tela_planta(planta.contexto, planta.tags, estilo, colunas, caso)
               if "━" not in li and "=" not in li[:3])


@pytest.mark.parametrize("ident, estado, qual", [("TO-001", "aguardando_entrada", "planta"),
                                                 ("V-001", "dimensionado", "planta"),
                                                 ("SG-001", "inviavel", "planta_morto")])
@pytest.mark.parametrize("variante, estilo, colunas", [("", UNI, 100), ("_ascii", ASC, 100), ("_estreita", UNI, 52)])
def test_snapshot_tag_nos_estados(request, ident, estado, qual, variante, estilo, colunas):
    planta = request.getfixturevalue(qual)
    rt = planta.tag(ident)
    assert rt.status == estado
    confere(f"tag_{ident}{variante}", tela.tela_tag(planta.contexto, rt, estilo, colunas))


def test_snapshot_tag_inativo(ctx, inativo):
    assert inativo.status == "inativo" and inativo.resultado is None
    linhas = tela.tela_tag(ctx, inativo, UNI, 100)
    confere("tag_B-001_inativo", linhas)
    assert "[B-001  -]" not in "\n".join(linhas) and "B-001  -" in "\n".join(linhas)


@pytest.mark.parametrize("variante, estilo, colunas", [("", UNI, 120), ("_estreita", UNI, 60), ("_ascii", ASC, 120)])
def test_snapshot_entradas_com_origem(planta, variante, estilo, colunas):
    rt = planta.tag("P-002")
    confere(f"entradas_P-002{variante}", tela.tabela_entradas(rt, 1, estilo, colunas))


def test_estreita_nunca_corta_identificadores(planta):
    linhas = tela.resumo(planta, UNI, 40)
    texto = "\n".join(linhas)
    topo = topologia()
    for ident in [*(b["id"] for b in topo["blocos"]), *(c["id"] for c in topo["correntes"]), *(t.tag for t in tags())]:
        assert re.search(rf"(?<![\w-]){re.escape(ident)}(?![\w-])", texto), ident
    for rt in planta.tags:
        for l in rt.entradas.lacunas:
            assert l.chave in texto
    assert all(largura(li) <= 40 for li in esquema.planta(topo, tela.marcadores(planta.tags, UNI), UNI, 40))


def test_ascii_e_so_ascii(planta, ctx):
    linhas = [*tela.resumo(planta, ASC, 100), *tela.tela_tag(ctx, planta.tag("V-001"), ASC, 100),
              *tela.tabela_entradas(planta.tag("P-002"), 1, ASC, 100)]
    assert all(ord(c) < 128 for li in linhas for c in li)


def test_cor_nao_muda_conteudo(planta, ctx):
    cor = Estilo(True, True)
    for fazer in (lambda e: tela.resumo(planta, e, 100), lambda e: tela.tela_tag(ctx, planta.tag("TO-001"), e, 100),
                  lambda e: tela.tela_tag(ctx, planta.tag("SG-001"), e, 100)):
        colorido, puro = fazer(cor), fazer(UNI)
        assert any("\x1b[" in li for li in colorido)
        assert [ANSI.sub("", li) for li in colorido] == puro
    # os estados têm rótulo e marcador, não só cor
    assert all(tela.rotulo_estado(s) and tela.marcador(s, UNI) for s in servico.ESTADOS)


# ------------------------------------------------------------------ esquemas × topologia
SETA = re.compile(r"\s*(?:→|->)\s*")
NOTA = re.compile(r"\s*\((saída|saida|retorno ao (\S+))\)$")


def reler_planta(linhas):
    """Linhas desenhadas → {bloco: (entradas, [(saída, nota)])}."""
    out = {}
    for li in linhas:
        partes = SETA.split(li.strip())
        if len(partes) != 3:
            continue
        ent, caixa, sai = partes
        bloco = re.fullmatch(r"\[(\S+)\s+\S\]", caixa).group(1)
        saidas = []
        for s in sai.split(", "):
            m = NOTA.search(s)
            saidas.append((NOTA.sub("", s), (m.group(2) or "saida") if m else None))
        out[bloco] = ([x for x in ent.split(", ") if x], saidas)
    return out


def conferir_planta(topo, linhas):
    relido = reler_planta(linhas)
    pos = {b["id"]: i for i, b in enumerate(topo["blocos"])}
    destino = {s: b["id"] for b in topo["blocos"] for s in b["entradas"]}
    assert list(relido) == [b["id"] for b in topo["blocos"]]  # ordem declarada
    for b in topo["blocos"]:
        ent, sai = relido[b["id"]]
        assert ent == b["entradas"] and [s for s, _ in sai] == b["saidas"]
        for s, nota in sai:
            if s in topo["global_out"]:
                assert nota == "saida" and s not in destino
            elif pos[destino[s]] <= pos[b["id"]]:
                assert nota == destino[s]  # reciclo: aponta o bloco aonde volta
            else:
                assert nota is None
    arest = esquema.arestas(topo)
    assert {a.corrente for a in arest} == {c for b in topo["blocos"] for c in (*b["entradas"], *b["saidas"])}
    assert {a.corrente for a in arest if a.origem is None} == set(topo["global_in"])
    assert {a.corrente for a in arest if a.destino is None} == set(topo["global_out"])


def reler_local(linhas):
    ent, sai = [], []
    for li in linhas:
        m = re.search(r"(\S+) (?:──|--) (\S+) (?:──→|-->) [│|]", li)
        if m:
            ent.append((m.group(1), m.group(2)))
        m = re.search(r"[│|] (?:──|--) (\S+) (?:──→|-->) (\S+)$", li)
        if m:
            sai.append((m.group(1), m.group(2)))
    return ent, sai


def conferir_local(topo, bloco, estilo=UNI):
    ent, sai = reler_local(esquema.local(topo, bloco, "?", estilo, 120))
    esperado_ent, esperado_sai = esquema.vizinhos(topo, bloco)
    assert ent == [(o or "entrada", s) for o, s in esperado_ent]
    assert sai == [(s, d or ("saída" if estilo.unicode else "saida")) for s, d in esperado_sai]
    b = next(x for x in topo["blocos"] if x["id"] == bloco)
    assert [s for _, s in ent] == b["entradas"] and [s for s, _ in sai] == b["saidas"]


def test_esquema_da_planta_confere_com_a_topologia(planta):
    topo = topologia()
    for estilo in (UNI, ASC):
        conferir_planta(topo, esquema.planta(topo, tela.marcadores(planta.tags, estilo), estilo, 100))
    # reciclo, fronteira e trocador com dois lados
    relido = reler_planta(esquema.planta(topo, {}, UNI, 100))
    assert ("C-02", "M-01") in relido["M-03"][1] and ("C-22", "P-001") in relido["B-001"][1]
    assert relido["P-001"][0] == ["C-06", "C-22"] and [s for s, _ in relido["P-001"][1]] == ["C-07", "C-23"]


def test_esquemas_locais_conferem_com_a_topologia():
    topo = topologia()
    for b in topo["blocos"]:
        conferir_local(topo, b["id"])
    conferir_local(topo, "P-001", ASC)


def renomeada():
    """Topologia com blocos e correntes renomeados e a ordem dos blocos invertida."""
    topo = copy.deepcopy(topologia())
    blocos = {b["id"]: f"Z{i:02d}-X" for i, b in enumerate(topo["blocos"])}
    correntes = {c["id"]: f"S{i:03d}" for i, c in enumerate(topo["correntes"])}
    for b in topo["blocos"]:
        b["id"] = blocos[b["id"]]
        b["entradas"] = [correntes[s] for s in b["entradas"]]
        b["saidas"] = [correntes[s] for s in b["saidas"]]
    topo["blocos"].reverse()
    topo["global_in"] = [correntes[s] for s in topo["global_in"]]
    topo["global_out"] = [correntes[s] for s in topo["global_out"]]
    topo["correntes"] = [{**c, "id": correntes[c["id"]]} for c in topo["correntes"]]
    return topo, blocos, correntes


def test_esquemas_acompanham_nomes_e_ordem_da_configuracao(planta):
    topo, blocos, correntes = renomeada()
    marcas = {blocos[t.tag.bloco]: tela.marcador(t.status, UNI) for t in planta.tags}
    linhas = esquema.planta(topo, marcas, UNI, 100)
    conferir_planta(topo, linhas)
    texto = "\n".join(linhas)
    assert not re.search(r"\bC-\d\d\b|\bM-01\b", texto)
    assert [li.split("[")[1].split()[0] for li in linhas] == [b["id"] for b in topo["blocos"]]
    # com a ordem invertida, o reciclo passa a ser outra aresta: quem vem antes muda
    relido = reler_planta(linhas)
    retornos = {s for _, sai in relido.values() for s, n in sai if n not in (None, "saida")}
    assert retornos and retornos != {correntes["C-02"], correntes["C-22"]}
    for b in topo["blocos"]:
        conferir_local(topo, b["id"])
    # a tela da planta usa a topologia que receber
    tela_ren = tela.tela_planta(planta.contexto, planta.tags, UNI, 100, topo=topo)
    assert "Z00-X" in "\n".join(tela_ren)


def test_tag_renomeado_segue_o_descritor(planta, ctx, monkeypatch):
    """O nome do TAG na tela vem do descritor (config/pfd/tags), não do código."""
    import dataclasses
    rt = planta.tag("P-001")
    novo = dataclasses.replace(rt.tag, tag="HX-900", nome="Trocador renomeado", bloco="P-001")
    rt2 = servico.ResultadoTAG(dataclasses.replace(rt.entradas, tag=novo), rt.resultado, rt.estado)
    texto = "\n".join(tela.tela_tag(ctx, rt2, UNI, 100))
    assert "HX-900 · Trocador renomeado" in texto and "P-001" in texto  # o bloco continua o do balanço


def test_faixa_de_casos():
    assert tela.faixa_casos([1, 2, 3, 5, 7, 8]) == "1–3, 5, 7–8" and tela.faixa_casos([]) == "—"


def test_tela_de_estado_dos_ajustes(ctx):
    aj = A.Ajustes(tags={"V-001": servico.estado_inicial("V-001", A.MANUAL)})
    aj.tags["V-001"].editar("q_oil", 1.0, casos=[2])
    linhas = tela.tabela_estado(aj, UNI)
    assert "V-001" in linhas[2] and "manual" in linhas[2]


def test_sessao_ascii_e_estreita_sem_quebrar():
    rc, out, s = rodar(op("principal", "planta"), "0", "0", colunas=60, unicode=False)
    assert rc == 0 and all(ord(c) < 128 for c in out)
    assert "[SG-001  D]" in out and "-> [" in out
