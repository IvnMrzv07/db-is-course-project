"""Regenerate the source inventory and diagram index from the current source tree."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ('competition', 'content', 'analytics', 'search', 'identity', 'ingestion')


def tree_lines(folder: Path, indent: str = '') -> list[str]:
    lines = []
    for path in sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if path.name.startswith('__'):
            continue
        if path.is_dir():
            children = tree_lines(path, indent + '    ')
            if children:
                lines.append(indent + path.name + '/')
                lines.extend(children)
        elif path.suffix in ('.py', '.yaml'):
            lines.append(indent + path.name)
    return lines


def main():
    inventory = ['# Code Inventory', '',
                 'Generated from the current Python source. These are typed architecture stubs, not completed runtime implementations.', '']
    structure = ['# Python Service Structure', '',
                 'The following layouts reflect the source files now present, replacing the earlier proposed filename lists. Package initializer files are omitted for readability.', '',
                 'Domain code depends only on the standard library and its own domain. Application code uses local ports and DTOs plus versioned transport contracts. Controllers and consumers are inbound adapters; technology implementations are outbound adapters. Composition roots inject the adapters.', '',
                 '| Folder | Responsibility |', '| --- | --- |',
                 '| `domain/entities` and `domain/services` | Business data and pure rules. |',
                 '| `application/dtos` | Typed command and query boundary data. |',
                 '| `application/services/commands` | State-changing application operations. |',
                 '| `application/services/queries` | Visibility-aware reads and projections. |',
                 '| `application/repositories` | Local CRUD persistence protocols. |',
                 '| `application/ports` | Transactions, specialized queries, cache, projection, provider, and pacing interfaces. |',
                 '| `application/mappers` | Entity-to-DTO conversions. |',
                 '| `presentation/api/controllers` | Named HTTP adapter classes; FastAPI routes remain to be registered. |',
                 '| `presentation/messaging/consumers` | Inbound message handlers delegating to application services. |',
                 '| `infrastructure` | Database, provider, graph, search, cache, and broker adapter stubs. |',
                 '| `bootstrap.py` | Typed dependency composition, without opening connections. |', '',
                 'See [Skeleton guide](skeleton-guide.md) for scope and verification, [Code inventory](code-inventory.md) for class links, and [Diagrams](diagrams.md) for interactions.', '']
    for service in (*SERVICES, 'contracts'):
        folder = ROOT / (service + '_service' if service != 'contracts' else 'contracts')
        title = service.title() + (' service' if service != 'contracts' else '')
        structure += ['## '+title, '', '```text', folder.name + '/']
        structure += tree_lines(folder, '    ')
        structure += ['```', '']
        inventory += ['## '+title, '', '| Module | Declared classes |', '| --- | --- |']
        for path in sorted(folder.rglob('*.py')):
            if path.name == '__init__.py':
                continue
            classes = [n.name for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.ClassDef)]
            if not classes:
                continue
            relative = path.relative_to(ROOT).as_posix()
            inventory.append(f'| [{path.relative_to(folder).as_posix()}](../{relative}) | '+', '.join(f'`{c}`' for c in classes)+' |')
        inventory.append('')
    (ROOT/'docs/service-structure.md').write_text('\n'.join(structure),encoding='utf-8')
    (ROOT/'docs/code-inventory.md').write_text('\n'.join(inventory),encoding='utf-8')
    diagrams=['# Module and Class Diagrams', '',
              'The class diagrams reference classes in the current skeleton. Interface realization arrows represent nominal or structural Python protocol implementation. Method execution, HTTP route registration, database topology, and broker operation are planned, not deployed.', '',
              'Each diagram is also stored as an editable `.mmd` source. The diagrams select representative interactions rather than placing every DTO on one unreadable page; [Code inventory](code-inventory.md) lists the complete class set.', '']
    order=['modules', *[s+'-classes' for s in SERVICES], 'document-flow']
    for name in order:
        source=ROOT/'diagrams'/f'{name}.mmd'
        diagrams += ['## '+name.replace('-',' ').title(), '', f'[Editable Mermaid source](../diagrams/{name}.mmd)', '', '```mermaid', source.read_text(encoding='utf-8').rstrip(), '```', '']
        if name == 'modules':
            diagrams += ['The module overview flows from left to right. Each group keeps a service near its storage. Solid arrows show routing, storage access, and labeled broker traffic; dashed arrows show direct owner-API reads or enrichment submissions. The two Redis symbols are namespaces that may share one deployment. MongoDB represents three data shards plus separate configuration infrastructure.', '',
                         'Files include Kaggle and prepared corpora; provider APIs include PandaScore and optional Liquipedia. Elasticsearch includes corpus and telemetry indexes. All infrastructure remains planned. Class diagrams below show selected fields from the actual Python declarations; optional markers and some collection details are abbreviated for readability. The code inventory contains the full definitions.', '']
    (ROOT/'docs/diagrams.md').write_text('\n'.join(diagrams),encoding='utf-8')


if __name__=='__main__':
    main()
