"""Fixtures imutáveis do PFD F1 Julia: paridade direta e bases de volume documentadas."""
import hashlib
import json
import math
import tomllib
from pathlib import Path

from fpso_siz.balanco.indicadores import q_real_gas

FJ = Path(__file__).resolve().parents[1] / "fixtures" / "julia" / "pfd"
MANIFESTO = json.loads((FJ / "manifesto.json").read_text(encoding="utf-8"))


def test_fixtures_integrais_do_manifesto(planta_referencia):
    assert MANIFESTO["provenance"]["input_json_sha256"] == planta_referencia.dados.sha256
    for e in MANIFESTO["equipment"]:
        caminho = FJ / Path(e["case_file"]).name
        assert hashlib.sha256(caminho.read_bytes()).hexdigest() == e["case_file_sha256"]
        assert len(tomllib.loads(caminho.read_text(encoding="utf-8"))["case"]) == 16


def test_entradas_compartilhadas_bit_a_bit(planta_referencia):
    total = 0
    for e in MANIFESTO["equipment"]:
        fx = tomllib.loads((FJ / Path(e["case_file"]).name).read_text(encoding="utf-8"))
        t = planta_referencia.tag(e["tag"])
        for c, esperado in zip(t.entradas.casos, fx["case"], strict=True):
            assert c.nome == esperado["name"]
            for k, v in c.valores.items():
                if k not in esperado or not isinstance(esperado[k], (int, float)) or not math.isfinite(esperado[k]):
                    continue
                # T, P, massa e cp conservam sua base. Qg no rascunho Julia era REAL;
                # agora é PADRÃO, como exige a equação de capacidade. Densidade/volume
                # aquoso, emulsão, Z e viscosidades foram detalhados na F10a/b.
                direto = v.origem in ("balanco", "premissa") and k != "q_gas"
                oleo = k in ("q_oil", "rho_oil") and e["equipment"] in ("separator", "treater")
                if direto or oleo:
                    assert v.valor == esperado[k], (e["tag"], c.num, k, v.valor, esperado[k])
                    total += 1
    assert total == 528


def test_base_original_dos_volumes_e_gas_ideal_bit_a_bit(planta_referencia):
    for e in MANIFESTO["equipment"]:
        fx = tomllib.loads((FJ / Path(e["case_file"]).name).read_text(encoding="utf-8"))
        for r, contexto, esperado in zip(planta_referencia.balanco, e["case_context"], fx["case"], strict=True):
            s = r.streams[contexto["feed"]]
            # Mesmo agrupamento do gerador congelado: base padrão, antes de Laliberté.
            ql = sum(r.vol(s, k) for k in ("O", "W", "D"))/24
            assert ql == contexto["liquid_flow_m3_h"]
            if "gas_vent" in contexto:
                vent = contexto["gas_vent"]
                real = q_real_gas(r, contexto["gas_source_key"], r.P[vent], r.T[vent], planta_referencia.dados)
                assert real == esperado["q_gas"]
                assert r.streams[vent]["G"]*3600/real == esperado["rho_gas"]
                v = planta_referencia.tag(e["tag"]).entradas.casos[r.num-1].valores["q_gas"]
                assert v.valor == r.vol(r.streams[vent], "G")/24
                assert "padrão" in v.fonte
