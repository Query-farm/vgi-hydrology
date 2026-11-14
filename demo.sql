-- Offline acceptance demos. Run with: uv run --with duckdb==2.0.0 python scripts/run_demo.py
-- The runner loads VGI, attaches this worker, and installs Spatial for geometry joins.

-- Demo monitoring station on bundled synthetic data
SELECT station_id FROM hydrology.main.demo_input;

-- Upstream catchments on bundled synthetic data
SELECT station_id, cell_count, area_m2 FROM hydrology.main.catchments((SELECT * FROM hydrology.main.demo_input)) ORDER BY station_id;

-- Catchment land cover on bundled synthetic data
SELECT sum(area_m2), min(coverage_fraction) FROM hydrology.main.landcover((SELECT station_id, geometry_wkb FROM hydrology.main.catchments((SELECT * FROM hydrology.main.demo_input)) WHERE status='ok'));

-- Join upstream facilities to catchments
INSTALL spatial; LOAD spatial;
WITH basins AS (SELECT * FROM hydrology.main.catchments((SELECT * FROM hydrology.main.demo_input))),
facilities(facility_id, x, y) AS (VALUES ('upstream-plant', 500015.0, 4100055.0), ('outside-plant', 500095.0, 4100055.0))
SELECT b.station_id, f.facility_id, b.area_m2, b.boundary_limited
FROM basins b JOIN facilities f ON ST_Covers(ST_GeomFromWKB(b.geometry_wkb), ST_Point(f.x, f.y))
ORDER BY b.station_id, f.facility_id;
