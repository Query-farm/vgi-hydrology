# Hydrology notebooks

Read the saved outputs on GitHub or use **Open in Colab** at the top of either notebook.

| Notebook | Question | Default → experiment |
|---|---|---|
| [01 · Compare upstream catchments](01_compare_upstream_catchments.ipynb) | How does station snapping change area, land cover and facility inclusion? | Snapping radius 0 → 15 metres |
| [02 · Pages and plan completeness](02_pages_are_not_procurement_completeness.ipynb) | Can a fully retrieved catalog price every requested item? | Local fixture page size 3 → 1 |

The first preserves the existing spatial analysis and twelve reconciliation checks. The second demonstrates the released `examples` starter schema separately; it is not a new hydrology or real procurement service. Every raster, station, facility, item, price and contact is synthetic. No real supplier, account, credential, order, email or external analytical data service is used.

## Run from this directory

Install [uv](https://docs.astral.sh/uv/). Initial packages, hash-verified notebook companions, signed SQL extensions and the released Git worker need internet access. The shared base package accepts Python3.11–3.14 kernels; uv provisions the isolated worker's declared Python>=3.13 requirement. Rasterio renders the GeoTIFFs, and the worker owns PyFlwDir/GIS computation. First PyFlwDir JIT compilation may take longer than later runs. No source checkout, local worker build or globally installed kernel is required.

```sh
uv sync --locked --extra runner
uv run --locked --extra runner vgi-notebooks
uv run --locked --extra runner vgi-notebooks 01_compare_upstream_catchments.ipynb --parameters '{"SNAP_RADIUS_M":15.0}' --output-dir validation/snapped
uv run --locked --extra runner vgi-notebooks 02_pages_are_not_procurement_completeness.ipynb --parameters '{"PAGE_SIZE":1}' --output-dir validation/page-1
```

For interactive Jupyter use this environment's Python kernel and this directory as cwd. Restart and Run All after changing a parameter. Colab installs only the shared base package plus Rasterio, preserving compatible imported plotting/data and kernel libraries; `[runner]` is only for local publication. [Shared v0.3.26](https://github.com/Query-farm/vgi-example-notebooks/releases/tag/v0.3.26) provides branding, SVG charts, an isolated SQL session, hash-verified companion setup, coverage validation and an atomic runner. Overrides require a separate output directory and failed runs preserve the last successful notebook.

Both notebooks visibly use the clean public release:

```sql
INSTALL vgi FROM community;
LOAD vgi;
ATTACH 'hydrology' (TYPE vgi,
 LOCATION 'uvx --from git+https://github.com/Query-farm/vgi-hydrology@v0.1.0 vgi-hydrology-worker');
```

Release v0.1.0 and the reviewed current public source resolve to `5eb227dd0a37deb1adab00d5129b4f86338c1d40`. No transitive `--with` overrides or source build are used. The notebook lock fixes publication packages; worker release dependencies use declared ranges and a separate uv environment. Upgrade the visible release deliberately and verify both parameter variants.

## Spatial provenance and interpretation

`fixtures/basin.tif` and `fixtures/landcover.tif` are unchanged copies of the published worker's bundled data. The DEM has49 cells of100 m² in EPSG:32618, with metre elevations; categorical codes 10/20 are toy classes. All station and facility coordinates are visible SQL literals in that same projected CRS. Worker WKB results retain their CRS for spatial joins.

Zero radius uses the containing cell without a stream threshold. A positive radius selects the nearest qualifying cell with at least 1,000 m² upstream area within that Euclidean distance; it does not follow a downstream path. The offset station can reach the channel 10 m away at 15 m radius. Out-of-raster stations stay unavailable. Basins are independent and can overlap; do not sum them as disjoint parcels. Every successful example reaches the DEM edge, so the full real-world watershed is not established.

Land-cover composition is conditional on valid pixels; coverage is a separate measure. The grid-aligned fixture conserves raster area, but pixel-centre inclusion is not an exact arbitrary-polygon area integral. Geometric facility inclusion is not pollutant transport, flood inundation, causality or impact. Compare facility identities as well as counts when the selected basin changes.

## Local REST fixture and credentials

`inventory_fixture.py` serves seven fixed synthetic inventory rows from an ephemeral `127.0.0.1` port. It implements GET pages only, requires the deliberately fake public token `synthetic-hydrology-notebook-only`, and records only page/page-size/status. The SQL-generated plan independently requests eight IDs and 15 units. ID 8 is absent, ID 5's price is NULL, ID 6's name is NULL; a known subtotal must remain distinct from a complete quote. Greeting labels are strings only, do not identify or authenticate contacts, and preserve NULLs.

Shared `connect(globals())` creates an empty temporary SQL-secret directory, disables persistence/default INI autoload, and verifies no secrets before ATTACH. Notebook02 explicitly creates only a TEMPORARY `hydrology_api` fixture secret, verifies its name/type/nonpersistent status, drops it at cleanup, then closes the session and server. Notebook01 uses no secret. The user's persistent credentials and global environment are never read or changed by notebook setup. The worker receives the explicit fake SQL secret for its local HTTP requests.

The real released `fetch_items` reader is tested against this fixture; no live API validation or production retry behavior is claimed. A real integration needs an endpoint matching the `/items` JSON contract and a credential intentionally supplied for that endpoint. Do not silently redirect this fixture notebook to a real account. Changing page size alters the number of successful GETs, while rows, missingness, subtotal and the chart stay fixed.

## Coverage and validation

The actual released catalog has 7 function rows and 1 physical table: `greet` has two overloads, and `demo_input` has a table plus same-named function alias. Counted once per (schema, name), the **six logical surfaces are all meaningfully demonstrated**: main.catchments, main.landcover, main.demo_input, examples.sequence_table, examples.fetch_items and examples.greet. Authenticated example APIs stay in the denominator. `coverage.json` retains complete native function/table/view exports, source evidence, result/editorial mappings and receipts hashed from final saved JSON.

Every default and meaningful experiment is executed. One fresh preloaded Python3.12 notebook-only setup exercises the common launcher and companion-download path. Actual hosted Colab remains untested. Review charts are inspected in both parameter variants; published SVG links are verified in GitHub's actual renderer. Generated logs, review PNGs, runtime audits and experiment copies remain ignored.

Unchanged source CI [43621432643](https://github.com/Query-farm/vgi-hydrology/actions/runs/43621432643) at the exact release/current source is reused. The source's latest CI accommodates PyFlwDir's cold JIT in its metadata timing budget. This notebook-only update does not rebuild the worker, rerun source suites, deploy services or publish containers. The new local fixture alone receives focused authentication/page/cleanup checks, and both notebooks exercise the real released worker.

The [shared standard](https://github.com/Query-farm/vgi-example-notebooks/blob/main/docs/standard.md) and [coverage format](https://github.com/Query-farm/vgi-example-notebooks/blob/main/docs/coverage.md) are maintained centrally.

The `hydrology` companion registry pins `46987e8b8f9394e2456ec318e287458a3c15efad`: two unchanged synthetic GeoTIFFs and the local inventory fixture helper, each checked against its registered SHA256 before use.
