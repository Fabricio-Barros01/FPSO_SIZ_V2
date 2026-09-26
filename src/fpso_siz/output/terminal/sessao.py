"""Modo interativo (`fpso-siz` num terminal, ou `fpso-siz interativo`).

A unidade de trabalho é um equipamento/TAG: preenchimento automático (balanço), manual ou
por arquivo/exemplo; pendências e recomendações por TAG × caso; edição, restauração e
revisão; o resultado recalculado a cada mudança. A Planta/PFD percorre o mesmo serviço
para todos os TAGs. Um único estado de sessão (ajustes_pfd.toml) serve aos dois; ao gravar,
a sessão mostra o comando que reproduz os mesmos arquivos.

Menus, textos e ordem vêm de config/interativo.toml; o código só despacha pelo id da ação.
Entrada e saída são injetáveis: os testes roteirizam sessões inteiras. Invariante 4:
menus e tabelas iteram o registro de métodos, os TAGs declarados e os descritores.
"""
import copy
import math
import os
import platform
import re
import shutil
import sys
import time
import tomllib
from datetime import datetime
from pathlib import Path

import fpso_siz.sizing  # noqa: F401  (registra os métodos de dimensionamento)
from fpso_siz import __version__
from fpso_siz.balanco import indicadores
from fpso_siz.balanco.auditoria import auditar
from fpso_siz.balanco.dados import carregar_casos, descritores_premissas, premissas
from fpso_siz.core import registro
from fpso_siz.core.configuracao import carregar
from fpso_siz.output import ajustes as saida_ajustes
from fpso_siz.output import pfd as saida_pfd
from fpso_siz.output.latex import compilacao
from fpso_siz.output.latex.balanco import memorial
from fpso_siz.output.latex.caso import memorial as memorial_caso
from fpso_siz.output.latex.tag import memorial as memorial_tag
from fpso_siz.output.terminal import pfd as tela
from fpso_siz.output.terminal import relatorio as rel
from fpso_siz.output.terminal.cabecalho import cabecalho
from fpso_siz.output.terminal.comum import alteracoes, comando, gravar_balanco
from fpso_siz.output.terminal.estilo import Estilo, tabela
from fpso_siz.pfd import ajustes as mod_ajustes
from fpso_siz.pfd import equipamento as servico
from fpso_siz.pfd import manual, planta
from fpso_siz.pfd.tags import compativeis, tag, tags

ERROS = (ValueError, KeyError, OSError)
CHAVES_BOT = ("casos_arquivo", "casos_sha256", "casos")
NOME_AVULSO = re.compile(r"[A-Za-z0-9_.-]+")
ORIGENS_DO_BALANCO = ("balanco", "propriedade", "premissa")

# id da ação (config/interativo.toml) → método que a executa; None = o chamador decide.
DESPACHO = {
    "principal": {"equipamento": "_equipamentos", "planta": "_planta", "balanco": "_balanco", "casos": "_casos",
                  "premissas": "_premissas", "ajustes": "_ajustes"},
    "preenchimento": {"automatico": "_preencher_automatico", "manual": "_preencher_manual",
                      "arquivo": "_preencher_arquivo"},
    "tag": {"pendencias": "_tag_pendencias", "revisar": "_tag_revisar", "entradas": "_tag_entradas",
            "editar": "_tag_editar", "restaurar": "_tag_restaurar", "atividade": "_tag_atividade",
            "rastro": "_tag_rastro", "varredura": "_tag_varredura", "exportar": "_tag_exportar",
            "memorial": "_tag_memorial", "modo": "_tag_modo", "associar": "_tag_associar"},
    "planta": {"abrir": "_planta_abrir", "pendencias": "_planta_pendencias", "filtro": "_planta_filtro",
               "exportar": "_planta_exportar", "memoriais": "_planta_memoriais"},
    "revisar": {"confirmar": "_rev_confirmar", "confirmar_todos": "_rev_confirmar_todos", "editar": "_rev_editar"},
    "escopo": {"todos": None, "escolher": None},
    "balanco": {"auditoria": "_bal_auditoria", "correntes": "_bal_correntes", "exportar": "_bal_exportar",
                "memorial_caso": "_bal_memorial_caso"},
    "casos": {"trocar": "_pedir_casos"},
    "ajustes": {"abrir": "_aj_abrir", "salvar": "_aj_salvar", "ver": "_aj_ver", "descartar": "_aj_descartar"},
    "reconciliar": {"adotar_arquivo": None, "adotar_sessao": None},
}


class _Sair(Exception):
    """Fim da entrada (Ctrl+D) ou pedido de saída."""


def _msg(e):
    return e.args[0] if isinstance(e, KeyError) and e.args else e  # KeyError põe aspas no str()


def _numero(texto):
    """Número digitado (aceita vírgula decimal); None se não for finito."""
    t = texto.strip().replace(" ", "")
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def casos_de(texto, validos):
    """'1-3, 5' → [1, 2, 3, 5]; None se inválido ou fora de `validos`."""
    out = []
    for parte in texto.replace(" ", "").split(","):
        if not parte:
            continue
        a, sep, b = parte.replace("–", "-").partition("-")
        if not a.isdigit() or (sep and not b.isdigit()):
            return None
        faixa = range(int(a), int(b) + 1) if sep else [int(a)]
        out += [n for n in faixa if n not in out]
    return sorted(out) if out and set(out) <= set(validos) else None


