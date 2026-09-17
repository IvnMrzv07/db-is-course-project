"""Architecture checks runnable with unittest or pytest, without third-party drivers."""
from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import re
import sys
import unittest
from pathlib import Path
from typing import get_type_hints
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ('competition', 'content', 'analytics', 'search', 'identity', 'ingestion')


def source_files():
    for name in (*[s + '_service' for s in SERVICES], 'contracts'):
        yield from (ROOT / name).rglob('*.py')


class ArchitectureTests(unittest.TestCase):
    def test_all_modules_import_and_annotations_resolve(self):
        """Catch missing imports and unresolved DTO/port type references."""
        for path in source_files():
            module_name = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
            with self.subTest(module=module_name):
                module = importlib.import_module(module_name)
                for _, cls in inspect.getmembers(module, inspect.isclass):
                    if cls.__module__ != module_name:
                        continue
                    get_type_hints(cls)
                    for _, member in inspect.getmembers(cls, inspect.isfunction):
                        if member.__module__ == module_name:
                            get_type_hints(member)

    def test_inward_dependencies_and_no_cross_service_imports(self):
        """Domain cannot see outer layers; application cannot see adapters."""
        for path in source_files():
            relative = path.relative_to(ROOT)
            root = relative.parts[0]
            layer = relative.parts[1] if len(relative.parts) > 2 else ''
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                imports = []
                if isinstance(node, ast.Import):
                    imports = [entry.name for entry in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        prefix = list(relative.parts[:-1])
                        prefix = prefix[:len(prefix) - node.level + 1]
                        imports = ['.'.join(prefix + ([node.module] if node.module else []))]
                    else:
                        imports = [node.module or '']
                for target in imports:
                    with self.subTest(path=str(relative), target=target):
                        other = target.split('.')[0]
                        self.assertFalse(other.endswith('_service') and other != root,
                                         'Use contracts or client ports, not another service implementation')
                        if layer == 'domain':
                            self.assertIn(other, sys.stdlib_module_names | {root})
                            self.assertFalse(any(x in target.split('.') for x in
                                                 ('application', 'presentation', 'infrastructure', 'contracts')))
                        if layer == 'application':
                            self.assertIn(other, sys.stdlib_module_names | {root, 'contracts'})
                            self.assertFalse(any(x in target.split('.') for x in ('presentation', 'infrastructure')))

    def test_every_composition_root_builds_without_external_services(self):
        for service in SERVICES:
            with self.subTest(service=service):
                bootstrap = importlib.import_module(service + '_service.bootstrap')
                settings = importlib.import_module(service + '_service.settings').Settings
                container = bootstrap.build_container(settings(service_name=service))
                self.assertTrue(dataclasses.is_dataclass(container))
                self.assertTrue(dataclasses.fields(container))
                for field in dataclasses.fields(container):
                    self.assertIsNotNone(getattr(container, field.name))

    def test_cqrs_is_present_in_every_service(self):
        for service in SERVICES:
            for group in ('commands', 'queries'):
                folder = ROOT / (service + '_service') / 'application' / 'services' / group
                self.assertTrue(any(p.name != '__init__.py' for p in folder.glob('*.py')))

    def test_public_account_dto_excludes_secrets(self):
        from identity_service.application.dtos.account_dto import AccountDTO
        names = {field.name for field in dataclasses.fields(AccountDTO)}
        self.assertTrue({'id', 'email', 'display_name'} <= names)
        self.assertFalse({'password', 'password_hash', 'opaque_credential'} & names)

    def test_request_mapper_gets_actor_from_trusted_context(self):
        from competition_service.presentation.api.schemas.player_request import PlayerRequest
        from competition_service.presentation.api.mappers.player_api_mapper import PlayerAPIMapper
        actor_id = uuid4()
        request = PlayerRequest(nickname='example', real_name=None, country_code=None, role=None)
        command = PlayerAPIMapper.to_command(request, actor_id=actor_id, idempotency_key='request-1')
        self.assertEqual(command.actor_id, actor_id)
        self.assertEqual(command.nickname, request.nickname)
        self.assertNotIn('actor_id', {field.name for field in dataclasses.fields(PlayerRequest)})

    def test_class_diagrams_reference_declared_classes(self):
        declared = set()
        for path in source_files():
            declared.update(n.name for n in ast.parse(path.read_text(encoding='utf-8')).body
                            if isinstance(n, ast.ClassDef))
        for path in (ROOT / 'diagrams').glob('*-classes.mmd'):
            text = path.read_text(encoding='utf-8')
            names = re.findall(r'^\s*class\s+(\w+)', text, flags=re.MULTILINE)
            with self.subTest(diagram=path.name):
                self.assertTrue(names)
                self.assertTrue(set(names) <= declared, set(names) - declared)

    def test_structural_adapters_match_port_signatures(self):
        pairs = [
            ('analytics', 'statistics_reader', 'StatisticsReader', 'database', 'PostgresStatisticsReader'),
            ('analytics', 'comparison_cache', 'ComparisonCache', 'cache', 'RedisComparisonCache'),
            ('analytics', 'relationship_reader', 'RelationshipReader', 'graph', 'Neo4jRelationshipReader'),
            ('search', 'search_reader', 'SearchReader', 'search', 'ElasticsearchReader'),
            ('search', 'search_cache', 'SearchCache', 'cache', 'RedisSearchCache'),
            ('search', 'search_history', 'SearchHistory', 'search', 'ElasticsearchHistory'),
            ('search', 'search_index', 'SearchIndex', 'search', 'ElasticsearchIndex'),
            ('ingestion', 'rate_controller', 'RateController', 'pacing', 'AsyncioRateController'),
            ('ingestion', 'dataset_reader', 'DatasetReader', 'datasets', 'KaggleAndTextFileReader'),
        ]
        for service, module, port_name, folder, adapter_name in pairs:
            port = getattr(importlib.import_module(f'{service}_service.application.ports.{module}'), port_name)
            adapter = getattr(importlib.import_module(f'{service}_service.infrastructure.{folder}.{module}_adapter'), adapter_name)
            for name, method in vars(port).items():
                if not name.startswith('_') and inspect.isfunction(method):
                    with self.subTest(adapter=adapter_name, method=name):
                        implementation = getattr(adapter, name)
                        self.assertEqual(inspect.signature(method), inspect.signature(implementation))
                        self.assertEqual(get_type_hints(method), get_type_hints(implementation))


class StubBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_unimplemented_repository_does_not_report_success(self):
        from competition_service.infrastructure.database.repositories.postgres_player_repository import PostgresPlayerRepository
        repository = PostgresPlayerRepository(connection_url='unused')
        with self.assertRaises(NotImplementedError):
            await repository.get(uuid4())

    async def test_controller_delegates_to_query_boundary(self):
        from competition_service.presentation.api.controllers.player_controller import PlayerController

        class Queries:
            async def get(self, entity_id, *, viewer_id=None):
                self.seen = (entity_id, viewer_id)
                return None

        queries = Queries()
        controller = PlayerController(commands=None, queries=queries)
        player_id, viewer_id = uuid4(), uuid4()
        self.assertIsNone(await controller.get(player_id, viewer_id=viewer_id))
        self.assertEqual(queries.seen, (player_id, viewer_id))


if __name__ == '__main__':
    unittest.main()
