from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely import from_wkb
from shapely.geometry import box

from hydrology_worker.analysis import delineate, load_flow, summarize
from hydrology_worker.support import resource


def args(**updates: Any) -> SimpleNamespace:
    return SimpleNamespace(
        **{
            "input_crs": "EPSG:32618",
            "snap_radius_m": 0.0,
            "min_stream_area_m2": 0.0,
            "geometry_crs": "EPSG:32618",
            "max_pixels": 2000000,
            **updates,
        }
    )


@pytest.fixture(scope="module")
def network() -> Any:
    return load_flow("demo://basin.tif", 1000)


def station(**updates: Any) -> Any:
    return {"station_id": "outlet", "x": 500035.0, "y": 4100005.0, **updates}


def test_known_basin_area_and_boundary_flag(network: Any) -> None:
    result = delineate(station(), network, args())
    assert result["cell_count"] == 49
    assert result["area_m2"] == 4900
    assert from_wkb(result["geometry_wkb"]).area == 4900
    assert result["boundary_limited"] is True


def test_landcover_area_conservation(network: Any) -> None:
    basin = delineate(station(), network, args())
    with rasterio.open(resource("demo://landcover.tif")) as ds:
        rows = summarize(basin, ds, args())
    assert [(r["class_code"], r["pixel_count"]) for r in rows] == [(10, 21), (20, 28)]
    assert sum(r["area_m2"] for r in rows) == 4900
    assert sum(r["fraction_of_valid"] for r in rows) == pytest.approx(1.0)
    assert all(r["coverage_fraction"] == 1.0 for r in rows)


def test_outside_and_failed_snapping(network: Any) -> None:
    assert delineate(station(x=499990), network, args())["status"] == "outside_dem"
    result = delineate(station(), network, args(snap_radius_m=5.0, min_stream_area_m2=10000.0))
    assert result["status"] == "no_stream_within_radius"
    assert result["geometry_wkb"] is None


def test_nested_outlets_keep_independent_upstream_areas(network: Any) -> None:
    upstream = delineate(station(station_id="upstream", y=4100035), network, args())
    downstream = delineate(station(), network, args())
    assert 0 < upstream["area_m2"] < downstream["area_m2"]
    assert from_wkb(downstream["geometry_wkb"]).covers(from_wkb(upstream["geometry_wkb"]))


def test_limits_and_nodata_station(network: Any) -> None:
    with pytest.raises(ValueError, match="max_cells"):
        load_flow("demo://basin.tif", 4)
    flow, valid, transform, crs = network
    valid = valid.copy()
    valid[6, 3] = False
    assert delineate(station(), (flow, valid, transform, crs), args())["status"] == "nodata"


def test_partial_landcover_extent_and_integer_overflow(tmp_path: Path) -> None:
    path = tmp_path / "landcover.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=2,
        height=2,
        count=1,
        dtype="uint64",
        crs="EPSG:32618",
        transform=from_origin(0, 20, 10, 10),
    ) as ds:
        ds.write(np.ones((2, 2), dtype="uint64"), 1)
    area = {"station_id": "partial", "geometry_wkb": box(0, 0, 40, 20).wkb}
    with rasterio.open(path) as ds:
        rows = summarize(area, ds, args())
    assert rows[0]["coverage_fraction"] == 0.5
    assert rows[0]["pixel_count"] == 4
    assert rows[0]["area_m2"] == 400.0
    with rasterio.open(path, "r+") as ds:
        ds.write(np.full((2, 2), 2**63, dtype="uint64"), 1)
    with rasterio.open(path) as ds, pytest.raises(ValueError, match="signed 64-bit"):
        summarize(area, ds, args())
