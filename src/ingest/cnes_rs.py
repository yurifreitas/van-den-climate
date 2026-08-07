"""CNES — capacidade hospitalar e de urgencia instalada no RS.

O QUE ESTA FONTE E, E O QUE ELA NAO E
=====================================

E o cadastro de ESTABELECIMENTOS: hospitais gerais e especializados, prontos-
socorros e prontos-atendimentos, com municipio e coordenada. Serve para
responder "onde ha porta de entrada de urgencia, e a que distancia" — que e a
pergunta de logistica de acesso numa cheia, quando a rodovia corta.

NAO e contagem de LEITOS. Leito por municipio mora na base CNES-LT do
DATASUS, publicada em arquivo `.dbc` (formato comprimido proprietario do
DATASUS) sem API publica. Chamar "estabelecimento com atendimento hospitalar"
de "leito" seria inflar capacidade por um fator que varia de 10 a 400 entre um
hospital de interior e o Hospital de Clinicas — o tipo de erro que numa
central de risco vira decisao de encaminhamento errada.

O payload declara `unidade: "estabelecimentos"` e a interface repete. Ver
LIMITES no fim do modulo.

Tipos coletados (codigo_tipo_unidade do CNES)
=============================================
     5  Hospital Geral
     7  Hospital Especializado
    20  Pronto Socorro Geral
    21  Pronto Socorro Especializado
    73  Pronto Atendimento

Unidade basica (tipo 2) fica de fora: sao milhares e nao sao porta de urgencia
em evento extremo. O recorte e "para onde vai a ambulancia", nao "onde se faz
consulta de rotina".
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

SOURCE_ID = "cnes_rs"
INGESTOR_VERSION = "1"
BASE = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
UF_RS = 43
PAGINA = 20  # teto da API, ignora `limit` maior
CACHE_HORAS = 24 * 30

TIPOS = {
    5: "hospital_geral",
    7: "hospital_especializado",
    20: "pronto_socorro_geral",
    21: "pronto_socorro_especializado",
    73: "pronto_atendimento",
}

CAMPOS = [
    "codigo_cnes",
    "nome_fantasia",
    "codigo_municipio",
    "codigo_tipo_unidade",
    "latitude_estabelecimento_decimo_grau",
    "longitude_estabelecimento_decimo_grau",
    "estabelecimento_possui_centro_cirurgico",
    "estabelecimento_possui_centro_obstetrico",
    "estabelecimento_possui_centro_neonatal",
    "estabelecimento_possui_atendimento_hospitalar",
]


class IngestError(RuntimeError):
    """Erro de ingestao — a mensagem sempre nomeia fonte + etapa."""


def _get(url: str, tentativas: int = 4) -> dict:
    if os.environ.get("CLIMATE_OFFLINE") == "1":
        raise IngestError(f"{SOURCE_ID}: fetch bloqueado (CLIMATE_OFFLINE=1)")
    ultimo: Exception | None = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            ultimo = exc
            if i < tentativas - 1:
                time.sleep(2**i)
    raise IngestError(f"{SOURCE_ID}: falha na etapa fetch, url={url}: {ultimo}")


def _latest_raw_dir() -> Path | None:
    base = DATA_RAW / SOURCE_ID
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return dirs[0] if dirs else None


def coletar() -> list[dict]:
    """Varre a API por tipo de unidade, paginando ate a pagina vazia.

    Paginacao por tipo, e nao por UF inteira: a API entrega 20 por chamada e o
    RS tem ~30 mil estabelecimentos de todos os tipos. Filtrando por tipo, a
    varredura cai para algumas dezenas de chamadas em vez de 1.500.
    """
    linhas: list[dict] = []
    for tipo, rotulo in TIPOS.items():
        offset = 0
        while True:
            url = f"{BASE}?codigo_uf={UF_RS}&codigo_tipo_unidade={tipo}&limit={PAGINA}&offset={offset}"
            payload = _get(url)
            itens = payload.get("estabelecimentos") or []
            if not itens:
                break
            for e in itens:
                linhas.append({**{c: e.get(c) for c in CAMPOS}, "tipo": rotulo})
            offset += PAGINA
            if offset > 20_000:  # guarda contra paginacao infinita
                raise IngestError(f"{SOURCE_ID}: paginacao nao terminou no tipo {tipo}")
        print(f"  tipo {tipo:>2} ({rotulo}): {sum(1 for x in linhas if x['tipo'] == rotulo)}", flush=True)
    return linhas


def run() -> pd.DataFrame:
    latest = _latest_raw_dir()
    usar_cache = False
    if latest is not None and (latest / "payload.json").exists():
        prov = json.loads((latest / "provenance.json").read_text(encoding="utf-8"))
        idade = (pd.Timestamp.now(tz="UTC") - pd.Timestamp(prov["fetched_at"])).total_seconds() / 3600
        usar_cache = idade <= CACHE_HORAS or os.environ.get("CLIMATE_OFFLINE") == "1"

    if usar_cache and latest is not None:
        linhas = json.loads((latest / "payload.json").read_text(encoding="utf-8"))
        raw_dir = latest
    else:
        linhas = coletar()
        raw_dir = DATA_RAW / SOURCE_ID / pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%S")
        raw_dir.mkdir(parents=True, exist_ok=True)
        bruto = json.dumps(linhas, ensure_ascii=False).encode()
        (raw_dir / "payload.json").write_bytes(bruto)
        (raw_dir / "provenance.json").write_text(
            json.dumps(
                {
                    "url": BASE,
                    "fetched_at": pd.Timestamp.now(tz="UTC").isoformat(),
                    "sha256": hashlib.sha256(bruto).hexdigest(),
                    "product_version": "CNES via apidadosabertos.saude.gov.br",
                    "ingestor_version": INGESTOR_VERSION,
                    "rows": len(linhas),
                    "notes": (
                        "Estabelecimentos hospitalares e de urgencia do RS. "
                        "NAO e contagem de leitos — leito exige CNES-LT (DATASUS, .dbc, sem API)."
                    ),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    df = pd.DataFrame(linhas)
    if df.empty:
        raise IngestError(f"{SOURCE_ID}: nenhum estabelecimento retornado — API mudou ou filtro invalido")

    # codigo_municipio do CNES tem 6 digitos (sem o verificador); a malha do
    # IBGE usa 7. Sem esta reconciliacao o join com o resto do projeto falha em
    # silencio e todo municipio aparece sem hospital.
    df["cod_mun6"] = pd.to_numeric(df["codigo_municipio"], errors="coerce").astype("Int64")
    df = df.rename(
        columns={
            "latitude_estabelecimento_decimo_grau": "lat",
            "longitude_estabelecimento_decimo_grau": "lon",
            "estabelecimento_possui_centro_cirurgico": "centro_cirurgico",
            "estabelecimento_possui_centro_obstetrico": "centro_obstetrico",
            "estabelecimento_possui_centro_neonatal": "centro_neonatal",
            "estabelecimento_possui_atendimento_hospitalar": "atendimento_hospitalar",
        }
    )
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(DATA_INTERIM / f"{SOURCE_ID}.parquet", index=False)

    prov_path = raw_dir / "provenance.json"
    if prov_path.exists():
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        prov["rows"] = len(df)
        prov_path.write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
    return df


if __name__ == "__main__":
    d = run()
    print(f"[OK] {SOURCE_ID}: {len(d)} estabelecimentos em {d['cod_mun6'].nunique()} municipios")
    print(d["tipo"].value_counts().to_string())
    sys.exit(0)
