"""Pessoal, voluntariado e auxilio mutuo — quem executa o plano.

A pergunta que faltava
======================

O plano de acao (src/risk/plano.py) diz o que fazer. Nao dizia COM QUEM. E o
proprio MUNIC 2024 registra que a falta de gente foi motivo declarado de nao
execucao do plano de contingencia em municipios do RS — mais frequente que
falta de recurso material ou de treinamento.

Este modulo responde tres coisas:

    quadro       quantos servidores o municipio tem, com que vinculo, e se
                 conseguiu repor quadro nos ultimos 24 meses
    voluntariado se ha corpo de bombeiros voluntarios instalado, e a que
                 distancia esta o mais proximo
    auxilio      quais vizinhos tem folga de pessoal e de recurso, isto e,
                 com quem faz sentido firmar acordo de auxilio mutuo

O ACHADO QUE ORGANIZA A ESTRATEGIA DE VOLUNTARIADO
==================================================

O RS ja tem um modelo de voluntariado que funciona: corpos de bombeiros
voluntarios, constituidos como associacao ou sociedade civil, alguns
cadastrados no CNES. Eles NAO estao distribuidos pelo estado — concentram-se
na regiao de colonizacao alema e italiana da Serra (Nova Petropolis, Carlos
Barbosa, Picada Cafe, Estancia Velha, Salvador do Sul, Rolante, Marau,
Tapejara), com casos isolados fora dela (Candelaria, Sobradinho).

A consequencia para a estrategia e direta e vale mais que qualquer
recomendacao generica: **nao e preciso importar modelo de fora**. Existe um
arranjo institucional testado dentro do proprio estado, com estatuto,
financiamento e relacao com o CBMRS ja resolvidos. A pergunta operacional
deixa de ser "como criar voluntariado" e passa a ser "por que ele parou na
Serra, e o que dos municipios que o tem pode ser replicado".

Este modulo NAO responde essa segunda pergunta — ela exige entrevista, nao
dado. Mas nomeia os municipios que ja o fazem, que e por onde comeca.

LIMITES
=======
- Quadro de pessoal e da administracao DIRETA. Nao inclui indireta, nem
  terceirizado, nem cedido. Nao e "quantas pessoas a prefeitura mobiliza".
- Servidor por mil habitantes NAO e medida de qualidade nem de suficiencia:
  municipio pequeno tem razao alta por indivisibilidade do cargo (um
  contador serve 2.000 ou 20.000 habitantes). Use para comparar pares de
  porte parecido, nunca em ranking absoluto.
- "Sem vinculo permanente" e "estagiarios" contam como capacidade mais fraca
  por nao terem estabilidade nem, em geral, treinamento de defesa civil. Isso
  e uma LEITURA declarada, nao um fato do dado.
- Voluntariado vem de duas bases parciais (CNES e OpenStreetMap). A ausencia
  de brigada no dado nao prova ausencia no municipio.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
INTERIM = REPO_ROOT / "data" / "interim"

MUNIC_PARQUET = INTERIM / "ibge_munic_rs.parquet"
CNES_PARQUET = INTERIM / "cnes_rs.parquet"
OSM_PARQUET = INTERIM / "osm_emergencia.parquet"

VERSION = "pessoal-v1"

# Fracao do quadro sem estabilidade a partir da qual a capacidade de resposta
# fica declaradamente fragil. Um terco e escolha editorial: nao ha limiar
# tecnico publicado para "quadro fragil" em defesa civil municipal.
LIMIAR_FRAGILIDADE = 0.33

# Raio para considerar um vizinho como parceiro plausivel de auxilio mutuo.
# 60 km em linha reta e o alcance em que deslocar equipe e viatura no mesmo
# dia ainda faz sentido operacional.
RAIO_AUXILIO_KM = 60.0

# Padroes que identificam brigada voluntaria pelo nome. Heuristica declarada,
# nao cadastro: nao ha campo "voluntario" nem no CNES nem no OSM.
PADRAO_VOLUNTARIO = re.compile(r"volunt", re.IGNORECASE)


@dataclass(frozen=True)
class PessoalResult:
    rows: list[dict[str, Any]]
    resumo: dict[str, Any]


def _haversine(lon1: float, lat1: float, lon2: np.ndarray, lat2: np.ndarray) -> np.ndarray:
    r = 6371.0
    p1, p2 = math.radians(lat1), np.radians(lat2)
    a = (
        np.sin((p2 - p1) / 2) ** 2
        + math.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * r * np.arcsin(np.sqrt(a))


def _brigadas_voluntarias() -> pd.DataFrame:
    """Uniao de CNES e OSM, filtrada por 'voluntari' no nome ou operador.

    Duas bases parciais somadas continuam parciais. O que a uniao ganha e
    cobertura: o CNES pega as que se cadastraram como estabelecimento de
    saude, o OSM pega as que alguem mapeou. Ha sobreposicao, e ela e mantida
    de proposito — deduplicar por nome aproximado erraria mais do que acerta,
    e o uso aqui e "existe brigada por perto?", nao contagem.
    """
    quadros = []
    if CNES_PARQUET.exists():
        c = pd.read_parquet(CNES_PARQUET).dropna(subset=["lat", "lon"])
        m = c["nome_fantasia"].fillna("").str.contains(PADRAO_VOLUNTARIO)
        if m.any():
            quadros.append(pd.DataFrame({
                "nome": c.loc[m, "nome_fantasia"],
                "lat": c.loc[m, "lat"].astype(float),
                "lon": c.loc[m, "lon"].astype(float),
                "fonte": "cnes_rs",
            }))
    if OSM_PARQUET.exists():
        o = pd.read_parquet(OSM_PARQUET)
        o = o[o["papel"] == "bombeiro"]
        m = o["nome"].fillna("").str.contains(PADRAO_VOLUNTARIO) | o["operador"].fillna("").str.contains(
            PADRAO_VOLUNTARIO
        )
        if m.any():
            quadros.append(pd.DataFrame({
                "nome": o.loc[m, "nome"],
                "lat": o.loc[m, "lat"].astype(float),
                "lon": o.loc[m, "lon"].astype(float),
                "fonte": "osm_emergencia",
            }))
    if not quadros:
        return pd.DataFrame(columns=["nome", "lat", "lon", "fonte"])
    return pd.concat(quadros, ignore_index=True)


def build(centroides: dict[int, tuple[float, float]] | None = None) -> PessoalResult:
    if not MUNIC_PARQUET.exists():
        raise FileNotFoundError(
            f"{MUNIC_PARQUET} ausente — rode `python -m src.ingest.ibge_rs munic`"
        )
    df = pd.read_parquet(MUNIC_PARQUET)

    if centroides is None:
        from src.risk.recursos import _centroides

        centroides = _centroides()

    brig = _brigadas_voluntarias()
    blon = brig["lon"].to_numpy() if len(brig) else np.array([])
    blat = brig["lat"].to_numpy() if len(brig) else np.array([])

    # Percentil de servidores por mil habitantes, para leitura relativa.
    pop = pd.to_numeric(df["populacao"], errors="coerce")
    total = pd.to_numeric(df["rh_total"], errors="coerce")
    por_mil = (total / pop * 1000.0).where(pop > 0)
    df["_por_mil"] = por_mil
    df["_pct_por_mil"] = por_mil.rank(pct=True)

    rows: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        cod = int(r["cod_mun"])

        tot = None if pd.isna(r.get("rh_total")) else int(r["rh_total"])
        frageis = 0
        for col in ("rh_sem_vinculo", "rh_estagiarios"):
            v = r.get(col)
            if not pd.isna(v):
                frageis += int(v)
        frac_fragil = (frageis / tot) if tot else None

        km_brig = None
        if blon.size and cod in centroides:
            lon, lat = centroides[cod]
            km_brig = round(float(_haversine(lon, lat, blon, blat).min()), 1)

        rows.append({
            "cod_mun": cod,
            "municipio": str(r["municipio"]),
            "populacao": None if pd.isna(r.get("populacao")) else int(r["populacao"]),
            "quadro": {
                "total": tot,
                "estatutarios": None if pd.isna(r.get("rh_estatutarios")) else int(r["rh_estatutarios"]),
                "celetistas": None if pd.isna(r.get("rh_celetistas")) else int(r["rh_celetistas"]),
                "comissionados": None if pd.isna(r.get("rh_comissionados")) else int(r["rh_comissionados"]),
                "estagiarios": None if pd.isna(r.get("rh_estagiarios")) else int(r["rh_estagiarios"]),
                "sem_vinculo": None if pd.isna(r.get("rh_sem_vinculo")) else int(r["rh_sem_vinculo"]),
                "por_mil_hab": None if pd.isna(r["_por_mil"]) else round(float(r["_por_mil"]), 1),
                "percentil_por_mil": None if pd.isna(r["_pct_por_mil"]) else round(float(r["_pct_por_mil"]), 3),
                "frac_sem_estabilidade": None if frac_fragil is None else round(frac_fragil, 4),
                "quadro_fragil": None if frac_fragil is None else bool(frac_fragil >= LIMIAR_FRAGILIDADE),
                "concurso_24m": _b(r.get("rh_concurso_24m")),
                "contratou_24m": _b(r.get("rh_contratou_24m")),
                "basis": "measured" if tot is not None else None,
            },
            "voluntariado": {
                "km_brigada_mais_proxima": km_brig,
                "tem_no_municipio": bool(km_brig is not None and km_brig <= 12.0),
                "basis": "measured" if km_brig is not None else None,
                "nota": "brigada identificada por 'voluntari' no nome — heuristica, nao cadastro",
            },
            # O motivo declarado no evento de 2024. E o unico campo aqui que
            # nao e estrutural: diz que a falta de gente JA travou o plano.
            "faltou_pessoal_em_2024": _b(r.get("falta_recurso_humano")),
        })

    com_quadro = [x for x in rows if x["quadro"]["total"] is not None]
    frageis_n = sum(1 for x in com_quadro if x["quadro"]["quadro_fragil"])
    sem_concurso = sum(1 for x in rows if x["quadro"]["concurso_24m"] is False)
    faltou = sum(1 for x in rows if x["faltou_pessoal_em_2024"] is True)
    sem_brigada = sum(
        1 for x in rows
        if x["voluntariado"]["km_brigada_mais_proxima"] is not None
        and x["voluntariado"]["km_brigada_mais_proxima"] > 60
    )

    valores = [x["quadro"]["por_mil_hab"] for x in com_quadro if x["quadro"]["por_mil_hab"]]
    resumo = {
        "version": VERSION,
        "n_municipios": len(rows),
        "n_com_quadro": len(com_quadro),
        "servidores_por_mil": {
            "mediana": round(float(np.median(valores)), 1) if valores else None,
            "min": round(float(np.min(valores)), 1) if valores else None,
            "max": round(float(np.max(valores)), 1) if valores else None,
            "nota": "NAO e medida de suficiencia — municipio pequeno tem razao alta por "
                    "indivisibilidade do cargo. Compare pares de porte parecido.",
        },
        "quadro_fragil": {
            "n": frageis_n,
            "limiar": LIMIAR_FRAGILIDADE,
            "definicao": "fracao sem vinculo permanente + estagiarios sobre o total",
        },
        "sem_concurso_24m": sem_concurso,
        "faltou_pessoal_em_2024": faltou,
        "voluntariado": {
            "n_brigadas_identificadas": int(len(brig)),
            "municipios_a_mais_de_60km": sem_brigada,
            "modelo_existente": (
                "O RS ja tem corpos de bombeiros voluntarios constituidos como associacao ou "
                "sociedade civil, concentrados na Serra (colonizacao alema e italiana). Nao e "
                "preciso importar modelo: existe arranjo testado dentro do estado, com estatuto, "
                "financiamento e relacao com o CBMRS ja resolvidos."
            ),
            "municipios_com_brigada": sorted(
                {str(n) for n in brig["nome"].dropna().tolist()}
            )[:30],
        },
        "limites": [
            "Quadro e da administracao DIRETA: nao inclui indireta, terceirizado nem cedido.",
            "Servidor por mil habitantes nao mede suficiencia nem qualidade.",
            "'Sem vinculo' e 'estagiario' como capacidade mais fraca e LEITURA declarada.",
            "Voluntariado vem de duas bases parciais (CNES, OpenStreetMap); ausencia no dado "
            "nao prova ausencia no municipio.",
            "Nao ha dado de efetivo de defesa civil municipal — o MUNIC nao pergunta.",
        ],
    }
    return PessoalResult(rows=rows, resumo=resumo)


def _b(v: Any) -> bool | None:
    if v is None or v is pd.NA or (isinstance(v, float) and math.isnan(v)):
        return None
    return bool(v)


def auxilio_mutuo(indice: list[dict[str, Any]], limite: int = 30) -> list[dict[str, Any]]:
    """Pares (municipio carente, vizinho com folga) dentro do raio de auxilio.

    "Folga" e definida de forma deliberadamente conservadora: o vizinho tem
    quadro NAO fragil, teve concurso nos ultimos 24 meses e esta acima da
    mediana de servidores por mil habitantes. Nao e capacidade ociosa medida
    — e ausencia dos sinais de fragilidade que o proprio dado registra.

    Serve para SUGERIR com quem conversar, nunca para afirmar que o vizinho
    tem gente sobrando.
    """
    from src.risk.recursos import _centroides

    centroides = _centroides()
    pes = build(centroides)
    por_cod = {r["cod_mun"]: r for r in pes.rows}
    risco = {m["cod_mun"]: m for m in indice if m["score"] is not None}

    def tem_folga(r: dict[str, Any]) -> bool:
        q = r["quadro"]
        return (
            q["quadro_fragil"] is False
            and q["concurso_24m"] is True
            and (q["percentil_por_mil"] or 0) >= 0.5
        )

    candidatos = [r for r in pes.rows if tem_folga(r) and r["cod_mun"] in centroides]
    if not candidatos:
        return []
    clon = np.array([centroides[r["cod_mun"]][0] for r in candidatos])
    clat = np.array([centroides[r["cod_mun"]][1] for r in candidatos])

    saida = []
    for cod, m in risco.items():
        r = por_cod.get(cod)
        if not r or cod not in centroides:
            continue
        carente = (
            r["quadro"]["quadro_fragil"] is True
            or r["faltou_pessoal_em_2024"] is True
            or r["quadro"]["concurso_24m"] is False
        )
        if not carente:
            continue
        lon, lat = centroides[cod]
        d = _haversine(lon, lat, clon, clat)
        ordem = np.argsort(d)[:3]
        vizinhos = [
            {
                "cod_mun": candidatos[i]["cod_mun"],
                "municipio": candidatos[i]["municipio"],
                "km": round(float(d[i]), 1),
                "servidores_por_mil": candidatos[i]["quadro"]["por_mil_hab"],
            }
            for i in ordem
            if d[i] <= RAIO_AUXILIO_KM and candidatos[i]["cod_mun"] != cod
        ]
        if not vizinhos:
            continue
        motivos = []
        if r["quadro"]["quadro_fragil"]:
            motivos.append(
                f"{(r['quadro']['frac_sem_estabilidade'] or 0) * 100:.0f}% do quadro sem vinculo permanente"
            )
        if r["faltou_pessoal_em_2024"]:
            motivos.append("declarou falta de recurso humano como motivo de nao execucao do plano em 2024")
        if r["quadro"]["concurso_24m"] is False:
            motivos.append("sem concurso nos ultimos 24 meses")
        saida.append({
            "cod_mun": cod,
            "municipio": m["municipio"],
            "score": m["score"],
            "level": m["level"],
            "motivos": motivos,
            "vizinhos_com_folga": vizinhos,
        })

    saida.sort(key=lambda x: -(x["score"] or 0))
    return saida[:limite]
