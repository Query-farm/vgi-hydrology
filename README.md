# Upstream catchments and land cover

Independent Python VGI worker: query geospatial analysis from SQL and join the resulting rows to your existing tables.

vgi-hydrology 0.3.0 speaks VGI protocol 3.4, so it needs Haybarn 2.0.1 or newer (Haybarn 2.0.0 loads a 3.3 `vgi` extension that cannot attach it).

## Run it

Requires Python 3.14+ and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Query-farm/vgi-hydrology.git
cd vgi-hydrology
uv sync --locked
make demo
make verify-stock
make check
```

`make demo` runs [demo.sql](demo.sql) in stock DuckDB 2.0.0. Demo datasets ship inside the wheel; no data credentials are required. The first run downloads dependencies and signed SQL extensions. `make verify-stock` asserts every expected result in [vgi-worker.json](vgi-worker.json), including empty inputs, joins and multiple batches.

## Analysis contract

`catchments((SELECT station_id, x, y FROM stations), ...)` returns independently delineated upstream polygons, areas, selected outlets and boundary flags. `landcover((SELECT station_id, geometry_wkb FROM catchments), ...)` returns categorical class counts, areas and coverage fractions.

**Acceptance:** the outlet drains 49 cells / 4,900 m². Land cover has 21 class-10 cells and 28 class-20 cells, conserving the catchment area. SQL finds the upstream facility and excludes the outside facility. Nested outlets retain their complete upstream areas.

Use a north-up, projected metre DEM with metre elevations and a suitable drainage extent. PyFlwDir derives a depression-filled D8 network. By default the station's containing cell is the outlet; `snap_radius_m` optionally searches for a nearby cell meeting `min_stream_area_m2`. This is Euclidean stream-cell snapping, so inspect the snapped outlet in ambiguous valleys. Catchments touching the DEM edge or a missing-data boundary are flagged as potentially incomplete.

Land cover is a north-up categorical raster in a projected metre CRS; polygons are reprojected into its CRS, and pixel-centre inclusion determines counts. No bilinear interpolation is applied to classes. Coverage includes missing/outside pixels. Use output `dem_crs` as `geometry_crs` when feeding catchments to landcover; defaults agree only for the bundled demo. Facility geometry must also share the catchment CRS before spatial joining.

Default DEM and land-cover window limits are 2 million and 2 million cells respectively. This is upstream drainage analysis, not flood inundation, hydraulic routing, discharge prediction or pollutant transport. DEM conditioning and local hydrological validation remain dataset-specific.

## Use your data

After `uv sync`, attach the executable with its absolute path:

```sql
SET allow_extension_repositories = 'allowed';
CREATE EXTENSION REPOSITORY IF NOT EXISTS query_farm
  WITH PREFIX 'https://duckdb-extensions.query.farm';
INSTALL vgi FROM query_farm;
LOAD vgi FROM query_farm;
INSTALL spatial;
LOAD spatial;
ATTACH 'hydrology' (TYPE vgi,
  LOCATION '/absolute/path/to/vgi-hydrology/.venv/bin/vgi-hydrology-worker');
```

The following template expects your own source tables and paths:

```sql
CREATE TEMP TABLE basins AS
SELECT * FROM hydrology.main.catchments((SELECT station_id, x, y FROM stations),
    dem := '/absolute/path/conditioned_dem.tif', input_crs := 'EPSG:4326');
SELECT * FROM hydrology.main.landcover(
    (SELECT station_id, geometry_wkb FROM basins WHERE status = 'ok'),
    raster := '/absolute/path/landcover.tif', geometry_crs := 'EPSG:32618')
ORDER BY station_id, class_code;
```

Nested gauges compose: delineate several stations, summarize each catchment's land cover, and join the class rows back. On the bundled data, this picks the class covering the most upstream area at each gauge (class 10 at `west`, class 20 at `east`, `mid` and `outlet`):

```sql
WITH basins AS (
  SELECT station_id, area_m2, geometry_wkb
  FROM hydrology.main.catchments((SELECT * FROM (VALUES
      ('west', 500015.0, 4100035.0), ('mid', 500035.0, 4100035.0),
      ('east', 500055.0, 4100035.0), ('outlet', 500035.0, 4100005.0)) AS gauges(station_id, x, y)))
  WHERE status = 'ok')
SELECT b.station_id, b.area_m2, arg_max(l.class_code, l.area_m2) AS dominant_class, max(l.fraction_of_valid) AS dominant_share
FROM basins AS b JOIN hydrology.main.landcover((SELECT station_id, geometry_wkb FROM basins)) AS l
  ON l.station_id = b.station_id GROUP BY b.station_id, b.area_m2 ORDER BY b.station_id;
```

WKB is an ordinary SQL BLOB with an explicit companion CRS, not an automatically transformed geometry. Use `ST_AsWKB` on input and `ST_GeomFromWKB` on output when using Spatial. Coordinates always use X/Y order. Do not join different coordinate systems without transforming them. Input IDs are retained as VARCHAR for joins. Invalid input schemas, geometries, coordinates and exceeded resource limits fail explicitly.

## Verification and provenance

- Scientific fixtures and edge cases: [tests/test_analysis.py](tests/test_analysis.py).
- Real SQL across stdio, launch and HTTP: [test/sql/gis.test](test/sql/gis.test), run by `make check`.
- Stock DuckDB contract: `validation/stock-duckdb.json` (generated locally).
- Full local checks: `validation/production-check.log` (local evidence); unmodified starter baseline: `validation/baseline.log` (local evidence).
- Worker language: Python, pinned locally to 3.14. SDK: `vgi-python 0.51.1` with the starter's `>=0.51.1,<0.52` compatibility bound retained.
- Starter: [Query-farm/vgi-starter-python](https://github.com/Query-farm/vgi-starter-python), commit `9cca9105474d6e0052b8e343c8ea21f3d1a7503c`, template 1.3.0.
- Stock engine: DuckDB 2.0.0, signed VGI extension `e75482339d` from `query_farm`. The starter integration runner is separately pinned to `haybarn-unittest 2.0.1rc3`; it is not the stock DuckDB check.

`make check` includes formatting, Ruff, strict mypy, docstring checks, unit tests, all three SQL transports, executed metadata examples and stock DuckDB assertions. `make lint-ai` is an optional agent evaluation and is not part of the completed checks. All functions live in the `main` schema. Tests use synthetic known-answer fixtures, not a claim of production accuracy on every dataset.

Run `make release-check` to build a wheel from the source archive and verify its installed SQL interface outside the checkout. `make verify-container` builds locked runtime dependencies and checks every stock SQL assertion through a non-root, read-only HTTP container. See [PRODUCTION.md](PRODUCTION.md) for deployment, capacity limits, release evidence and operational boundaries.

## Support

Source and support: [Query-farm/vgi-hydrology](https://github.com/Query-farm/vgi-hydrology). Report reproducible issues in GitHub Issues. No service is deployed and container publishing is manual-only. Keep reports tied to the input CRS, resource limits and reproducible SQL. See [LICENSE](LICENSE) for the starter's license and dependency licenses for their terms.

## Executed notebook

[Compare upstream catchments](notebooks/README.md) follows station snapping, land-cover
composition and facility inclusion through the published worker, with mapped results
and a standalone parameter experiment. It runs from the notebook directory alone.
