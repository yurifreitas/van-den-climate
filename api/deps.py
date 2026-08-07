"""Camada de acesso a dado — DuckDB sobre Parquet, com fallback sintetico.

Reusa o PADRAO de `app/data_source.py` (real->sintetico automatico, sem flag
manual) mas nao importa aquele modulo: `app/` e territorio de outro agente
(front Streamlit) e a Regra de implementacao §5.1 do contrato pede DuckDB
lendo o parquet direto, nao pandas inteiro na memoria. Reimplementar aqui,
com a mesma filosofia, mantem a fronteira de diretorio limpa (ARCHITECTURE §5:
fronteiras de diretorio == fronteiras reais de acoplamento).

Regra de implementacao §5.3 do contrato: fonte ausente -> 200 com
basis=None/synthetic, NUNCA excecao. Por isso toda funcao publica aqui
devolve um envelope com `is_synthetic` e nunca deixa uma excecao de
I/O escapar para o router.
"""
from __future__ import annotations

import functools
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
RAW = ROOT / "data" / "raw"
FEATURES = ROOT / "data" / "features"
LEDGER_PATH = ROOT / "ledger" / "forecasts.parquet"

CONTRACT_VERSION = "v0"

# signal -> (arquivo parquet em interim, signal_id dentro do arquivo)
# Mapa fechado deliberadamente: o contrato so promete oni|sam|soi|nino34|satl
# em /series/{signal} (§1). Um signal fora daqui e 404, nao 500.
SIGNAL_MAP: dict[str, tuple[str, str]] = {
    "oni": ("cpc_oni.parquet", "oni"),
    "sam": ("cpc_aao.parquet", "sam_cpc_monthly"),
    "soi": ("cpc_soi.parquet", "soi"),
    "nino34": ("psl_nino.parquet", "nino34_raw"),
    "satl": ("cpc_soi.parquet", "satl"),  # ainda nao ingerido -> cai em sintetico
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Cache por (endpoint, as_of): §5.1 do contrato — o dado sazonal muda
# mensalmente, nao a cada request. Chave inclui o dia corrente (nao a hora)
# para que o cache expire sozinho sem precisar de invalidacao manual: uma
# ingestao nova hoje so aparece amanha no pior caso, o que e aceitavel para
# um dado que muda em cadencia sazonal/mensal.
# ---------------------------------------------------------------------------
def _cache_key_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@functools.lru_cache(maxsize=256)
def _cached_series(file_name: str, signal_id: str, day_key: str) -> bytes:
    """Le UMA serie via DuckDB direto do parquet e devolve JSON (bytes) para
    poder viver num lru_cache (DataFrame nao e hasheavel/imutavel o bastante
    para cache seguro entre requests concorrentes).
    """
    path = INTERIM / file_name
    con = duckdb.connect()
    q = """
        SELECT timestamp, value, quality_flag
        FROM read_parquet(?)
        WHERE signal_id = ?
        ORDER BY timestamp
    """
    df = con.execute(q, [str(path), signal_id]).fetch_df()
    con.close()
    df["timestamp"] = df["timestamp"].astype(str)
    # Series como SOI tem lacunas (value NaN com quality_flag proprio) —
    # dropar aqui para blocos de percentil/trilha, que nao sabem lidar com
    # buraco. /series/{signal} le o parquet de novo sem esse corte quando
    # precisar expor a lacuna ao front (nao e o caso hoje).
    df = df.dropna(subset=["value"])
    return df.to_json(orient="records").encode()


@dataclass(frozen=True)
class SeriesResult:
    df: pd.DataFrame
    is_synthetic: bool
    source_ids: list[str] = field(default_factory=list)


def get_series(signal: str) -> SeriesResult | None:
    """Devolve a serie (real via DuckDB, ou sintetica) para um `signal` do
    contrato. None se `signal` nao existe no mapa (-> 404 no router).
    """
    if signal not in SIGNAL_MAP:
        return None
    file_name, signal_id = SIGNAL_MAP[signal]
    path = INTERIM / file_name
    if path.exists():
        try:
            raw = _cached_series(file_name, signal_id, _cache_key_day())
            import io
            df = pd.read_json(io.StringIO(raw.decode()), orient="records")
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                source_id = file_name.replace(".parquet", "")
                return SeriesResult(df, is_synthetic=False, source_ids=[source_id])
        except Exception:
            # parquet corrompido/parcial (escrita concorrente de outro agente
            # de ingestao) nao pode virar 500 — cai no sintetico abaixo.
            pass
    return SeriesResult(_synthetic_series(signal), is_synthetic=True, source_ids=[])


def _synthetic_series(signal: str) -> pd.DataFrame:
    """Serie sintetica deterministica (seed fixa), mesmo espirito de
    app/fixtures.py mas minimalista — a central de risco so precisa de uma
    trilha plausivel para nao quebrar o front quando o dado real falta, nao
    de um gerador completo (esse ja existe em app/fixtures.py).
    """
    seed = {"oni": 1, "sam": 2, "soi": 3, "nino34": 4, "satl": 5}.get(signal, 0)
    rng = np.random.default_rng(20260807 + seed)
    months = pd.date_range("1991-01-01", periods=36 * 12, freq="MS")
    n = len(months)
    t = np.arange(n)
    cycle = 0.9 * np.sin(2 * np.pi * t / 42)
    noise = rng.normal(0, 0.3, n)
    value = cycle + noise
    return pd.DataFrame({
        "timestamp": months,
        "value": value.round(3),
        "quality_flag": 0,
    })


# ---------------------------------------------------------------------------
# Percentil causal, resolucao 1/t (§1 do contrato).
# ---------------------------------------------------------------------------
def causal_percentile(values: np.ndarray) -> np.ndarray:
    """rank(<=) contra tudo ate o instante i, dividido por (i+1). Resolucao
    1/t explicita: com t pequeno o percentil so pode assumir poucos valores
    discretos — dai o resolution_warning quando t<30 (§1).
    """
    out = np.empty(len(values))
    for i in range(len(values)):
        window = values[: i + 1]
        out[i] = float((window <= values[i]).sum()) / len(window)
    return out


def state_headline() -> tuple[dict[str, Any], bool, list[str]]:
    """Headline de /state — DEVE vir de src/state_report.py (ONI real), nunca
    hardcoded (instrucao explicita da tarefa). Reusa a mesma logica de
    classificacao e taxa por temporada, mas le via DuckDB para nao duplicar
    pandas.read_parquet em dois lugares com semanticas diferentes.
    """
    res = get_series("oni")
    if res is None or res.df.empty:
        return {"oni": None, "classification": None, "rate_per_season": None}, True, []

    df = res.df.sort_values("timestamp")
    last_val = float(df["value"].iloc[-1])
    tail = df["value"].tail(4).to_numpy()
    rate = float((tail[-1] - tail[0]) / (len(tail) - 1)) if len(tail) > 1 else 0.0

    a = abs(last_val)
    if a < 0.5:
        classification = "Neutro"
    else:
        tier = "fraco" if a < 1.0 else "moderado" if a < 1.5 else "forte" if a < 2.0 else "muito forte"
        classification = f"El Nino {tier}" if last_val > 0 else f"La Nina {tier}"

    headline = {
        "oni": round(last_val, 2),
        "classification": classification,
        "rate_per_season": round(rate, 2),
    }
    return headline, res.is_synthetic, res.source_ids


# ---------------------------------------------------------------------------
# §4 /health/sources — le provenance.json real em data/raw/<source_id>/<ts>/
# ---------------------------------------------------------------------------
KNOWN_SOURCES = ["cpc_oni", "cpc_aao", "cpc_soi", "psl_nino"]


def sources_health() -> list[dict[str, Any]]:
    out = []
    for source_id in KNOWN_SOURCES:
        src_dir = RAW / source_id
        if not src_dir.exists():
            out.append({
                "source_id": source_id, "last_ingested_at": None, "sha256": None,
                "status": "missing", "rows": None,
                "notes": "diretorio raw/ ausente — nunca ingerido",
            })
            continue
        # timestamps sao nomes de diretorio ISO compacto (20260807T123347) —
        # ordenar por nome == ordenar por tempo, sem parse.
        runs = sorted([p for p in src_dir.iterdir() if p.is_dir()], key=lambda p: p.name)
        if not runs:
            out.append({
                "source_id": source_id, "last_ingested_at": None, "sha256": None,
                "status": "missing", "rows": None, "notes": "sem execucoes registradas",
            })
            continue
        latest = runs[-1]
        prov_path = latest / "provenance.json"
        if not prov_path.exists():
            out.append({
                "source_id": source_id, "last_ingested_at": None, "sha256": None,
                "status": "stale", "rows": None,
                "notes": f"{latest.name} sem provenance.json — ingestao incompleta",
            })
            continue
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:
            out.append({
                "source_id": source_id, "last_ingested_at": None, "sha256": None,
                "status": "stale", "rows": None, "notes": "provenance.json corrompido",
            })
            continue
        out.append({
            "source_id": source_id,
            "last_ingested_at": prov.get("fetched_at"),
            "sha256": prov.get("sha256"),
            "status": "ok",
            "rows": prov.get("rows"),
            "notes": prov.get("notes"),
        })
    return out
