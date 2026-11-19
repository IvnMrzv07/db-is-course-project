"""Index maintenance: `python -m search_service.manage ensure|recreate|status [--wait-count N --timeout S]`.

`recreate` drops and recreates the versioned index (empty); refill it with `python -m content_service.reindex`.
`status --wait-count N` polls until the index holds N documents (used to time the backfill).
"""
import argparse
import asyncio
import json
import time

from search_service.application.ports.document_index import SearchBackendUnavailable
from search_service.runtime import build_index


async def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('ensure', 'recreate', 'status'))
    parser.add_argument('--wait-count', type=int)
    parser.add_argument('--timeout', type=float, default=900)
    options = parser.parse_args(arguments)
    index = build_index()
    try:
        if options.command == 'ensure':
            result = await index.ensure_index()
        elif options.command == 'recreate':
            result = await index.recreate_index()
        else:
            started = time.perf_counter()
            while True:
                try:
                    await index._request('POST', '/cs-documents/_refresh')
                    result = await index.status()
                except SearchBackendUnavailable as exc:
                    result = {'status': 'degraded', 'detail': str(exc)}
                if options.wait_count is None or result.get('documents') == options.wait_count \
                        or time.perf_counter() - started > options.timeout:
                    break
                await asyncio.sleep(1)
            result['waited_seconds'] = round(time.perf_counter() - started, 1)
    finally:
        await index.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    asyncio.run(main())
