"""F7b — modo interativo, subcomando `dimensionar` e cabeçalho.

As sessões são roteirizadas (entrada injetada); o que a sessão grava tem de ser idêntico,
byte a byte, ao que o comando equivalente que ela imprime grava."""
import io
import json
import shlex
from datetime import datetime
from pathlib import Path

import pytest

from fpso_siz import cli
from fpso_siz.cli import main
from fpso_siz.core.configuracao import exemplos
from fpso_siz.output.terminal import sessao as mod_sessao
from fpso_siz.output.terminal.cabecalho import LARGURA, cabecalho
from fpso_siz.output.terminal.estilo import ANSI, Estilo, largura, num, sig, tabela
from fpso_siz.output.terminal.relatorio import curto
from fpso_siz.output.terminal.sessao import Sessao

RAIZ = Path(__file__).resolve().parents[1]
CASOS = RAIZ / "tests" / "fixtures" / "python_ref" / "design_cases_bot.json"
FJ_CASOS = RAIZ / "tests" / "fixtures" / "julia" / "casos"
AGORA = datetime(2026, 9, 23, 14, 2, 11)


@pytest.fixture(autouse=True)
def metodos_registrados():
    """Outros testes esvaziam o registro (métodos-brinquedo); a CLI precisa dos reais."""
    import fpso_siz.sizing
    fpso_siz.sizing.registrar()


def roteiro(*respostas):
    fila = list(respostas)

    def entrada(prompt):
        if not fila:
            raise EOFError
        r = fila.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r
    return entrada


def sessao(*respostas, casos=CASOS, colunas=100, cor=False):
    out = io.StringIO()
    s = Sessao(casos=casos, entrada=roteiro(*respostas), saida=out, estilo=Estilo(cor), colunas=colunas,
               agora=lambda: AGORA)
    return s, out


def rodar(*respostas, **kw):
    s, out = sessao(*respostas, **kw)
    return s.rodar(), out.getvalue()


def repetir_comando(texto):
    """Executa, via main(), cada linha 'fpso-siz …' que a sessão mandou repetir."""
    bloco = texto.split("Para repetir sem o assistente:")[-1]
    cmds = [shlex.split(li.strip())[1:] for li in bloco.splitlines() if li.strip().startswith("fpso-siz ")]
    assert cmds
    return [main(c) for c in cmds]


# ------------------------------------------------------------------ cabeçalho
def test_cabecalho_moldura_openfoam_sem_cor():
    txt = cabecalho(["", "título", "Versão: x"], [("Exec", "fpso-siz interativo"), ("PID", "1")], Estilo(False))
    linhas = txt.splitlines()
    assert linhas[0] == "/*" + "-" * (LARGURA - 4) + "*\\"
    assert linhas[6] == "\\*" + "-" * (LARGURA - 4) + "*/"
    assert linhas[2].startswith("  \\\\      /  F loating")
    assert linhas[5].startswith("     \\\\/     O ffloading")
    assert all(li.index("|") == 28 for li in linhas[1:6])
    assert "| título" in linhas[2] and "Exec : fpso-siz interativo" in txt and "Dicas:" in txt


def test_cabecalho_colorido_tem_mesma_largura_visivel():
    args = (["", "título"], [("Exec", "x")])
    puro, cor = cabecalho(*args, Estilo(False)), cabecalho(*args, Estilo(True))
    assert "\x1b[" in cor and "\x1b[" not in puro
    assert ANSI.sub("", cor) == puro


def test_cabecalho_compacto_em_terminal_estreito():
    txt = cabecalho(["", "título"], [("Exec", "x")], Estilo(False), colunas=60)
    assert "/*" not in txt and txt.startswith("FPSO_Siz título") and "Exec: x" in txt


def test_sessao_mostra_cabecalho_e_contexto():
    rc, out = rodar("0")
    assert rc == 0
    assert "F loating" in out and "Data  : 23/09/2026  14:02:11" in out
    assert "design_cases_bot.json · 16 casos" in out and "Fonte    BOT I-ET-3010" in out
    assert out.rstrip().endswith("Até logo.")


