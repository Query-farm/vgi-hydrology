"""D8 catchment delineation and categorical upstream land-cover summaries."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

import numpy as np
import pyarrow as pa
import pyflwdir
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from rasterio.windows import Window, from_bounds
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from vgi import Arg
from vgi.arguments import TableInput
from vgi.catalog import Table
from vgi.catalog.constraints import constraint_record
from vgi.invocation import BindResponse
from vgi.table_function import (
    BindParams,
    OutputCollector,
    ProcessParams,
    TableFunctionGenerator,
    bind_fixed_schema,
    init_single_worker,
)
from vgi.table_in_out_function import TableInOutGenerator
from vgi_rpc import ArrowSerializableDataclass

from .raster_support import elevation, north_up, open_raster
from .support import (
    example,
    finite_parameters,
    geometry,
    identifier,
    metadata,
    metric_crs,
    numeric,
    require_columns,
    schema_of,
)

GIS_DESCRIPTION = (
    "Delineate DEM-derived upstream catchments for monitoring-station rows, then "
    "summarize categorical land cover "
    "and spatially join facilities with the returned WKB polygons. Flow uses PyFlwDir's"
    " depression-filled D8 network. "
    "Catchments reaching the DEM boundary or nodata are flagged as potentially incomplete. "
    "Projected metre DEMs and explicit input coordinate systems are required. This is "
    "drainage analysis, not a flood model."
)
INPUT = schema_of(
    [
        ("station_id", pa.string(), "Caller-owned station identity."),
        ("x", pa.float64(), "Station X in input_crs."),
        ("y", pa.float64(), "Station Y in input_crs."),
    ]
)
CATCHMENTS = schema_of(
    [
        ("station_id", pa.string(), "Input monitoring-station identity."),
        ("cell_count", pa.int64(), "Number of upstream DEM cells, including the outlet cell."),
        ("area_m2", pa.float64(), "Cell count multiplied by projected DEM cell area, square metres."),
        ("outlet_x", pa.float64(), "Selected outlet cell centre X in dem_crs."),
        ("outlet_y", pa.float64(), "Selected outlet cell centre Y in dem_crs."),
        (
            "snap_distance_m",
            pa.float64(),
            "Euclidean distance from the supplied station to the selected cell centre, metres.",
        ),
        (
            "boundary_limited",
            pa.bool_(),
            "True if the catchment reaches the DEM boundary or missing-data boundary; extent may be incomplete.",
        ),
        (
            "geometry_wkb",
            pa.binary(),
            "Upstream Polygon/MultiPolygon WKB in dem_crs; use ST_GeomFromWKB for spatial joins.",
        ),
        ("dem_crs", pa.string(), "Projected metre CRS for catchment geometry and outlet coordinates."),
        ("status", pa.string(), "ok, outside_dem, nodata, or no_stream_within_radius."),
    ]
)
LANDCOVER = schema_of(
    [
        ("station_id", pa.string(), "Caller-owned station identity."),
        ("class_code", pa.int64(), "Integer land-cover class; NULL if the polygon has no valid raster data."),
        ("pixel_count", pa.int64(), "Valid cell centres inside the catchment for this class."),
        (
            "area_m2",
            pa.float64(),
            "Class pixel count times source raster cell area, square metres; pixel-centre approximation.",
        ),
        ("fraction_of_valid", pa.float64(), "This class's share of valid observed catchment pixels."),
        (
            "coverage_fraction",
            pa.float64(),
            "Fraction of all catchment grid centres with valid land-cover observations.",
        ),
        ("status", pa.string(), "ok or no_data; unknown land cover is not classified as a real category."),
    ]
)


def load_flow(path: str, max_cells: int) -> tuple[Any, Any, Any, Any]:
    """Build one bounded D8 flow network from a north-up projected DEM."""
    with open_raster(path) as ds:
        crs = metric_crs(ds.crs)
        if ds.width * ds.height > max_cells:
            raise ValueError(f"DEM exceeds max_cells={max_cells}; provide a bounded drainage region")
        transform = ds.transform
        if transform.a <= 0 or transform.e >= 0 or transform.b != 0 or transform.d != 0:
            raise ValueError("DEM must be a north-up grid")
        data = elevation(ds)
    valid = np.isfinite(data)
    if not valid.any():
        raise ValueError("DEM has no valid elevations")
    filled = np.where(valid, data, -9999.0)
    if np.any(data[valid] == -9999.0):
        raise ValueError("Valid elevation -9999 collides with the routing nodata sentinel")
    flow = pyflwdir.from_dem(filled, nodata=-9999.0, transform=transform, latlon=False)
    return flow, valid, transform, crs


def delineate(row: dict[str, Any], network: tuple[Any, Any, Any, Any], args: Any) -> dict[str, Any]:
    """Delineate each outlet independently so nested catchments retain their full upstream areas."""
    flow, valid, transform, crs = network
    key = identifier(row, "station_id")
    x, y = numeric(row, "x", "y")
    x, y = Transformer.from_crs(args.input_crs, crs, always_xy=True).transform(x, y)
    if not np.isfinite([x, y]).all():
        raise ValueError("Station coordinates cannot be transformed to the DEM CRS")
    col, r = math.floor((x - transform.c) / transform.a), math.floor((y - transform.f) / transform.e)
    result = {
        "station_id": key,
        "cell_count": 0,
        "area_m2": None,
        "outlet_x": None,
        "outlet_y": None,
        "snap_distance_m": None,
        "boundary_limited": None,
        "geometry_wkb": None,
        "dem_crs": crs.to_string(),
        "status": "outside_dem",
    }
    if not (0 <= r < valid.shape[0] and 0 <= col < valid.shape[1]):
        return result
    if not valid[r, col]:
        return {**result, "status": "nodata"}
    if args.snap_radius_m > 0:
        area = flow.upstream_area(unit="m2")
        rr, cc = np.where(valid & (area >= args.min_stream_area_m2))
        xs = transform.c + (cc + 0.5) * transform.a
        ys = transform.f + (rr + 0.5) * transform.e
        distance = np.hypot(xs - x, ys - y)
        if not len(distance) or float(distance.min()) > args.snap_radius_m:
            return {**result, "status": "no_stream_within_radius"}
        selected = int(np.argmin(distance))
        r, col = int(rr[selected]), int(cc[selected])
    idx = r * valid.shape[1] + col
    basin = flow.basins(idxs=np.array([idx], dtype=np.int64)) > 0
    count = int(basin.sum())
    outlines = [shape(g) for g, value in shapes(basin.astype("uint8"), mask=basin, transform=transform) if value == 1]
    boundary = bool(basin[0].any() or basin[-1].any() or basin[:, 0].any() or basin[:, -1].any())
    for dr, dc in [(r, c) for r in (-1, 0, 1) for c in (-1, 0, 1) if r or c]:
        adjacent = np.roll(~valid, (dr, dc), axis=(0, 1))
        boundary = boundary or bool((basin & adjacent).any())
    ox, oy = transform.c + (col + 0.5) * transform.a, transform.f + (r + 0.5) * transform.e
    result.update(
        cell_count=count,
        area_m2=count * abs(transform.a * transform.e),
        outlet_x=ox,
        outlet_y=oy,
        snap_distance_m=math.hypot(ox - x, oy - y),
        boundary_limited=boundary,
        geometry_wkb=unary_union(outlines).wkb,
        status="ok",
    )
    return result


def summarize(row: dict[str, Any], ds: Any, args: Any) -> list[dict[str, Any]]:
    """Count categorical raster pixels within a catchment without interpolating class codes."""
    key = identifier(row, "station_id")
    crs = metric_crs(ds.crs)
    if ds.transform.b != 0 or ds.transform.d != 0 or ds.transform.a <= 0 or ds.transform.e >= 0:
        raise ValueError("Land cover must be a north-up grid")
    poly = geometry(row["geometry_wkb"], args.geometry_crs, crs)
    north_up(ds)
    if ds.scales[0] != 1 or ds.offsets[0] != 0:
        raise ValueError("Categorical land cover must have identity scale/offset metadata")
    raw = from_bounds(*poly.bounds, transform=ds.transform)
    col, r = math.floor(raw.col_off), math.floor(raw.row_off)
    width, height = math.ceil(raw.col_off + raw.width) - col, math.ceil(raw.row_off + raw.height) - r
    if width * height > args.max_pixels:
        raise ValueError("Catchment land-cover window exceeds max_pixels")
    window = Window(col, r, width, height)
    data = ds.read(1, window=window, boundless=True, masked=True)
    inside = geometry_mask([mapping(poly)], (height, width), ds.window_transform(window), invert=True)
    usable = inside & ~np.ma.getmaskarray(data) & np.isfinite(data.data)
    values = data.data[usable]
    total, observed = int(inside.sum()), int(usable.sum())
    coverage = observed / total if total else 0.0
    if not observed:
        return [
            {
                "station_id": key,
                "class_code": None,
                "pixel_count": 0,
                "area_m2": 0.0,
                "fraction_of_valid": None,
                "coverage_fraction": coverage,
                "status": "no_data",
            }
        ]
    if not np.equal(values, np.floor(values)).all() or np.any(values < -(2**63)) or np.any(values >= 2**63):
        raise ValueError("Land cover must contain categorical codes representable as signed 64-bit integers")
    codes, counts = np.unique(values.astype("int64"), return_counts=True)
    return [
        {
            "station_id": key,
            "class_code": int(code),
            "pixel_count": int(count),
            "area_m2": float(count) * abs(ds.transform.a * ds.transform.e),
            "fraction_of_valid": float(count) / observed,
            "coverage_fraction": coverage,
            "status": "ok",
        }
        for code, count in zip(codes, counts, strict=True)
    ]


@dataclass(slots=True, frozen=True, kw_only=True)
class CatchmentArgs:
    """Monitoring stations and drainage-model controls."""

    data: Annotated[
        TableInput,
        Arg(
            0,
            doc=(
                "Rows containing station_id, x and y. Every station is delineated independently, "
                "including nested stations."
            ),
        ),
    ]
    dem: Annotated[
        str,
        Arg(
            "dem",
            default="demo://basin.tif",
            doc="North-up projected-metre DEM GeoTIFF path or URL; vertical elevations must use metres.",
        ),
    ]
    input_crs: Annotated[
        str, Arg("input_crs", default="EPSG:32618", doc="Explicit CRS for station coordinates, always XY order.")
    ]
    max_cells: Annotated[
        int, Arg("max_cells", default=2000000, ge=4, doc="Maximum DEM cells for in-memory D8 routing.")
    ]
    snap_radius_m: Annotated[
        float,
        Arg(
            "snap_radius_m",
            default=0.0,
            ge=0,
            doc=(
                "Optional Euclidean snapping radius to cells meeting min_stream_area_m2; zero uses the containing cell."
            ),
        ),
    ]
    min_stream_area_m2: Annotated[
        float,
        Arg(
            "min_stream_area_m2",
            default=0.0,
            ge=0,
            doc="Minimum upstream drainage area for candidate snap cells, square metres.",
        ),
    ]


@dataclass(slots=True, frozen=True, kw_only=True)
class LandcoverArgs:
    """Catchment polygons and a categorical land-cover raster."""

    data: Annotated[
        TableInput,
        Arg(
            0, doc=("Rows containing station_id and valid polygon geometry_wkb, such as successful catchments results.")
        ),
    ]
    raster: Annotated[
        str,
        Arg(
            "raster",
            default="demo://landcover.tif",
            doc="Categorical land-cover GeoTIFF with projected metre coordinates and declared nodata.",
        ),
    ]
    geometry_crs: Annotated[
        str, Arg("geometry_crs", default="EPSG:32618", doc="CRS of input catchment WKB; use the catchment's dem_crs.")
    ]
    max_pixels: Annotated[
        int,
        Arg("max_pixels", default=2000000, ge=1, doc="Maximum cells in one catchment's land-cover bounding window."),
    ]


CATCH_SQL = (
    "SELECT station_id, cell_count, area_m2 FROM hydrology.main.catchments((SELECT * "
    "FROM hydrology.main.demo_input)) ORDER BY station_id"
)
LAND_SQL = (
    "SELECT sum(area_m2), min(coverage_fraction) FROM hydrology.main.landcover((SELECT "
    "station_id, geometry_wkb FROM hydrology.main.catchments((SELECT * FROM "
    "hydrology.main.demo_input)) WHERE status='ok'))"
)
# Composed: delineate several gauges, feed the polygons to landcover, and join the class
# rows back to each catchment to pick the class covering the most upstream area.
DOMINANT_SQL = (
    "WITH basins AS (SELECT station_id, area_m2, geometry_wkb FROM hydrology.main.catchments(("
    "SELECT * FROM (VALUES ('west', 500015.0, 4100035.0), ('mid', 500035.0, 4100035.0), "
    "('east', 500055.0, 4100035.0), ('outlet', 500035.0, 4100005.0)) AS gauges(station_id, x, y))) "
    "WHERE status = 'ok') "
    "SELECT b.station_id, b.area_m2, arg_max(l.class_code, l.area_m2) AS dominant_class, "
    "max(l.fraction_of_valid) AS dominant_share "
    "FROM basins AS b JOIN hydrology.main.landcover((SELECT station_id, geometry_wkb FROM basins)) AS l "
    "ON l.station_id = b.station_id GROUP BY b.station_id, b.area_m2 ORDER BY b.station_id"
)
DOMINANT_TEXT = (
    "Dominant upstream land-cover class for four gauges on the synthetic valley: the two "
    "single-cell side gauges are pure class 10 (west) and class 20 (east), while the nested "
    "mid-valley gauge and the outlet are both mostly class 20"
)
DOMINANT_ROWS: list[list[Any]] = [
    ["east", 200.0, 20, 1.0],
    ["mid", 1600.0, 20, 0.625],
    ["outlet", 4900.0, 20, 0.5714285714285714],
    ["west", 200.0, 10, 1.0],
]
# Composed: add an upstream gauge to demo_input, delineate both nested catchments, summarize
# each one's land cover, and subtract per class to get the area draining only to the outlet.
INTERVENING_SQL = (
    "WITH gauges AS (SELECT station_id, x, y FROM hydrology.main.demo_input "
    "UNION ALL SELECT 'mid', 500035.0, 4100035.0), "
    "cover AS (SELECT station_id, class_code, area_m2 FROM hydrology.main.landcover(("
    "SELECT station_id, geometry_wkb FROM hydrology.main.catchments((SELECT * FROM gauges)) "
    "WHERE status = 'ok'))) "
    "SELECT class_code, sum(area_m2) FILTER (WHERE station_id = 'outlet') AS outlet_area_m2, "
    "sum(area_m2) FILTER (WHERE station_id = 'mid') AS upstream_gauge_area_m2, "
    "outlet_area_m2 - upstream_gauge_area_m2 AS intervening_area_m2 "
    "FROM cover GROUP BY class_code ORDER BY class_code"
)
INTERVENING_TEXT = (
    "Land cover of the intervening drainage between a mid-valley gauge and the demo outlet: "
    "per class, outlet catchment area minus the nested upstream gauge's catchment area "
    "(1,500 m2 of class 10 and 1,800 m2 of class 20)"
)
INTERVENING_ROWS: list[list[Any]] = [[10, 2100.0, 600.0, 1500.0], [20, 2800.0, 1000.0, 1800.0]]


class Catchments(TableInOutGenerator[CatchmentArgs]):
    """Return full upstream basins for each station."""

    class Meta:
        """Catchment algorithm and example."""

        name = "catchments"
        description = "Delineate upstream D8 catchments for monitoring stations"
        tags = metadata(
            "Upstream catchments",
            GIS_DESCRIPTION
            + (
                " The model fills depressions to spill points and routes one D8 downstream link per"
                " cell. Boundary-limited catchments must not be treated as globally complete. "
                "Null/invalid station coordinates fail; outside and nodata stations return explicit"
                " status rows."
            ),
            CATCHMENTS,
            CATCH_SQL,
            [["outlet", 49, 4900.0]],
            [(DOMINANT_TEXT, DOMINANT_SQL, DOMINANT_ROWS)],
        )
        examples = example(CATCH_SQL, "Delineate the known synthetic valley") + example(DOMINANT_SQL, DOMINANT_TEXT)

    @classmethod
    def on_bind(cls, params: BindParams[CatchmentArgs]) -> BindResponse:
        """Require station IDs and coordinates."""
        finite_parameters(params.args)
        require_columns(params.bind_call.input_schema, ("station_id", "x", "y"))
        return BindResponse(output_schema=CATCHMENTS)

    @classmethod
    def process(
        cls, params: ProcessParams[CatchmentArgs], state: None, batch: pa.RecordBatch, out: OutputCollector
    ) -> None:
        """Reuse one flow network for the whole station batch."""
        network = load_flow(params.args.dem, params.args.max_cells)
        out.emit(
            pa.RecordBatch.from_pylist(
                [delineate(row, network, params.args) for row in batch.to_pylist()], schema=params.output_schema
            )
        )


class Landcover(TableInOutGenerator[LandcoverArgs]):
    """Return one area/share row per observed catchment land-cover class."""

    class Meta:
        """Land-cover semantics and validation example."""

        name = "landcover"
        description = "Summarize categorical land cover inside upstream catchment polygons"
        tags = metadata(
            "Catchment land cover",
            "Count categorical raster pixel centres within catchment polygons. Returns class "
            "codes, area in square metres, class share of valid pixels, and observed coverage "
            "including out-of-raster gaps. Never averages or interpolates class codes. Supply "
            "geometry_crs matching the catchment geometry. Join catchment WKB to facility "
            "points separately with ST_Covers(ST_GeomFromWKB(geometry_wkb), facility_geom).",
            LANDCOVER,
            LAND_SQL,
            [[4900.0, 1.0]],
            [(INTERVENING_TEXT, INTERVENING_SQL, INTERVENING_ROWS)],
        )
        examples = example(LAND_SQL, "Confirm the entire synthetic upstream area has classified land cover") + example(
            INTERVENING_SQL, INTERVENING_TEXT
        )

    @classmethod
    def on_bind(cls, params: BindParams[LandcoverArgs]) -> BindResponse:
        """Require the catchment identity and geometry."""
        finite_parameters(params.args)
        require_columns(params.bind_call.input_schema, ("station_id", "geometry_wkb"))
        return BindResponse(output_schema=LANDCOVER)

    @classmethod
    def process(
        cls, params: ProcessParams[LandcoverArgs], state: None, batch: pa.RecordBatch, out: OutputCollector
    ) -> None:
        """Share one raster handle across every catchment in the input batch."""
        with open_raster(params.args.raster) as ds:
            rows = [item for row in batch.to_pylist() for item in summarize(row, ds, params.args)]
        out.emit(pa.RecordBatch.from_pylist(rows, schema=params.output_schema))


@dataclass(slots=True, frozen=True, kw_only=True)
class DemoArgs:
    """No arguments: select the bundled monitoring station."""


@dataclass(kw_only=True)
class Cursor(ArrowSerializableDataclass):
    """Demo emission flag."""

    done: bool = False


DEMO_SQL = "SELECT station_id FROM hydrology.main.demo_input"


@init_single_worker
@bind_fixed_schema
class DemoInput(TableFunctionGenerator[DemoArgs, Cursor]):
    """Return the outlet of a known seven-by-seven-cell synthetic valley."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = INPUT

    class Meta:
        """Synthetic outlet metadata."""

        name = "demo_input"
        description = "Synthetic monitoring station at the bundled valley outlet"
        tags = metadata(
            "Demo monitoring station",
            "One station in EPSG:32618 at the outlet of demo://basin.tif. The synthetic DEM has"
            " 49 cells of 100 square metres each. A matching landcover.tif supports area "
            "summaries without network access.",
            INPUT,
            DEMO_SQL,
            [["outlet"]],
        )
        examples = example(DEMO_SQL, "Identify the synthetic outlet")

    @classmethod
    def initial_state(cls, params: ProcessParams[DemoArgs]) -> Cursor:
        """Start before the demo row."""
        return Cursor()

    @classmethod
    def process(cls, params: ProcessParams[DemoArgs], state: Cursor, out: OutputCollector) -> None:
        """Emit the station once."""
        if state.done:
            out.finish()
            return
        out.emit(
            pa.RecordBatch.from_pylist(
                [{"station_id": "outlet", "x": 500035.0, "y": 4100005.0}], schema=params.output_schema
            )
        )
        state.done = True


GIS_FUNCTIONS: list[type[Any]] = [DemoInput, Catchments, Landcover]

GIS_TABLES = [
    Table(
        name="demo_input",
        function=DemoInput,
        comment=DemoInput.Meta.description,
        constraints=(
            constraint_record(
                ["main"],
                "demo_input",
                "id_not_null",
                "NOT_NULL",
                [["station_id"]],
                enforcement="ENFORCED",
                validation="ALL_ROWS",
            ),
            constraint_record(
                ["main"],
                "demo_input",
                "demo_pk",
                "PRIMARY_KEY",
                [["station_id"]],
                enforcement="ENFORCED",
                validation="ALL_ROWS",
            ),
        ),
        tags={
            **DemoInput.Meta.tags,
            "domain": "geospatial",
            "vgi.example_queries": json.dumps(
                [{"description": ex.description, "sql": ex.sql} for ex in DemoInput.Meta.examples]
            ),
        },
        column_comments={f.name: (f.metadata or {}).get(b"comment", b"").decode() for f in DemoInput.FIXED_SCHEMA},
    )
]
