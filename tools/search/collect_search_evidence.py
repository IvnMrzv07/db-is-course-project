"""Collect plan item 7 evidence from a running cs-sharded stand (through Nginx, like the UI).

    python tools/search/collect_search_evidence.py [--base http://127.0.0.1:8082] [--out docs/coursework/stages/search-summary]

Writes index-status.json, search-examples.json (full responses, trimmed hit lists) and timings.json
(median/p95 of repeated requests: Elasticsearch `took` and end-to-end latency through Nginx).
"""
import argparse
import json
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

EXAMPLES = [
    ('team_and_map_all_words', {'q': 'Vitality Mirage', 'mode': 'all'}),
    ('player_nickname', {'q': 's1mple', 'mode': 'all', 'document_type': 'map'}),
    ('tournament_phrase', {'q': 'IEM Katowice', 'mode': 'phrase', 'include_synthetic': 'false'}),
    ('typo_tolerant', {'q': 'Natus Vincere Inferrno', 'mode': 'fuzzy'}),
    ('any_word', {'q': 'FaZe Astralis', 'mode': 'any', 'corpus_scope': 'kaggle-cs'}),
    ('map_filter_kaggle_only', {'q': 'NAVI', 'map_name': 'Nuke', 'include_synthetic': 'false'}),
    ('synthetic_scope', {'q': 'Synthetic Team 039', 'corpus_scope': 'synthetic-cs', 'document_type': 'series'}),
    ('synthetic_excluded', {'q': 'Synthetic Team 039', 'include_synthetic': 'false'}),
    ('empty_result', {'q': 'qwxzvj nonexistent', 'mode': 'all'}),
    ('filters_only', {'q': '', 'corpus_scope': 'all', 'document_type': 'map', 'map_name': 'Ancient'}),
]


def call(base, path, params=None):
    url = base + path + ('?' + urllib.parse.urlencode(params) if params else '')
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            status, body = response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        status, body = exc.code, json.loads(exc.read() or b'null')
    return status, body, round((time.perf_counter() - started) * 1000, 1)


def trim(body):
    if isinstance(body, dict) and 'hits' in body:
        body = {**body, 'hits': [{k: v for k, v in hit.items() if k != 'metadata'} for hit in body['hits'][:5]]}
    return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:8082')
    parser.add_argument('--out', default='docs/coursework/stages/search-summary')
    parser.add_argument('--repeat', type=int, default=7)
    options = parser.parse_args()
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)

    status, body, _ = call(options.base, '/api/v1/search/status')
    (out / 'index-status.json').write_text(json.dumps({'http_status': status, **body}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    examples, timings = {}, {}
    for name, params in EXAMPLES:
        call(options.base, '/api/v1/search', params)  # warm-up
        took, wall, last = [], [], None
        for _ in range(options.repeat):
            code, result, elapsed = call(options.base, '/api/v1/search', params)
            took.append(result.get('took_ms') or 0)
            wall.append(elapsed)
            last = (code, result)
        examples[name] = {'request': params, 'http_status': last[0], 'response': trim(last[1])}
        timings[name] = {'status': last[1].get('status'), 'total': last[1].get('total'),
                         'es_took_ms_median': statistics.median(took), 'end_to_end_ms_median': statistics.median(wall),
                         'end_to_end_ms_max': max(wall), 'runs': options.repeat}
        print(f"{name:28} {timings[name]['status']:6} total={timings[name]['total']!s:>7} "
              f"es={timings[name]['es_took_ms_median']} ms e2e={timings[name]['end_to_end_ms_median']} ms")
    (out / 'search-examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'timings.json').write_text(json.dumps(timings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
