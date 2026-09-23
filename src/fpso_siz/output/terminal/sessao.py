"""Modo interativo (`fpso-siz` num terminal, ou `fpso-siz interativo`).

Contexto primeiro (arquivo, casos, premissas), resumo antes de exportar, exportar é
opcional e, ao gravar, a sessão mostra a linha de comando que repete o que foi feito.
Entrada e saída são injetáveis: os testes roteirizam sessões inteiras.
Invariante 4: menus e tabelas iteram o registro de métodos e os descritores.
"""
import os
import platform
import shutil
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

from fpso_siz import __version__
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import carregar_casos, descritores_premissas, premissas
from fpso_siz.balanco.modelo import resolver_todos
from fpso_siz.core import registro
from fpso_siz.core.casos import case_set_from_config
from fpso_siz.core.configuracao import carregar, exemplos
from fpso_siz.core.motor import size_envelope
from fpso_siz.output import dimensionamento
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.balanco import memorial
from fpso_siz.output.terminal import relatorio as rel
from fpso_siz.output.terminal.cabecalho import cabecalho
from fpso_siz.output.terminal.comum import alteracoes, comando, gravar_balanco
from fpso_siz.output.terminal.estilo import Estilo, tabela

PASTA_PADRAO = "saida"
LAYOUT_PADRAO = "senai"
ERROS = (ValueError, KeyError, OSError)


class _Sair(Exception):
    """Fim da entrada (Ctrl+D) ou pedido de saída."""


def _msg(e):
    return e.args[0] if isinstance(e, KeyError) and e.args else e  # KeyError põe aspas no str()