# ------------------------------------------------------------------ estilo
@pytest.mark.parametrize("env, tty, cor", [
    ({}, True, True), ({}, False, False), ({"NO_COLOR": "1"}, True, False), ({"FORCE_COLOR": "1"}, False, True),
    ({"TERM": "dumb"}, True, False),
])
def test_estilo_decide_cor(env, tty, cor):
    class S:
        def isatty(self):
            return tty
    assert Estilo.para(S(), env).cor is cor


def test_numeros_e_tabela():
    assert num(1234.5, 1) == "1.234,5" and num(float("nan")) == "—" and num(None) == "—" and num("x") == "x"
    assert sig(0.000123456789) == "0,000123457" and sig(float("inf")) == "—" and sig("t") == "t"
    linhas = tabela(["a", "b"], [["x", "1,0"], ["yy", "10,0"]], Estilo(False))
    assert linhas[2] == "  x    1,0" and linhas[3] == "  yy  10,0"
    assert tabela(["a"], [], Estilo(False))[0] == "  a"
    e = Estilo(True)
    assert largura(e.ok("✓")) == 1 and e.status("erro") != e.status("ok") and e.status("neutro") == " "


def test_nome_de_caso_curto_preserva_etiqueta_de_canto():
    assert curto("abc") == "abc"
    assert curto("x" * 60).endswith("…") and len(curto("x" * 60)) == 44
    c = curto("Faixa de operação muito longa demais [mu_oil↑ q_oil↑ q_water↓]")
    assert c.endswith("[mu_oil↑ q_oil↑ q_water↓]") and "…" in c


# ------------------------------------------------------------------ balanço
def test_balanco_resumo_auditoria_correntes_e_voltar():
    rc, out = rodar("1", "1", "2", "8", "2", "99", "0", "0")
    assert rc == 0
    assert "16 casos · 16 convergidos ✓" in out and "Premissas: todas no valor de base." in out
    assert "SG-001 FWKO" in out and "10, 11, 12, 13, 14, 15, 16" in out
    assert "energia_global" in out and "Correntes do caso 8" in out and "C-26" in out
    assert "caso '99' não existe." in out


def test_balanco_exporta_igual_ao_comando_equivalente(tmp_path):
    pasta = tmp_path / "s"
    rc, out = rodar("3", "BSW_pre=0.02", "", "1", "3", "1,2", str(pasta), "original", "0", "0")
    assert rc == 0
    assert "Premissas alteradas: P-28 BSW_pre = 0.02" in out
    assert "--premissa BSW_pre=0.02" in out and "--layout original" in out
    feitos = {p: p.read_bytes() for p in [pasta / "balanco.json", pasta / "correntes.csv", pasta / "memorial" / "main.tex"]}
    for p in feitos:
        p.unlink()
    assert repetir_comando(out) == [0, 0]
    assert all(p.read_bytes() == b for p, b in feitos.items())
    j = json.loads(feitos[pasta / "balanco.json"])
    assert [p["nome"] for p in j["premissas"] if p["alterada"]] == ["BSW_pre"]


def test_balanco_exportacao_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_sessao.compilacao, "compilar", lambda tex: Path(tex).with_suffix(".pdf"))
    rc, out = rodar("1", "3", "3", str(tmp_path), "senai", "0", "0")
    assert "main.pdf" in out and "--pdf" in out

    def falha(tex):
        raise mod_sessao.compilacao.ErroCompilacao("latexmk ausente")
    monkeypatch.setattr(mod_sessao.compilacao, "compilar", falha)
    rc, out = rodar("1", "3", "3", str(tmp_path), "senai", "0", "0")
    assert "PDF não gerado: latexmk ausente" in out


@pytest.mark.parametrize("respostas, trecho", [
    (("1", "3", "9"), "formatos inválidos: '9'"),
    (("1", "3", "2", "p", "xyz"), "layout desconhecido 'xyz'"),
])
def test_balanco_exportacao_invalida(respostas, trecho):
    _, out = rodar(*respostas, "0", "0")
    assert trecho in out


