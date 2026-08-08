"""BDiA/IBGE — o chao do estado em tres camadas: solo, vegetacao e relevo.

A pergunta que estas fontes respondem
=====================================

Ate aqui a central sabia ONDE chove, ONDE ja foi agua e ONDE ha concreto. Nao
sabia NO QUE a chuva cai. Essa e a diferenca entre uma chuva de 100 mm que
infiltra e a mesma chuva que escoa inteira: nao esta no ceu, esta no chao.

O Banco de Dados de Informacoes Ambientais do IBGE mapeia o territorio
nacional a 1:250.000 em camadas tematicas. Tres importam aqui, e sao servidas
pelo mesmo WFS, no mesmo recorte, com a mesma disciplina:

  pedo_area   PEDOLOGIA — ordem do solo (SiBCS), textura, relevo local,
              pedregosidade, rochosidade. Responde "esse solo absorve?".
  vege_area   VEGETACAO E USO — fitofisionomia original, vegetacao secundaria
              e uso antropico (agropecuaria, silvicultura, influencia urbana).
              Responde "o que cobre esse solo hoje?".
  geom_area   GEOMORFOLOGIA — unidade de relevo, forma de topo, DENSIDADE DE
              DRENAGEM e aprofundamento de incisao. Responde "para onde a agua
              vai, e com que pressa?".

As tres juntas sao o que falta para sair de "choveu muito" e chegar em "quanto
dessa chuva vira enxurrada, quanto leva solo junto, e em quanto tempo chega no
fundo do vale".

O QUE ESTE MODULO GRAVA, E O QUE ELE SE RECUSA A GRAVAR
=======================================================

Grava o que o IBGE afirma: a fracao de cada municipio ocupada por cada
combinacao de atributos, medida sobre a grade. Nada mais.

NAO grava grupo hidrologico de solo, nao grava fator de erodibilidade, nao
grava Curve Number. Essas tres coisas sao TRADUCOES — julgamento nosso sobre o
dado do IBGE, apoiado em literatura, e passivel de estar errado sem que o dado
esteja. Elas vivem em `src/risk/hidrologia.py` e `src/risk/degradacao.py`,
onde carregam selo `modeled`.

A fronteira e a regra 2 do projeto aplicada a uma camada nova: se a traducao
morasse neste parquet, o mapa medido e o julgamento sairiam do mesmo arquivo
com a mesma cara, e ninguem a jusante saberia qual e qual.

A GRADE, E POR QUE 250 m
========================

Rasterizamos em 0,0025 grau (~250 m no RS). Nao e resolucao do dado — a fonte
e vetorial a 1:250.000, cuja menor area mapeavel e da ordem de quilometros
quadrados. E resolucao de AMOSTRAGEM: fina o bastante para que o erro de borda
de poligono se dilua na fracao municipal, grossa o bastante para caber na
memoria (11,3 milhoes de celulas por camada).

Numerador e denominador vivem na mesma grade, como no GHSL: a fracao usa a
soma das areas de celula do municipio, nao a area oficial do IBGE. Assim o
erro de rasterizacao se cancela em vez de somar.

Area de celula e calculada por LINHA, com a formula exata do quadrilatero
esferico. Uma celula perto de Chui cobre ~17% menos area que uma perto de
Barra do Quarai; somar celulas como iguais criaria um gradiente falso
norte-sul, justo a direcao em que o estado mais varia.

O QUE 1:250.000 NAO VE
======================

Toda leitura desta fonte carrega o mesmo limite, e ele e grande: a escala.
Um poligono de pedologia tem quilometros de largura, e dentro dele o solo
varia. Uma varzea estreita de fundo de vale, uma mancha de afloramento, o
corte de estrada que expoe saprolito — nada disso aparece. A fonte descreve o
municipio, nao o lote, e qualquer numero derivado dela vale para decidir ONDE
olhar, nunca O QUE construir.

A segunda limitacao e temporal, e vale sobretudo para a vegetacao: o
levantamento tem decadas de defasagem em varias folhas. A camada de uso
antropico deve ser lida como "vocacao e uso consolidado", nao como cobertura
do ano corrente — para o ano corrente existe sensoriamento, que esta fora
desta ingestao.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_INTERIM = REPO_ROOT / "data" / "interim"

MALHA_GEOJSON = DATA_INTERIM / "ibge_malha_rs.geojson"
MUNIC_PARQUET = DATA_INTERIM / "ibge_munic_rs.parquet"

INGESTOR_VERSION = "1"
WFS = "https://geoservicos.ibge.gov.br/geoserver/wfs"

# Caixa do RS com folga: a rasterizacao precisa da celula de borda inteira.
BBOX = {"lon_min": -58.2, "lon_max": -49.1, "lat_min": -34.3, "lat_max": -26.5}

# ~250 m. Ver o cabecalho: resolucao de amostragem, nao do dado.
RES_GRAUS = 0.0025

R_TERRA_M = 6_371_000.0

# Teto de seguranca no GetFeature. O RS tem ~9,7 mil feicoes por camada; se um
# dia passar disto, e melhor falhar alto do que truncar em silencio e publicar
# um estado com um pedaco faltando.
MAX_FEICOES = 40_000


@dataclass(frozen=True)
class Camada:
    """Uma camada do BDiA e os atributos que sobrevivem a agregacao.

    `campos` e deliberadamente curto. O WFS devolve 20+ colunas por feicao;
    guardar todas produziria um parquet onde cada municipio tem centenas de
    combinacoes unicas e nenhuma delas com area relevante — a agregacao vira
    ruido. Cada campo listado aqui responde uma pergunta hidrologica ou de
    degradacao declarada no cabecalho do modulo.
    """

    id: str
    typename: str
    campos: tuple[str, ...]
    saida: str
    descricao: str


CAMADAS: dict[str, Camada] = {
    "pedologia": Camada(
        id="pedologia",
        typename="BDIA:pedo_area",
        # `ordem` e `textura` decidem infiltracao e erodibilidade; `relevo` e a
        # declividade qualitativa do poligono; pedregosidade e rochosidade
        # separam solo raso de solo profundo com a mesma ordem.
        campos=("legenda_2", "ordem", "subordem", "textura", "relevo",
                "pedregosid", "rochosidad", "erosao"),
        saida="bdia_pedologia_rs.parquet",
        descricao="Pedologia 1:250.000 — ordem SiBCS, textura, relevo local",
    ),
    "vegetacao": Camada(
        id="vegetacao",
        typename="BDIA:vege_area",
        # `nm_uveg` e a vegetacao original mapeada; `nm_uantr` e o uso que a
        # substituiu; `nm_sec1` e a vegetacao secundaria. Guardar os tres
        # separados e o que permite dizer "aqui havia floresta, hoje ha
        # pastagem" — uma frase que a coluna `legenda_2` sozinha nao sustenta.
        campos=("legenda_2", "clas_domi", "nm_uveg", "nm_uantr", "nm_sec1"),
        saida="bdia_vegetacao_rs.parquet",
        descricao="Vegetacao e uso da terra 1:250.000 — fitofisionomia e uso antropico",
    ),
    "geomorfologia": Camada(
        id="geomorfologia",
        typename="BDIA:geom_area",
        # `dens_dren` e `aprof_inci` sao os dois campos que fazem esta camada
        # valer para hidrologia: densidade de drenagem alta concentra rapido,
        # incisao profunda diz que o vale ja foi escavado pela propria agua.
        campos=("nm_dominio", "nm_regiao", "nm_unidade", "forma",
                "dens_dren", "aprof_inci", "niv_alt"),
        saida="bdia_geomorfologia_rs.parquet",
        descricao="Geomorfologia 1:250.000 — unidade de relevo, forma, drenagem",
    ),
}


@dataclass(frozen=True)
class Resultado:
    df: pd.DataFrame
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------
def _url(camada: Camada) -> str:
    """GetFeature em GeoJSON, recortado pela caixa do RS.

    A ordem dos eixos e a armadilha desta API: com o CRS em forma de URN
    (`urn:ogc:def:crs:EPSG::4326`), o WFS 2.0 segue a ordem oficial do EPSG,
    que para 4326 e LATITUDE PRIMEIRO. Passar lon,lat aqui nao da erro —
    devolve zero feicoes, que e o modo de falha pior: parece um estado sem
    solo nenhum. `srsName` separado garante que a GEOMETRIA volte em lon,lat,
    como manda o GeoJSON.
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": camada.typename,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": str(MAX_FEICOES),
        # `geom` PRECISA estar na lista. Com `propertyName` presente o
        # GeoServer devolve exatamente as colunas pedidas — e se a geometria
        # nao for pedida, ele responde 200 com feicoes de `geometry: null`.
        # A rasterizacao entao pula tudo e o estado sai com 0 km2 mapeados,
        # sem um unico erro no caminho.
        "propertyName": ",".join(camada.campos + ("ar_poli_km", "geom")),
        "bbox": (f"{BBOX['lat_min']},{BBOX['lon_min']},"
                 f"{BBOX['lat_max']},{BBOX['lon_max']},"
                 "urn:ogc:def:crs:EPSG::4326"),
    }
    return f"{WFS}?{urllib.parse.urlencode(params)}"


