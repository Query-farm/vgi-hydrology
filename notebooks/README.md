# Hydrology notebooks

[01_compare_upstream_catchments.ipynb](01_compare_upstream_catchments.ipynb)
investigates how station location and stream-cell snapping change upstream area,
land-cover composition and geometric facility inclusion. It keeps outside stations,
coverage, boundary limitation and overlapping catchments explicit.

## Reproduce the executed example

Install [uv](https://docs.astral.sh/uv/) and Python 3.13 or 3.14. A copy of this whole
notebooks directory is sufficient; no worker source tree or root virtual environment
is needed. From this directory:

```sh
uv sync --locked
uv run python execute.py
```

The runner creates a temporary kernel specification using the notebook environment.
To work interactively, select `.venv/bin/python`, or explicitly register it:

```sh
uv run python -m ipykernel install --user --name vgi-hydrology-notebooks --display-name "VGI Hydrology notebooks"
```

The environment pins Haybarn 2.0.0rc11. Visible SQL installs VGI and Spatial and
launches the real worker with uvx from public full Git revision
`af768fc3a4cca451a27d0023efd317aff580fe11`. First installation needs internet access;
the analysis itself reads only local synthetic GeoTIFFs. The worker includes
Rasterio, PyFlwDir and its numerical dependencies. Initial compilation/cache setup
may take longer than later runs. No account, cloud service or API credential is used.
An empty temporary SQL secret directory and disabled persistent secrets keep the
session independent of saved credentials.

## Model and provenance

`fixtures/basin.tif` and `fixtures/landcover.tif` are unchanged copies of the
published worker's `src/hydrology_worker/data/` fixtures. The DEM has 49 cells of
100 m² in EPSG:32618, with metre elevations; class codes 10 and 20 are synthetic
categories. The outlet drains the full 4,900 m² fixture. Input stations and toy
facility points are visible SQL values in the same coordinate system.

PyFlwDir derives a depression-filled D8 network. Zero snapping radius uses the
containing cell even when it falls below the stream-area threshold. A positive
radius chooses the nearest cell with at least 1,000 m² upstream drainage inside
that Euclidean distance. It does not follow a downstream path. Out-of-raster points
remain unavailable. Catchments are delineated independently, so nested or coincident
polygons overlap. Do not sum them as disjoint areas.

Every successful example basin reaches the DEM boundary; its full real-world
upstream extent is therefore unknown. Land-cover class shares are conditional on
valid pixels, while coverage is reported separately. This fixture is fully covered
and grid-aligned; pixel-centre categorical summaries are not exact arbitrary-polygon
area integrals. WKB carries an explicit CRS, and facility inclusion is a geometric
join, not a transport, pollution, inundation or causality model.

Python only validates parameters and renders returned geometry and raster imagery.
The real worker computes catchments and categorical summaries; visible SQL performs
comparisons, spatial joins and twelve reconciliation checks.

## One-parameter experiment

```sh
uv run python execute.py --parameters '{"SNAP_RADIUS_M":15.0}' --output-dir artifacts/snapped
```

Compare the offset station's area, outlet, land-cover counts and covered facility
IDs with the 0.0 m default. It should reach the channel 10 m away and share the
midstream basin. Track facility IDs as well as counts: selecting another basin can
replace one included site with another. The fixed baseline, reference stations and raster bytes remain
unchanged. Reset SNAP_RADIUS_M to 0.0 afterward. Accepted values are finite numbers
from 0 through 30 metres; smaller positive radii can legitimately fail to find a
stream cell for the offset station.

The runner writes only after complete success. Overrides require a separate output
directory and cannot overwrite the original. Experiment copies include branding,
fixtures, helpers, this README and locked environment files. Artifacts, caches and
extracted charts are ignored. Portability is checked by copying only these notebook
files into a separate directory, syncing there and executing the experiment.

## Validation

Both default and experiment should pass twelve visible SQL checks. Review both
figures in each run, including status and boundary annotations. Notebook checks:

```sh
uvx ruff check .
uvx ruff format --check .
```

The source release passed its separate `make release-check`: 12 pytest tests;
109 stdio, 109 Unix-launch and 70 HTTP SQL assertions; Ruff, strict mypy, pydoclint;
metadata 100/100 L2 with zero findings; six stock DuckDB contracts; and six contracts
against a clean wheel built from the source archive. Source locks and GIS algorithms
were preserved. Historical container evidence remains local; this publication did
not run a container release, deployment or optional agent-driven metadata check.
