"""F7b/F10c — modo interativo, subcomando `dimensionar` e cabeçalho.

As sessões são roteirizadas (entrada injetada); o que a sessão grava tem de ser idêntico,
byte a byte, ao que o comando equivalente que ela imprime grava. Os números das opções vêm
de config/interativo.toml (op), não de literais: a ordem é da configuração."""
import io
import json
import shlex
from datetime import datetime
from pathlib import Path

import pytest

from fpso_siz import cli
from fpso_siz.cli import main
from fpso_siz.core.configuracao import carregar, exemplos
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


@pytest.fixture(autouse=True)
def pasta_temporaria(tmp_path, monkeypatch):
    """Sessões roteirizadas rodam numa pasta temporária: um roteiro desalinhado nunca
    grava no repositório."""
    monkeypatch.chdir(tmp_path)


def op(menu, acao):
    """Número da ação no menu, pela ordem declarada em interativo.toml."""
    ids = [a["id"] for a in carregar("interativo.toml")["menus"][menu]["acoes"]]
    return str(ids.index(acao) + 1)


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
    rc, out = rodar(op("principal", "balanco"), op("balanco", "auditoria"), op("balanco", "correntes"), "8",
                    op("balanco", "correntes"), "99", "0", "0")
    assert rc == 0
    assert "16 casos · 16 convergidos ✓" in out and "Premissas: todas no valor de base." in out
    assert "SG-001 FWKO" in out and "10, 11, 12, 13, 14, 15, 16" in out
    assert "energia_global" in out and "Correntes do caso 8" in out and "C-26" in out
    assert "caso '99' não existe." in out


def test_balanco_exporta_igual_ao_comando_equivalente(tmp_path):
    pasta = tmp_path / "s"
    rc, out = rodar(op("principal", "premissas"), "BSW_pre=0.02", "", op("principal", "balanco"),
                    op("balanco", "exportar"), "1,2", str(pasta), "0", "0")
    assert rc == 0
    assert "Premissas alteradas: P-28 BSW_pre = 0.02" in out
    assert "--premissa BSW_pre=0.02" in out and "--layout" not in out
    feitos = {p: p.read_bytes() for p in [pasta / "balanco.json", pasta / "correntes.csv", pasta / "memorial" / "main.tex"]}
    for p in feitos:
        p.unlink()
    assert repetir_comando(out) == [0, 0]
    assert all(p.read_bytes() == b for p, b in feitos.items())
    j = json.loads(feitos[pasta / "balanco.json"])
    assert [p["nome"] for p in j["premissas"] if p["alterada"]] == ["BSW_pre"]


def test_balanco_exportacao_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(mod_sessao.compilacao, "compilar", lambda tex: Path(tex).with_suffix(".pdf"))
    b, x = op("principal", "balanco"), op("balanco", "exportar")
    rc, out = rodar(b, x, "3", str(tmp_path), "0", "0")
    assert "main.pdf" in out and "--pdf" in out

    def falha(tex):
        raise mod_sessao.compilacao.ErroCompilacao("latexmk ausente")
    monkeypatch.setattr(mod_sessao.compilacao, "compilar", falha)
    rc, out = rodar(b, x, "3", str(tmp_path), "0", "0")
    assert "PDF não gerado: latexmk ausente" in out


@pytest.mark.parametrize("respostas, trecho", [
    (("9",), "formatos inválidos: '9'"),
])
def test_balanco_exportacao_invalida(respostas, trecho):
    _, out = rodar(op("principal", "balanco"), op("balanco", "exportar"), *respostas, "0", "0")
    assert trecho in out


def test_premissas_alterar_errar_e_restaurar():
    s, out = sessao(op("principal", "premissas"), "XX=1", "BSW_pre", "BSW_pre=abc", "BSW_pre=0.03", "base", "", "0")
    assert s.rodar() == 0
    txt = out.getvalue()
    assert "premissas desconhecidas: ['XX']" in txt and "espera NOME=VALOR" in txt and "não numérico" in txt
    assert "* alterada nesta sessão" in txt and s.alt == {}


