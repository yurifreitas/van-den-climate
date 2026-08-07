"""Testes da Camada 1 (ingestao). Nada aqui bate na rede — CLIMATE_OFFLINE=1
e forcado no topo do modulo, e os parsers sao exercitados com fixtures
inline (amostras curtas dos formatos reais, capturadas em 2026-08-07).
"""
from __future__ import annotations

import json
import os

os.environ["CLIMATE_OFFLINE"] = "1"

import pandas as pd
import pytest

from src.contracts import QualityFlag, validate_series
from src.ingest.base import DATA_INTERIM, DATA_RAW, Ingestor, IngestError, FetchResult
from src.ingest.cpc_aao import CpcAaoIngestor
from src.ingest.cpc_oni import CpcOniIngestor
from src.ingest.cpc_soi import CpcSoiIngestor
from src.ingest.psl_nino import PslNinoIngestor
from src.ingest.registry import RunReport, SourceReport, register, registered_ids, run_all

# ---------------------------------------------------------------------
# Fixtures inline — amostras curtas dos formatos reais
# ---------------------------------------------------------------------

ONI_SAMPLE = """ SEAS  YR   TOTAL   ANOM
  DJF 1950  25.01  -1.32
  JFM 1950  25.36  -1.20
  OND 2025  26.04  -0.61
  NDJ 2025  25.96  -0.60
"""

# formato PSL "correlation .data": 1a linha ano_inicial/ano_final, depois
# ano + 12 valores, faltante -99.99, rodape com linhas de texto livre.
NINA34_SAMPLE = """        1948        1950
 1948 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99
 1949 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99 -99.99
 1950  24.55  25.06  25.87  26.28  26.18  26.46  26.29  25.88  25.74  25.69  25.47  25.29
   -99.99
  Nino 3.4 Mean using NOAA OISST v2 from NCEI
"""

SOI_SAMPLE = """(STAND TAHITI - STAND DARWIN)  SEA LEVEL PRESS
                        ANOMALY

YEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC
1951   2.5   1.5  -0.2  -0.5  -1.1   0.3  -1.7  -0.4  -1.8  -1.6  -1.3  -1.2
2027-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9-999.9
(STAND TAHITI - STAND DARWIN)  SEA LEVEL PRESS
                    STANDARDIZED    DATA

YEAR   JAN   FEB   MAR   APR   MAY   JUN   JUL   AUG   SEP   OCT   NOV   DEC
1951   1.1   0.7  -0.1  -0.2  -0.5   0.1  -0.8  -0.2  -0.9  -0.8  -0.6  -0.5
"""

AAO_SAMPLE = """ 1979    1    0.2088
 1979    2    0.3563
 2026    7    0.3938
"""


# ---------------------------------------------------------------------
# Parsers — cada fonte contra sua fixture
# ---------------------------------------------------------------------

def test_parse_cpc_oni():
    ing = CpcOniIngestor()
    df = ing.parse(ONI_SAMPLE.encode())
    out = validate_series(df, name="cpc_oni")
    assert len(out) == 4
    # DJF 1950 ancora no mes central (janeiro do YR listado)
    row = out[out["timestamp"] == pd.Timestamp("1950-01-01")].iloc[0]
    assert row["value"] == pytest.approx(-1.32)
    assert (out["signal_id"] == "oni").all()


def test_parse_psl_nino_missing_flagged_invalid():
    ing = PslNinoIngestor()
    # payload concatenado: os 4 blocos precisam existir para o parser
    blocks = "\n".join(f"### {fname}\n{NINA34_SAMPLE}" for fname in ["nina1", "nina3", "nina34", "nina4"])
    df = ing.parse(blocks.encode())
    out = validate_series(df, name="psl_nino")
    # 1948 e 1949 sao -99.99 -> INVALID + NaN, nunca 0
    missing = out[out["timestamp"] == pd.Timestamp("1948-01-01")]
    assert missing["quality_flag"].eq(int(QualityFlag.INVALID)).all()
    assert missing["value"].isna().all()
    real = out[out["timestamp"] == pd.Timestamp("1950-01-01")]
    assert real["quality_flag"].eq(int(QualityFlag.OK)).all()
    assert set(out["signal_id"]) == {"nino12_raw", "nino3_raw", "nino34_raw", "nino4_raw"}


def test_parse_cpc_soi_dedupes_standardized_table_and_flags_future_missing():
    ing = CpcSoiIngestor()
    df = ing.parse(SOI_SAMPLE.encode())
    out = validate_series(df, name="cpc_soi")
    # a segunda tabela (STANDARDIZED) nao pode vazar como duplicata
    assert not out.duplicated(["signal_id", "timestamp"]).any()
    jan1951 = out[out["timestamp"] == pd.Timestamp("1951-01-01")].iloc[0]
    assert jan1951["value"] == pytest.approx(2.5)
    jan2027 = out[out["timestamp"] == pd.Timestamp("2027-01-01")].iloc[0]
    assert jan2027["quality_flag"] == int(QualityFlag.INVALID)
    assert pd.isna(jan2027["value"])


def test_parse_cpc_aao():
    ing = CpcAaoIngestor()
    df = ing.parse(AAO_SAMPLE.encode())
    out = validate_series(df, name="cpc_aao")
    assert len(out) == 3
    assert out["anchor_mode"].eq("fixed_1951_1990").all()  # bloco `sam` ancora fixo, nao relativo


# ---------------------------------------------------------------------
# Framework: cache, offline, proveniencia, run()
# ---------------------------------------------------------------------

