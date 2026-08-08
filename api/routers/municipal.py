"""§3b do contrato — Risco municipal: prioridade preventiva nos 497 municipios.

Este e o unico endpoint da central com resolucao geografica abaixo do estado,
e por isso o que mais precisa dizer o que NAO e. O modelo por tras
(`src/risk/municipal.py`) e um indice de PRIORIDADE PREVENTIVA, nao uma
previsao de cheia: ordena onde a proxima tempestade encontra a pior
combinacao de impacto ja observado, deficit declarado de prevencao e
exposicao humana. A ADR-013 continua valendo integralmente — nenhuma camada
desta engine antecipa evento individual, e o payload repete isso em
`model_card.limites` para que nenhum consumidor da API precise ler o docstring
para descobrir.

Tres decisoes de contrato que valem registro:

1. `/risk/municipal` devolve os 497, incluindo os que ficaram sem indice
   (`level: null`, `completude: "insuficiente"`). Filtrar o municipio que nao
   respondeu ao IBGE o faria sumir do mapa — a mesma logica que faz
   `flash_flood` aparecer com `level: null` em vez de ser omitido (§3).

2. A malha vem num endpoint separado (`/geo/municipios`), nao embutida na
   lista. Sao ~1 MB de geometria estatica contra ~600 KB de indice que muda
   com o ONI: juntar os dois obrigaria o front a rebaixar a geometria toda vez
   que o indice mudasse.

3. `provenance.basis` do envelope e `modeled` porque o indice composto e
   modelado — mas cada COMPONENTE carrega o proprio basis dentro da linha, e
   os componentes medidos sao a maioria do peso. Achatar tudo em um basis so
   perderia justamente a informacao que o §0 existe para preservar.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api import deps
from api.models import (
    MunicipalDetailResponse,
    MunicipalRiskResponse,
    MunicipalRow,
    Provenance,
)
from src.ingest import cpc_enso_advisory as advisory
from src.risk import aguas
from src.risk import historico
from src.risk import municipal as model
from src.risk import pessoal, plano, recursos, resposta

router = APIRouter(tags=["risco municipal"])

SOURCE_IDS = ["ibge_munic_rs", "ibge_pop_rs", "cpc_oni"]


def _tabela(cenario: str = "atual") -> model.MunicipalRiskTable:
    """Tabela completa, com o ONI corrente injetado pela camada de dados.

    O modelo nao le parquet de serie: quem sabe onde mora o ONI e `deps`.
    Isso mantem `src/risk/` testavel sem DuckDB e sem arquivo em disco.
    """
    headline, is_synth, _ = deps.state_headline()
    oni = None if is_synth else headline.get("oni")
    if cenario not in model.CENARIOS:
        raise HTTPException(
            status_code=422,
            detail=f"cenario invalido: {cenario!r}; disponiveis: {list(model.CENARIOS)}",
        )
    try:
        return model.build_table(oni, cenario)
    except FileNotFoundError as exc:
        # §5.3: fonte ausente vira resposta declarada, nunca 500. Aqui a
        # excecao vira 503 porque a base municipal e um pre-requisito de
        # ingestao, nao um dado que da para sintetizar: inventar impacto de
        # enchente por municipio seria a pior fabricacao possivel nesta central.
        raise HTTPException(
            status_code=503,
            detail=(
                "Base municipal do IBGE ausente. Rode `python -m src.ingest.ibge_rs`. "
                f"({exc})"
            ),
        ) from exc


@router.get("/risk/municipal", response_model=MunicipalRiskResponse)
def get_municipal_risk(
    level: str | None = Query(None, description="Filtra por nivel: low|moderate|elevated|high"),
    limit: int | None = Query(None, ge=1, le=497, description="Corta o ranking nos N primeiros"),
    cenario: str = Query(
        "atual",
        description="Horizonte: atual (ONI medido) | ond2026 (outlook CPC) | estrutural (2027+, sem ENSO)",
    ),
) -> MunicipalRiskResponse:
    tabela = _tabela(cenario)
    rows = tabela.rows
    if level is not None:
        rows = [r for r in rows if r["level"] == level]
    if limit is not None:
        rows = rows[:limit]

    headline, is_synth, _ = deps.state_headline()
    return MunicipalRiskResponse(
        as_of=deps.now_iso()[:10],
        provenance=Provenance(
            basis="synthetic" if is_synth else "modeled",
            horizon="seasonal",
            source_ids=SOURCE_IDS,
            as_of=deps.now_iso()[:10],
            n_effective=tabela.n_completo,
        ),
        model_card=model.model_card(),
        as_of_source=tabela.as_of_source,
        n_total=len(tabela.rows),
        n_completo=tabela.n_completo,
        n_parcial=tabela.n_parcial,
        n_insuficiente=tabela.n_insuficiente,
        oni=headline.get("oni"),
        cenario=tabela.cenario,
        cenario_spec=tabela.cenario_spec,
        municipios=[MunicipalRow(**r) for r in rows],
    )


@router.get("/outlook/enso")
def get_enso_outlook() -> dict:
    """Boletim ENSO do CPC/NOAA — a unica camada prospectiva da central.

    CONTEXTO, nunca feature (ADR-012): a previsao e do CPC, e a resposta diz
    isso em `autoria` para que nenhum consumidor confunda "o CPC preve" com
    "esta engine preve". A engine local continua sem previsao aceita —
    nenhum modelo passou a ADR-007.

    Ausente -> 200 com `disponivel: false` e instrucao de ingestao, nao 503:
    ao contrario da base municipal, aqui a lacuna nao quebra nada a jusante,
    e o front sabe desenhar "outlook indisponivel" (regra §5.3).
    """
    adv = advisory.load()
    if adv is None:
        return {
            "disponivel": False,
            "motivo": "boletim nao ingerido — rode `python -m src.ingest.cpc_enso_advisory`",
        }
    horizonte = model.model_card()["horizonte_previsao"]
    return {
        "disponivel": True,
        "autoria": "CPC/NCEP/NWS — NOAA. Previsao EXTERNA, consumida como contexto (ADR-012).",
        "basis": "modeled",
        "issued": adv.issued,
        "alert_status": adv.alert_status,
        "synopsis": adv.synopsis,
        "probabilities": adv.probabilities,
        "next_update": adv.next_update,
        "source_url": adv.source_url,
        "horizonte": horizonte,
        # O que a engine LOCAL diz — deliberadamente ao lado do outlook
        # externo, para que a diferenca entre os dois seja visivel de imediato.
        "engine_local": {
            "tem_previsao_aceita": False,
            "motivo": "nenhum modelo passou o criterio da ADR-007 (limite inferior do IC90 de RPSS > 0)",
        },
    }


@router.get("/risk/municipal/{cod_mun}", response_model=MunicipalDetailResponse)
def get_municipal_detail(cod_mun: int) -> MunicipalDetailResponse:
    tabela = _tabela()
    match = next((r for r in tabela.rows if r["cod_mun"] == cod_mun), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"municipio {cod_mun} nao esta no RS")
    posicao = next(
        (i + 1 for i, r in enumerate(tabela.rows) if r["cod_mun"] == cod_mun and r["score"] is not None),
        None,
    )
    return MunicipalDetailResponse(
        as_of=deps.now_iso()[:10],
        provenance=Provenance(
            basis=match["basis"],
            horizon="seasonal",
            source_ids=SOURCE_IDS,
            as_of=deps.now_iso()[:10],
        ),
        posicao=posicao,
        n_ranqueados=sum(1 for r in tabela.rows if r["score"] is not None),
        municipio=MunicipalRow(**match),
        model_card=model.model_card(),
    )


@router.get("/geo/aguas/meta")
def get_aguas_meta() -> dict:
    """Metadados da camada de memoria hidrica: bbox, cores, totais e limites.

    Separado do PNG porque o front precisa do bbox ANTES de decidir onde
    desenhar a imagem — e porque um cliente que so quer os numeros nao deve
    baixar 330 KB de raster para obte-los.
    """
    meta = aguas.load_meta()
    if meta is None:
        return {
            "disponivel": False,
            "motivo": (
                "camada nao calculada — rode `python -m src.ingest.jrc_gsw` e depois "
                "`python -m src.risk.aguas`"
            ),
        }
    return {
        "disponivel": True,
        "basis": "measured",
        **meta,
        "limites": [
            "Serie 1984-2021: NAO contem a cheia de maio de 2024.",
            "Nao cobre 150 anos — nao existe base vetorial da hidrografia do RS do seculo XIX.",
            "Sensor optico de 30 m: curso d'agua mais estreito que ~30 m nao aparece.",
            "Agua sazonal nao distingue banhado de lavoura de arroz irrigada por inundacao.",
            "A malha municipal do IBGE exclui as grandes lagoas (Patos, parte da Mirim).",
        ],
    }


@router.get("/geo/aguas.png")
def get_aguas_png() -> FileResponse:
    """Overlay RGBA alinhado ao bbox de `/geo/aguas/meta`.

    PNG e nao GeoJSON: sao ~2,2 milhoes de celulas de 500 m. Como vetor seriam
    dezenas de MB e o navegador travaria; como imagem sao 330 KB, e o
    alinhamento continua exato porque a projecao do mapa e linear em lon/lat.
    """
    caminho = aguas.SAIDA_PNG
    if not caminho.exists():
        raise HTTPException(
            status_code=503,
            detail="Overlay ausente. Rode `python -m src.ingest.jrc_gsw` e `python -m src.risk.aguas`.",
        )
    return FileResponse(caminho, media_type="image/png")


@router.get("/risk/municipal/cruzamento/aguas")
def get_cruzamento_aguas(
    limit: int = Query(25, ge=1, le=497),
) -> dict:
    """Municipios onde a agua voltou: memoria hidrica alta E inundacao em 2024.

    O cruzamento que da sentido a camada. Duas bases independentes:

      - JRC (optica, satelite, 1984-2021): onde JA FOI agua e deixou de ser;
      - MUNIC 2024 (declaratoria, prefeitura, pos-evento): onde inundou.

    A serie do JRC termina em 2021 e nao conhece a cheia de 2024. Se
    conhecesse, a concordancia entre as duas seria circular e nao valeria
    nada. Como nao conhece, concordancia e evidencia.
    """
    tabela = _tabela()
    itens = []
    for r in tabela.rows:
        ag = r.get("aguas")
        if not ag or ag.get("memoria_hidrica_frac") is None:
            continue
        det = r["componentes"]["impacto"]["detalhe"]
        perigos = det.get("perigos") or []
        hidrico = [p for p in perigos if p in ("oc_inundacao", "oc_enchente_enxurrada", "oc_alagamento")]
        if not hidrico:
            continue
        itens.append({
            "cod_mun": r["cod_mun"],
            "municipio": r["municipio"],
            "memoria_hidrica_frac": ag["memoria_hidrica_frac"],
            "memoria_hidrica_km2": ag["memoria_hidrica_km2"],
            "agua_perdida_km2": ag["perdida"]["km2"],
            "perigos_2024": hidrico,
            "score": r["score"],
            "level": r["level"],
        })
    itens.sort(key=lambda x: -(x["memoria_hidrica_frac"] or 0))
    return {
        "as_of": deps.now_iso()[:10],
        "n_com_memoria_e_inundacao": len(itens),
        "criterio": (
            "memoria hidrica (agua perdida + efemera, JRC 1984-2021) presente E "
            "inundacao, enchente/enxurrada ou alagamento declarados ao IBGE em 2024"
        ),
        "independencia": (
            "As duas bases nao se conhecem: o JRC termina em 2021 e e optico; o MUNIC e "
            "declaratorio e posterior ao evento. Concordancia aqui e evidencia, nao circularidade."
        ),
        "municipios": itens[:limit],
    }


@router.get("/resposta/municipios")
def get_resposta(
    limit: int | None = Query(None, ge=1, le=497),
    sem_unidade: bool = Query(False, description="So municipios sem hospital nem pronto-socorro"),
) -> dict:
    """Vulnerabilidade, capacidade de saude, autonomia logistica e resposta.

    Dominio do DEPOIS do evento, deliberadamente separado do indice de
    prioridade (que mede o antes). Ver o docstring de `src/risk/resposta.py`
    para por que os dois nao se somam.

    `capacidade.unidade` e sempre `"estabelecimentos"` — NUNCA leitos. A
    lacuna esta declarada em `lacunas`, com a fonte que resolveria.
    """
    try:
        tabela = resposta.build_table()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Base municipal ausente. Rode `python -m src.ingest.ibge_rs`. ({exc})",
        ) from exc

    linhas = tabela.rows
    if sem_unidade:
        linhas = [r for r in linhas if r["capacidade"]["total"] == 0]
        linhas.sort(key=lambda r: -(r["capacidade"]["km_ate_unidade_mais_proxima"] or 0))
    if limit is not None:
        linhas = linhas[:limit]

    return {
        "as_of": deps.now_iso()[:10],
        "provenance": {
            "basis": "measured",
            "horizon": "seasonal",
            "source_ids": ["ibge_munic_rs", "cnes_rs", "ibge_pop_rs"],
            "as_of": deps.now_iso()[:10],
        },
        "resumo": tabela.resumo,
        # As lacunas viajam com o dado, nao so na documentacao: quem consome a
        # capacidade precisa topar com "isto nao e leito" no mesmo payload.
        "lacunas": tabela.lacunas,
        "municipios": linhas,
    }


@router.get("/pessoal")
def get_pessoal() -> dict:
    """Quadro de pessoal, voluntariado instalado e pares de auxilio mutuo.

    Responde "com quem" o plano se executa. O achado que organiza a estrategia
    de voluntariado esta em `resumo.voluntariado.modelo_existente`: o RS ja tem
    corpos de bombeiros voluntarios constituidos, concentrados na Serra — nao
    e preciso importar modelo de fora.

    `auxilio_mutuo` sugere COM QUEM CONVERSAR, nunca afirma que o vizinho tem
    gente sobrando: "folga" aqui e ausencia dos sinais de fragilidade que o
    proprio dado registra, nao capacidade ociosa medida.
    """
    try:
        p = pessoal.build()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Base municipal ausente. Rode `python -m src.ingest.ibge_rs`. ({exc})",
        ) from exc

    headline, is_synth, _ = deps.state_headline()
    oni = None if is_synth else headline.get("oni")
    indice = model.build_table(oni).rows

    return {
        "as_of": deps.now_iso()[:10],
        "provenance": {
            "basis": "measured",
            "horizon": "seasonal",
            "source_ids": ["ibge_munic_rs", "cnes_rs", "osm_emergencia"],
            "as_of": deps.now_iso()[:10],
        },
        "resumo": p.resumo,
        "auxilio_mutuo": pessoal.auxilio_mutuo(indice, limite=30),
        "municipios": p.rows,
    }


@router.get("/recursos")
def get_recursos(pontos: bool = Query(True, description="Inclui a lista de pontos para o mapa")) -> dict:
    """Mapa geral de recursos de resposta e vazios de cobertura.

    Tres ressalvas viajam no payload e nao sao rodape (ver `resumo.ressalvas`):
    e BASE e nunca viatura; o CNES nao registra a frota do SAMU; e bombeiro e
    policia vem do OpenStreetMap, que e colaborativo — ausencia no mapa nao
    prova ausencia no territorio.
    """
    try:
        r = recursos.build()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Bases de recursos ausentes. Rode `python -m src.ingest.cnes_rs` e "
                f"`python -m src.ingest.osm_emergencia`. ({exc})"
            ),
        ) from exc

    headline, is_synth, _ = deps.state_headline()
    oni = None if is_synth else headline.get("oni")
    indice = model.build_table(oni).rows

    return {
        "as_of": deps.now_iso()[:10],
        "provenance": {
            "basis": "measured",
            "horizon": "seasonal",
            "source_ids": ["cnes_rs", "osm_emergencia", "ibge_malha_rs"],
            "as_of": deps.now_iso()[:10],
        },
        "resumo": r.resumo,
        "vazios": recursos.vazios_priorizados(indice, limite=40),
        # `pontos=false` para quem so quer os numeros: sao ~1.600 registros e
        # nem todo consumidor vai desenhar o mapa.
        "pontos": r.pontos if pontos else [],
        "por_municipio": {str(k): v for k, v in r.por_municipio.items()},
    }


@router.get("/plano")
def get_plano(
    cenario: str = Query("atual", description="atual | ond2026 | estrutural"),
    limit: int | None = Query(None, ge=1, le=497),
    horizonte: str | None = Query(None, description="imediato | estrutural"),
) -> dict:
    """Plano de acao preventiva: de lacuna declarada para acao nomeada.

    E a ultima traducao da central: todas as camadas anteriores diagnosticam,
    esta diz o que fazer e onde. Cada acao carrega `evidencia` — o campo exato
    que a disparou — e `fonte`. Nao existe acao inferida: se o campo falta, a
    acao nao aparece.

    Ver `src/risk/plano.py` para o que este plano NAO e (nao e engenharia, nao
    e custo-beneficio, e `esforco` e escolha editorial).
    """
    if cenario not in model.CENARIOS:
        raise HTTPException(
            status_code=422,
            detail=f"cenario invalido: {cenario!r}; disponiveis: {list(model.CENARIOS)}",
        )
    headline, is_synth, _ = deps.state_headline()
    oni = None if is_synth else headline.get("oni")
    try:
        dados = plano.build(cenario, oni)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Bases ausentes. Rode `python -m src.ingest.ibge_rs`. ({exc})",
        ) from exc

    municipios = dados["municipios"]
    if horizonte:
        municipios = [
            {**m, "acoes": [a for a in m["acoes"] if a["horizonte"] == horizonte]}
            for m in municipios
        ]
        municipios = [m for m in municipios if m["acoes"]]
    if limit is not None:
        municipios = municipios[:limit]

    return {
        "as_of": deps.now_iso()[:10],
        "provenance": {
            "basis": "modeled",  # a ORDEM e modelada; cada acao e measured
            "horizon": "seasonal",
            "source_ids": ["ibge_munic_rs", "cnes_rs", "jrc_gsw", "cpc_oni"],
            "as_of": deps.now_iso()[:10],
        },
        **{k: v for k, v in dados.items() if k != "municipios"},
        "municipios": municipios,
    }


@router.get("/historico/chuva")
def get_historico_chuva() -> dict:
    """Historia longa da chuva de primavera no RS e o deslocamento por ENSO.

    ATENCAO ao que este endpoint significa para o projeto: o calculo por tras
    dele E CONTATO COM O ALVO (ADR-004). A partir dele, mudar
    `feature_blocks.yaml` invalida o experimento. O payload repete isso em
    `meta.contato_com_alvo` para que nenhum consumidor descubra tarde.

    E analise DESCRITIVA: contagem e intervalo por reamostragem. Nenhum modelo
    foi ajustado, nenhum preditor foi selecionado — isso exigiria passar pelo
    criterio da ADR-007, que segue sem nenhum modelo aprovado.
    """
    dados = historico.load_json()
    if dados is None:
        return {
            "disponivel": False,
            "motivo": (
                "camada nao calculada — rode `python -m src.ingest.ghcn_rs` e depois "
                "`python -m src.risk.historico`"
            ),
        }
    return {"disponivel": True, "basis": "measured", **dados}


@router.get("/geo/municipios")
def get_malha_municipal() -> dict:
    """Malha municipal do RS em GeoJSON (IBGE, qualidade minima).

    Sem `response_model`: e GeoJSON, cuja forma e definida pela RFC 7946 e nao
    pelo nosso contrato. Modelar Polygon/MultiPolygon em Pydantic aqui so
    adicionaria validacao redundante sobre um payload que ja chega validado do
    IBGE e que o front consome como opaco.
    """
    geo = model.load_malha()
    if geo is None:
        raise HTTPException(
            status_code=503,
            detail="Malha municipal ausente. Rode `python -m src.ingest.ibge_rs malha`.",
        )
    return geo
