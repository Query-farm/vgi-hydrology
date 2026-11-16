# Changelog

## 0.2.2 (2026-11-16)

- Bump vgi-python to 0.52.2.
- Move to Python 3.14: `requires-python >=3.14`, CI, the Docker image and lint tooling target 3.14.

## 0.2.1

- Docs link to upstream sources: the catalog `vgi.doc_md` gains a Sources and references section linking PyFlwDir (and its `from_dem` D8 routine), Rasterio, Shapely and pyproj (VGI183).

## 0.2.0 (2026-11-14)

- Removed the starter template's demo schema (`examples.greet` / `fetch_items` / `sequence_table`), `demo_input` and the placeholder `hydrology_api` secret type. The worker now exposes only `main.catchments` and `main.landcover` and needs no credentials.
- Examples, tests and agent tasks that read the synthetic outlet from `demo_input` now use an inline `VALUES` station relation (`('outlet', 500035.0, 4100005.0)`).
- Removed the starter's SDK recipe scripts (`examples/`), the mock REST API and the starter-only paginated-inventory notebook.
- The catalog comment is now a short plain-text description of what the worker covers; the detailed analysis notes remain in the catalog's `vgi.doc_md` and `vgi.doc_llm` documentation.

## 0.1.0 (2026-11-14)

First release.

- `catchments`: D8 upstream catchment delineation from a projected DEM (PyFlwDir), with optional stream-cell outlet snapping and edge/missing-data completeness flags.
- `landcover`: categorical land-cover class counts, areas and coverage fractions per polygon.
- Composed catchments -> landcover examples (dominant class per nested gauge) and agent test task.
- Initial worker generated from the VGI starter template.

Targets: vgi-python 0.51 · VGI protocol 3.3 · Haybarn 2.0.0rc11 · vgi-lint-check 2.x (unpinned)