class _FakeIngestor(Ingestor):
    """Ingestor de teste: fetch() conta chamadas para verificar cache/offline."""

    source_id = "fake_source"
    INGESTOR_VERSION = "test1"
    file_ext = "txt"
    product_version = "fake-v1"
    fetch_count = 0

    def fetch(self) -> FetchResult:
        type(self).fetch_count += 1
        return FetchResult(content=b"2020 1 0.5\n2020 2 0.6\n", url="http://fake.example/data", notes="fixture de teste")

    def parse(self, raw: bytes) -> pd.DataFrame:
        rows = []
        for line in raw.decode().splitlines():
            year, month, val = line.split()
            rows.append((int(year), int(month), float(val)))
        d = pd.DataFrame(rows, columns=["year", "month", "value"])
        timestamp = pd.to_datetime({"year": d["year"], "month": d["month"], "day": 1})
        return pd.DataFrame({
            "signal_id": "fake",
            "timestamp": timestamp,
            "value": d["value"],
            "source_version": self.product_version,
            "quality_flag": int(QualityFlag.OK),
            "anchor_mode": "relative_30y",
        })


@pytest.fixture(autouse=True)
def _isolated_data_dirs(tmp_path, monkeypatch):
    """Redireciona DATA_RAW/DATA_INTERIM para um tmp_path — testes nao devem
    escrever no data/ real do repositorio nem depender do que ja esta la."""
    import src.ingest.base as base_mod

    raw = tmp_path / "raw"
    interim = tmp_path / "interim"
    monkeypatch.setattr(base_mod, "DATA_RAW", raw)
    monkeypatch.setattr(base_mod, "DATA_INTERIM", interim)
    _FakeIngestor.fetch_count = 0
    yield


def test_run_writes_provenance_with_required_fields(monkeypatch):
    monkeypatch.delenv("CLIMATE_OFFLINE", raising=False)
    ing = _FakeIngestor()
    df = ing.run()
    assert len(df) == 2

    import src.ingest.base as base_mod
    raw_dirs = list((base_mod.DATA_RAW / "fake_source").iterdir())
    assert len(raw_dirs) == 1
    prov = json.loads((raw_dirs[0] / "provenance.json").read_text(encoding="utf-8"))
    required = {"url", "fetched_at", "sha256", "product_version", "ingestor_version", "rows", "notes"}
    assert required.issubset(prov)
    assert prov["ingestor_version"] == "test1"
    assert prov["product_version"] == "fake-v1"

    parquet_path = base_mod.DATA_INTERIM / "fake_source.parquet"
    assert parquet_path.exists()


def test_cache_avoids_second_fetch_within_window(monkeypatch):
    monkeypatch.delenv("CLIMATE_OFFLINE", raising=False)
    ing1 = _FakeIngestor(cache_hours=24)
    ing1.run()
    assert _FakeIngestor.fetch_count == 1

    ing2 = _FakeIngestor(cache_hours=24)
    ing2.run()
    assert _FakeIngestor.fetch_count == 1  # reusou o payload em cache, nao chamou fetch() de novo


def test_cache_expired_triggers_new_fetch(monkeypatch):
    monkeypatch.delenv("CLIMATE_OFFLINE", raising=False)
    ing1 = _FakeIngestor(cache_hours=0)  # janela zero -> qualquer download anterior ja esta "velho"
    ing1.run()
    assert _FakeIngestor.fetch_count == 1

    ing2 = _FakeIngestor(cache_hours=0)
    ing2.run()
    assert _FakeIngestor.fetch_count == 2


def test_offline_mode_uses_latest_download_without_network(monkeypatch):
    monkeypatch.delenv("CLIMATE_OFFLINE", raising=False)
    ing1 = _FakeIngestor()
    ing1.run()
    assert _FakeIngestor.fetch_count == 1

    monkeypatch.setenv("CLIMATE_OFFLINE", "1")
    ing2 = _FakeIngestor()
    df = ing2.run()
    assert _FakeIngestor.fetch_count == 1  # offline nunca chama fetch()
    assert len(df) == 2


def test_offline_mode_without_prior_download_fails_clearly(monkeypatch):
    monkeypatch.setenv("CLIMATE_OFFLINE", "1")
    ing = _FakeIngestor()
    with pytest.raises(IngestError, match="fake_source.*offline"):
        ing.run()


def test_parse_error_names_source_and_stage(monkeypatch):
    monkeypatch.delenv("CLIMATE_OFFLINE", raising=False)

    class _BrokenParse(_FakeIngestor):
        source_id = "broken_source"

        def parse(self, raw: bytes) -> pd.DataFrame:
            raise ValueError("boom")

    with pytest.raises(IngestError, match="broken_source.*parse"):
        _BrokenParse().run()


# ---------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------

def test_registered_ids_includes_priority_sources():
    ids = registered_ids()
    for expected in ["cpc_oni", "psl_nino", "cpc_soi", "cpc_aao"]:
        assert expected in ids


def test_run_all_collects_failures_without_aborting(monkeypatch):
    """Uma fonte sem ingestor registrado nao pode impedir o relatorio das demais."""
    report = run_all(ids=["cpc_oni", "nao_existe_xyz"])
    assert isinstance(report, RunReport)
    ok_ids = {r.source_id for r in report.ok}
    fail_ids = {r.source_id for r in report.failed}
    assert "nao_existe_xyz" in fail_ids
    # cpc_oni pode falhar por falta de rede (ambiente sem download previo em
    # CLIMATE_OFFLINE) ou ter sucesso se houver cache — o que importa e que
    # o relatorio cobre as duas fontes sem lancar excecao.
    assert ok_ids | fail_ids == {"cpc_oni", "nao_existe_xyz"}