class Sessao:
    def __init__(self, casos=None, entrada=input, saida=None, estilo=None, colunas=None, agora=datetime.now,
                 ajustes=None, ascii=False):
        self.saida = saida if saida is not None else sys.stdout
        self.entrada = entrada
        self.e = estilo if estilo is not None else Estilo.para(self.saida, ascii=ascii)
        self.colunas = colunas or shutil.get_terminal_size().columns
        self.agora = agora
        self.cfg = carregar("interativo.toml")
        self.tx = self.cfg["textos"]
        self.dados = None
        self.caminho_casos = None
        self.alt = {}
        self._ctx = None
        self.ajustes = mod_ajustes.Ajustes()
        self.caminho_ajustes = None
        self._inicial = casos
        self._ajustes_inicial = ajustes
        self._filtro = None

    # ------------------------------------------------------------------ E/S
    def dizer(self, *linhas):
        for li in linhas:
            print(self.e.t(li), file=self.saida)

    def aviso(self, texto):
        self.dizer(self.e.aviso(f"  ! {texto}"))

    def perguntar(self, texto, padrao=None):
        dica = f" [{padrao}]" if padrao not in (None, "") else ""
        try:
            r = self.entrada(self.e.t(f"{texto}{dica} › "))
        except EOFError:
            raise _Sair from None
        r = r.strip()
        return r if r else ("" if padrao is None else str(padrao))

    def escolher(self, titulo, opcoes, voltar=None, padrao=None):
        """opcoes = [(rótulo, detalhe)] → índice 0-based, ou None (0 = voltar)."""
        self.dizer("", self.e.negrito(titulo))
        w = max((len(r) for r, _ in opcoes), default=0)
        for i, (r, d) in enumerate(opcoes, 1):
            self.dizer(f"  {self.e.destaque(str(i).rjust(2))}  {r.ljust(w)}  {self.e.fraco(d)}".rstrip())
        self.dizer(f"  {self.e.fraco(' 0')}  {self.e.fraco(voltar or self.tx['voltar'])}")
        while True:
            r = self.perguntar(self.tx["opcao"], padrao)
            if r.isdigit() and 0 <= int(r) <= len(opcoes):
                return None if int(r) == 0 else int(r) - 1
            self.aviso(self.tx["opcao_invalida"].format(n=len(opcoes)))

    def menu(self, ident, fmt=None, detalhes=None, indisponivel=None):
        """Menu declarado em interativo.toml → id da ação escolhida, ou None (voltar).
        Ação indisponível aparece esmaecida com o motivo e não é executada."""
        m = self.cfg["menus"][ident]
        detalhes, indisponivel = detalhes or {}, indisponivel or {}
        ops = [(a["rotulo"], self.tx["indisponivel"].format(motivo=indisponivel[a["id"]])
                if a["id"] in indisponivel else detalhes.get(a["id"], "")) for a in m["acoes"]]
        while True:
            i = self.escolher(m["titulo"].format(**(fmt or {})), ops, voltar=m.get("voltar"))
            if i is None:
                return None
            acao = m["acoes"][i]["id"]
            if acao not in indisponivel:
                return acao
            self.aviso(self.tx["indisponivel"].format(motivo=indisponivel[acao]))

    def _rotulo(self, menu, acao):
        return next(a["rotulo"] for a in self.cfg["menus"][menu]["acoes"] if a["id"] == acao)

    def repetir(self, comandos, gravados):
        self.dizer("", self.e.negrito("  " + self.tx["gravado"]), *(f"    {p}" for p in gravados))
        self.dizer("", self.e.negrito("  " + self.tx["repetir"]), *(f"    {self.e.destaque(c)}" for c in comandos))

    # ------------------------------------------------------------------ contexto
    @property
    def ctx(self):
        """Contexto dos TAGs: recriado ao trocar o arquivo de casos ou as premissas (o que
        dependia do anterior — balanço, propriedades, resultados — fica para trás)."""
        if self._ctx is None:
            self._ctx = servico.Contexto(self.dados, alteracoes=self.alt)
        return self._ctx

    def _invalidar(self):
        self._ctx = None

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
                self.aviso(self.tx["ler_casos_falhou"].format(erro=_msg(erro_inicial)))
            self._contexto()
            if self._ajustes_inicial is not None:
                try:
                    self._abrir_ajustes(Path(self._ajustes_inicial))
                except ERROS as e:
                    self.aviso(self.tx["erro"].format(erro=_msg(e)))
            self._menu()
        except _Sair:
            pass
        except KeyboardInterrupt:
            self.dizer("", self.tx["interrompido"])
            return 130
        self.dizer("", self.e.fraco(self.tx["ate_logo"]))
        return 0

    def _carregar_inicial(self):
        if self._inicial is not None:
            self._carregar(self._inicial)
            return
        padrao = Path(self.cfg["arquivo_casos_padrao"])
        if padrao.is_file():
            self._carregar(padrao)

    def _carregar(self, caminho):
        novos = carregar_casos(caminho)
        anterior = self.dados.sha256 if self.dados is not None else self.ajustes.contexto.get("casos_sha256")
        if self.ajustes.tags and anterior not in (None, novos.sha256):
            self.aviso(self.tx["novo_bot"])
            if not self._reconciliar_casos(novos):
                return False
        self.ajustes.contexto = {}
        self.dados = novos
        self.caminho_casos = Path(caminho)
        self._invalidar()
        self._filtro = None
        return True

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
        self.dizer(self.e.negrito(self.tx["contexto_titulo"]))
        if self.dados is None:
            self.dizer(*rel.quebrar(self.tx["sem_casos"], self.colunas))
            return
        self.dizer(*rel.contexto_casos(self.dados, self.e))

    def _menu(self):
        while True:
            n_alt = len(self.alt)
            det = {"balanco": self.tx["casos_n"].format(n=len(self.dados.casos)) if self.dados else self.tx["pede_casos"],
                   "equipamento": self.tx["tags_n"].format(n=len(tags()), avulsos=len(self.ajustes.avulsos)),
                   "planta": self.tx["casos_n"].format(n=len(self.dados.casos)) if self.dados else self.tx["pede_casos"],
                   "premissas": self.tx["premissas_alteradas"].format(n=n_alt) if n_alt else self.tx["premissas_base"],
                   "casos": self.dados.origem if self.dados else self.tx["carregar_casos"],
                   "ajustes": (self.tx["ajustes_n"].format(n=len(self.ajustes.todos())) if self.ajustes.todos()
                               else self.tx["ajustes_vazio"])}
            acao = self.menu("principal", detalhes=det)
            if acao is None:
                return
            try:
                getattr(self, DESPACHO["principal"][acao])()
            except ERROS as e:
                self.aviso(self.tx["erro"].format(erro=_msg(e)))

    # ------------------------------------------------------------------ casos
    def _pedir_casos(self):
        atual = str(self.caminho_casos) if self.caminho_casos else self.cfg["arquivo_casos_padrao"]
        caminho = self.perguntar(self.tx["arquivo_casos"], atual)
        if self._carregar(Path(caminho).expanduser()):
            self.dizer("", *rel.contexto_casos(self.dados, self.e))

    def _exigir_casos(self):
        if self.dados is None:
            self._pedir_casos()
        if self.dados is None:
            raise ValueError(self.tx["casos_necessarios"])

    def _casos(self):
        self._exigir_casos()
        while True:
            self.dizer(*rel.titulo(self.tx["casos_titulo"], self.e, self.colunas), *rel.tabela_casos(self.dados, self.e))
            acao = self.menu("casos", detalhes={"trocar": str(self.caminho_casos)})
            if acao is None:
                return
            getattr(self, DESPACHO["casos"][acao])()

    def _reconciliar_casos(self, novos):
        """Outro arquivo de casos com TAGs já trabalhados: pede decisão explícita."""
        acao = self.menu("reconciliar", indisponivel={"adotar_arquivo": self.tx["sem_divergencia_premissas"]})
        if acao is None:
            return False
        nums = [c["num"] for c in novos.casos]
        for e in self.ajustes.tags.values():
            fora = e.restringir(nums)
            if fora:
                self.aviso(self.tx["casos_descartados"].format(id=e.id, casos=tela.faixa_casos(fora)))
        return True

    # ------------------------------------------------------------------ premissas
    def _premissas(self):
        mostrar = True
        while True:
            if mostrar:
                self._tabela_premissas()
            r = self.perguntar(self.tx["premissas_prompt"])
            if not r:
                return
            mostrar = True
            if r.lower() == "base":
                self.alt = {}
                self._invalidar()
                continue
            try:
                novo = {**self.alt, **alteracoes([r])}
                premissas(self.dados, **novo)
            except ERROS as e:
                self.aviso(str(_msg(e)).replace("--premissa ", ""))
                mostrar = False
                continue
            self.alt = novo
            self._invalidar()

    def _tabela_premissas(self):
        prem = premissas(self.dados, **self.alt)
        linhas = []
        for d in descritores_premissas(self.dados):
            v = prem[d["nome"]]
            marca = self.e.aviso("*") if d["nome"] in self.alt else ""
            linhas.append([d["id"], d["nome"], marca, f"({d['origem']})" if v is None else str(v), d["unidade"],
                           d["descricao"]])
        self.dizer(*rel.titulo(self.tx["premissas_titulo"], self.e, self.colunas),
                   *tabela(self.tx["premissas_colunas"], linhas, self.e))
        if self.alt:
            self.dizer(self.e.fraco("  " + self.tx["premissa_alterada"]))

    def _args_premissa(self):
        return [f"{k}={v}" for k, v in self.alt.items()]

    # ------------------------------------------------------------------ balanço
    def _balanco(self):
        self._exigir_casos()
        ctx = self.ctx
        self.dizer("", "  " + self.tx["resolvendo"].format(n=len(self.dados.casos)))
        t0 = time.perf_counter()
        res = ctx.resultados_balanco
        aud = auditar(res, self.dados, ctx.prem)
        dt = time.perf_counter() - t0
        self.dizer(*rel.resumo_balanco(res, aud, self.dados, ctx.prem, descritores_premissas(self.dados), self.e,
                                       self.colunas, dt))
        det = {"auditoria": self.tx["auditoria_n"].format(n=len(aud)), "correntes": self.tx["correntes"],
               "exportar": self.tx["formatos_balanco"]}
        while True:
            acao = self.menu("balanco", detalhes=det)
            if acao is None:
                return
            try:
                getattr(self, DESPACHO["balanco"][acao])(res, aud)
            except ERROS as e:
                self.aviso(self.tx["erro"].format(erro=_msg(e)))

    def _bal_auditoria(self, res, aud):
        self.dizer(*rel.titulo(self.tx["auditoria_titulo"], self.e, self.colunas), *rel.tabela_auditoria(aud, self.e))

    def _bal_correntes(self, res, aud):
        nums = [r.num for r in res]
        sem_agua = indicadores.verificacao_fisica(res, self.ctx.prem)["sem_fase_aquosa"]
        padrao = next((n for n in nums if n not in sem_agua), nums[0])  # um caso com água, se houver
        r = self.perguntar(self.tx["caso_balanco"].format(min=nums[0], max=nums[-1]), padrao)
        if not r.isdigit() or int(r) not in nums:
            self.aviso(self.tx["caso_invalido"].format(texto=r))
            return
        self.dizer(*rel.titulo(self.tx["correntes_titulo"].format(n=r), self.e, self.colunas),
                   *rel.tabela_correntes_caso(res, int(r), self.e))
        if int(r) in sem_agua:
            self.dizer(self.e.fraco("  " + self.tx["caso_sem_agua"].format(n=r)))

    def _bal_exportar(self, res, aud):
        prem = self.ctx.prem
        r = self.perguntar(self.tx["formatos_prompt"], "1")
        formatos = {x.strip() for x in r.split(",") if x.strip()}
        if not formatos or not formatos <= {"1", "2", "3"}:
            self.aviso(self.tx["formatos_invalidos"].format(texto=r))
            return
        pasta = Path(self.perguntar(self.tx["pasta_prompt"], self.cfg["pasta_padrao"])).expanduser()
        base = dict(casos=str(self.caminho_casos), saida=str(pasta), premissa=self._args_premissa())
        gravados, cmds = [], []
        if "1" in formatos:
            gravados += gravar_balanco(self.dados, prem, res, aud, pasta)
            cmds.append(comando("balanco", **base))
        if formatos & {"2", "3"}:
            layout = self.perguntar(self.tx["layout_prompt"].format(layouts="/".join(sorted(memorial.LAYOUTS))),
                                    self.cfg["layout_padrao"])
            if layout not in memorial.LAYOUTS:
                self.aviso(self.tx["layout_invalido"].format(texto=layout))
                return
            destino = pasta / "memorial"
            tex = memorial.gravar(self.dados, prem, res, destino, layout)
            gravados.append(tex)
            cmds.append(comando("memorial", **{**base, "saida": str(destino)}, layout=layout, pdf="3" in formatos))
            if "3" in formatos:
                self.dizer("  " + self.tx["compilando"])
                try:
                    gravados.append(compilacao.compilar(tex))
                except compilacao.ErroCompilacao as e:
                    self.aviso(self.tx["pdf_falhou"].format(erro=e))
        self.repetir(cmds, gravados)

    def _bal_memorial_caso(self, res, aud):
        """Um MC_CasoNN por caso escolhido (itera o registro de casos do arquivo), pelo mesmo
        gerador de `memorial --caso`."""
        nums = [r.num for r in res]
        texto = self.perguntar(self.tx["casos_memorial_prompt"].format(min=nums[0], max=nums[-1]), memorial_caso.TODOS)
        try:
            escolhidos = memorial_caso.selecionar(texto, nums)
        except ValueError as e:
            self.aviso(self.tx["erro"].format(erro=e))
            return
        opcoes = [*memorial_caso.LAYOUTS, "ambos"]
        layout = self.perguntar(self.tx["layouts_caso_prompt"].format(layouts="/".join(opcoes)), opcoes[-1])
        if layout not in opcoes:
            self.aviso(self.tx["layout_invalido"].format(texto=layout))
            return
        pasta = Path(self.perguntar(self.tx["pasta_prompt"], str(Path(self.cfg["pasta_padrao"]) / "memorial"))).expanduser()
        pdf = self._mc_pdf()
        if pdf:
            self.dizer("  " + self.tx["compilando"])
        layouts = memorial_caso.LAYOUTS if layout == opcoes[-1] else (layout,)
        gravados, erros = memorial_caso.exportar_lote(self.dados, self.ctx.prem, res, escolhidos, pasta, layouts, pdf=pdf)
        for erro in erros:
            self.aviso(self.tx["pdf_falhou"].format(erro=erro))
        cmd = comando("memorial", casos=str(self.caminho_casos), caso=texto, saida=str(pasta), layout=layout,
                      premissa=self._args_premissa(), pdf=pdf)
        self.repetir([cmd], gravados)

    # ------------------------------------------------------------------ equipamentos / TAGs
    def _estado_detalhe(self, ident):
        e = self.ajustes.tags.get(ident)
        t = tag(ident)
        if e is None:
            return self.tx["tag_sem_estado"].format(nome=t.nome)
        guardado = self.ctx.cache.get(ident) if self._ctx is not None else None
        estado = tela.rotulo_estado(guardado[1].status) if guardado else "…"
        modo = self.tx["modo_manual"] if e.modo == mod_ajustes.MANUAL else self.tx["modo_automatico"]
        return self.tx["tag_com_estado"].format(nome=t.nome, modo=modo, estado=estado)

    def _equipamentos(self):
        while True:
            lista = list(tags())
            avulsos = list(self.ajustes.avulsos.values())
            ops = [(t.tag, self._estado_detalhe(t.tag)) for t in lista]
            ops += [(a.id, self.tx["avulso_detalhe"].format(equipamento=registro.equipment(a.equipamento).label,
                                                            casos=len(a.nomes_casos))) for a in avulsos]
            ops.append((self.tx["novo_avulso"], self.tx["novo_avulso_detalhe"]))
            i = self.escolher(self.tx["escolher_equipamento"], ops)
            if i is None:
                return
            if i < len(lista):
                self._tag(lista[i].tag)
            elif i < len(lista) + len(avulsos):
                self._tela(avulsos[i - len(lista)])
            else:
                self._novo_avulso()

    def _tag(self, ident, modo=None):
        estado = self.ajustes.tags.get(ident)
        if estado is None:
            t = tag(ident)
            if modo is not None:
                self._exigir_casos()
                estado = servico.estado_inicial(ident, modo)
            else:
                estado = self._preenchimento(t.tag, t.nome, t.equipamento, t.metodo)
            if estado is None:
                return
            self.ajustes.tags[ident] = estado
        self._tela(estado)

    def _preenchimento(self, ident, nome, equipamento, metodo, atual=None, avulso=False):
        det = {"automatico": self.tx["auto_contexto"].format(
                   arquivo=self.dados.origem if self.dados else self.tx["pede_casos"],
                   casos=tela.faixa_casos([c["num"] for c in self.dados.casos]) if self.dados else "—"),
               "manual": self.tx["manual_detalhe"], "arquivo": self.tx["arquivo_detalhe"]}
        acao = self.menu("preenchimento", fmt={"id": ident, "nome": nome}, detalhes=det)
        if acao is None:
            return None
        return getattr(self, DESPACHO["preenchimento"][acao])(ident, equipamento, metodo, atual, avulso)

    def _preencher_automatico(self, ident, equipamento, metodo, atual, avulso):
        if avulso:
            t = self._escolher_compativel(equipamento, metodo)
            if t is not None:
                self._tag(t.tag, mod_ajustes.AUTOMATICO)
            return None
        self._exigir_casos()
        if atual is None:
            return mod_ajustes.EstadoTAG(ident, equipamento, metodo, mod_ajustes.AUTOMATICO)
        descartadas = atual.para_automatico()
        if descartadas:
            self.aviso(self.tx["faixas_descartadas"].format(id=ident, chaves=", ".join(descartadas)))
        return atual

    def _preencher_manual(self, ident, equipamento, metodo, atual, avulso):
        if avulso:
            n = self.perguntar(self.tx["n_casos_avulso"], 1)
            if not n.isdigit() or int(n) < 1:
                self.aviso(self.tx["valor_invalido"].format(texto=n))
                return None
            nomes = [self.perguntar(self.tx["nome_caso_avulso"].format(i=i), self.tx["caso_padrao"].format(i=i))
                     for i in range(1, int(n) + 1)]
            return manual.avulso(ident, equipamento, metodo, nomes=nomes)
        self._exigir_casos()
        if atual is None:
            return mod_ajustes.EstadoTAG(ident, equipamento, metodo, mod_ajustes.MANUAL)
        atual.modo = mod_ajustes.MANUAL
        return atual

    def _preencher_arquivo(self, ident, equipamento, metodo, atual, avulso):
        nomes = manual.exemplos_de(equipamento)
        exs = {n: carregar(f"exemplos/exemplo_{n}.toml") for n in nomes}
        ops = [(c.get("label", n), self.tx["exemplo_detalhe"].format(n=len(c.get("case", [])))) for n, c in exs.items()]
        ops.append((self.tx["arquivo_toml"], self.tx["arquivo_toml_detalhe"]))
        i = self.escolher(self.tx["escolher_fonte"], ops)
        if i is None:
            return None
        if i < len(nomes):
            cfg_casos, origem = manual.ler_exemplo(nomes[i])
        else:
            cfg_casos, origem = manual.ler_arquivo(Path(self.perguntar(self.tx["caminho_toml"])).expanduser())
        if avulso:
            specs = servico.especificacoes_de(equipamento, metodo, pfd=False)
            imp = manual.importar(cfg_casos, origem, equipamento, metodo, specs)
            estado = manual.avulso(ident, equipamento, metodo, imp=imp)
        else:
            self._exigir_casos()
            specs = servico.especificacoes_de(equipamento, metodo)
            imp = manual.importar(cfg_casos, origem, equipamento, metodo, specs, self.ctx.casos())
            estado = atual if atual is not None else mod_ajustes.EstadoTAG(ident, equipamento, metodo)
            manual.aplicar(estado, imp)
        self.dizer("", "  " + self.tx["importado"].format(origem=origem, n=len(imp.nomes), pendentes=len(imp.nao_finitos)))
        return estado

    def _escolher_compativel(self, equipamento, metodo):
        lista = compativeis(equipamento, metodo)
        if not lista:
            self.aviso(self.tx["sem_tag_compativel"])
            return None
        i = self.escolher(self.tx["tag_compativel"], [(t.tag, t.nome) for t in lista])
        return None if i is None else lista[i]

    def _novo_avulso(self):
        eqs = registro.equipments()
        i = self.escolher(self.tx["escolher_tipo"], [(eq.label, eq.method_id) for eq in eqs])
        if i is None:
            return
        eq = eqs[i]
        metodos = registro.methods_for(eq)
        j = 0 if len(metodos) == 1 else self.escolher(self.tx["escolher_metodo"], [(m.label, m.method_id) for m in metodos])
        if j is None:
            return
        m = metodos[j]
        nome = self.perguntar(self.tx["nome_avulso"], m.method_id)
        if not NOME_AVULSO.fullmatch(nome) or nome in self.ajustes.avulsos or nome in {t.tag for t in tags()}:
            self.aviso(self.tx["valor_invalido"].format(texto=nome))
            return
        estado = self._preenchimento(nome, eq.label, eq.method_id, m.method_id, avulso=True)
        if estado is None:
            return
        self.ajustes.avulsos[nome] = estado
        self._tela(estado)

    # ------------------------------------------------------------------ tela do equipamento
    def _executar(self, estado):
        return servico.executar(self.ctx, estado)

    def _indisponiveis(self, estado, rt):
        tx = self.tx
        ind = {}
        if not rt.entradas.lacunas:
            ind["pendencias"] = tx["indisponivel_lacunas"]
        if not rt.entradas.revisoes():
            ind["revisar"] = tx["indisponivel_revisoes"]
        if not estado.chaves_ajustadas():
            ind["restaurar"] = tx["indisponivel_ajustes"]
        if estado.modo != mod_ajustes.MANUAL:
            ind["atividade"] = tx["indisponivel_manual"]
        if rt.resultado is None or not rt.resultado.rows:
            ind["varredura"] = tx["indisponivel_resultado"]
        if not estado.avulso:
            ind["associar"] = tx["indisponivel_avulso"]
        return ind

    def _tela(self, estado):
        mostrar = True
        while True:
            try:
                rt = self._executar(estado)
            except ERROS as e:
                self.aviso(self.tx["erro"].format(erro=_msg(e)))
                return
            if mostrar:
                self.dizer(*tela.tela_tag(self.ctx, rt, self.e, self.colunas))
            acao = self.menu("tag", fmt={"id": estado.id}, indisponivel=self._indisponiveis(estado, rt))
            if acao is None:
                return
            try:
                mudou = getattr(self, DESPACHO["tag"][acao])(estado, rt)
            except ERROS as e:
                self.aviso(self.tx["erro"].format(erro=_msg(e)))
                mudou = False
            if mudou == "sair":
                return
            mostrar = bool(mudou)

    def _nums(self, rt):
        return [c.num for c in rt.entradas.casos]

    def _escopo(self, afetados, rt):
        """None = geral (todos os casos); lista = só esses casos; False = cancelado."""
        todos = self._nums(rt)
        ativos = [c.num for c in rt.entradas.casos if c.ativo]
        if len(afetados) == 1:
            return None if todos == afetados else list(afetados)
        acao = self.menu("escopo", detalhes={"todos": tela.faixa_casos(afetados)})
        if acao is None:
            return False
        if acao == "todos":
            return None if set(afetados) >= set(ativos) else list(afetados)
        r = self.perguntar(self.tx["casos_prompt"])
        casos = casos_de(r, todos)
        if casos is None:
            self.aviso(self.tx["casos_invalidos"].format(texto=r, min=todos[0], max=todos[-1]))
            return False
        return None if casos == todos else casos

    def _pedir_valor(self, rotulo, unidade, faixa, chave_prompt):
        while True:
            r = self.perguntar(self.tx[chave_prompt].format(rotulo=rotulo, unidade=unidade))
            if not r:
                return None
            v = _numero(r)
            if v is None:
                self.aviso(self.tx["valor_invalido"].format(texto=r))
                continue
            if faixa and not faixa[0] <= v <= faixa[1]:
                self.aviso(self.tx["fora_da_faixa"].format(valor=r, faixa=tela.faixa_descritor(faixa)))
            return v

    def _aplicar(self, estado, rt, chave, valor, casos):
        """Entrada do usuário; registra o que ela substitui e desfaz se o equipamento não
        puder ser preparado com ela (erro de entrada, nunca inviabilidade)."""
        alvo = set(casos) if casos is not None else set(self._nums(rt))
        anteriores = {}
        for c in rt.entradas.casos:
            if c.num in alvo:
                v = c.valores.get(chave) or c.insumos.get(chave)
                anteriores[c.num] = ("lacuna", "", None) if v is None else (
                    v.origem, v.fonte, None if v.lacuna or v.nao_aplicavel else v.numero)
        copia = copy.deepcopy(estado)
        estado.editar(chave, valor, casos, anteriores)
        try:
            self._executar(estado)
        except ERROS as e:
            estado.__dict__.update(copia.__dict__)
            self.aviso(self.tx["edicao_recusada"].format(erro=_msg(e)))
            return False
        return True

    def _formulario_lacunas(self, estado, rt):
        mudou = False
        for chave in [l.chave for l in rt.entradas.lacunas]:
            rt = self._executar(estado)
            lac = next((l for l in rt.entradas.lacunas if l.chave == chave), None)
            if lac is None:
                continue
            self.dizer("", self.e.negrito(f"  {lac.chave} — {lac.rotulo} [{lac.unidade}] · casos "
                                          f"{tela.faixa_casos(lac.casos)}"))
            det = []
            if lac.faixa:
                det.append(self.tx["lacuna_faixa"].format(faixa=tela.faixa_descritor(lac.faixa)))
            if lac.dica:
                det.append(self.tx["lacuna_dica"].format(dica=lac.dica))
            if lac.dependentes:
                det.append(self.tx["lacuna_dependentes"].format(lista=", ".join(lac.dependentes)))
            for d in det:
                self.dizer(*(self.e.fraco(x) for x in rel.quebrar(d, self.colunas, "    ")))
            casos = self._escopo(list(lac.casos), rt)
            if casos is False:
                continue
            valor = self._pedir_valor(lac.rotulo, lac.unidade, lac.faixa, "valor_prompt")
            if valor is None:
                self.dizer(self.e.fraco("  " + self.tx["adiado"].format(chave=lac.chave)))
                continue
            mudou = self._aplicar(estado, rt, lac.chave, valor, casos) or mudou
        return mudou

    def _tag_pendencias(self, estado, rt):
        return self._formulario_lacunas(estado, rt)

    # revisão -----------------------------------------------------------
    def _tag_revisar(self, estado, rt):
        mudou = False
        while True:
            rt = self._executar(estado)
            if not rt.entradas.revisoes():
                return mudou
            self.dizer(*tela.bloco_revisoes(rt, self.e, self.colunas))
            acao = self.menu("revisar")
            if acao is None:
                return mudou
            mudou = getattr(self, DESPACHO["revisar"][acao])(estado, rt) or mudou

    def _item_revisao(self, rt):
        revs = rt.entradas.revisoes()
        r = self.perguntar(self.tx["escolher_item"], 1 if len(revs) == 1 else None)
        if not r.isdigit() or not 1 <= int(r) <= len(revs):
            self.aviso(self.tx["item_invalido"].format(texto=r))
            return None
        return revs[int(r) - 1]

    def _confirmar(self, estado, itens):
        n = 0
        for x in itens:
            estado.confirmar(x.chave, {c: (x.valor, x.fonte) for c in x.casos})
            n += len(x.casos)
        self.dizer("  " + self.tx["confirmados"].format(n=n))
        return True

    def _rev_confirmar(self, estado, rt):
        x = self._item_revisao(rt)
        return x is not None and self._confirmar(estado, [x])

    def _rev_confirmar_todos(self, estado, rt):
        return self._confirmar(estado, rt.entradas.revisoes())

    def _rev_editar(self, estado, rt):
        x = self._item_revisao(rt)
        if x is None:
            return False
        s = rt.entradas.specs[x.chave]
        valor = self._pedir_valor(s.label, s.unit, (s.min, s.max), "valor_edicao")
        if valor is None:
            return False
        ativos = [c.num for c in rt.entradas.casos if c.ativo]
        casos = None if set(x.casos) >= set(ativos) else list(x.casos)
        return self._aplicar(estado, rt, x.chave, valor, casos)

    # entradas, edição, restauração -------------------------------------
    def _pedir_caso(self, rt):
        nums = self._nums(rt)
        padrao = next((c.num for c in rt.entradas.casos if c.ativo), nums[0])
        r = self.perguntar(self.tx["caso_prompt"].format(min=nums[0], max=nums[-1], padrao=padrao), padrao)
        if not r.isdigit() or int(r) not in nums:
            self.aviso(self.tx["caso_invalido"].format(texto=r))
            return None
        return int(r)

    def _tag_entradas(self, estado, rt):
        n = self._pedir_caso(rt)
        if n is not None:
            self.dizer(*tela.tabela_entradas(rt, n, self.e, self.colunas))
        return False

    def _chaves_editaveis(self, estado, rt):
        e = rt.entradas
        chaves = list(e.specs)
        if not estado.avulso and estado.modo == mod_ajustes.AUTOMATICO:
            chaves += list(e.tag.insumos)
        return chaves

    def _rotulo_unidade(self, rt, chave):
        e = rt.entradas
        if chave in e.specs:
            return e.specs[chave].label, e.specs[chave].unit, (e.specs[chave].min, e.specs[chave].max)
        ins = e.tag.insumos[chave]
        return ins["rotulo"], ins["unidade"], ()

    def _tag_editar(self, estado, rt):
        chaves = self._chaves_editaveis(estado, rt)
        ref = next((c for c in rt.entradas.casos if c.ativo), rt.entradas.casos[0])
        ops = []
        for k in chaves:
            rot, und, _ = self._rotulo_unidade(rt, k)
            v = ref.valores.get(k) or ref.insumos.get(k)
            origem = tela.origem_tela(v) if v is not None else self.cfg["origens_tela"]["lacuna"]
            ops.append((f"{k} — {rot}", self.tx["entrada_detalhe"].format(unidade=und, origem=origem)))
        i = self.escolher(self.tx["escolher_entrada"], ops)
        if i is None:
            return False
        chave = chaves[i]
        v = ref.valores.get(chave) or ref.insumos.get(chave)
        if v is not None and v.origem in ORIGENS_DO_BALANCO:
            self.dizer(*(self.e.fraco(x) for x in rel.quebrar(self.tx["edicao_final"], self.colunas)))
        casos = self._escopo(self._nums(rt), rt)
        if casos is False:
            return False
        rot, und, faixa = self._rotulo_unidade(rt, chave)
        valor = self._pedir_valor(rot, und, faixa, "valor_edicao")
        if valor is None:
            return False
        return self._aplicar(estado, rt, chave, valor, casos)

    def _tag_restaurar(self, estado, rt):
        chaves = estado.chaves_ajustadas()
        ops = []
        for k in chaves:
            casos = [n for n in self._nums(rt) if estado.ajustado(k, n)]
            ops.append((k, tela.faixa_casos(casos)))
        i = self.escolher(self.tx["escolher_entrada"], ops)
        if i is None:
            return False
        chave = chaves[i]
        afetados = [n for n in self._nums(rt) if estado.ajustado(chave, n)]
        casos = self._escopo(afetados, rt) if len(afetados) > 1 else afetados
        if casos is False:
            return False
        if casos is not None and set(casos) >= set(afetados):
            casos = None
        estado.restaurar(chave, casos, self._nums(rt))
        self.dizer("  " + self.tx["restaurado"].format(chave=chave))
        return True

    def _tag_atividade(self, estado, rt):
        n = self._pedir_caso(rt)
        if n is None:
            return False
        c = rt.entradas.caso(n)
        if n in estado.inativos:
            estado.definir_atividade(n, None)
        elif c.ativo:
            estado.definir_atividade(n, self.perguntar(self.tx["motivo_prompt"], self.tx["motivo_padrao"]))
        else:
            self.aviso(c.motivo)
            return False
        return True

    # rastro, varredura, exportação ---------------------------------------
    def _tag_rastro(self, estado, rt):
        n = self._pedir_caso(rt)
        if n is None:
            return False
        c = rt.entradas.caso(n)
        self.dizer(*rel.titulo(f"{estado.id} · {c.nome}", self.e, self.colunas),
                   *rel.rastro_blocos(c.rastro, {}, self.e, self.colunas))
        r = rt.resultado
        if r is not None and c.nome in r.case_names:
            m = rt.entradas.metodo
            self.dizer(*rel.rastro(m, r.per_case[r.case_names.index(c.nome)], self.e, self.colunas))
        return False

    def _tag_varredura(self, estado, rt):
        self.dizer(*rel.titulo(self._rotulo("tag", "varredura"), self.e, self.colunas),
                   *rel.tabela_varredura(rt.entradas.metodo, rt.resultado, self.e))
        return False

    def _destino(self, sugestao):
        pasta = Path(self.perguntar(self.tx["pasta_prompt"], sugestao)).expanduser()
        padrao = self.caminho_ajustes if self.caminho_ajustes is not None else pasta / saida_ajustes.NOME
        arq = Path(self.perguntar(self.tx["ajustes_prompt"], str(padrao))).expanduser()
        return pasta, arq

    def _gravar_ajustes(self, arq):
        caminho = saida_ajustes.gravar(self.ajustes, self.ctx, arq)
        self.caminho_ajustes = caminho
        return caminho

    def _tag_exportar(self, estado, rt):
        pasta, arq = self._destino(str(Path(self.cfg["pasta_padrao"]) / estado.id))
        gravados = saida_pfd.gravar_tag(self.ctx, rt, pasta) + [self._gravar_ajustes(arq)]
        if estado.avulso:
            cmd = comando("dimensionar", avulso=estado.id, ajustes=str(arq), saida=str(pasta))
        else:
            cmd = comando("dimensionar", tag=estado.id, casos=str(self.caminho_casos),
                          **{"auto-balanco": estado.modo == mod_ajustes.AUTOMATICO}, ajustes=str(arq),
                          saida=str(pasta), premissa=self._args_premissa())
        self.repetir([cmd], gravados)
        return False

    def _mc_pdf(self):
        return self.perguntar(self.tx["mc_pdf_prompt"], "n").strip().lower() in ("s", "sim", "y")

    def _mc_gravar(self, resultados, pasta, pdf):
        if pdf:
            self.dizer("  " + self.tx["compilando"])
        gravados, erros = memorial_tag.exportar_lote(self.ctx, resultados, pasta, pdf=pdf)
        for erro in erros:
            self.aviso(self.tx["pdf_falhou"].format(erro=erro))
        return gravados

    def _tag_memorial(self, estado, rt):
        """MC do TAG pelo mesmo gerador de `dimensionar --tag … --mc`."""
        pasta, arq = self._destino(str(Path(self.cfg["pasta_padrao"]) / estado.id))
        pdf = self._mc_pdf()
        gravados = saida_pfd.gravar_tag(self.ctx, rt, pasta) + self._mc_gravar([rt], pasta, pdf)
        gravados.append(self._gravar_ajustes(arq))
        if estado.avulso:
            cmd = comando("dimensionar", avulso=estado.id, ajustes=str(arq), saida=str(pasta), mc=True, pdf=pdf)
        else:
            cmd = comando("dimensionar", tag=estado.id, casos=str(self.caminho_casos),
                          **{"auto-balanco": estado.modo == mod_ajustes.AUTOMATICO}, ajustes=str(arq),
                          saida=str(pasta), premissa=self._args_premissa(), mc=True, pdf=pdf)
        self.repetir([cmd], gravados)
        return False

    def _tag_modo(self, estado, rt):
        t = servico.descritor(estado)
        novo = self._preenchimento(estado.id, t.nome, estado.equipamento, estado.metodo, atual=estado,
                                   avulso=estado.avulso)
        if novo is None:
            return False
        if estado.avulso and novo is not estado:
            novo.geral = {**estado.geral, **novo.geral}  # as entradas gerais do usuário continuam
            estado.__dict__.update(novo.__dict__)
        modo = self.tx["modo_manual"] if estado.modo == mod_ajustes.MANUAL else self.tx["modo_automatico"]
        self.dizer("  " + self.tx["modo_trocado"].format(id=estado.id, modo=modo))
        return True

    def _tag_associar(self, estado, rt):
        t = self._escolher_compativel(estado.equipamento, estado.metodo)
        if t is None:
            return False
        self._exigir_casos()
        novo = manual.associar(estado, t, self.ctx.casos())
        self.ajustes.tags[t.tag] = novo
        del self.ajustes.avulsos[estado.id]
        self.dizer("  " + self.tx["avulso_associado"].format(avulso=estado.id, tag=t.tag))
        self._tela(novo)
        return "sair"

    # ------------------------------------------------------------------ planta
    def _executar_planta(self):
        return planta.dimensionar(contexto=self.ctx, ajustes=self.ajustes)

    def _planta(self):
        self._exigir_casos()
        mostrar = True
        while True:
            p = self._executar_planta()
            if mostrar:
                self.dizer(*tela.tela_planta(self.ctx, p.tags, self.e, self.colunas, self._filtro))
            ind = {} if any(t.entradas.lacunas for t in p.tags) else {"pendencias": self.tx["sem_pendencias"]}
            acao = self.menu("planta", indisponivel=ind)
            if acao is None:
                return
            try:
                mostrar = getattr(self, DESPACHO["planta"][acao])(p) is not False
            except ERROS as e:
                self.aviso(self.tx["erro"].format(erro=_msg(e)))
                mostrar = False

    def _planta_abrir(self, p):
        i = self.escolher(self.tx["escolher_equipamento"],
                          [(t.tag.tag, f"{t.tag.nome} · {tela.rotulo_estado(t.status)}") for t in p.tags])
        if i is None:
            return False
        self._tag(p.tags[i].tag.tag, mod_ajustes.AUTOMATICO)
        return True

    def _planta_pendencias(self, p):
        for t in p.tags:
            if not t.entradas.lacunas:
                continue
            ident = t.tag.tag
            estado = self.ajustes.tags.get(ident) or servico.estado_inicial(ident)
            self.dizer(*rel.titulo(self.tx["pendencias_tag"].format(id=ident), self.e, self.colunas))
            if self._formulario_lacunas(estado, self._executar(estado)):
                self.ajustes.tags.setdefault(ident, estado)
        return True

    def _planta_filtro(self, p):
        nums = [c["num"] for c in self.dados.casos]
        r = self.perguntar(self.tx["filtro_prompt"].format(min=nums[0], max=nums[-1]))
        if not r:
            self._filtro = None
        elif r.isdigit() and int(r) in nums:
            self._filtro = int(r)
        else:
            self.aviso(self.tx["caso_invalido"].format(texto=r))
            return False
        return True

    def _planta_exportar(self, p):
        pasta, arq = self._destino(str(Path(self.cfg["pasta_padrao"]) / self.cfg["pasta_planta"]))
        gravados = saida_pfd.gravar(p, pasta) + [self._gravar_ajustes(arq)]
        cmd = comando("pfd", casos=str(self.caminho_casos), ajustes=str(arq), saida=str(pasta),
                      premissa=self._args_premissa())
        self.repetir([cmd], gravados)
        return False

    def _planta_memoriais(self, p):
        pasta, arq = self._destino(str(Path(self.cfg["pasta_padrao"]) / self.cfg["pasta_planta"]))
        pdf = self._mc_pdf()
        gravados = saida_pfd.gravar(p, pasta) + self._mc_gravar(p.tags, pasta, pdf) + [self._gravar_ajustes(arq)]
        cmd = comando("pfd", casos=str(self.caminho_casos), ajustes=str(arq), saida=str(pasta),
                      premissa=self._args_premissa(), mc=True, pdf=pdf)
        self.repetir([cmd], gravados)
        return False

    # ------------------------------------------------------------------ ajustes
    def _ajustes(self):
        while True:
            acao = self.menu("ajustes", detalhes={"abrir": str(self.caminho_ajustes or saida_ajustes.NOME),
                                                   "salvar": str(self.caminho_ajustes or saida_ajustes.NOME)})
            if acao is None:
                return
            try:
                getattr(self, DESPACHO["ajustes"][acao])()
            except ERROS as e:
                self.aviso(self.tx["erro"].format(erro=_msg(e)))

    def _aj_abrir(self):
        padrao = self.caminho_ajustes or saida_ajustes.NOME
        self._abrir_ajustes(Path(self.perguntar(self.tx["arquivo_ajustes"], padrao)).expanduser())

    def _abrir_ajustes(self, caminho):
        aj = mod_ajustes.ler(tomllib.loads(caminho.read_text(encoding="utf-8")))
        if aj.legado:
            self.aviso(self.tx["ajustes_legado"])
        if not self._reconciliar_ajustes(aj):
            return
        self.ajustes = aj
        self.caminho_ajustes = caminho
        self._invalidar()
        self.dizer("  " + self.tx["ajustes_abertos"].format(arquivo=caminho, n=len(aj.todos())))

    def _reconciliar_ajustes(self, aj):
        """Divergências de contexto: avisos passam; bloqueantes pedem decisão explícita."""
        bot = self.dados is not None
        atual = self.ctx.identidade()
        gravado = aj.contexto if bot else {k: v for k, v in aj.contexto.items() if k not in CHAVES_BOT}
        divs = mod_ajustes.comparar_contexto(gravado, atual, aj.todos())
        # sem arquivo de casos, a identidade do BOT fica guardada até ele ser carregado
        pendente = {} if bot else {k: aj.contexto[k] for k in CHAVES_BOT if k in aj.contexto}
        if not divs:
            aj.contexto = pendente
            return True
        self.dizer("", self.e.negrito("  " + self.tx["divergencias_titulo"]))
        for d in divs:
            (self.aviso if d.bloqueante else self.dizer)(self.tx["divergencia"].format(mensagem=d.mensagem))
        bloq = [d for d in divs if d.bloqueante]
        if not bloq:
            aj.contexto = pendente
            return True
        ind = ({} if any(d.campo == "premissas" for d in bloq)
               else {"adotar_arquivo": self.tx["sem_divergencia_premissas"]})
        acao = self.menu("reconciliar", indisponivel=ind)
        if acao is None:
            return False
        if acao == "adotar_arquivo":
            novas = dict(aj.contexto.get("premissas", {}))
            premissas(self.dados, **novas)
            self.alt = novas
            self._invalidar()
        for d in bloq:
            if d.campo == "metodo":
                aj.tags.pop(d.tag, None)
                self.aviso(self.tx["metodo_descartado"].format(tag=d.tag))
        if bot:
            nums = [c["num"] for c in self.dados.casos]
            for e in aj.tags.values():
                fora = e.restringir(nums)
                if fora:
                    self.aviso(self.tx["casos_descartados"].format(id=e.id, casos=tela.faixa_casos(fora)))
        aj.contexto = pendente
        return True

    def _aj_salvar(self):
        padrao = self.caminho_ajustes or saida_ajustes.NOME
        caminho = self._gravar_ajustes(Path(self.perguntar(self.tx["arquivo_ajustes"], padrao)).expanduser())
        self.dizer("  " + self.tx["ajustes_salvos"].format(arquivo=caminho))

    def _aj_ver(self):
        self.dizer("", *tela.tabela_estado(self.ajustes, self.e))

    def _aj_descartar(self):
        if self.perguntar(self.tx["confirmar_descartar"]).lower().startswith("s"):
            self.ajustes = mod_ajustes.Ajustes()
            self._invalidar()
            self.dizer("  " + self.tx["ajustes_descartados"])
