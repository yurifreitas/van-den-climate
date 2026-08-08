"""Mapa geral de recursos de resposta e os vazios de cobertura.

A pergunta
==========

"Onde estao os recursos, e onde falta?" — e, a partir dai, onde realocar antes
da temporada.

O que entra
===========

    fixo_hospitalar   hospital geral e especializado (CNES)
    fixo_urgencia     pronto-socorro e pronto-atendimento (CNES)
    movel             unidade movel terrestre (CNES) — ver ressalva abaixo
    regulacao         central de regulacao de urgencia / SAMU (CNES)
    psicossocial      CAPS e residencial terapeutico (CNES)
    bombeiro          quartel (OpenStreetMap)
    policia           unidade policial (OpenStreetMap)

TRES RESSALVAS QUE MUDAM A LEITURA
==================================

1. **Base, nunca viatura.** Nao ha dado publico de frota — nem de ambulancia,
   nem de viatura policial, nem de caminhao de bombeiro. "Realocar viatura"
   aqui so pode significar *onde o vazio de cobertura e maior diante do
   risco*. Dizer "mova N carros de A para B" exigiria frota, malha viaria e
   modelo de tempo-resposta, e nenhum dos tres existe nesta engine.

2. **O CNES nao registra a frota do SAMU.** As unidades moveis cadastradas no
   RS somam 205, das quais so 31 se identificam por nome como ambulancia,
   resgate ou bombeiro — o resto e unidade odontologica, farmacia movel e
   saude movel. A frota real do SAMU e operada sob o CNES da central de
   regulacao, nao registrada uma a uma. As 7 centrais sao o sinal confiavel
   de cobertura SAMU; a contagem de moveis NAO e.

3. **Bombeiro e policia vem do OpenStreetMap**, que e colaborativo. Quartel
   existente e nao mapeado nao aparece, e ausencia no mapa NAO prova ausencia
   no territorio. Um vazio aqui e hipotese de vazio, e a interface diz isso.

Distancia
=========

Haversine sobre centroide municipal: linha reta, nao rota. Em cheia a
diferenca entre uma e outra e exatamente o problema — a distancia real cresce
e as vezes vira infinita quando a rodovia corta. O numero aqui e um PISO da
dificuldade de acesso, nunca uma estimativa de tempo.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

CNES_PARQUET = INTERIM / "cnes_rs.parquet"
OSM_PARQUET = INTERIM / "osm_emergencia.parquet"
OSM_RECURSOS_PARQUET = INTERIM / "osm_recursos.parquet"
MALHA_GEOJSON = INTERIM / "ibge_malha_rs.geojson"
GRADE_AGUAS_NPZ = INTERIM / "jrc_gsw_rs_grade.npz"

VERSION = "recursos-v1"

# Papeis e como cada um deve ser lido. `completude` distingue cadastro oficial
# de mapeamento colaborativo — sem isso, um vazio do OSM parece um vazio real.
PAPEIS: dict[str, dict[str, Any]] = {
    # --- socorro: quem chega ---------------------------------------------
    "fixo_hospitalar": {"label": "Hospital", "fonte": "cnes_rs", "completude": "cadastro",
                        "familia": "socorro"},
    "fixo_urgencia": {"label": "Pronto-socorro / atendimento", "fonte": "cnes_rs",
                      "completude": "cadastro", "familia": "socorro"},
    "regulacao": {"label": "Central de regulacao (SAMU)", "fonte": "cnes_rs",
                  "completude": "cadastro", "familia": "socorro"},
    "psicossocial": {"label": "CAPS e residencial terapeutico", "fonte": "cnes_rs",
                     "completude": "cadastro", "familia": "socorro"},
    "movel": {"label": "Unidade movel terrestre", "fonte": "cnes_rs",
              "completude": "cadastro_parcial", "familia": "socorro"},
    "bombeiro": {"label": "Quartel de bombeiros", "fonte": "osm_emergencia",
                 "completude": "colaborativa", "familia": "socorro"},
    "policia": {"label": "Unidade policial", "fonte": "osm_emergencia",
                "completude": "colaborativa", "familia": "socorro"},

    # --- abrigo: onde as pessoas ficam -----------------------------------
    # As tres classes abaixo sao POTENCIAL, nunca cadastro de abrigo. Ver a
    # ressalva no topo de src/ingest/osm_recursos.py: predio grande e coberto
    # nao declara capacidade, banheiro, cozinha nem gerador, e a lista real e
    # decisao da Defesa Civil municipal, que nao publica.
    "abrigo_escola": {"label": "Escola (abrigo potencial)", "fonte": "osm_recursos",
                      "completude": "colaborativa", "familia": "abrigo"},
    "abrigo_comunitario": {"label": "Ginasio e centro comunitario", "fonte": "osm_recursos",
                           "completude": "colaborativa", "familia": "abrigo"},
    "abrigo_religioso": {"label": "Templo", "fonte": "osm_recursos",
                         "completude": "colaborativa", "familia": "abrigo"},

    # --- acesso: por onde se entra quando a estrada corta -----------------
    "heliponto": {"label": "Heliponto", "fonte": "osm_recursos",
                  "completude": "colaborativa", "familia": "acesso"},
    "aerodromo": {"label": "Aerodromo", "fonte": "osm_recursos",
                  "completude": "colaborativa", "familia": "acesso"},

    # --- infraestrutura: o que faz o resto funcionar ----------------------
    "energia_subestacao": {"label": "Subestacao de energia", "fonte": "osm_recursos",
                           "completude": "colaborativa", "familia": "infraestrutura"},
    "agua_tratamento": {"label": "Tratamento / captacao de agua", "fonte": "osm_recursos",
                        "completude": "colaborativa", "familia": "infraestrutura"},
    "agua_reservatorio": {"label": "Reservatorio de agua", "fonte": "osm_recursos",
                          "completude": "colaborativa", "familia": "infraestrutura"},

    # --- suprimento: o que sustenta a semana seguinte ---------------------
    "combustivel": {"label": "Posto de combustivel", "fonte": "osm_recursos",
                    "completude": "colaborativa", "familia": "suprimento"},
    "alimento": {"label": "Supermercado", "fonte": "osm_recursos",
                 "completude": "colaborativa", "familia": "suprimento"},
}

# As familias existem porque os papeis respondem a perguntas diferentes e nao
# se somam. Contar hospital junto com supermercado daria um "total de
# recursos" que nao significa nada: um atende ferido, o outro decide se a
# cidade come na quinta-feira. A interface agrupa por familia e nunca soma
# entre elas.
FAMILIAS: dict[str, str] = {
    "socorro": "Quem chega",
    "abrigo": "Onde as pessoas ficam",
    "acesso": "Por onde se entra quando a estrada corta",
    "infraestrutura": "O que faz o resto funcionar",
    "suprimento": "O que sustenta a semana seguinte",
}

# Papeis cuja ausencia vira acao no plano. `movel` fica de fora: a contagem
# nao e confiavel (ver ressalva 2) e um vazio ali nao sustenta recomendacao.
PAPEIS_CRITICOS = ("fixo_urgencia", "bombeiro", "psicossocial")

# Distancia a partir da qual o vazio deixa de ser geografia e vira problema
# operacional. 30 km em linha reta ja significa, em estrada de interior,
# tempo de resposta acima do que qualquer protocolo de urgencia aceita.
LIMIAR_VAZIO_KM = 30.0


def _aneis(geometry: dict) -> list[list[list[float]]]:
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    return [anel for poly in geometry["coordinates"] for anel in poly]


def _centroides() -> dict[int, tuple[float, float]]:
    geo = json.loads(MALHA_GEOJSON.read_text(encoding="utf-8"))
    out: dict[int, tuple[float, float]] = {}
    for f in geo["features"]:
        pts = [p for anel in _aneis(f["geometry"]) for p in anel]
        out[int(f["properties"]["codarea"])] = (
            float(np.mean([p[0] for p in pts])),
            float(np.mean([p[1] for p in pts])),
        )
    return out


def _haversine(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


@dataclass(frozen=True)
class RecursosResult:
    pontos: list[dict[str, Any]]
    por_municipio: dict[int, dict[str, Any]]
    resumo: dict[str, Any]


def _carregar_pontos() -> pd.DataFrame:
    quadros = []
    if CNES_PARQUET.exists():
        c = pd.read_parquet(CNES_PARQUET)
        c = c.dropna(subset=["lat", "lon"])
        quadros.append(pd.DataFrame({
            "id": c["codigo_cnes"].astype(str),
            "papel": c["papel"],
            "nome": c["nome_fantasia"],
            "subtipo": c.get("subtipo"),
            "lat": c["lat"].astype(float),
            "lon": c["lon"].astype(float),
            "fonte": "cnes_rs",
        }))
    if OSM_PARQUET.exists():
        o = pd.read_parquet(OSM_PARQUET)
        quadros.append(pd.DataFrame({
            "id": o["osm_id"],
            "papel": o["papel"],
            "nome": o["nome"],
            "subtipo": None,
            "lat": o["lat"].astype(float),
            "lon": o["lon"].astype(float),
            "fonte": "osm_emergencia",
        }))
    if OSM_RECURSOS_PARQUET.exists():
        r = pd.read_parquet(OSM_RECURSOS_PARQUET)
        quadros.append(pd.DataFrame({
            "id": r["osm_id"],
            "papel": r["papel"],
            "nome": r["nome"],
            "subtipo": r["subtipo"],
            "lat": r["lat"].astype(float),
            "lon": r["lon"].astype(float),
            "fonte": "osm_recursos",
        }))
    if not quadros:
        raise FileNotFoundError(
            "Nenhuma base de recursos ingerida — rode `python -m src.ingest.cnes_rs`, "
            "`python -m src.ingest.osm_emergencia` e `python -m src.ingest.osm_recursos`"
        )
    df = pd.concat(quadros, ignore_index=True)
    # Coordenada fora do RS (erro de cadastro) distorceria toda distancia.
    return df[(df.lat.between(-34, -26.5)) & (df.lon.between(-58, -49))].reset_index(drop=True)


# Fracao da celula de ~500 m que ja foi agua entre 1984 e 2021 a partir da
# qual o recurso e considerado exposto. 5% e piso deliberadamente baixo: a
# celula tem meio quilometro de lado e o predio ocupa uma fracao dela, entao
# exigir metade da celula alagada esconderia justamente o hospital construido
# na borda da varzea — que e o caso que interessa.
LIMIAR_EXPOSICAO_HIDRICA = 0.05


def _exposicao_hidrica(pontos: pd.DataFrame) -> pd.Series:
    """Fracao da celula do JRC, no ponto de cada recurso, que ja foi agua.

    POR QUE ISTO IMPORTA MAIS QUE A CONTAGEM

    Um mapa de recursos responde "onde estao". Nao responde a pergunta que
    2024 fez no RS: quais deles saem de operacao junto com o evento. Hospital
    que alaga nao e capacidade — vira demanda, e no pior momento possivel.

    O cruzamento e com a memoria hidrica do JRC (1984-2021), nao com mancha de
    inundacao modelada: a leitura e "este ponto esta onde ja houve agua",
    apurada por satelite e sem nenhum conhecimento do evento de 2024. Se um
    recurso aparece exposto aqui e alagou de fato, sao duas fontes
    independentes concordando, nao circularidade.

    LIMITES, e sao grandes: a celula tem ~500 m, entao o resultado diz "nesta
    quadra ja houve agua", nunca "este predio alaga". Nao ha cota, nao ha
    profundidade e nao ha defesa — um predio protegido por dique aparece
    exposto do mesmo jeito, porque o satelite viu agua ali antes do dique.
    """
    if not GRADE_AGUAS_NPZ.exists():
        return pd.Series([None] * len(pontos), index=pontos.index, dtype=object)

    z = np.load(GRADE_AGUAS_NPZ, allow_pickle=True)
    meta = json.loads(z["meta"].item()) if isinstance(z["meta"].item(), str) else z["meta"].item()
    b = meta["bbox"]
    res = meta["res_saida"]
    n_px = meta["fator"] ** 2

    # Qualquer classe de agua conta: permanente e o rio de hoje, sazonal e a
    # varzea que enche todo ano, perdida e o leito que foi drenado ou aterrado
    # — e essa ultima e a que a agua reencontra.
    agua = (z["count_permanente"] + z["count_sazonal"]
            + z["count_perdida"] + z["count_efemera"])

    col = ((pontos["lon"].to_numpy() - b["lon_min"]) / res).astype(int)
    lin = ((b["lat_max"] - pontos["lat"].to_numpy()) / res).astype(int)
    dentro = (
        (col >= 0) & (col < meta["n_lon"]) & (lin >= 0) & (lin < meta["n_lat"])
    )
    saida = np.full(len(pontos), np.nan)
    saida[dentro] = agua[lin[dentro], col[dentro]] / n_px
    return pd.Series(
        [None if np.isnan(v) else round(float(min(v, 1.0)), 3) for v in saida],
        index=pontos.index,
        dtype=object,
    )


# Papeis cuja perda tira a cidade de operacao, e nao apenas reduz conforto.
# Supermercado exposto e prejuizo; subestacao exposta e o bairro inteiro sem
# energia — inclusive a casa de bomba que deveria estar tirando a agua.
PAPEIS_CRITICOS_EXPOSICAO = (
    "fixo_hospitalar", "fixo_urgencia", "bombeiro", "regulacao",
    "energia_subestacao", "agua_tratamento",
)


def _taxa_exposicao_por_familia(pontos: pd.DataFrame) -> dict[str, dict[str, Any]]:
    saida: dict[str, dict[str, Any]] = {}
    for familia in FAMILIAS:
        papeis = [p for p, v in PAPEIS.items() if v["familia"] == familia]
        sub = pontos[pontos["papel"].isin(papeis)]
        n = int(len(sub))
        expostos = int(sum(1 for x in sub["exposto_a_agua"] if x))
        saida[familia] = {
            "label": FAMILIAS[familia],
            "n": n,
            "n_expostos": expostos,
            "taxa": round(expostos / n, 4) if n else None,
        }
    return saida


def _criticos_expostos(
    pontos: pd.DataFrame, centroides: dict[int, tuple[float, float]]
) -> list[dict[str, Any]]:
    """Recursos criticos sobre area com memoria hidrica, do mais exposto ao menos.

    Esta lista e o produto mais acionavel do modulo inteiro, e tambem o mais
    facil de ler errado. Ela NAO afirma que o hospital alaga: afirma que o
    satelite viu agua naquela quadra em algum momento entre 1984 e 2021, e que
    portanto vale a pena alguem olhar a cota do terreno e a defesa existente.
    E fila de inspecao, nao laudo.
    """
    sub = pontos[
        pontos["papel"].isin(PAPEIS_CRITICOS_EXPOSICAO)
        & pontos["exposto_a_agua"].astype("object").eq(True)
    ]
    if sub.empty:
        return []
    codigos = list(centroides)
    lons = np.array([centroides[c][0] for c in codigos])
    lats = np.array([centroides[c][1] for c in codigos])

    linhas = []
    for r in sub.itertuples():
        d = _haversine(float(r.lon), float(r.lat), lons, lats)
        cod = codigos[int(np.argmin(d))]
        linhas.append({
            "id": r.id,
            "papel": r.papel,
            "label": PAPEIS[r.papel]["label"],
            "nome": r.nome,
            "cod_mun_proximo": cod,
            "memoria_hidrica_frac": r.memoria_hidrica_frac,
            "fonte": r.fonte,
        })
    linhas.sort(key=lambda x: -(x["memoria_hidrica_frac"] or 0))
    return linhas[:60]


def build() -> RecursosResult:
    pontos = _carregar_pontos()
    pontos["memoria_hidrica_frac"] = _exposicao_hidrica(pontos)
    pontos["exposto_a_agua"] = [
        None if v is None else bool(v >= LIMIAR_EXPOSICAO_HIDRICA)
        for v in pontos["memoria_hidrica_frac"]
    ]
    centroides = _centroides()

    # Distancia ao recurso mais proximo de cada papel, por municipio.
    por_papel: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for papel in PAPEIS:
        sub = pontos[pontos["papel"] == papel]
        por_papel[papel] = (
            sub["lon"].to_numpy(),
            sub["lat"].to_numpy(),
            np.array([bool(x) if x is not None else False for x in sub["exposto_a_agua"]]),
        )

    por_municipio: dict[int, dict[str, Any]] = {}
    for cod, (lon, lat) in centroides.items():
        linha: dict[str, Any] = {}
        for papel, (plons, plats, pexpo) in por_papel.items():
            if plons.size == 0:
                linha[papel] = {"n_no_municipio": 0, "km_mais_proximo": None,
                                "completude": PAPEIS[papel]["completude"],
                                "familia": PAPEIS[papel]["familia"],
                                "n_expostos_a_agua": None}
                continue
            d = _haversine(lon, lat, plons, plats)
            # "no municipio" aproximado por proximidade ao centroide: a
            # alternativa (ponto-em-poligono para 1.700 pontos x 497 areas) nao
            # muda nenhuma decisao e custa muito mais.
            perto = d <= 12.0
            expostos = pexpo[perto]
            linha[papel] = {
                "n_no_municipio": int(perto.sum()),
                "km_mais_proximo": round(float(d.min()), 1),
                "completude": PAPEIS[papel]["completude"],
                "familia": PAPEIS[papel]["familia"],
                # Quantos desses recursos estao onde ja houve agua. `None`
                # quando nao ha nenhum recurso perto — zero ali afirmaria
                # "nenhum exposto", que e leitura oposta a "nenhum existe".
                "n_expostos_a_agua": (
                    int(np.nansum(expostos.astype(float))) if perto.sum() else None
                ),
            }
        por_municipio[cod] = linha

    vazios: dict[str, int] = {}
    for papel in PAPEIS_CRITICOS:
        vazios[papel] = sum(
            1 for v in por_municipio.values()
            if (v[papel]["km_mais_proximo"] or 0) >= LIMIAR_VAZIO_KM
        )

    expostos_por_papel = {
        papel: int(sum(1 for x in pontos[pontos["papel"] == papel]["exposto_a_agua"] if x))
        for papel in PAPEIS
    }
    # Municipios sem NENHUM abrigo potencial mapeado. Nao e "cidade sem
    # abrigo" — e cidade onde o mapa colaborativo nao registrou nem escola nem
    # ginasio nem templo, o que quase sempre significa mapa ralo, e nao
    # ausencia de predio. Vale como fila de verificacao, jamais como achado.
    sem_abrigo = [
        cod for cod, v in por_municipio.items()
        if all(v[p]["n_no_municipio"] == 0 for p in PAPEIS if PAPEIS[p]["familia"] == "abrigo")
    ]

    resumo = {
        "version": VERSION,
        "total_pontos": int(len(pontos)),
        "familias": FAMILIAS,
        "por_papel": {
            papel: {
                **PAPEIS[papel],
                "n": int((pontos["papel"] == papel).sum()),
                "municipios_alem_do_limiar": vazios.get(papel),
                "n_expostos_a_agua": expostos_por_papel[papel],
            }
            for papel in PAPEIS
        },
        "exposicao_hidrica": {
            "limiar_frac_celula": LIMIAR_EXPOSICAO_HIDRICA,
            "n_expostos": int(sum(1 for x in pontos["exposto_a_agua"] if x)),
            "n_avaliados": int(sum(1 for x in pontos["exposto_a_agua"] if x is not None)),
            # A taxa por familia e o achado, nao o total. Infraestrutura de
            # agua e energia aparece exposta numa proporcao varias vezes maior
            # que escola ou mercado — e a explicacao e projeto, nao acaso:
            # captacao PRECISA ficar junto do rio, e subestacao procura
            # terreno plano e barato, que na planicie e a varzea. O que
            # protege a cidade foi construido onde a agua passa.
            "taxa_por_familia": _taxa_exposicao_por_familia(pontos),
            "criticos_expostos": _criticos_expostos(pontos, centroides),
            "nota": (
                "Fracao da celula de ~500 m do JRC (1984-2021) que ja foi agua, no ponto "
                "do recurso. Diz 'nesta quadra ja houve agua', nunca 'este predio alaga': "
                "nao ha cota, profundidade nem defesa — predio atras de dique aparece "
                "exposto do mesmo jeito, porque o satelite viu agua ali antes do dique."
            ),
        },
        "municipios_sem_abrigo_mapeado": len(sem_abrigo),
        "limiar_vazio_km": LIMIAR_VAZIO_KM,
        "subtipos_moveis": (
            pontos[pontos["papel"] == "movel"]["subtipo"].value_counts().to_dict()
            if "subtipo" in pontos else {}
        ),
        "ressalvas": [
            "E BASE, nunca viatura: nao ha dado publico de frota de ambulancia, viatura "
            "policial ou caminhao de bombeiro.",
            "O CNES nao registra a frota do SAMU — as unidades moveis cadastradas incluem "
            "farmacia movel e unidade odontologica. As centrais de regulacao sao o sinal "
            "confiavel de cobertura SAMU; a contagem de moveis nao e.",
            "Bombeiro e policia vem do OpenStreetMap (colaborativo). Ausencia no mapa NAO "
            "prova ausencia no territorio — um vazio ali e hipotese de vazio.",
            "Distancia e linha reta sobre centroide municipal, nunca rota. E um PISO da "
            "dificuldade de acesso: em cheia a distancia real cresce e as vezes nao existe.",
            "ABRIGO E POTENCIAL, nunca cadastro: escola, ginasio e templo sao predio "
            "grande e coberto, sem capacidade, banheiro, cozinha ou gerador declarados. A "
            "lista real e da Defesa Civil municipal e nao existe em base publica aberta — "
            "por isso nenhum campo aqui emite vagas de abrigo.",
            "Os papeis NAO se somam entre familias: hospital e supermercado respondem "
            "perguntas diferentes, e um 'total de recursos' misturando os dois nao "
            "significaria nada.",
            "Exposicao hidrica e da CELULA de ~500 m, nao do predio, e nao considera "
            "dique nem cota: e sinal para inspecionar, nunca laudo de vulnerabilidade.",
        ],
    }
    # O payload de pontos triplicou ao entrar abrigo, suprimento e
    # infraestrutura, e ele viaja inteiro para o navegador na demo estatica.
    # Tres cortes, nenhum deles perdendo informacao usada:
    #
    #   - ponte sai: e da camada geotecnica, nunca foi desenhada aqui, e
    #     ocupava 2,1 mil registros;
    #   - coordenada com 5 casas (~1 m) — o mapa e estadual, e 14 casas de
    #     float sao ruido caro;
    #   - `subtipo` sai do ponto: so era usado para agregar as unidades
    #     moveis, e essa agregacao ja vem pronta em `resumo`.
    saida = pontos[pontos["papel"].isin(PAPEIS)].copy()
    saida["lat"] = saida["lat"].round(5)
    saida["lon"] = saida["lon"].round(5)
    saida = saida.drop(columns=["subtipo"])

    return RecursosResult(
        pontos=saida.to_dict(orient="records"),
        por_municipio=por_municipio,
        resumo=resumo,
    )


def vazios_priorizados(indice: list[dict[str, Any]], limite: int = 40) -> list[dict[str, Any]]:
    """Municipios ordenados por (risco x vazio de cobertura).

    E o mais perto de "onde realocar" que o dado sustenta: cruza o indice de
    prioridade preventiva com a distancia ao recurso critico mais proximo.
    NAO e otimizacao de frota — ver ressalvas.
    """
    rec = build()
    linhas = []
    for m in indice:
        if m["score"] is None:
            continue
        cob = rec.por_municipio.get(m["cod_mun"])
        if not cob:
            continue
        faltas = [
            {
                "papel": p,
                "label": PAPEIS[p]["label"],
                "km": cob[p]["km_mais_proximo"],
                "completude": cob[p]["completude"],
            }
            for p in PAPEIS_CRITICOS
            if (cob[p]["km_mais_proximo"] or 0) >= LIMIAR_VAZIO_KM
        ]
        if not faltas:
            continue
        pior = max(f["km"] for f in faltas)
        linhas.append({
            "cod_mun": m["cod_mun"],
            "municipio": m["municipio"],
            "score": m["score"],
            "level": m["level"],
            "populacao": m["populacao"],
            "faltas": faltas,
            "pior_km": pior,
            # Produto risco x distancia, ambos normalizados de forma grosseira.
            # Serve para ORDENAR, nao para ser lido como grandeza — por isso
            # nao aparece na interface como numero.
            "_ordem": (m["score"] / 100.0) * min(pior / 100.0, 1.0),
        })
    linhas.sort(key=lambda x: -x["_ordem"])
    for x in linhas:
        x.pop("_ordem")
    return linhas[:limite]
