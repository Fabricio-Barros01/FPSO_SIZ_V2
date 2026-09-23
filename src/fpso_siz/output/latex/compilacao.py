"""Compilação opcional do LaTeX com latexmk (quando instalado no sistema)."""
import shutil
import subprocess
from pathlib import Path


class ErroCompilacao(RuntimeError):
    pass


def disponivel():
    return shutil.which("latexmk") is not None


def compilar(tex, tempo_max=900):
    """Compila `tex` (PDF) no próprio diretório; devolve o caminho do PDF."""
    tex = Path(tex)
    if not disponivel():
        raise ErroCompilacao("latexmk não encontrado no PATH")
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                       cwd=tex.parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=tempo_max)
    pdf = tex.with_suffix(".pdf")
    if r.returncode != 0 or not pdf.exists():
        log = tex.with_suffix(".log")
        cauda = log.read_text(encoding="utf-8", errors="replace").splitlines()[-25:] if log.exists() else r.stdout.splitlines()[-25:]
        raise ErroCompilacao("latexmk falhou:\n" + "\n".join(cauda))
    return pdf