def test_premissas_alterar_errar_e_restaurar():
    s, out = sessao("3", "XX=1", "BSW_pre", "BSW_pre=abc", "BSW_pre=0.03", "base", "", "0")
    assert s.rodar() == 0
    txt = out.getvalue()
    assert "premissas desconhecidas: ['XX']" in txt and "espera NOME=VALOR" in txt and "não numérico" in txt
    assert "* alterada nesta sessão" in txt and s.alt == {}


def test_sem_arquivo_de_casos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out = rodar("1", str(CASOS), "0", "0", casos=None)
    assert "Nenhum arquivo de casos carregado" in out and "nenhum arquivo carregado" in out
    assert "16 convergidos" in out


def test_arquivo_padrao_na_pasta_corrente(tmp_path, monkeypatch):
    (tmp_path / "design_cases_bot.json").write_bytes(CASOS.read_bytes())
    monkeypatch.chdir(tmp_path)
    _, out = rodar("0", casos=None)
    assert "design_cases_bot.json · 16 casos" in out


def test_arquivo_invalido_vira_aviso_e_troca_de_arquivo(tmp_path):
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{}", encoding="utf-8")
    rc, out = rodar("4", str(tmp_path / "nao.json"), "4", str(CASOS), "1", str(CASOS), "0", "0", casos=ruim)
    assert rc == 0
    assert "não consegui ler o arquivo de casos" in out and "faltam as chaves" in out
    assert "erro: " in out and "Early Life Blend" in out


def test_opcao_invalida_eof_e_ctrl_c():
    _, out = rodar("7", "x")
    assert "opção inválida: digite um número de 0 a 4." in out and "Até logo." in out
    rc, out = rodar(KeyboardInterrupt())
    assert rc == 130 and "Interrompido." in out


# ------------------------------------------------------------------ equipamentos
def _indice(label):
    import fpso_siz.sizing  # noqa: F401
    from fpso_siz.core import registro
    return str([e.method_id for e in registro.equipments()].index(label) + 1)


@pytest.mark.parametrize("nome", sorted(exemplos()))
def test_equipamento_exemplo_resumo_varredura_rastro_e_exportacao(nome, tmp_path):
    eq_id = exemplos()[nome]["equipment"]
    pasta = tmp_path / eq_id
    rc, out = rodar("2", _indice(eq_id), "1", "1", "2", "1", "3", str(pasta), "0", "0")
    assert rc == 0
    assert "Casos de entrada · Exemplo" in out and "Resultado · " in out and "✓ Viável" in out
    assert "━━ Varredura" in out and "◀" in out and "━━ Rastro · " in out
    assert f"fpso-siz dimensionar --exemplo {nome} --saida {pasta}" in out
    feitos = {p: p.read_bytes() for p in [pasta / "dimensionamento.json", pasta / "varredura.csv"]}
    for p in feitos:
        p.unlink()
    assert repetir_comando(out) == [0]
    assert all(p.read_bytes() == b for p, b in feitos.items())
    j = json.loads(feitos[pasta / "dimensionamento.json"])
    assert j["equipamento"]["id"] == eq_id and j["resultado"]["viavel"] and j["entrada"]["origem"] == f"exemplo:{nome}"
    assert j["casos"] and j["resultado"]["cartao"]


def test_equipamento_por_arquivo_toml(tmp_path):
    toml = FJ_CASOS / "exemplo_bomba.toml"
    pasta = tmp_path / "b"
    rc, out = rodar("2", _indice("pump"), "2", str(toml), "3", str(pasta), "0", "0")
    assert rc == 0 and f"--casos {toml} --equipamento pump --saida {pasta}" in out
    assert repetir_comando(out) == [0]


def test_equipamento_arquivo_de_outro_equipamento(tmp_path):
    _, out = rodar("2", _indice("pump"), "2", str(FJ_CASOS / "exemplo_trocador.toml"), "0")
    assert "declara equipment = 'exchanger', não 'pump'" in out


def test_equipamento_inviavel_e_voltas(tmp_path):
    toml = tmp_path / "inviavel.toml"
    toml.write_text('[[case]]\nname = "sem vazão"\nq_oil = 0\nq_water = 0\nq_gas = 0\n', encoding="utf-8")
    rc, out = rodar("2", _indice("separator"), "2", str(toml), "2", "0", "0")
    assert rc == 0 and "✗ Inviável" in out and "caso sem as entradas de corrente" in out
    assert "não há caso dimensionado para mostrar." in out
    _, out = rodar("2", "0", "2", _indice("pump"), "0", "0")
    assert out.count("Qual equipamento?") == 2


