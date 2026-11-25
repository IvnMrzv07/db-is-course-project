"""Tables and charts from finished runs:  python tools/load/report.py artifacts/load/E1-ordered [more runs] --out DIR

Writes results.md (always) and PNG charts (when matplotlib from requirements-load.txt is installed).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.load.metrics import rolling

INK, MUTED, GRID = '#191919', '#666666', '#e6e6e6'
SERIES = ('#257de0', '#f47230', '#00b894')  # validated categorical order; a shard keeps its colour in every chart
# (column, title, scale) of the per-shard panels: one measure per panel, never two scales on one axis.
PANELS = (('cache_used_pct', 'Зайнято кешу, %', 1), ('cache_dirty_pct', 'Незаписані сторінки в кеші, %', 1),
          ('checkpoint_ms', 'Останній checkpoint, с', 1e-3), ('write_latency_ms', 'Затримка запису, мс', 1),
          ('pages_read_per_s', 'Читань сторінок із диска за секунду', 1), ('index_bytes', 'Індекси, ГБ', 1e-9))


def number(value) -> float | None:
    return float(value) if value not in ('', None) else None


def read_run(directory: Path) -> dict:
    summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    rows = {}
    for name in ('samples', 'shards'):
        path = directory / f'{name}.csv'
        rows[name] = list(csv.DictReader(path.open(encoding='utf-8'))) if path.exists() else []
    samples = [{'t': float(row['t']), 'phase': row['phase'], 'writing': int(row['writing']),
                'stored': number(row['stored']), 'docs_per_s': number(row['docs_per_s'])} for row in rows['samples']]
    return {'name': directory.name, 'summary': summary, 'samples': samples, 'shards': rows['shards']}


def cell(value, digits=0) -> str:
    return '—' if value is None else f'{value:,.{digits}f}'.replace(',', ' ').replace('.', ',')


def tables(runs: list[dict]) -> str:
    lines = ['# Результати навантажувальних прогонів', '', '## Швидкість', '',
             '| Прогін | Фаза | Тривалість, с | Документів | Медіана, док/с | Перша хвилина | Остання хвилина |',
             '|---|---|---:|---:|---:|---:|---:|']
    for run in runs:
        for phase in run['summary']['phases']:
            lines.append(f"| {run['name']} | {phase['phase']} | {cell(phase['seconds'])} | {cell(phase['documents'])} | "
                         f"{cell(phase['median'])} | {cell(phase['first_minute'])} | {cell(phase['last_minute'])} |")
    lines += ['', '## Сповільнення', '', 'Медіана за 60 с нижча за 80 % медіани хвилин 2–5 протягом щонайменше 2 хв.', '',
              '| Прогін | Базова, док/с | Початок, хв | Документів на цей момент |', '|---|---:|---:|---:|']
    for run in runs:
        found = run['summary']['slowdown']
        moment = found.get('started_at')
        lines.append(f"| {run['name']} | {cell(found.get('baseline'))} | {cell(moment / 60, 1) if moment is not None else 'немає'} | "
                     f"{cell(found.get('stored_at_start'))} |")
    if any(run['summary'].get('reads') for run in runs):
        lines += ['', '## Читання під час запису', '', '| Прогін | Запит | Запитів | Помилок | p50, мс | p95, мс | p99, мс |',
                  '|---|---|---:|---:|---:|---:|---:|']
        for run in runs:
            for path, value in (run['summary'].get('reads') or {}).items():
                lines.append(f"| {run['name']} | `{path}` | {cell(value['requests'])} | {cell(value['failed'])} | "
                             f"{cell(value['p50_ms'], 1)} | {cell(value['p95_ms'], 1)} | {cell(value['p99_ms'], 1)} |")
    lines += ['', '## Перевірка втрат', '', '| Прогін | Підтверджено | Знайдено | Втрачено | Помилка |', '|---|---:|---:|---:|---|']
    for run in runs:
        check = run['summary'].get('verify') or {}
        lines.append(f"| {run['name']} | {cell(check.get('confirmed'))} | {cell(check.get('found'))} | {cell(check.get('missing'))} | "
                     f"{run['summary'].get('error') or '—'} |")
    return '\n'.join(lines) + '\n'


def style(axis, title):
    axis.set_title(title, loc='left', fontsize=10, color=INK)
    axis.grid(axis='y', color=GRID, linewidth=.8)
    axis.set_axisbelow(True)
    for side in ('top', 'right', 'left'):
        axis.spines[side].set_visible(False)
    axis.spines['bottom'].set_color(GRID)
    axis.tick_params(colors=MUTED, labelsize=8, length=0)
    axis.set_ylim(bottom=0)


def speed_chart(plt, run: dict, target: Path):
    figure, axis = plt.subplots(figsize=(9, 3.6), dpi=150)
    written = [row for row in run['samples'] if row['docs_per_s'] is not None]
    axis.plot([row['t'] / 60 for row in written], [row['docs_per_s'] for row in written], color='#c9dcf5', linewidth=.8)
    smooth = rolling(run['samples'])
    axis.plot([moment / 60 for moment, _ in smooth], [value for _, value in smooth], color=SERIES[0], linewidth=2)
    started = run['summary']['slowdown'].get('started_at')
    if started is not None:
        axis.axvline(started / 60, color=MUTED, linewidth=1)
        axis.annotate('сповільнення', (started / 60, axis.get_ylim()[1]), xytext=(4, -10), textcoords='offset points', fontsize=8, color=MUTED)
    style(axis, f"{run['name']}: підтверджений запис, док/с (лінія — медіана за 60 с)")
    axis.set_xlabel('хвилини', fontsize=8, color=MUTED)
    figure.tight_layout()
    figure.savefig(target)
    plt.close(figure)


def shard_chart(plt, run: dict, target: Path):
    names = sorted({row['shard'] for row in run['shards']})
    figure, axes = plt.subplots(3, 2, figsize=(9, 7.5), dpi=150, sharex=True)
    for axis, (column, title, scale) in zip(axes.flat, PANELS):
        for name, color in zip(names, SERIES):
            points = [(float(row['t']) / 60, float(row[column]) * scale) for row in run['shards']
                      if row['shard'] == name and row.get(column) not in ('', None)]
            if points:
                axis.plot(*zip(*points), color=color, linewidth=1.5, label=name)
        style(axis, title)
    for axis in axes[-1]:
        axis.set_xlabel('хвилини', fontsize=8, color=MUTED)
    if len(names) > 1:
        handles, labels = axes.flat[0].get_legend_handles_labels()
        figure.legend(handles, labels, loc='upper right', ncols=len(names), frameon=False, fontsize=8, labelcolor=INK)
    figure.suptitle(run['name'], x=.01, ha='left', fontsize=11, color=INK)
    figure.tight_layout()
    figure.savefig(target)
    plt.close(figure)


def comparison_chart(plt, runs: list[dict], target: Path):
    bars = [(f"{run['name']} · {phase['phase']}", phase['median']) for run in runs for phase in run['summary']['phases']]
    figure, axis = plt.subplots(figsize=(9, .9 + .42 * len(bars)), dpi=150)
    axis.barh([name for name, _ in bars], [value for _, value in bars], color=SERIES[0], height=.5)
    for index, (_, value) in enumerate(bars):
        axis.annotate(cell(value), (value, index), xytext=(5, 0), textcoords='offset points', va='center', fontsize=8, color=INK)
    style(axis, 'Медіанна швидкість запису, док/с')
    axis.grid(axis='y', visible=False)
    axis.set_ylim(len(bars) - .5, -.5)
    axis.set_xlim(left=0, right=max([value for _, value in bars] or [1]) * 1.12)
    axis.xaxis.set_visible(False)
    axis.tick_params(axis='y', labelcolor=INK)
    figure.tight_layout()
    figure.savefig(target)
    plt.close(figure)


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('runs', type=Path, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    options = parser.parse_args(arguments)
    runs = [read_run(directory) for directory in options.runs]
    options.out.mkdir(parents=True, exist_ok=True)
    (options.out / 'results.md').write_text(tables(runs), encoding='utf-8')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('matplotlib is not installed (requirements-load.txt): tables only')
        return 0
    for run in runs:
        speed_chart(plt, run, options.out / f"{run['name']}-speed.png")
        if run['shards']:
            shard_chart(plt, run, options.out / f"{run['name']}-shards.png")
    comparison_chart(plt, runs, options.out / 'comparison.png')
    print(f'Report: {options.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
