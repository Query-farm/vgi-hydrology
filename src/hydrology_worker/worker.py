"""Assemble the functions into a catalog and run the worker.

The functions live in ``analysis.py``; to add one, write it there and append the
class to ``GIS_FUNCTIONS``.

Run it:

    vgi-hydrology-worker                      # stdio: what DuckDB launches by default
    vgi-hydrology-worker --http --port 8000   # HTTP: for Docker / hosted deploys
    vgi-hydrology-worker --help

Attach it from DuckDB:

    ATTACH 'hydrology' (TYPE vgi, LOCATION '/abs/path/to/.venv/bin/vgi-hydrology-worker');
"""

from __future__ import annotations

import json
from typing import Any

from vgi import Worker
from vgi.catalog import Catalog, Schema

from .analysis import GIS_DESCRIPTION, GIS_FUNCTIONS
from .meta import CATALOG_NAME, CATALOG_TAGS, SCHEMA_CATEGORIES, SOURCE_URL, keywords_array

# One-paragraph catalog description shown in directories (VGI001); the long
# analysis guidance lives in the vgi.doc_md / vgi.doc_llm tags.
CATALOG_COMMENT = (
    "Watershed analysis over digital elevation models: upstream catchments for river gauges and "
    "monitoring stations from D8 flow routing, and the land cover inside each catchment. Drainage "
    "analysis only, not a flood model. Sample rasters are included."
)


def _stamp_example_queries(functions: list[type[Any]]) -> list[dict[str, str]]:
    """Publish each function's examples as ``vgi.example_queries`` (with descriptions).

    Overloads share one SQL name, so their examples are merged per name.
    Returns every example, for the schema-level list.
    """
    by_name: dict[str, list[dict[str, str]]] = {}
    for fn in functions:
        bucket = by_name.setdefault(fn.Meta.name, [])
        for ex in getattr(fn.Meta, "examples", []):
            entry = {"description": ex.description, "sql": ex.sql}
            if entry not in bucket:
                bucket.append(entry)
    for fn in functions:
        fn.Meta.tags = {**fn.Meta.tags, "vgi.example_queries": json.dumps(by_name[fn.Meta.name])}
    return [entry for entries in by_name.values() for entry in entries]


_GIS_EXAMPLES = _stamp_example_queries(GIS_FUNCTIONS)


class HydrologyWorker(Worker):
    """The worker process: one catalog, one ``main`` schema."""

    catalog = Catalog(
        name=CATALOG_NAME,
        comment=CATALOG_COMMENT,
        source_url=SOURCE_URL,
        tags={
            **CATALOG_TAGS,
            "vgi.doc_llm": GIS_DESCRIPTION,
            "vgi.doc_md": "## GIS analysis\n\n" + GIS_DESCRIPTION + "\n\n### SQL workflow\n\n"
            "Pass query results to the main schema functions, retaining IDs for joins. "
            "Use bundled synthetic data to try the executable examples without network access. "
            "CRS, coverage, inference limits and resource bounds are explicit function parameters.",
            "vgi.subtitle": "Upstream catchments and land-cover summaries for monitoring stations.",
        },
        schemas=[
            Schema(
                path=["main"],
                comment="Spatial functions for " + CATALOG_NAME.replace("_", " ") + " analysis.",
                functions=GIS_FUNCTIONS,
                tags={
                    "vgi.title": "GIS Analysis",
                    "domain": "geospatial",
                    "vgi.keywords": keywords_array("GIS, spatial, raster, analysis"),
                    "vgi.doc_llm": GIS_DESCRIPTION,
                    "vgi.doc_md": "## GIS analysis\n\n" + GIS_DESCRIPTION + "\n\n### SQL workflow\n\n"
                    "Pass query results to the main schema functions, retaining IDs for joins. "
                    "Use bundled synthetic data to try the executable examples without network access. "
                    "CRS, coverage, inference limits and resource bounds are explicit function parameters.",
                    "vgi.categories": json.dumps(SCHEMA_CATEGORIES),
                    "vgi.example_queries": json.dumps(_GIS_EXAMPLES),
                },
            ),
        ],
    )


def main() -> None:
    """Console-script entry point: parse ``--http`` / ``--unix`` / logging flags and serve."""
    HydrologyWorker.main()


if __name__ == "__main__":
    main()
