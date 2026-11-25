# Load measurements

Questions answered by the scenarios in `scenarios/`:

| Scenario | Question |
|---|---|
| `E1-ordered`, `E1-random` | Does the write speed fall with time, when, and how do ordered IDs, indexes (`reset --lean-indexes`) and cache size change it? |
| `E2-pause`, `E2-restart`, `E2-purge` | After a slowdown: does a pause, a cold restart or deleting half of the data bring the speed back? |
| `E3-nodes` | One node against three (`--shards 1` with `WT_CACHE_GB=3` and `1`, `--shards 3` with `WT_CACHE_GB=1`) |

```sh
python tools/ops/cs_ops.py up
python tools/ops/cs_ops.py reset --yes                  # every run starts empty
python tools/load/host_probe.py artifacts/load/E1-host.csv &   # macOS: thermal state, load, free disk
docker compose -f deploy/docker-compose.sharded.yml --env-file .env run --rm loadtest \
    python tools/load/run.py tools/load/scenarios/E1-ordered.yaml --out /out/E1-ordered
python -m venv .venv-load && .venv-load/bin/pip install -r requirements-load.txt   # charts only
.venv-load/bin/python tools/load/report.py artifacts/load/E1-ordered artifacts/load/E1-random --out artifacts/load/report
```

For the one-shard stand use `python tools/ops/cs_ops.py --shards 1 up` and run the measurement with
`SHARDS=shard1 docker compose -p cs-single -f deploy/docker-compose.sharded.yml --env-file .env run --rm loadtest ...`.

- The speed is the change of the committed counters in MongoDB per second, not the broker rate.
- A slowdown means: the 60-second median stays below 80 % of the median of minutes 2–5 for at least two minutes.
- The job is cancelled at the end; runs without deletion finish with `verify` (exit code 1 on any loss).
- `restart_shards` uses the `shutdown` command and relies on `restart: unless-stopped`.
- One laptop shares its disk and CPU between all shards, and a fanless one throttles: read the results together with the host probe.
