# Changelog

## 0.1.0 (2026-11-14)

First release.

- `catchments`: D8 upstream catchment delineation from a projected DEM (PyFlwDir), with optional stream-cell outlet snapping and edge/missing-data completeness flags.
- `landcover`: categorical land-cover class counts, areas and coverage fractions per polygon.
- Composed catchments -> landcover examples (dominant class per nested gauge) and agent test task.
- Initial worker generated from the VGI starter template.

Targets: vgi-python 0.51 · VGI protocol 3.3 · Haybarn 2.0.0rc11 · vgi-lint-check 2.x (unpinned)