def baixar(camada: Camada, *, timeout_s: float = 900.0) -> tuple[bytes, str]:
    url = _url(camada)
    req = urllib.request.Request(url, headers={"User-Agent": "climate-rs-engine/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return resp.read(), url
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"bdia/{camada.id}: falha no GetFeature do IBGE ({exc}). "
            "O geoservicos.ibge.gov.br cai com alguma frequencia; o bruto ja "
            "baixado em data/raw/ibge_bdia/ continua servindo."
        ) from exc


def _gravar_bruto(camada: Camada, payload: bytes, url: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    destino = DATA_RAW / "ibge_bdia" / camada.id / ts
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "payload.geojson").write_bytes(payload)
    (destino / "provenance.json").write_text(
        json.dumps(
            {
                "url": url,
                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "product_version": "BDiA/IBGE 1:250.000 (WFS geoservicos)",
                "ingestor_version": INGESTOR_VERSION,
                "bytes": len(payload),
                "notes": camada.descricao,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return destino


def _bruto_mais_recente(camada: Camada) -> Path | None:
    base = DATA_RAW / "ibge_bdia" / camada.id
    if not base.exists():
        return None
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True)
    return (dirs[0] / "payload.geojson") if dirs else None


# ---------------------------------------------------------------------------
# Grade
# ---------------------------------------------------------------------------
def _area_celula_m2(lat_centro: np.ndarray, res_graus: float) -> np.ndarray:
    """Area exata do quadrilatero esferico de cada linha da grade."""
    dlat = math.radians(res_graus)
    dlon = math.radians(res_graus)
    lat_r = np.radians(lat_centro)
    return (R_TERRA_M**2) * dlon * (np.sin(lat_r + dlat / 2) - np.sin(lat_r - dlat / 2))


def _transform_e_forma() -> tuple[Any, int, int]:
    from rasterio.transform import from_origin

    n_col = int(round((BBOX["lon_max"] - BBOX["lon_min"]) / RES_GRAUS))
    n_lin = int(round((BBOX["lat_max"] - BBOX["lat_min"]) / RES_GRAUS))
    transform = from_origin(BBOX["lon_min"], BBOX["lat_max"], RES_GRAUS, RES_GRAUS)
    return transform, n_lin, n_col


def _raster_municipios(transform: Any, forma: tuple[int, int]) -> tuple[np.ndarray, list[int], dict[int, str]]:
    """Rotulo de municipio por celula. 0 e fundo; indice i+1 e o i-esimo feature."""
    from rasterio.features import rasterize

    if not MALHA_GEOJSON.exists():
        raise FileNotFoundError(f"{MALHA_GEOJSON} ausente — rode `python -m src.ingest.ibge_rs`")
    malha = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    feats = malha["features"]
    codigos = [int(f["properties"]["codarea"]) for f in feats]
    rot = rasterize(
        ((f["geometry"], i + 1) for i, f in enumerate(feats)),
        out_shape=forma,
        transform=transform,
        fill=0,
        dtype="int32",
    )
    munic = pd.read_parquet(MUNIC_PARQUET)[["cod_mun", "municipio"]]
    nomes = {int(r.cod_mun): r.municipio for r in munic.itertuples()}
    return rot, codigos, nomes


def _chave(props: dict, campos: Iterable[str]) -> tuple:
    """Tupla de atributos, com None normalizado.

    None nao vira string vazia: em pedologia, `ordem` nula significa corpo
    d'agua ou area urbana — informacao, nao lacuna — e `legenda_2` diz qual.
    Achatar os dois casos em "" apagaria essa distincao logo na chave.
    """
    saida = []
    for c in campos:
        v = props.get(c)
        if v in ("", None):
            saida.append(None)
            continue
        # O WFS devolve rotulos quebrados por linha, herdados da diagramacao
        # da carta impressa: "suave \nondulado". Normalizar aqui e obrigatorio
        # — sem isto o mesmo relevo vira duas classes distintas na chave, e
        # qualquer mapeamento a jusante erra a metade que nao previu.
        saida.append(" ".join(str(v).split()))
    return tuple(saida)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build(camada_id: str, *, baixar_se_faltar: bool = True) -> Resultado:
    camada = CAMADAS[camada_id]
    from rasterio.features import rasterize

    bruto = _bruto_mais_recente(camada)
    if bruto is None:
        if not baixar_se_faltar:
            raise FileNotFoundError(
                f"bdia/{camada.id}: sem bruto em data/raw/ e download desabilitado"
            )
        payload, url = baixar(camada)
        _gravar_bruto(camada, payload, url)
    else:
        payload = bruto.read_bytes()

    geo = json.loads(payload.decode("utf-8"))
    feats = geo.get("features") or []
    if not feats:
        raise RuntimeError(
            f"bdia/{camada.id}: zero feicoes. Quase sempre e a ordem dos eixos "
            "do bbox (o WFS 2.0 com CRS em URN espera lat,lon) — e ela falha "
            "devolvendo vazio, nao erro."
        )
    if len(feats) >= MAX_FEICOES:
        raise RuntimeError(
            f"bdia/{camada.id}: {len(feats)} feicoes atingiu o teto {MAX_FEICOES} — "
            "o recorte pode estar truncado. Aumente MAX_FEICOES conscientemente."
        )

    # Guarda contra o modo de falha silencioso descrito em `_url`: geometria
    # nula rasteriza em nada, e o estado sai com 497 municipios e zero km2 —
    # um parquet integro afirmando que o RS nao tem solo.
    sem_geom = sum(1 for f in feats if not f.get("geometry"))
    if sem_geom > len(feats) * 0.02:
        raise RuntimeError(
            f"bdia/{camada.id}: {sem_geom}/{len(feats)} feicoes sem geometria — "
            "quase sempre e `geom` faltando em propertyName no GetFeature."
        )

    transform, n_lin, n_col = _transform_e_forma()
    rot_mun, codigos, nomes = _raster_municipios(transform, (n_lin, n_col))

    # Dimensao: cada combinacao distinta de atributos vira um id inteiro.
    chaves: dict[tuple, int] = {}
    formas = []
    for f in feats:
        k = _chave(f["properties"], camada.campos)
        idx = chaves.setdefault(k, len(chaves) + 1)   # 0 fica para "sem dado"
        formas.append((f["geometry"], idx))

    rot_cls = rasterize(formas, out_shape=(n_lin, n_col), transform=transform,
                        fill=0, dtype="int32")

    lat_centros = BBOX["lat_max"] - (np.arange(n_lin) + 0.5) * RES_GRAUS
    area = np.repeat(_area_celula_m2(lat_centros, RES_GRAUS)[:, None], n_col, axis=1)

    n_cls = len(chaves) + 1
    combinada = rot_mun.ravel().astype(np.int64) * n_cls + rot_cls.ravel().astype(np.int64)
    soma = np.bincount(combinada, weights=area.ravel(), minlength=(len(codigos) + 1) * n_cls)

    inv = {v: k for k, v in chaves.items()}
    linhas = []
    for i, cod in enumerate(codigos, start=1):
        base = i * n_cls
        total = float(soma[base:base + n_cls].sum())
        if total <= 0:
            continue
        for j in range(n_cls):
            m2 = float(soma[base + j])
            if m2 <= 0:
                continue
            atributos = dict(zip(camada.campos, inv[j])) if j else {c: None for c in camada.campos}
            linhas.append({
                "cod_mun": cod,
                "municipio": nomes.get(cod),
                **atributos,
                # `sem_mapeamento` distingue "o IBGE mapeou e nao ha classe"
                # de "o poligono nao cobre esta celula". Sem o campo, um
                # municipio de borda pareceria ter menos solo do que tem.
                "sem_mapeamento": j == 0,
                "km2": round(m2 / 1e6, 4),
                "frac": round(m2 / total, 6),
            })

    df = pd.DataFrame(linhas).sort_values(["cod_mun", "km2"], ascending=[True, False])
    df = df.reset_index(drop=True)

    cobertos = df[~df.sem_mapeamento]
    frac_vazia = df[df.sem_mapeamento].groupby("cod_mun").frac.sum()
    meta = {
        "version": INGESTOR_VERSION,
        "camada": camada.id,
        "typename": camada.typename,
        "fonte": (
            "IBGE, Banco de Dados de Informacoes Ambientais (BDiA), "
            f"{camada.descricao}. Servido por geoservicos.ibge.gov.br (WFS)."
        ),
        "res_graus": RES_GRAUS,
        "n_feicoes": len(feats),
        "n_combinacoes": len(chaves),
        "n_municipios": int(df.cod_mun.nunique()),
        "km2_mapeados": round(float(cobertos.km2.sum()), 1),
        "frac_sem_mapeamento_mediana": round(float(frac_vazia.median()) if len(frac_vazia) else 0.0, 5),
        "campos": list(camada.campos),
        "limites": [
            "Escala 1:250.000: o poligono tem quilometros de largura e o dado "
            "descreve o municipio, nunca o lote. Serve para decidir onde olhar, "
            "nao o que construir.",
            "Varzea estreita, afloramento pontual e corte de estrada nao "
            "aparecem — estao abaixo da menor area mapeavel.",
            "O levantamento tem decadas de defasagem em varias folhas. A camada "
            "de uso antropico e vocacao consolidada, nao cobertura do ano.",
            "Fracao calculada sobre a grade de ~250 m, com area de celula por "
            "latitude; o denominador e a propria grade, nao a area oficial.",
        ],
    }
    return Resultado(df=df, meta=meta)


# ---------------------------------------------------------------------------
# Cruzamento das tres camadas
# ---------------------------------------------------------------------------
# Campos que sobrevivem ao cruzamento. Sao MENOS que os de cada camada: no
# cruzado, cada campo a mais multiplica o numero de combinacoes, e combinacao
# com 0,3 km2 nao sustenta afirmacao nenhuma. Ficam os que entram em conta.
CAMPOS_CRUZADOS: dict[str, tuple[str, ...]] = {
    "pedologia": ("legenda_2", "ordem", "textura", "relevo"),
    "vegetacao": ("legenda_2", "nm_uantr"),
    "geomorfologia": ("nm_unidade", "dens_dren", "forma"),
}
SAIDA_CRUZADO = "bdia_cruzado_rs.parquet"


def build_cruzado() -> Resultado:
    """Solo, cobertura e relevo NA MESMA CELULA — nao tres tabelas ao lado.

    Por que o cruzamento e obrigatorio, e nao um refinamento.

    O metodo do Curve Number nao pergunta "que fracao do municipio e Planossolo"
    nem "que fracao e lavoura". Ele pergunta, para cada pedaco de terreno, o par
    (grupo hidrologico, cobertura) — porque lavoura sobre Latossolo profundo e
    lavoura sobre Planossolo raso escoam de forma completamente diferente, e a
    diferenca e maior que a de trocar a cultura.

    Com tres tabelas separadas so restaria supor independencia entre solo e
    cobertura, e essa suposicao e falsa numa direcao conhecida: a cobertura
    SEGUE o solo. Lavoura procura o solo profundo, pecuaria fica no raso, mata
    sobra na encosta. Supor independencia misturaria a lavoura com a encosta e
    produziria um CN medio que nao descreve pedaco nenhum do municipio.

    Aqui as tres camadas sao rasterizadas na mesma grade e cruzadas celula a
    celula, entao cada linha e uma combinacao que EXISTE no territorio, com a
    area que ela de fato ocupa.
    """
    from rasterio.features import rasterize

    transform, n_lin, n_col = _transform_e_forma()
    rot_mun, codigos, nomes = _raster_municipios(transform, (n_lin, n_col))

    rasters: dict[str, np.ndarray] = {}
    dicionarios: dict[str, dict[int, tuple]] = {}
    for cid, campos in CAMPOS_CRUZADOS.items():
        camada = CAMADAS[cid]
        bruto = _bruto_mais_recente(camada)
        if bruto is None:
            raise FileNotFoundError(
                f"bdia/{cid}: sem bruto — rode `python -m src.ingest.ibge_bdia {cid}` antes"
            )
        feats = json.loads(bruto.read_bytes().decode("utf-8"))["features"]
        chaves: dict[tuple, int] = {}
        formas = []
        for f in feats:
            if not f.get("geometry"):
                continue
            k = _chave(f["properties"], campos)
            formas.append((f["geometry"], chaves.setdefault(k, len(chaves) + 1)))
        rasters[cid] = rasterize(formas, out_shape=(n_lin, n_col), transform=transform,
                                 fill=0, dtype="int32")
        dicionarios[cid] = {v: k for k, v in chaves.items()}

    lat_centros = BBOX["lat_max"] - (np.arange(n_lin) + 0.5) * RES_GRAUS
    area = np.repeat(_area_celula_m2(lat_centros, RES_GRAUS)[:, None], n_col, axis=1).ravel()

    # Chave unica por celula. int64 porque o produto dos quatro cardinais passa
    # de 2^31 com folga; estourar aqui daria colisao silenciosa entre
    # combinacoes diferentes, que e indetectavel a jusante.
    n_p = len(dicionarios["pedologia"]) + 1
    n_v = len(dicionarios["vegetacao"]) + 1
    n_g = len(dicionarios["geomorfologia"]) + 1
    chave = (
        ((rot_mun.ravel().astype(np.int64) * n_p + rasters["pedologia"].ravel()) * n_v
         + rasters["vegetacao"].ravel()) * n_g
        + rasters["geomorfologia"].ravel()
    )

    dentro = rot_mun.ravel() > 0
    chave = chave[dentro]
    peso = area[dentro]
    unicos, inverso = np.unique(chave, return_inverse=True)
    m2 = np.bincount(inverso, weights=peso, minlength=len(unicos))

    linhas = []
    for k, a in zip(unicos.tolist(), m2.tolist()):
        g_i = k % n_g
        k //= n_g
        v_i = k % n_v
        k //= n_v
        p_i = k % n_p
        cod = codigos[k // n_p - 1]
        linha = {"cod_mun": cod, "municipio": nomes.get(cod)}
        for cid, idx in (("pedologia", p_i), ("vegetacao", v_i), ("geomorfologia", g_i)):
            campos = CAMPOS_CRUZADOS[cid]
            valores = dicionarios[cid].get(idx, tuple([None] * len(campos)))
            prefixo = cid[:4]
            linha.update({f"{prefixo}_{c}": v for c, v in zip(campos, valores)})
        linha["km2"] = round(a / 1e6, 4)
        linhas.append(linha)

    df = pd.DataFrame(linhas)
    total = df.groupby("cod_mun").km2.transform("sum")
    df["frac"] = (df.km2 / total).round(6)
    df = df.sort_values(["cod_mun", "km2"], ascending=[True, False]).reset_index(drop=True)
    # Poeira de rasterizacao: combinacao com menos de 5 ha num municipio e
    # borda de poligono, nao unidade de paisagem. Some as linhas, nao a area —
    # o que sai daqui e ruido de recorte, e mante-lo infla a contagem de
    # combinacoes sem mover nenhum numero.
    df = df[df.km2 >= 0.05].reset_index(drop=True)

    meta = {
        "version": INGESTOR_VERSION,
        "camada": "cruzado",
        "fonte": (
            "IBGE/BDiA 1:250.000 — pedologia x vegetacao e uso x geomorfologia, "
            "cruzadas celula a celula em grade de ~250 m."
        ),
        "res_graus": RES_GRAUS,
        "n_linhas": len(df),
        "n_combinacoes": int(df.groupby(
            [c for c in df.columns if c.startswith(("pedo_", "vege_", "geom_"))],
            dropna=False).ngroups),
        "combinacoes_por_municipio_mediana": float(df.groupby("cod_mun").size().median()),
        "km2_total": round(float(df.km2.sum()), 1),
        "campos": {k: list(v) for k, v in CAMPOS_CRUZADOS.items()},
        "limites": [
            "Herda todos os limites das tres camadas de origem, a comecar pela "
            "escala 1:250.000.",
            "O cruzamento e geometrico, nao amostral: duas cartas levantadas em "
            "decadas diferentes podem discordar na borda, e a discordancia vira "
            "combinacao de area pequena em vez de erro visivel.",
            "Combinacao abaixo de 5 ha por municipio e descartada como poeira "
            "de rasterizacao.",
        ],
    }
    return Resultado(df=df, meta=meta)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    alvos = argv or [*CAMADAS, "cruzado"]
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    for cid in alvos:
        if cid == "cruzado":
            r = build_cruzado()
            r.df.to_parquet(DATA_INTERIM / SAIDA_CRUZADO, index=False)
            (DATA_INTERIM / SAIDA_CRUZADO.replace(".parquet", ".meta.json")).write_text(
                json.dumps(r.meta, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            print(f"[OK] cruzado: {len(r.df)} linhas, {r.meta['n_combinacoes']} combinacoes "
                  f"distintas, mediana de {r.meta['combinacoes_por_municipio_mediana']:.0f} "
                  f"por municipio -> {SAIDA_CRUZADO}")
            continue
        if cid not in CAMADAS:
            print(f"[ERRO] camada desconhecida: {cid}. Ha {list(CAMADAS)}")
            return 2
        r = build(cid)
        camada = CAMADAS[cid]
        r.df.to_parquet(DATA_INTERIM / camada.saida, index=False)
        (DATA_INTERIM / camada.saida.replace(".parquet", ".meta.json")).write_text(
            json.dumps(r.meta, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"[OK] {cid}: {len(r.df)} linhas, {r.meta['n_combinacoes']} combinacoes, "
              f"{r.meta['km2_mapeados']} km2 -> {camada.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
