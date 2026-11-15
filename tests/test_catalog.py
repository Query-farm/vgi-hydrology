"""The published catalog exposes only the hydrology functions."""

from __future__ import annotations

from hydrology_worker.analysis import GIS_FUNCTIONS
from hydrology_worker.worker import HydrologyWorker


def test_catalog_exposes_only_hydrology_functions() -> None:
    schemas = HydrologyWorker.catalog.schemas
    assert [list(s.path) for s in schemas] == [["main"]]
    assert list(schemas[0].functions) == GIS_FUNCTIONS
    assert sorted(f.Meta.name for f in GIS_FUNCTIONS) == ["catchments", "landcover"]
    assert not schemas[0].tables
    assert not getattr(HydrologyWorker, "secret_types", [])
