"""Distributed map-reduce endpoint: unit tests, an opt-in real-MongoDB test and an opt-in cs-sharded stand test."""
import asyncio
import json
import os
import urllib.request
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from content_service.application.dtos.distributed_query import DistributedAggregationQuery as Query
from content_service.application.services.queries.distributed_aggregation_query_service import (
    DistributedAggregationQueryService, compare_rows, derive_rows)
from content_service.infrastructure.database.distributed_aggregation import (
    build_map_reduce, build_match, build_pipeline, map_function, normalize, sort_rows, summarize_explain)
from content_service.presentation.api.app import app as content_app
from content_service.presentation.api.controllers.distributed_aggregation_controller import DistributedAggregationController


# ---------------------------------------------------------------- request validation
@pytest.mark.parametrize('arguments', [
    {'metric': 'unknown'}, {'engine': 'spark'}, {'corpus_scope': 'other'}, {'document_type': 'article'},
    {'limit': 0}, {'limit': 101},
    {'metric': 'map_pool', 'document_type': 'series'}, {'metric': 'series_scores', 'document_type': 'map'},
    {'metric': 'top_players'}])  # players without a type would sum series and map statistics together
def test_query_validation(arguments):
    with pytest.raises(ValueError):
        Query(**arguments)


def test_document_type_is_fixed_for_type_specific_metrics():
    assert Query(metric='map_pool').resolved_document_type == 'map'
    assert Query(metric='series_scores').resolved_document_type == 'series'
    assert Query(metric='document_types').resolved_document_type is None
    assert Query(metric='top_players', document_type='series').resolved_document_type == 'series'


# ---------------------------------------------------------------- pipelines
def test_match_is_v2_only_and_index_friendly():
    match = build_match(Query(metric='map_pool'))
    assert match == {'corpus_scope': {'$in': ['kaggle-cs', 'synthetic-cs']}, 'publication_status': 'published',
                     'metadata.template_version': '2', 'metadata.document_type': 'map'}
    assert build_match(Query(metric='document_types', corpus_scope='kaggle-cs'))['corpus_scope'] == 'kaggle-cs'
    assert 'metadata.document_type' not in build_match(Query(metric='document_types'))


def test_pipeline_shapes():
    stages = lambda q: [next(iter(stage)) for stage in build_pipeline(q)]
    assert stages(Query(metric='map_pool')) == ['$match', '$group', '$sort']
    players = Query(metric='top_players', document_type='map', limit=7)
    assert stages(players) == ['$match', '$unwind', '$match', '$group', '$sort', '$limit']
    pipeline = build_pipeline(players)
    assert pipeline[-1] == {'$limit': 7} and pipeline[-2] == {'$sort': {'kills': -1, '_id': 1}}
    assert build_pipeline(Query(metric='document_types'))[-1] == {'$sort': {'_id.corpus_scope': 1, '_id.document_type': 1}}
    assert build_pipeline(Query(metric='series_scores'))[-1] == {'$sort': {'_id.best_of': 1, 'documents': -1, '_id.score': 1}}


def test_map_reduce_command_uses_the_same_filter_and_inline_output():
    query = Query(metric='series_scores', corpus_scope='synthetic-cs')
    command = build_map_reduce(query)
    assert list(command)[0] == 'mapReduce' and command['out'] == {'inline': 1}
    assert command['query'] == build_match(query)
    for metric in ('map_pool', 'document_types', 'series_scores', 'top_players'):
        source = map_function(metric)
        assert source.startswith('function () {') and 'emit(' in source and source.count('{') == source.count('}')


# ---------------------------------------------------------------- normalisation and ordering
def test_normalize_flattens_keys_and_integral_floats():
    assert normalize('map_pool', None, {'maps': 3.0, 'rounds': 40.0}) == {'map_name': None, 'maps': 3, 'rounds': 40}
    assert normalize('series_scores', {'best_of': 3.0, 'score': '2:1'}, {'documents': 2}) == \
        {'best_of': 3, 'score': '2:1', 'documents': 2}
    assert normalize('top_players', 'p1', {'adr_sum': 150.5}) == {'player_id': 'p1', 'adr_sum': 150.5}