class Sessao:
    def __init__(self, casos=None, entrada=input, saida=None, estilo=None, colunas=None, agora=datetime.now):
        self.saida = saida if saida is not None else sys.stdout
        self.entrada = entrada
        self.e = estilo if estilo is not None else Estilo.para(self.saida)
        self.colunas = colunas or shutil.get_terminal_size().columns
        self.agora = agora
        self.cfg = carregar("interativo.toml")
        self.dados = None
        self.caminho_casos = None
        self.alt = {}
        self._inicial = casos

    # ------------------------------------------------------------------ E/S
    def dizer(self, *linhas):
        for li in linhas:
            print(li, file=self.saida)

    def aviso(self, texto):
        self.dizer(self.e.aviso(f"  ! {texto}"))

    def perguntar(self, texto, padrao=None):
        dica = f" [{padrao}]" if padrao not in (None, "") else ""
        try:
            r = self.entrada(f"{texto}{dica} › ")
        except EOFError:
            raise _Sair from None
        r = r.strip()
        return r if r else ("" if padrao is None else str(padrao))

    def escolher(self, titulo, opcoes, voltar="Voltar", padrao=None):
        """opcoes = [(rótulo, detalhe)] → índice 0-based, ou None (0 = voltar)."""
        self.dizer("", self.e.negrito(titulo))
        w = max((len(r) for r, _ in opcoes), default=0)
        for i, (r, d) in enumerate(opcoes, 1):
            self.dizer(f"  {self.e.destaque(str(i).rjust(2))}  {r.ljust(w)}  {self.e.fraco(d)}".rstrip())
        self.dizer(f"  {self.e.fraco(' 0')}  {self.e.fraco(voltar)}")
        while True:
            r = self.perguntar("Opção", padrao)
            if r.isdigit() and 0 <= int(r) <= len(opcoes):
                return None if int(r) == 0 else int(r) - 1
            self.aviso(f"opção inválida: digite um número de 0 a {len(opcoes)}.")

    def repetir(self, comandos, gravados):
        self.dizer("", self.e.negrito("  Gravado:"), *(f"    {p}" for p in gravados))
        self.dizer("", self.e.negrito("  Para repetir sem o assistente:"),
                   *(f"    {self.e.destaque(c)}" for c in comandos))

    # ------------------------------------------------------------------ ciclo
    def rodar(self):
        if self.entrada is input and sys.stdin.isatty():  # pragma: no cover - só num terminal real
            try:
                import readline  # noqa: F401  (edição de linha e histórico no input())
            except ImportError:
                pass
        erro_inicial = None
        try:
            self._carregar_inicial()
        except ERROS as e:
            erro_inicial = e
        try:
            self.dizer(self._cabecalho())
            if erro_inicial is not None:
                self.aviso(f"não consegui ler o arquivo de casos: {_msg(erro_inicial)}")
            self._contexto()
            self._menu()
        except _Sair:
            pass
        except KeyboardInterrupt:
            self.dizer("", "Interrompido.")
            return 130
        self.dizer("", self.e.fraco("Até logo."))
        return 0

    def _carregar_inicial(self):
        if self._inicial is not None:
            self._carregar(self._inicial)
            return
        padrao = Path(self.cfg["arquivo_casos_padrao"])
        if padrao.is_file():
            self._carregar(padrao)

    def _carregar(self, caminho):
        self.dados = carregar_casos(caminho)
        self.caminho_casos = Path(caminho)

    def _cabecalho(self):
        n_eq = len(registro.equipments())
        n_m = sum(len(registro.methods_for(eq)) for eq in registro.equipments())
        py = platform.python_version()
        direita = ["", "FPSO_Siz: balanço de massa e energia e dimensionamento",
                   f"Versão:   {__version__}", f"Núcleo:   Python {py} · {n_eq} equipamentos, {n_m} métodos",
                   "Uso:      fpso-siz --help (comandos para scripts)"]
        agora = self.agora()
        casos = (f"{self.dados.origem} · {len(self.dados.casos)} casos" if self.dados
                 else self.e.fraco("nenhum arquivo carregado"))
        execucao = [("Exec", "fpso-siz interativo"), ("Data", agora.strftime("%d/%m/%Y  %H:%M:%S")),
                    ("Host", f"{platform.node() or '?'} · PID {os.getpid()}"), ("Pasta", str(Path.cwd())),
                    ("Casos", casos)]
        return cabecalho(direita, execucao, self.e, self.colunas)

    def _contexto(self):
        self.dizer(self.e.negrito("Contexto"))
        if self.dados is None:
            self.dizer("  Nenhum arquivo de casos carregado. O balanço pede o JSON do BOT (opção 4);",
                       "  os equipamentos têm exemplos embutidos (opção 2).")
            return
        self.dizer(*rel.contexto_casos(self.dados, self.e))

    def _menu(self):
        while True:
            n_alt = len(self.alt)
            ops = [("Balanço de massa e energia",
                    f"{len(self.dados.casos)} casos" if self.dados else "pede um arquivo de casos"),
                   ("Dimensionar equipamento", f"{len(registro.equipments())} equipamentos"),
                   ("Premissas do balanço", f"{n_alt} alterada(s)" if n_alt else "todas no valor de base"),
                   ("Casos de projeto", self.dados.origem if self.dados else "carregar arquivo")]
            i = self.escolher("O que você quer fazer?", ops, voltar="Sair")
            if i is None:
                return
            try:
                (self._balanco, self._equipamento, self._premissas, self._casos)[i]()
            except ERROS as e:
                self.aviso(f"erro: {_msg(e)}")

    # ------------------------------------------------------------------ casos
    def _pedir_casos(self):
        atual = str(self.caminho_casos) if self.caminho_casos else self.cfg["arquivo_casos_padrao"]
        caminho = self.perguntar("Arquivo de casos (JSON do BOT)", atual)
        self._carregar(Path(caminho).expanduser())
        self.dizer("", *rel.contexto_casos(self.dados, self.e))

    def _casos(self):
        if self.dados is None:
            self._pedir_casos()
        while True:
            self.dizer(*rel.titulo("Casos de projeto", self.e, self.colunas), *rel.tabela_casos(self.dados, self.e))
            if self.escolher("Casos", [("Trocar arquivo de casos", str(self.caminho_casos))]) is None:
                return
            self._pedir_casos()

    # ------------------------------------------------------------------ premissas
    def _premissas(self):
        mostrar = True
        while True:
            if mostrar:
                self._tabela_premissas()
            r = self.perguntar("Alterar (NOME=VALOR; 'base' restaura todas; Enter volta)")
            if not r:
                return
            mostrar = True
            if r.lower() == "base":
                self.alt = {}
                continue
            try:
                novo = {**self.alt, **alteracoes([r])}
                premissas(self.dados, **novo)
            except ERROS as e:
                self.aviso(str(_msg(e)).replace("--premissa ", ""))
                mostrar = False
                continue
            self.alt = novo

    def _tabela_premissas(self):
        prem = premissas(self.dados, **self.alt)
        linhas = []
        for d in descritores_premissas(self.dados):
            v = prem[d["nome"]]
            marca = self.e.aviso("*") if d["nome"] in self.alt else ""
            linhas.append([d["id"], d["nome"], marca, f"({d['origem']})" if v is None else str(v), d["unidade"],
                           d["descricao"]])
        self.dizer(*rel.titulo("Premissas do balanço", self.e, self.colunas),
                   *tabela(["Id", "Nome", "", "Valor", "Unidade", "Descrição"], linhas, self.e))
        if self.alt:
            self.dizer(self.e.fraco("  * alterada nesta sessão (vale para o balanço e para o memorial)"))

    # ------------------------------------------------------------------ balanço
    def _balanco(self):
        if self.dados is None:
            self._pedir_casos()
        prem = premissas(self.dados, **self.alt)
        self.dizer("", f"  Resolvendo {len(self.dados.casos)} casos…")
        t0 = time.perf_counter()
        res = resolver_todos(self.dados, prem)
        aud = auditar(res, self.dados, prem)
        dt = time.perf_counter() - t0
        self.dizer(*rel.resumo_balanco(res, aud, self.dados, prem, descritores_premissas(self.dados), self.e,
                                       self.colunas, dt))
        while True:
            i = self.escolher("Próximo passo", [("Ver auditoria independente", f"{len(aud)} verificações"),
                                                ("Ver correntes de um caso", "T, P e vazões por corrente"),
                                                ("Exportar", "JSON/CSV, memorial LaTeX, PDF")])
            if i is None:
                return
            if i == 0:
                self.dizer(*rel.titulo("Auditoria independente", self.e, self.colunas),
                           *rel.tabela_auditoria(aud, self.e))
            elif i == 1:
                nums = [r.num for r in res]
                r = self.perguntar(f"Caso ({nums[0]}–{nums[-1]})", nums[0])
                if not r.isdigit() or int(r) not in nums:
                    self.aviso(f"caso {r!r} não existe.")
                    continue
                self.dizer(*rel.titulo(f"Correntes do caso {r}", self.e, self.colunas),
                           *rel.tabela_correntes_caso(res, int(r), self.e))
            else:
                self._exportar_balanco(prem, res, aud)

    def _exportar_balanco(self, prem, res, aud):
        r = self.perguntar("Formatos: 1 JSON+CSV · 2 memorial LaTeX · 3 memorial + PDF (ex.: 1,2)", "1")
        formatos = {x.strip() for x in r.split(",") if x.strip()}
        if not formatos or not formatos <= {"1", "2", "3"}:
            self.aviso(f"formatos inválidos: {r!r}.")
            return
        pasta = Path(self.perguntar("Pasta de saída", PASTA_PADRAO)).expanduser()
        base = dict(casos=str(self.caminho_casos), saida=str(pasta),
                    premissa=[f"{k}={v}" for k, v in self.alt.items()])
        gravados, cmds = [], []
        if "1" in formatos:
            gravados += gravar_balanco(self.dados, prem, res, aud, pasta)
            cmds.append(comando("balanco", **base))
        if formatos & {"2", "3"}:
            layout = self.perguntar(f"Layout do memorial ({'/'.join(sorted(memorial.LAYOUTS))})", LAYOUT_PADRAO)
            if layout not in memorial.LAYOUTS:
                self.aviso(f"layout desconhecido {layout!r}.")
                return
            destino = pasta / "memorial"
            tex = memorial.gravar(self.dados, prem, res, destino, layout)
            gravados.append(tex)
            cmds.append(comando("memorial", **{**base, "saida": str(destino)}, layout=layout, pdf="3" in formatos))
            if "3" in formatos:
                self.dizer("  Compilando o PDF (latexmk)…")
                try:
                    gravados.append(compilacao.compilar(tex))
                except compilacao.ErroCompilacao as e:
                    self.aviso(f"PDF não gerado: {e}")
        self.repetir(cmds, gravados)

    # ------------------------------------------------------------------ equipamentos
    def _equipamento(self):
        eqs = registro.equipments()
        i = self.escolher("Qual equipamento?",
                          [(eq.label, f"{len(registro.methods_for(eq))} método(s)") for eq in eqs])
        if i is None:
            return
        eq = eqs[i]
        metodos = registro.methods_for(eq)
        j = 0 if len(metodos) == 1 else self.escolher("Qual método?", [(m.label, m.method_id) for m in metodos])
        if j is None:
            return
        m = metodos[j]
        ref = getattr(m, "method_reference", lambda: "")()
        self.dizer("", f"  Método: {self.e.negrito(m.label)}", *(self.e.fraco(s) for s in rel.quebrar(ref, self.colunas)))
        fonte = self._fonte_casos(eq)
        if fonte is None:
            return
        cfg, origem, opcao = fonte
        casos = case_set_from_config(cfg)
        self.dizer(*rel.titulo(f"Casos de entrada · {cfg.get('label', origem)}", self.e, self.colunas),
                   *rel.tabela_entradas(m, casos, self.e))
        self.dizer("", f"  {m.action_label()}…")
        r = size_envelope(eq, m, casos)
        self.dizer(*rel.resumo_dimensionamento(eq, m, r, self.e, self.colunas))
        while True:
            k = self.escolher("Próximo passo", [("Ver varredura", f"{len(r.rows)} pontos da grade"),
                                                ("Ver rastro de cálculo de um caso", "equação por equação"),
                                                ("Exportar", "JSON (resultado) + CSV (varredura)")])
            if k is None:
                return
            if k == 0:
                self.dizer(*rel.titulo("Varredura", self.e, self.colunas), *rel.tabela_varredura(m, r, self.e))
            elif k == 1:
                self._rastro(m, r)
            else:
                self._exportar_equipamento(eq, m, casos, r, origem, opcao)

    def _fonte_casos(self, eq):
        exs = {n: c for n, c in exemplos().items() if c.get("equipment") == eq.method_id}
        ops = [(c.get("label", n), f"exemplo embutido · {len(c.get('case', []))} caso(s)") for n, c in exs.items()]
        i = self.escolher("Casos de entrada", ops + [("Arquivo TOML de casos…", "blocos [[case]]")])
        if i is None:
            return None
        if i < len(exs):
            nome = list(exs)[i]
            return exs[nome], f"exemplo:{nome}", {"exemplo": nome}
        caminho = Path(self.perguntar("Arquivo de casos (.toml)")).expanduser()
        cfg = tomllib.loads(caminho.read_text(encoding="utf-8"))
        declarado = cfg.get("equipment")
        if declarado not in (None, eq.method_id):
            raise ValueError(f"{caminho.name} declara equipment = {declarado!r}, não {eq.method_id!r}")
        return cfg, str(caminho), {"casos": str(caminho), "equipamento": eq.method_id}

    def _rastro(self, m, r):
        if not r.per_case:
            self.aviso("não há caso dimensionado para mostrar.")
            return
        i = self.escolher("Rastro de qual caso?", [(rel.curto(n), "viável" if pc.feasible else "inviável")
                                                   for n, pc in zip(r.case_names, r.per_case)])
        if i is None:
            return
        self.dizer(*rel.titulo(f"Rastro · {r.case_names[i]}", self.e, self.colunas),
                   *rel.rastro(m, r.per_case[i], self.e, self.colunas))

    def _exportar_equipamento(self, eq, m, casos, r, origem, opcao):
        pasta = Path(self.perguntar("Pasta de saída", f"{PASTA_PADRAO}/{eq.method_id}")).expanduser()
        gravados = dimensionamento.gravar(eq, m, casos, r, pasta, origem)
        metodo = m.method_id if len(registro.methods_for(eq)) > 1 else None
        self.repetir([comando("dimensionar", **opcao, metodo=metodo, saida=str(pasta))], gravados)