def test_sem_arquivo_de_casos(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc, out = rodar(op("principal", "balanco"), str(CASOS), "0", "0", casos=None)
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
    c = op("principal", "casos")
    rc, out = rodar(c, str(tmp_path / "nao.json"), c, str(CASOS), op("casos", "trocar"), str(CASOS), "0", "0",
                    casos=ruim)
    assert rc == 0
    assert "não consegui ler o arquivo de casos" in out and "faltam as chaves" in out
    assert "erro: " in out and "Early Life Blend" in out


def test_opcao_invalida_eof_e_ctrl_c():
    n = len(carregar("interativo.toml")["menus"]["principal"]["acoes"])
    _, out = rodar(str(n + 1), "x")
    assert f"opção inválida: digite um número de 0 a {n}." in out and "Até logo." in out
    rc, out = rodar(KeyboardInterrupt())
    assert rc == 130 and "Interrompido." in out


# ------------------------------------------------------------------ equipamento avulso (arquivo/exemplo)
def _indice(label):
    import fpso_siz.sizing  # noqa: F401
    from fpso_siz.core import registro
    return str([e.method_id for e in registro.equipments()].index(label) + 1)


def _novo_avulso():
    """Equipamento / TAG → última opção da lista (novo avulso)."""
    from fpso_siz.pfd.tags import tags
    return [op("principal", "equipamento"), str(len(tags()) + 1)]


def _exemplo(eq_id, nome):
    from fpso_siz.pfd.manual import exemplos_de
    return str(exemplos_de(eq_id).index(nome) + 1)


@pytest.mark.parametrize("nome", sorted(exemplos()))
def test_avulso_por_exemplo_pendencias_sem_fonte_e_exportacao(nome, tmp_path):
    """O exemplo entra no adaptador manual: o que o arquivo não traz e não tem fonte no
    catálogo fica pendente (nunca herda o default do descritor em silêncio)."""
    from fpso_siz.output import ajustes as saida_ajustes
    eq_id = exemplos()[nome]["equipment"]
    pasta = tmp_path / eq_id
    s, out = sessao(*_novo_avulso(), _indice(eq_id), "", op("preenchimento", "arquivo"), _exemplo(eq_id, nome),
                    op("tag", "exportar"), str(pasta), "", "0", "0", "0")
    assert s.rodar() == 0
    txt = out.getvalue()
    assert f"Importado de exemplo:{nome}" in txt and "equipamento avulso" in txt.lower()
    estado = next(iter(s.ajustes.avulsos.values()))
    assert estado.arquivo == f"exemplo:{nome}" and estado.avulso
    assert f"fpso-siz dimensionar --avulso {estado.id} --ajustes {pasta / saida_ajustes.NOME} --saida {pasta}" in txt
    feitos = {p: p.read_bytes() for p in [pasta / f"{estado.id}.json", pasta / f"{estado.id}_varredura.csv"]}
    for p in feitos:
        p.unlink()
    assert repetir_comando(txt) in ([0], [1])
    assert all(p.read_bytes() == b for p, b in feitos.items())
    j = json.loads(feitos[pasta / f"{estado.id}.json"])
    assert j["avulso"] and j["modo"] == "manual" and j["proveniencia"]["arquivo"] is None
    origens = {v["origem"] for c in j["casos"] for v in c["valores"].values()}
    assert "arquivo" in origens and not origens & {"balanco", "propriedade", "premissa"}


def test_avulso_arquivo_de_outro_equipamento():
    _, out = rodar(*_novo_avulso(), _indice("pump"), "", op("preenchimento", "arquivo"),
                   str(len(exemplos_de_bomba()) + 1), str(FJ_CASOS / "exemplo_trocador.toml"), "0", "0")
    assert "declara equipment = 'exchanger', não 'pump'" in out


def exemplos_de_bomba():
    from fpso_siz.pfd.manual import exemplos_de
    return exemplos_de("pump")


def test_avulso_entrada_nao_declarada_e_erro(tmp_path):
    toml = tmp_path / "extra.toml"
    base = (FJ_CASOS / "exemplo_bomba.toml").read_text(encoding="utf-8")
    toml.write_text(base.replace("q_oil       = 215.8", "q_oil       = 215.8\nchave_estranha = 1", 1),
                    encoding="utf-8")
    _, out = rodar(*_novo_avulso(), _indice("pump"), "", op("preenchimento", "arquivo"),
                   str(len(exemplos_de_bomba()) + 1), str(toml), "0", "0")
    assert "entradas que o método não declara ['chave_estranha']" in out


def test_avulso_manual_preenche_e_dimensiona():
    """Knockout avulso digitado: sem arquivo, sem balanço; os defaults com fonte do
    catálogo entram como default a revisar e o resto é pedido."""
    # ordem das lacunas = ordem do método: tr_liquid, q_oil, q_gas, rho_oil, rho_gas, mu_gas, pressure,
    # temperature, z (valores do exemplo do Julia; só dados de teste)
    s, out = sessao(*_novo_avulso(), _indice("knockout"), "ko", op("preenchimento", "manual"), "1", "Caso A",
                    op("tag", "pendencias"), "3", "36", "25000", "780", "", "0,012", "3500", "60", "0.9",
                    op("tag", "pendencias"), "38", "0", "0", "0")
    assert s.rodar() == 0
    txt = out.getvalue()
    e = s.ajustes.avulsos["ko"]
    assert e.nomes_casos == ["Caso A"] and len(e.geral) == 9
    assert "adiado: rho_gas continua pendente." in txt
    assert "✓ Viável" in txt and "Resultado preliminar" in txt


def test_avulso_conta_impossivel_e_inviavel_nao_excecao():
    """Gás mais denso que o líquido: a raiz da velocidade terminal não existe. A edição não
    é desfeita; o equipamento fica inviável, com o diagnóstico."""
    s, out = sessao(*_novo_avulso(), _indice("knockout"), "ko", op("preenchimento", "manual"), "1", "Caso A",
                    op("tag", "pendencias"), "3", "36", "25000", "780", "900", "0,012", "3500", "60", "0.9",
                    "0", "0", "0")
    assert s.rodar() == 0
    txt = out.getvalue()
    assert "edição desfeita" not in txt and "✗ Inviável" in txt and "Cálculo impossível" in txt
    assert s.ajustes.avulsos["ko"].geral["rho_gas"] == 900


def test_avulso_nome_invalido_e_voltas():
    _, out = rodar(*_novo_avulso(), _indice("pump"), "nome com espaço", "0", "0")
    assert "não é um número finito" in out or "inválid" in out
    _, out = rodar(*_novo_avulso(), "0", "0", "0")
    assert out.count("Qual equipamento?") == 2


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


@pytest.mark.parametrize("encoding, forcar, unicode", [("utf-8", False, True), ("UTF8", False, True),
                                                      ("ascii", False, False), ("latin-1", False, False),
                                                      (None, False, True), ("utf-8", True, False)])
def test_estilo_detecta_unicode_pela_saida(encoding, forcar, unicode):
    class S:
        def isatty(self):
            return False
    s = S()
    s.encoding = encoding
    e = Estilo.para(s, {}, ascii=forcar)
    assert e.unicode is unicode and e.cor is False
    assert e.t("→ ρ µm ³ ✓ ação —") == ("→ ρ µm ³ ✓ ação —" if unicode else "-> rho um 3 ok acao -")


def test_dimensionar_exemplo_grava_no_contrato_do_julia(tmp_path, capsys):
    assert main(["dimensionar", "--exemplo", "alves_komesu", "--saida", str(tmp_path)]) == 0
    assert "gravados:" in capsys.readouterr().out
    j = json.loads((tmp_path / "dimensionamento.json").read_text(encoding="utf-8"))
    assert j["entrada"]["origem"] == "exemplo:alves_komesu" and j["resultado"]["x"] == 6300
    assert (tmp_path / "varredura.csv").read_text(encoding="utf-8").count("\n") > 10


def test_balanco_mostra_agua_e_padrao_num_caso_com_agua():
    """F10v: o resumo diz por onde a água sai e quais casos não têm fase aquosa; "Ver
    correntes" abre por padrão no primeiro caso com água (Enter), e um caso sem água é
    identificado como tal (BOT Nota 5, P-42)."""
    rc, out = rodar(op("principal", "balanco"), op("balanco", "correntes"), "",
                    op("balanco", "correntes"), "1", "0", "0")
    assert rc == 0
    assert "sai por C-05, C-25" in out and "Casos sem fase aquosa: 1, 4, 5, 6, 7" in out
    assert "Correntes do caso 2" in out  # Enter = padrão: o primeiro caso com água
    assert "Correntes do caso 1" in out and "O caso 1 não tem fase aquosa" in out