def test_python_sort_matches_mongo_order_null_first_and_tie_breaks():
    rows = [{'map_name': 'Nuke', 'maps': 5}, {'map_name': None, 'maps': 5}, {'map_name': 'Ancient', 'maps': 9},
            {'map_name': 'Anubis', 'maps': 5}]
    assert [r['map_name'] for r in sort_rows('map_pool', rows)] == ['Ancient', None, 'Anubis', 'Nuke']
    series = [{'best_of': 3, 'score': '2:0', 'documents': 10}, {'best_of': None, 'score': '1:0', 'documents': 1},
              {'best_of': 3, 'score': '2:1', 'documents': 12}, {'best_of': 3, 'score': None, 'documents': 12}]
    assert [(r['best_of'], r['score']) for r in sort_rows('series_scores', series)] == \
        [(None, '1:0'), (3, None), (3, '2:1'), (3, '2:0')]


# ---------------------------------------------------------------- explain summary
def _shard(host, matched, groups, emit=False):
    cursor = {'$cursor': {'queryPlanner': {'winningPlan': {'stage': 'PROJECTION_DEFAULT', 'inputStage': {
                  'stage': 'SHARDING_FILTER', 'inputStage': {'stage': 'FETCH', 'inputStage': {
                      'stage': 'IXSCAN', 'indexName': 'corpus_scope_1_metadata.document_type_1__id_1'}}}}},
              'executionStats': {'nReturned': matched, 'executionTimeMillis': 9, 'totalKeysExamined': matched + 1,
                                 'totalDocsExamined': matched}},
              'nReturned': matched, 'executionTimeMillisEstimate': 5}
    if emit:
        cursor['$cursor']['queryPlanner']['parsedQuery'] = {'$_internalJsEmit': {}}
    return {'host': host, 'stages': [cursor, {'$group': {}, 'nReturned': groups, 'executionTimeMillisEstimate': 12}]}


def test_summarize_sharded_explain():
    explain = {'mergeType': 'anyShard', 'splitPipeline': {
                   'shardsPart': [{'$match': {}}, {'$group': {}}],
                   'mergerPart': [{'$mergeCursors': {}}, {'$group': {'$doingMerge': True}}, {'$sort': {'sortKey': {'kills': -1}, 'limit': 20}}]},
               'shards': {'shard2RS': _shard('shard2:27018', 30, 4), 'shard1RS': _shard('shard1:27018', 40, 5)}}
    plan = summarize_explain(explain)
    assert plan['topology'] == 'sharded' and plan['merge_type'] == 'anyShard'
    assert plan['shards_part'] == ['$match', '$group']
    assert plan['merger_part'] == ['$mergeCursors', '$group', '$sort (limit 20)']
    first = plan['shards'][0]
    assert first['shard'] == 'shard1RS' and first['matched'] == 40 and first['partial_groups'] == 5 and first['time_ms'] == 12
    assert first['plan'] == 'PROJECTION_DEFAULT → SHARDING_FILTER → FETCH → IXSCAN(corpus_scope_1_metadata.document_type_1__id_1)'
    assert first['keys_examined'] == 41 and first['pipeline'] == ['$cursor', '$group']


def test_summarize_map_reduce_and_unsharded_explain():
    mr = {'mergeType': 'anyShard', 'splitPipeline': {
              'shardsPart': [{'$match': {}}, {'$project': {'emits': {'$_internalJsEmit': {'eval': 'f'}}}}, {'$unwind': {}},
                             {'$group': {'value': {'$_internalJsReduce': {}}}}],
              'mergerPart': [{'$mergeCursors': {}}, {'$group': {'value': {'$_internalJsReduce': {}}}}]},
          'shards': {'shard1RS': _shard('h', 3, 1)}}
    plan = summarize_explain(mr)
    assert plan['shards_part'][1] == '$project ($_internalJsEmit)' and plan['merger_part'][1] == '$group ($_internalJsReduce)'
    single = summarize_explain({'stages': _shard('rs0:27017', 7, 2)['stages']})
    assert single['topology'] == 'single' and single['merger_part'] == []
    assert single['shards'][0]['shard'] == 'local' and single['shards'][0]['partial_groups'] == 2


