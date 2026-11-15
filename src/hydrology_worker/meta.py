"""Discovery metadata: the one file to edit when you rename or extend the worker.

DuckDB, coding agents and the ``vgi-lint`` metadata checker all read these
tags. Keep every object documented and ``make lint`` stays at 100.

* Catalog-level tags (title, license, author, links, long description) live in
  ``CATALOG_TAGS`` below.
* Every function and table carries ``object_tags(...)``: a title, a category
  from ``SCHEMA_CATEGORIES``, search keywords, and LLM- and human-facing docs.
"""

from __future__ import annotations

import json
from typing import Any

import pyarrow as pa

CATALOG_NAME = "hydrology"

SOURCE_URL = "https://github.com/Query-farm/vgi-hydrology"

# Categories group functions in docs and agent tools. Every object's
# ``vgi.category`` must name one of these.
SCHEMA_CATEGORIES = [
    {
        "name": "gis",
        "title": "GIS Analysis",
        "description": "Spatial analysis over query results and geospatial assets.",
    },
]


# Upstream specs, data providers and libraries the catalog docs link to (VGI183).
CATALOG_REFERENCES_MD = (
    "\n\n## Sources and references\n\n"
    "- [PyFlwDir](https://deltares.github.io/pyflwdir/latest/): the Deltares flow-direction library; "
    "[pyflwdir.from_dem](https://deltares.github.io/pyflwdir/latest/_generated/pyflwdir.from_dem.html) "
    "fills depressions and derives the D8 network used for catchments.\n"
    "- [Rasterio](https://rasterio.readthedocs.io/): reads the DEM and land-cover rasters and polygonizes "
    "catchment masks.\n"
    "- [Shapely](https://shapely.readthedocs.io/) and [pyproj](https://pyproj4.github.io/pyproj/stable/): "
    "geometry handling and the coordinate transforms between station, DEM and land-cover CRSs."
)


def keywords_array(keywords: str) -> str:
    """Turn ``"a, b, c"`` into the JSON array string ``vgi.keywords`` requires."""
    return json.dumps([k.strip() for k in keywords.split(",") if k.strip()])


def object_tags(*, title: str, category: str, keywords: str, doc_llm: str, doc_md: str) -> dict[str, str]:
    """Build the standard per-object discovery tags."""
    if category not in {c["name"] for c in SCHEMA_CATEGORIES}:
        raise ValueError(f"unknown category {category!r}; add it to SCHEMA_CATEGORIES")
    return {
        "vgi.title": title,
        "vgi.category": category,
        "vgi.keywords": keywords_array(keywords),
        "vgi.doc_llm": doc_llm,
        "vgi.doc_md": doc_md,
    }


def column(name: str, type_: pa.DataType, comment: str, *, nullable: bool = True) -> pa.Field[Any]:
    """Build an Arrow field whose ``comment`` shows up in DuckDB's ``DESCRIBE`` and agent tools."""
    return pa.field(name, type_, nullable=nullable, metadata={b"comment": comment.encode()})


# Public analyst tasks for `vgi-lint simulate`; private graders live in vgi-agent-tests.yaml.
AGENT_TEST_TASKS = [
    {
        "name": "gis_catchments",
        "prompt": "Delineate the upstream catchment of the synthetic valley's outlet gauge 'outlet' at "
        "(x=500035, y=4100005) in EPSG:32618 on the bundled synthetic DEM. Return the columns and "
        "ordering shown in the catchments catalog example.",
    },
    {
        "name": "gis_landcover",
        "prompt": "Confirm the entire upstream area of the synthetic valley's outlet gauge 'outlet' at "
        "(x=500035, y=4100005) in EPSG:32618 has classified land cover, using the bundled synthetic "
        "DEM and land cover. Return the columns and ordering shown in the landcover catalog example.",
    },
    {
        "name": "gis_class20_share",
        "prompt": "Gauges west (x=500015, y=4100035), mid (x=500035, y=4100035) and east "
        "(x=500055, y=4100035), in EPSG:32618, sit on the bundled synthetic DEM. Using the bundled "
        "synthetic land cover, what percentage of each gauge's upstream catchment area is land-cover "
        "class 20? Return station_id and pct_class_20 (a DOUBLE rounded to 1 decimal place, 0.0 when "
        "the catchment has none), one row per gauge ordered by station_id.",
    },
]

CATALOG_TAGS = {
    "vgi.title": "VGI Hydrology Worker",
    "vgi.source_url": SOURCE_URL,
    "vgi.icon_url": "https://query.farm/media-kit/products/vgi/vgi-logo.png",
    "vgi.license": "0BSD",
    "vgi.author": "Query.Farm",
    "vgi.copyright": "Copyright 2026 Query.Farm LLC",
    "vgi.keywords": keywords_array("vgi, duckdb, hydrology, catchments, D8 routing, land cover, geospatial"),
    "vgi.support_contact": f"{SOURCE_URL}/issues",
    "vgi.support_policy_url": f"{SOURCE_URL}#support",
    "vgi.agent_test_tasks": json.dumps(AGENT_TEST_TASKS),
}
