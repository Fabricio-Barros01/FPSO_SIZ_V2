"""F5 — as fixtures do Julia são rastreáveis (commit) e reproduzíveis."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
FJ = RAIZ / "tests" / "fixtures" / "julia"
MANIFESTO = json.loads((FJ / "manifesto.json").read_text(encoding="utf-8"))


def test_manifesto_registra_commit_e_arquivos():
    assert MANIFESTO["commit"] == "ab58fc631749aa81fdf7db566aa14a0cecd777c4"
    assert MANIFESTO["julia"] and all((FJ / a).exists() for a in MANIFESTO["arquivos"])
    boxes = {json.loads((FJ / a).read_text(encoding="utf-8"))["box"] for a in MANIFESTO["arquivos"] if a != "formatos_julia.json"}
    assert boxes == {"separador-3f", "knockout-2f", "vaso-eletrostatico", "bomba-centrifuga", "trocador-calor",
                     "analise-pinch", "controle-separador"}


def test_caso_de_referencia_alves_komesu():
    e = json.loads((FJ / "separador-3f.json").read_text(encoding="utf-8"))["envelope"]
    assert e["feasible"] and e["x"] == 6300.0 and round(e["y"], 2) == 18.59 and e["driver_case"] == "Fim de vida"
    assert len(e["case_names"]) == 10


@pytest.mark.julia
@pytest.mark.skipif(not (shutil.which("julia") and (RAIZ.parent / "FPSO_Siz" / ".git").exists()),
                    reason="julia ou repositório FPSO_Siz ausente")
def test_regeneracao_e_identica(tmp_path):
    antes = {p.relative_to(FJ): p.read_bytes() for p in FJ.rglob("*") if p.is_file()}
    subprocess.run([str(RAIZ / "tools" / "exportar_fixtures_julia.sh")], check=True, capture_output=True, timeout=900)
    depois = {p.relative_to(FJ): p.read_bytes() for p in FJ.rglob("*") if p.is_file()}
    assert depois == antes