# ---------------------------------------------------------------- reduce-side service
def test_derived_indicators():
    [row] = derive_rows('map_pool', [{'map_name': 'Mirage', 'maps': 4, 'scored': 3, 'rounds': 66, 'margin': 12,
                                      'team1_wins': 3, 'team2_wins': 1, 'draws': 0}])
    assert (row['share'], row['avg_rounds'], row['avg_margin'], row['team1_win_share']) == (1.0, 22.0, 4.0, 0.75)
    [player] = derive_rows('top_players', [{'player_id': 'p', 'name': 'P', 'documents': 2, 'kills': 30, 'deaths': 0,
                                            'assists': 1, 'adr_sum': 150.0, 'adr_n': 2, 'kast_sum': 0, 'kast_n': 0}])
    assert player['kd'] is None and player['avg_adr'] == 75.0 and player['avg_kast'] is None and player['kills_per_document'] == 15.0


def test_compare_rows_tolerates_float_summation_order_only():
    a = [{'player_id': 'p', 'kills': 10, 'adr_sum': 0.1 + 0.2}]
    assert compare_rows(a, [{'player_id': 'p', 'kills': 10, 'adr_sum': 0.3}])['equal']
    result = compare_rows(a, [{'player_id': 'p', 'kills': 11, 'adr_sum': 0.3}])
    assert not result['equal'] and result['differences'][0]['field'] == 'kills'
    assert compare_rows(a, [])['differences'][0]['field'] == 'row_count'


def _reader(aggregate_rows, mapreduce_rows, matched):
    plan = {'topology': 'sharded', 'merge_type': 'anyShard', 'shards_part': [], 'merger_part': [], 'shards': []}
    rows = {'aggregate': aggregate_rows, 'mapreduce': mapreduce_rows}
    return SimpleNamespace(
        count=AsyncMock(return_value=matched),
        execute=AsyncMock(side_effect=lambda q, engine: {'engine': engine, 'rows': rows[engine], 'elapsed_ms': 1.0,
                                                         'groups_returned': len(rows[engine]), 'plan': plan}),
        topology=AsyncMock(return_value={'sharded': True, 'shards': [{'shard': 'shard1RS', 'documents': 5}]}))


def test_service_runs_both_engines_and_checks_coverage():
    rows = [{'corpus_scope': 'kaggle-cs', 'document_type': 'map', 'documents': 3, 'with_players': 3, 'player_rows': 30,
             'team1_wins': 2, 'team2_wins': 1, 'draws': 0},
            {'corpus_scope': 'kaggle-cs', 'document_type': 'series', 'documents': 2, 'with_players': 0, 'player_rows': 0,
             'team1_wins': 1, 'team2_wins': 1, 'draws': 0}]
    reader = _reader(rows, [dict(r) for r in rows], 5)
    result = asyncio.run(DistributedAggregationQueryService(reader).run(Query(metric='document_types', engine='both')))
    assert [e['engine'] for e in result['executions']] == ['aggregate', 'mapreduce']
    assert result['comparison']['equal'] and result['coverage']['consistent']
    assert result['rows'][0]['avg_players'] == 10.0 and result['template_version'] == '2'
    # A lost shard (fewer grouped documents than matched) must be visible.
    reader = _reader(rows[:1], rows[:1], 5)
    result = asyncio.run(DistributedAggregationQueryService(reader).run(Query(metric='document_types')))
    assert result['comparison'] is None and not result['coverage']['consistent']
    assert reader.execute.await_count == 1


# ---------------------------------------------------------------- HTTP
def test_http_endpoint_validation_and_errors():
    service = SimpleNamespace(run=AsyncMock(return_value={'rows': []}))
    content_app.state.distributed = DistributedAggregationController(service)
    client = TestClient(content_app)
    assert client.get('/api/v1/distributed/map-reduce?metric=top_players&document_type=map&limit=5&engine=both').status_code == 200
    query = service.run.call_args.args[0]
    assert (query.metric, query.document_type, query.limit, query.engine, query.explain) == ('top_players', 'map', 5, 'both', True)
    assert client.get('/api/v1/distributed/map-reduce?metric=top_players').status_code == 422
    assert client.get('/api/v1/distributed/map-reduce?metric=map_pool&document_type=series').status_code == 422
    assert client.get('/api/v1/distributed/map-reduce?limit=0').status_code == 422
    from pymongo.errors import ExecutionTimeout
    service.run = AsyncMock(side_effect=ExecutionTimeout('operation exceeded time limit'))
    assert client.get('/api/v1/distributed/map-reduce').status_code == 503