def test_rastro_sem_casos(tmp_path):
    toml = tmp_path / "vazio.toml"
    toml.write_text('[[case]]\nname = "off"\nenabled = false\nq_oil = 1\n', encoding="utf-8")
    _, out = rodar("2", _indice("separator"), "2", str(toml), "2", "0", "0")
    assert "Nenhum caso ativo" in out and "não há caso dimensionado para mostrar." in out


def test_entradas_nao_declaradas_sao_avisadas(tmp_path):
    toml = tmp_path / "extra.toml"
    base = (FJ_CASOS / "exemplo_bomba.toml").read_text(encoding="utf-8")
    toml.write_text(base.replace("q_oil       = 215.8", "q_oil       = 215.8\nchave_estranha = 1", 1),
                    encoding="utf-8")
    _, out = rodar("2", _indice("pump"), "2", str(toml), "0", "0")
    assert "Entradas que o método não declara (ignoradas): chave_estranha" in out


# ------------------------------------------------------------------ CLI por comando
def test_dimensionar_exemplo_so_resumo(capsys):
    assert main(["dimensionar", "--exemplo", "alves_komesu"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("━━ Resultado · Separador Trifásico Horizontal") and "6.300 mm" in out
    assert "gravados" not in out


def test_dimensionar_inviavel_retorna_1(tmp_path, capsys):
    toml = tmp_path / "x.toml"
    base = (FJ_CASOS / "exemplo_alves_komesu.toml").read_text(encoding="utf-8")
    toml.write_text(base.replace("[[case]]", "[[case]]\nsr_min = 9.0\nsr_max = 9.5\nsr_target = 9.2", 1),
                    encoding="utf-8")
    assert main(["dimensionar", "--casos", str(toml)]) == 1
    assert "Inviável" in capsys.readouterr().out


@pytest.mark.parametrize("args, trecho", [
    (["--casos", "{sem}"], "informe --equipamento"),
    (["--exemplo", "bomba", "--equipamento", "separator"], "mas --equipamento = 'separator'"),
    (["--exemplo", "bomba", "--metodo", "nenhum"], "método desconhecido 'nenhum'"),
])
def test_dimensionar_erros(tmp_path, capsys, args, trecho):
    sem = tmp_path / "sem.toml"
    sem.write_text('[[case]]\nname = "a"\n', encoding="utf-8")
    assert main(["dimensionar", *[a.replace("{sem}", str(sem)) for a in args]]) == 2
    assert trecho in capsys.readouterr().err


def test_registro_resolver():
    import fpso_siz.sizing  # noqa: F401
    from fpso_siz.core import registro
    eq, m = registro.resolver("pump", "moran")
    assert (eq.method_id, m.method_id) == ("pump", "moran")
    with pytest.raises(ValueError, match="equipamento desconhecido"):
        registro.resolver("reator")
    registro.register(type("Vazio", (registro.Equipamento,), {"method_id": "vazio", "label": "Vazio"})())
    try:
        with pytest.raises(ValueError, match="não tem método"):
            registro.resolver("vazio")
    finally:
        registro._EQUIPAMENTOS.pop("vazio")
        registro._METODOS.pop("vazio")


def test_sem_argumentos(monkeypatch):
    monkeypatch.setattr(cli, "_terminal", lambda: False)
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2
    monkeypatch.setattr(cli, "_terminal", lambda: True)
    monkeypatch.setattr(cli.Sessao, "rodar", lambda self: 42)
    assert main([]) == 42
    assert main(["interativo", "--casos", str(CASOS)]) == 42


def test_exemplos_embutidos_sao_copia_dos_do_julia():
    for nome in exemplos():
        pacote = RAIZ / "src" / "fpso_siz" / "config" / "exemplos" / f"exemplo_{nome}.toml"
        assert pacote.read_bytes() == (FJ_CASOS / pacote.name).read_bytes(), nome
