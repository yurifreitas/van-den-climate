"""ONI (Oceanic Nino Index) mensal — NOAA CPC.

Formato: colunas fixas "SEAS YR TOTAL ANOM", uma linha por temporada movel de
3 meses sobreposta (DJF, JFM, FMA, ...). Ancoramos no mes central da
temporada: DJF -> Jan do YR listado (convencao CPC: YR acompanha o mes
central, nao o primeiro mes). anchor_mode=relative_30y por ADR-005 —
teleconexao responde a gradiente, nao a valor absoluto fixo.
"""
from __future__ import annotations

import io

import pandas as pd

from src.contracts import AnchorMode, QualityFlag
from src.ingest.base import FetchResult, Ingestor
from src.ingest.registry import register

URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"

# Mes central de cada temporada trimestral sobreposta (convencao CPC: o YR
# da linha acompanha o ano do mes central, nao o do primeiro mes de DJF).
SEASON_CENTER_MONTH = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}


@register("cpc_oni")
class CpcOniIngestor(Ingestor):
    source_id = "cpc_oni"
    INGESTOR_VERSION = "1"
    file_ext = "txt"
    product_version = "oni.ascii.txt"

    def fetch(self) -> FetchResult:
        content = self._http_get(URL)
        return FetchResult(content=content, url=URL, notes="ONI ascii, colunar SEAS YR TOTAL ANOM")

    def parse(self, raw: bytes) -> pd.DataFrame:
        text = raw.decode("utf-8", errors="replace")
        buf = io.StringIO(text)
        df = pd.read_csv(buf, sep=r"\s+")
        df.columns = [c.strip().upper() for c in df.columns]
        expected = {"SEAS", "YR", "TOTAL", "ANOM"}
        if not expected.issubset(df.columns):
            raise ValueError(f"colunas inesperadas no ONI ascii: {list(df.columns)}")

        months = df["SEAS"].map(SEASON_CENTER_MONTH)
        if months.isna().any():
            bad = sorted(set(df.loc[months.isna(), "SEAS"]))
            raise ValueError(f"codigo de temporada nao reconhecido: {bad}")

        timestamp = pd.to_datetime(
            {"year": df["YR"].astype(int), "month": months.astype(int), "day": 1}
        )
        out = pd.DataFrame({
            "signal_id": "oni",
            "timestamp": timestamp,
            "value": df["ANOM"].astype(float),
            "source_version": self.product_version,
            "quality_flag": int(QualityFlag.OK),
            "anchor_mode": AnchorMode.RELATIVE,
        })
        return out