# ---------------------------------------------------------------- opt-in real MongoDB (replica set or mongos)
@pytest.mark.skipif(not os.getenv('TEST_MONGO_URL'), reason='Requires an isolated MongoDB with server-side JavaScript')
def test_real_mongo_engines_agree_on_incomplete_v2_documents():
    from pymongo import AsyncMongoClient
    from content_service.infrastructure.database.distributed_aggregation import MongoDistributedAggregation

    def doc(scope, kind, **metadata):
        players = metadata.pop('players', [])
        return {'_id': str(uuid4()), 'corpus_scope': scope, 'publication_status': 'published',
                'metadata': {'template_version': '2', 'document_type': kind, 'players': players, **metadata}}
    player = lambda pid, kills, adr=70.5: {'player_id': pid, 'name': 'N' + pid, 'kills': kills, 'deaths': 10,
                                           'assists': 2, 'adr': adr, 'kast': 70.0}
    documents = [
        doc('kaggle-cs', 'map', map_name='Mirage', score1=13, score2=7, winner='team1', players=[player('a', 20), player('b', 5, None)]),
        doc('kaggle-cs', 'map', map_name=None, score1=None, score2=None, winner=None),
        doc('synthetic-cs', 'map', map_name='Mirage', score1=11, score2=13, winner='team2', players=[player('a', 9.0)]),
        doc('kaggle-cs', 'series', best_of=3, score1=2, score2=1, winner='team1', players=[player('a', 50)]),
        doc('kaggle-cs', 'series', best_of=None, score1=0, score2=2, winner='team2'),
        {**doc('kaggle-cs', 'map', map_name='Nuke', score1=13, score2=0), 'metadata': {'template_version': '1', 'document_type': 'map'}},
    ]

    async def scenario():
        client = AsyncMongoClient(os.environ['TEST_MONGO_URL'], serverSelectionTimeoutMS=5000)
        database = client['test_' + uuid4().hex]
        try:
            await database.source_documents.insert_many(documents)
            service = DistributedAggregationQueryService(MongoDistributedAggregation(database))
            results = {}
            for query in (Query(metric='map_pool', engine='both'), Query(metric='document_types', engine='both'),
                          Query(metric='series_scores', engine='both'),
                          Query(metric='top_players', document_type='map', engine='both', limit=1)):
                result = await service.run(query)
                assert result['comparison']['equal'], result['comparison']
                if result['coverage']:
                    assert result['coverage']['consistent']
                results[query.metric] = result
            pool = {row['map_name']: row for row in results['map_pool']['rows']}
            assert pool['Mirage']['maps'] == 2 and pool['Mirage']['rounds'] == 44 and pool[None]['scored'] == 0
            assert results['map_pool']['matched_documents'] == 3  # template_version 1 is excluded
            assert [(r['best_of'], r['score']) for r in results['series_scores']['rows']] == [(None, '2:0'), (3, '2:1')]
            [top] = results['top_players']['rows']
            assert (top['player_id'], top['kills'], top['documents']) == ('a', 29, 2)
        finally:
            await client.drop_database(database.name)
            await client.close()
    asyncio.run(scenario())


# ---------------------------------------------------------------- opt-in live cs-sharded stand
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv('SHARDED_BASE_URL'), reason='Set SHARDED_BASE_URL=http://localhost:8082 with the cs-sharded stack running')
@pytest.mark.parametrize('params', ['metric=document_types', 'metric=map_pool', 'metric=series_scores',
                                    'metric=top_players&document_type=series&limit=10'])
def test_live_sharded_stand(params):
    url = os.environ['SHARDED_BASE_URL'].rstrip('/') + '/api/v1/distributed/map-reduce?engine=both&' + params
    with urllib.request.urlopen(url, timeout=120) as response:
        result = json.load(response)
    assert result['comparison']['equal'], result['comparison']
    assert result['topology']['sharded'] and len(result['topology']['shards']) == 3
    for execution in result['executions']:
        plan = execution['plan']
        assert plan['topology'] == 'sharded' and len(plan['shards']) == 3
        assert sum(shard['matched'] for shard in plan['shards']) == result['matched_documents']
    if result['coverage']:
        assert result['coverage']['consistent']
    if params == 'metric=document_types':
        assert result['matched_documents'] == sum(s['documents'] for s in result['topology']['shards']) == 100_000
