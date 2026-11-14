# Production operation

The supported runtime is a trusted SQL client querying one local worker or one HTTP worker instance. The analyses, assumptions and NULL/status semantics are described in [README.md](README.md). Python 3.13 and 3.14 unit tests are exercised; runtime dependencies are resolved in [uv.lock](uv.lock). Keep the starter VGI SDK compatibility range intact when updating dependencies.

## Release gates

```sh
uv sync --locked
make release-check
make verify-container
uv run --with duckdb==2.0.0 python scripts/run_demo.py --verify --output validation/stock-duckdb.json
```

`release-check` includes formatting, Ruff, strict mypy, pydoclint, unit tests, Haybarn SQL tests over stdio/launch/HTTP, executed VGI metadata examples and stock DuckDB 2.0.0 assertions. It then builds an sdist, builds the wheel from that archive, installs it with locked runtime dependencies in a fresh environment, and runs the shipped SQL manifest outside the source checkout. Artifacts are in `dist/`; SHA-256 hashes and executed queries are in validation/packaged.json (`validation/packaged.json`, generated locally).

`verify-container` builds the image, starts it as UID 10001 with a read-only root filesystem, two CPUs and a 2 GiB memory limit, runs the complete stock DuckDB manifest over HTTP, and removes its temporary container. Evidence is in validation/container.json (`validation/container.json`, generated locally). The image remains available as `vgi-hydrology-worker:production-check`. It uses the locked runtime dependencies and the native libraries needed by the scientific wheels.

Current local evidence: full gates (`validation/production-check.log`, generated locally), stock SQL (`validation/stock-duckdb.json`, generated locally), Python 3.14 units (`validation/python314.log`, generated locally). Local validation covers macOS ARM64 and Linux ARM64 containers. CI additionally defines Ubuntu/Windows SQL and installed-package jobs; those hosted CI runs have not been executed locally. No public release or deployment is created by these checks.

## Serve

For a local SQL client, use the tested absolute executable path in the README's `ATTACH`. For HTTP, this reproduces the checked runtime layout:

```sh
docker build -t vgi-hydrology-worker:local .
docker run --rm --name vgi-hydrology-worker-local \
  --publish 127.0.0.1:8000:8000 --read-only --memory 2g --cpus 2 \
  --cap-drop ALL --security-opt no-new-privileges \
  --tmpfs /tmp:rw,nosuid,size=256m,mode=1777 \
  --tmpfs /home/worker/.cache:rw,nosuid,size=256m,mode=1777 \
  --tmpfs /var/lib/vgi:rw,nosuid,size=1g,mode=0700,uid=10001,gid=10001 \
  vgi-hydrology-worker:local
```

Mount source datasets read-only when needed, for example `--mount type=bind,src=/absolute/datasets,dst=/data,readonly`; SQL paths then refer to `/data`. The process needs writable temporary/cache/state directories even with read-only source data. `GET /health` checks process availability; the SQL verification checks behavior. Diagnostics go to stderr as JSON; stdout is reserved for Arrow in stdio mode. `PORT` defaults to 8000 and `HTTP_THREADS` to 2.

After installing/loading VGI as in the README, the HTTP attachment is:

```sql
INSTALL httpfs;
LOAD httpfs;
ATTACH 'hydrology' (TYPE vgi, LOCATION 'http://127.0.0.1:8000');
```

The HTTP listener itself is unauthenticated. Keep it on a private interface or behind an authenticated TLS proxy. SQL callers control dataset paths and, where supported, remote URLs, so grant access only to trusted clients and mount only the intended datasets. The sample container binds localhost. Replicas require a deliberately configured shared VGI state backend; independent ephemeral state directories do not support requests moving between replicas. Restarting the sample container discards in-flight query state. Bound concurrent analyses in the service/proxy and size RAM/state storage for your data; the demo's 2 GiB limit is a verified fixture configuration, not a maximum-scale capacity guarantee.

## Resource and data contract

The DEM is limited to 2,000,000 cells; a land-cover bounding window to 2,000,000 cells. DEM scale/offset metadata is honored; declared non-metre elevation units are rejected. Land cover must contain unscaled categorical values representable as signed 64-bit integers. Boundary flags include diagonal missing-data neighbors. Supply an extent large enough to contain the upstream basin.

All geometry WKB inputs are capped at 16 MiB and identifiers at 4,096 UTF-8 bytes. Nonfinite numeric parameters and invalid geometries/coordinates fail explicitly. Exceeded limits fail instead of truncating results. Query failures are tested followed by valid queries to check recovery. Raising a limit does not reserve memory; start with smaller tiled jobs and measure on representative data.

Keep input source versions, CRS, vertical units/datum, query arguments and output statuses with results. Geographic coordinates use X/Y order. Missing observations remain NULL or have explicit status/coverage fields. Fixture accuracy is established against known answers; suitability of external DEMs, classifications, positioning and sensor metadata remains dataset-specific. The optional agent-driven `make lint-ai` evaluation is not part of these completed gates.

## Public source publication

The source repository is https://github.com/Query-farm/vgi-hydrology. Local validation reports and logs are ignored rather than shipped as release inputs. Image publishing is manual-only. The 2026-11-14 recovery reruns the source and installed-package gates; it does not deploy a service or rerun the historical container checks.
