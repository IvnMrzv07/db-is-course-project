"""Refresh representative diagram fields from the declared Python classes."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXTRA = {
    'competition': {'Player': ('MatchLineup', 'player_ids'), 'Team': ('Match', 'team IDs'), 'Tournament': ('Match', 'tournament_id')},
    'content': {'Article': ('ArticleRepository', 'stores'), 'ArticleDTO': ('ArticleQueryService', 'returns'), 'CorpusStatisticsDTO': ('CorpusStatisticsQueryService', 'returns')},
    'analytics': {'ComparisonQuery': ('ComparisonService', 'input'), 'TeamComparisonDTO': ('ComparisonService', 'returns'), 'RelationshipDTO': ('RelationshipService', 'returns')},
    'identity': {'User': ('UserRepository', 'stores'), 'Bookmark': ('BookmarkRepository', 'stores'), 'RegistrationDTO': ('AccountCommandService', 'input')},
    'ingestion': {'ReplayJob': ('ReplayJobRepository', 'stores'), 'StartReplayDTO': ('ReplayCommandService', 'input'), 'JobProgressDTO': ('ImportService', 'returns')},
    'search': {'SearchHitDTO': ('SearchResultDTO', 'hits'), 'SearchHistoryDTO': ('SearchHistory', 'records')},
}


def main():
    for service, additions in EXTRA.items():
        classes = {}
        for path in (ROOT / f'{service}_service').rglob('*.py'):
            for node in ast.parse(path.read_text(encoding='utf-8')).body:
                if isinstance(node, ast.ClassDef):
                    classes[node.name] = node
        path = ROOT / 'diagrams' / f'{service}-classes.mmd'
        text = path.read_text(encoding='utf-8')
        for name, (owner, label) in additions.items():
            if not re.search(r'\bclass '+name+r'\b', text):
                text += f'    class {name}\n    {owner} --> {name} : {label}\n'

        def expand(match):
            name = match.group(1)
            node = classes.get(name)
            if node is None:
                return match.group(0)
            fields = []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    annotation = ast.unparse(item.annotation).replace(' | None', '')
                    if annotation.startswith(('tuple[', 'list[', 'dict[')):
                        annotation = annotation.split('[', 1)[0]
                    fields.append(f'        {annotation} {item.target.id}')
            if not fields:
                init = next((n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == '__init__'), None)
                if init:
                    for arg in init.args.args + init.args.kwonlyargs:
                        if arg.arg != 'self' and arg.annotation:
                            fields.append(f'        {ast.unparse(arg.annotation)} {arg.arg}')
            old = match.group(2) or ''
            interface = '<<interface>>' in old
            body = (['        <<interface>>'] if interface else []) + fields[:5]
            old_methods = [line for line in old.splitlines() if '(' in line]
            if old_methods:
                body += old_methods
            elif not fields:
                for method in [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith('_')][:2]:
                    args = ', '.join(a.arg for a in method.args.args if a.arg != 'self')
                    body.append(f'        {method.name}({args})')
            if not body:
                return match.group(0)
            return f'    class {name} {{\n' + '\n'.join(body) + '\n    }'

        text = re.sub(r'^    class (\w+)(?: \{\n(.*?)\n    \})?$', expand, text, flags=re.M | re.S)
        path.write_text(text,encoding='utf-8')


if __name__ == '__main__':
    main()
