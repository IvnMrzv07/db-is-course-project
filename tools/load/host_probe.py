"""Host-side log next to a run (macOS): thermal state, load and free disk.  python tools/load/host_probe.py out.csv

A fanless laptop throttles after minutes of full load, which looks like a slowing database. Containers cannot see
the host's thermal state, so this runs on the host. Stop with Ctrl+C.
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import time


def _output(*command) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ''


def thermal_pressure(output: str) -> int | None:
    """`com.apple.system.thermalpressurelevel`: 0 nominal, 1 moderate, 2 heavy, 3 trapping, 4 sleeping."""
    match = re.search(r'thermalpressurelevel\s+(\d+)', output)
    return int(match.group(1)) if match else None


def speed_limit(output: str) -> int | None:
    """CPU_Speed_Limit of `pmset -g therm` (Intel Macs only): 100 = no throttling."""
    match = re.search(r'CPU_Speed_Limit\s*=\s*(\d+)', output)
    return int(match.group(1)) if match else None


def main(path: str, interval: float = 5) -> None:
    started = time.time()
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as target:
        writer = csv.writer(target)
        writer.writerow(['t', 'thermal_pressure', 'cpu_speed_limit', 'load_1m', 'disk_free_gb'])
        while True:
            load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else None
            writer.writerow([round(time.time() - started, 1),
                             thermal_pressure(_output('notifyutil', '-g', 'com.apple.system.thermalpressurelevel')),
                             speed_limit(_output('pmset', '-g', 'therm')), load, round(shutil.disk_usage('.').free / 1e9, 2)])
            target.flush()
            time.sleep(interval)


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except KeyboardInterrupt:
        pass
