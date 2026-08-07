"""Framework de ingestao (Camada 1, §6/§8.3 do documento mestre).

Toda fonte externa entra pela mesma disciplina: fetch bruto -> grava payload +
proveniencia em data/raw/ (imutavel, auditavel) -> parse para o esquema unico
de contracts.py -> valida -> grava data/interim/<source_id>.parquet.

Por que gravar o bruto separado do parseado: a API do INMET (e varias fontes
CPC/PSL) mudam de formato sem aviso. Se o parser quebrar amanha, o bruto de
hoje ainda esta no disco para reprocessar sem precisar bater na rede de novo.
"""
from __future__ import annotations

import abc
import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.contracts import validate_series

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

DEFAULT_CACHE_HOURS = 24
DEFAULT_TIMEOUT_S = 30
DEFAULT_MAX_RETRIES = 4


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa (fetch/parse/validate)."""


@dataclass
class FetchResult:
    """Payload bruto + metadados minimos, antes de qualquer parse."""

    content: bytes
    url: str
    notes: str = ""


class Ingestor(abc.ABC):
    """Uma fonte = um Ingestor. Subclasses implementam fetch() e parse()."""

    source_id: str = ""          # bate com a chave em manifests/sources.yaml
    INGESTOR_VERSION: str = "1"  # bump ao mudar o parser — proveniencia registra qual versao gerou cada linha
    file_ext: str = "txt"        # extensao do payload bruto gravado em disco

    def __init__(
        self,
        *,
        cache_hours: float = DEFAULT_CACHE_HOURS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        if not self.source_id:
            raise IngestError(f"{type(self).__name__}: source_id nao definido")
        self.cache_hours = cache_hours
        self.timeout_s = timeout_s
        self.max_retries = max_retries

    # ------------------------------------------------------------------
    # Contrato da subclasse
    # ------------------------------------------------------------------
    @abc.abstractmethod
    def fetch(self) -> FetchResult:
        """Baixa o payload bruto. Deve levantar IngestError com contexto claro em falha."""

    @abc.abstractmethod
    def parse(self, raw: bytes) -> pd.DataFrame:
        """Converte payload bruto no esquema de contracts.SERIES_COLUMNS."""

    # ------------------------------------------------------------------
    # Infra comum: HTTP com retry+backoff, cache por sha256, modo offline
    # ------------------------------------------------------------------
    def _http_get(self, url: str) -> bytes:
        """GET com retry exponencial + jitter. stdlib pura — sem dependencia externa obrigatoria."""
        if os.environ.get("CLIMATE_OFFLINE") == "1":
            raise IngestError(
                f"{self.source_id}: fetch bloqueado (CLIMATE_OFFLINE=1) — use run(offline=True)"
            )
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    return resp.read()
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    backoff = (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(backoff)
        raise IngestError(
            f"{self.source_id}: falha na etapa fetch apos {self.max_retries} tentativas, "
            f"url={url}: {last_exc}"
        )

    def _raw_dir_for(self, ts_dir: str) -> Path:
        return DATA_RAW / self.source_id / ts_dir

    def _latest_raw_dir(self) -> Path | None:
        """Diretorio de download mais recente para esta fonte, ou None se nao houver nenhum."""
        base = DATA_RAW / self.source_id
        if not base.exists():
            return None
        candidates = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
        return candidates[0] if candidates else None

    def _recent_cached(self) -> tuple[Path, dict] | None:
        """Retorna (dir, provenance) do download mais recente se estiver dentro da janela de cache."""
        latest = self._latest_raw_dir()
        if latest is None:
            return None
        prov_path = latest / "provenance.json"
        if not prov_path.exists():
            return None
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        fetched_at = pd.Timestamp(prov["fetched_at"])
        age_hours = (pd.Timestamp.now(tz="UTC") - fetched_at).total_seconds() / 3600
        if age_hours <= self.cache_hours:
            return latest, prov
        return None

    def _write_raw(self, content: bytes, *, url: str, notes: str, rows: int) -> Path:
        ts_dir = pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
        out_dir = self._raw_dir_for(ts_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        payload_path = out_dir / f"payload.{self.file_ext}"
        payload_path.write_bytes(content)
        provenance = {
            "url": url,
            "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "sha256": hashlib.sha256(content).hexdigest(),
            "product_version": getattr(self, "product_version", "unknown"),
            "ingestor_version": self.INGESTOR_VERSION,
            "rows": rows,
            "notes": notes,
        }
        (out_dir / "provenance.json").write_text(
            json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return out_dir

    def _get_raw_payload(self) -> tuple[bytes, Path]:
        """Resolve o payload bruto respeitando cache e modo offline. Retorna (bytes, dir_usado)."""
        offline = os.environ.get("CLIMATE_OFFLINE") == "1"

        if offline:
            latest = self._latest_raw_dir()
            if latest is None:
                raise IngestError(
                    f"{self.source_id}: modo offline (CLIMATE_OFFLINE=1) sem download previo "
                    f"em {DATA_RAW / self.source_id} — impossivel prosseguir"
                )
            payload_path = next(latest.glob("payload.*"), None)
            if payload_path is None:
                raise IngestError(f"{self.source_id}: {latest} nao contem payload.* — proveniencia corrompida")
            return payload_path.read_bytes(), latest

        # Cache: evita bater na API instavel do INMET/CPC a cada iteracao de desenvolvimento.
        cached = self._recent_cached()
        if cached is not None:
            cache_dir, _ = cached
            payload_path = next(cache_dir.glob("payload.*"), None)
            if payload_path is not None:
                return payload_path.read_bytes(), cache_dir

        try:
            result = self.fetch()
        except IngestError:
            raise
        except Exception as exc:  # rede/parse inesperado — ainda assim contextualiza a fonte
            raise IngestError(f"{self.source_id}: falha na etapa fetch: {exc}") from exc

        rows_hint = len(result.content.splitlines())
        out_dir = self._write_raw(result.content, url=result.url, notes=result.notes, rows=rows_hint)
        return result.content, out_dir

    # ------------------------------------------------------------------
    # Orquestracao
    # ------------------------------------------------------------------
    def run(self) -> pd.DataFrame:
        """fetch (ou cache/offline) -> grava bruto -> parse -> valida -> grava interim parquet."""
        raw_bytes, raw_dir = self._get_raw_payload()

        try:
            df = self.parse(raw_bytes)
        except Exception as exc:
            raise IngestError(f"{self.source_id}: falha na etapa parse ({raw_dir}): {exc}") from exc

        try:
            df = validate_series(df, name=self.source_id)
        except Exception as exc:
            raise IngestError(f"{self.source_id}: falha na etapa validate: {exc}") from exc

        DATA_INTERIM.mkdir(parents=True, exist_ok=True)
        out_path = DATA_INTERIM / f"{self.source_id}.parquet"
        df.to_parquet(out_path, index=False)
        return df
