"""Costura entre camadas — o teste que faltava quando o front ficou sintetico
com o dado real ja em disco.

Cada camada foi construida em paralelo e passou nos proprios testes. O que
falhou foi o CONTRATO ENTRE elas: a ingestao escrevia `data/interim/cpc_oni.
parquet`, o front esperava `data/features/signals/oni.parquet`. Nenhum teste
de nenhum dos lados podia pegar isso — por construcao.

O modo de falha e pior que uma excecao: o front degrada graciosamente para
fixtures e continua bonito, exibindo dado sintetico enquanto o dado medido
esta la. Silencioso e plausivel. Dai o teste.
"""
from __future__ import annotations

import pytest

import src.ingest  # noqa: F401  — o import e o que popula o registro
from app import data_source as ds
from src.ingest.base import DATA_INTERIM
from src.ingest.registry import registered_ids


def _ingested_paths() -> dict[str, object]:
    """Onde cada ingestor registrado grava, segundo a convencao de base.py."""
    return {sid: DATA_INTERIM / f"{sid}.parquet" for sid in registered_ids()}


@pytest.mark.parametrize("key,source_id", [("oni", "cpc_oni"), ("sam", "cpc_aao")])
def test_front_points_at_the_path_the_ingestor_writes(key, source_id):
    paths = _ingested_paths()
    assert source_id in paths, f"ingestor {source_id} nao registrado"
    assert ds.EXPECTED[key] == paths[source_id], (
        f"costura quebrada: front espera {ds.EXPECTED[key]}, "
        f"ingestor grava {paths[source_id]} — o front cairia em fixtures "
        "silenciosamente, com o dado real em disco"
    )


@pytest.mark.parametrize("key", ["oni", "sam"])
def test_resolves_to_measured_when_file_exists(key):
    """Se o parquet existe, `is_synthetic` TEM que ser False.

    Skip quando ausente: data/interim e gitignored e CI limpo nao tem dado.
    Skip e honesto aqui; passar sem verificar nao seria.
    """
    if not ds.EXPECTED[key].exists():
        pytest.skip(f"{ds.EXPECTED[key].name} ausente — rode `python -m src.ingest.cli --all`")
    r = ds._resolve(key, lambda: (_ for _ in ()).throw(AssertionError("caiu em fixtures")))
    assert not r.is_synthetic and len(r.df) > 0


def test_signal_filter_targets_existing_signals():
    """Um signal_id errado em SIGNAL_FILTER esvazia o DataFrame e o front volta
    a fixtures — mesma falha silenciosa, por outra porta."""
    import pandas as pd

    for key, sig in ds.SIGNAL_FILTER.items():
        path = ds.EXPECTED[key]
        if not path.exists():
            pytest.skip(f"{path.name} ausente")
        available = set(pd.read_parquet(path)["signal_id"].unique())
        assert sig in available, (
            f"SIGNAL_FILTER['{key}']='{sig}' nao existe em {path.name}; "
            f"disponiveis: {sorted(available)}"
        )
