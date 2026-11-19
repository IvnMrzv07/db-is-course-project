"""Search projection of a Content document (template v2): what is indexed, filtered and highlighted.

Pure domain rules, no I/O. The full `metadata` object is kept in the index source for display, while
frequently searched/filtered metadata values are lifted to top-level fields with fixed mappings.
"""
from __future__ import annotations

from uuid import UUID

from search_service.domain.exceptions import DomainError

CORPUS_SCOPES = {'kaggle-cs': False, 'synthetic-cs': True}  # scope -> required is_synthetic
DOCUMENT_TYPES = ('series', 'map')
LIFTED_TEXT = ('team1', 'team2', 'tournament', 'winner_team')


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def player_names(metadata: dict) -> list[str]:
    players = metadata.get('players')
    if not isinstance(players, list):
        return []
    names = []
    for player in players:
        name = _text(player.get('name')) if isinstance(player, dict) else None
        if name and name not in names:
            names.append(name)
    return names


def project(document: dict) -> dict:
    """Validate one `search.index` document and build the index source; raises DomainError if invalid."""
    try:
        document_id = str(UUID(str(document['document_id'])))
    except (KeyError, ValueError, TypeError) as exc:
        raise DomainError('Document id must be a UUID') from exc
    version = document.get('version')
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise DomainError('Document version must be a positive integer')
    scope = document.get('corpus_scope')
    if scope not in CORPUS_SCOPES:
        raise DomainError('Unsupported corpus scope')
    if document.get('is_synthetic') is not CORPUS_SCOPES[scope]:
        raise DomainError('Synthetic flag does not match corpus scope')
    title, text = _text(document.get('title')), _text(document.get('text'))
    if not title or not text:
        raise DomainError('Title and text are required')
    metadata = document.get('metadata')
    if not isinstance(metadata, dict):
        raise DomainError('Metadata must be an object')
    document_type = metadata.get('document_type')
    if document_type not in DOCUMENT_TYPES:
        raise DomainError('Unknown document type')
    source = {
        'id': document_id, 'version': version, 'title': title, 'text': text,
        'language': _text(document.get('language')) or 'en', 'corpus_scope': scope,
        'is_synthetic': CORPUS_SCOPES[scope], 'source_id': _text(document.get('source_id')),
        'document_type': document_type, 'map_name': _text(metadata.get('map_name')),
        'played_at': _text(metadata.get('played_at')), 'best_of': _integer(metadata.get('best_of')),
        'template_version': _text(metadata.get('template_version')),
        'player_names': player_names(metadata), 'metadata': metadata,
    }
    for field in LIFTED_TEXT:
        source[field] = _text(metadata.get(field))
    return source
