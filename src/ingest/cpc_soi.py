"""SOI (Southern Oscillation Index) mensal — NOAA CPC.

Formato de largura fixa: ano nos primeiros 4 caracteres, seguido de 12
campos de 6 caracteres (JAN..DEZ). Sem separador garantido entre ano e o
primeiro valor quando o valor e negativo (ex.: "2027-999.9-999.9..."), por
isso o parser usa slicing fixo, nao split() por espaco. Valor faltante
-999.9 (usado tanto para lacunas reais quanto para anos futuros no rodape
da tabela — CPC publica a tabela com anos vazios pre-alocados).
"""
from __future__ import annotations

import pandas as pd

from src.contracts import AnchorMode, QualityFlag
from src.ingest.base import FetchResult, Ingestor
from src.ingest.registry import register

URL = "https://www.cpc.ncep.noaa.gov/data/indices/soi"
MISSING = -999.9
FIELD_WIDTH = 6


@register("cpc_soi")
class CpcSoiIngestor(Ingestor):
    source_id = "cpc_soi"
    INGESTOR_VERSION = "1"
    file_ext = "txt"
    product_version = "cpc soi ascii"

    def fetch(self) -> FetchResult:
        content = self._http_get(URL)
        return FetchResult(content=content, url=URL, notes="SOI, largura fixa, cabecalho de 4 linhas")

    def parse(self, raw: bytes) -> pd.DataFrame:
        lines = raw.decode("utf-8", errors="replace").splitlines()

        # O arquivo publica DUAS tabelas identicas em anos (anomalia bruta,
        # depois "STANDARDIZED DATA") separadas por um segundo bloco de
        # cabecalho. Sem cortar aqui, os mesmos (signal_id, timestamp) da
        # tabela de anomalia reaparecem na tabela padronizada -> duplicata
        # rejeitada por contracts.validate_series. So a primeira tabela
        # (anomalia, a documentada em sources.yaml) interessa aqui.
        second_header_idx = next(
            (i for i, l in enumerate(lines) if "STANDARDIZED" in l.upper()), None
        )
        if second_header_idx is not None:
            lines = lines[:second_header_idx]

        rows = []
        for line in lines:
            head = line[:4]
            if not head.isdigit():
                continue  # cabecalho/rotulo — linha de dados sempre comeca com ano de 4 digitos
            year = int(head)
            rest = line[4:]
            for month in range(1, 13):
                start = (month - 1) * FIELD_WIDTH
                field = rest[start:start + FIELD_WIDTH]
                if not field.strip():
                    continue
                try:
                    val = float(field)
                except ValueError:
                    continue
                rows.append((year, month, val))

        if not rows:
            raise ValueError("nenhuma linha de dados reconhecida no formato SOI")

        df = pd.DataFrame(rows, columns=["year", "month", "value"])
        timestamp = pd.to_datetime({"year": df["year"], "month": df["month"], "day": 1})
        is_missing = df["value"] <= (MISSING + 1e-6)
        quality = pd.Series(int(QualityFlag.OK), index=df.index)
        quality[is_missing] = int(QualityFlag.INVALID)
        value = df["value"].where(~is_missing)

        return pd.DataFrame({
            "signal_id": "soi",
            "timestamp": timestamp,
            "value": value,
            "source_version": self.product_version,
            "quality_flag": quality,
            "anchor_mode": AnchorMode.RELATIVE,
        })
