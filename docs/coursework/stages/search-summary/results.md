# Elasticsearch: повнотекстовий пошук і асинхронна індексація (пункт 7 плану)

Дата: 19.11.2026. Стенд `cs-sharded` (порт 8082): 3 шарди MongoDB + `mongos`, RabbitMQ, новий Elasticsearch 8.15.3. Корпус: 100 000 документів `template_version = "2"` (`kaggle-cs` 20 675 + `synthetic-cs` 79 325). Основний стек `cs-coursework` не запускався, його томи не змінювалися. На `cs-sharded` додано том `cs-sharded_es_data`. Наявні томи не видалялися (`down -v` не виконувався). Перестворено лише `content_api`, `content_worker` і `web` (`up -d --no-deps`), а також додано `elasticsearch`, `search_api` і `search_worker`.

## Архітектура

```
Ingestion ──corpus.store──▶ content_worker ── одна Mongo-транзакція ──┐
                                                documents + receipt + counter
                                                + outbox{corpus.completed}
                                                + outbox{search.index}   (SEARCH_INDEX_EVENTS=1)
content_worker (dispatcher) ──search.index──▶ search_worker ──_bulk──▶ Elasticsearch (alias cs-documents)
content_service.reindex (backfill) ──search.index──┘                         ▲
Browser ─▶ nginx /api/v1/search ─▶ search_api ────────────────────────────────┘
```

| Шар | Файл | Призначення |
|---|---|---|
| Контракт | `backend/contracts/messages.py` (`IndexSourceDocuments`, `SEARCH_INDEX_QUEUE`) | Схема події `source_documents.indexable` v1 |
| Content | `application/services/commands/search_index_events.py` | Проєкція опублікованих документів. Чернетки не потрапляють у подію |
| Content | `infrastructure/database/corpus_repository.py` | Рядок `outbox` з `queue: search.index` у тій самій транзакції, що й пакет |
| Content | `worker.py`, `infrastructure/messaging/runtime_broker.py` | Публікація outbox за чергою. Після підтвердження брокером індексна подія видаляється з outbox |
| Content | `reindex.py` | Повна переіндексація: Content читає власну MongoDB і публікує події через брокер |
| Search: domain | `domain/services/index_projection.py` | Валідація (UUID, версія, відповідність `corpus_scope` ↔ `is_synthetic`) і поля індексу |
| Search: application | `dtos/full_text_query.py`, `ports/document_index.py`, `services/commands/document_indexing_service.py`, `services/queries/full_text_search_service.py` | CQRS: індексація та запити, стани found/empty/degraded |
| Search: infrastructure | `infrastructure/search/elasticsearch_documents.py`, `infrastructure/messaging/index_broker.py` | REST до ES (httpx), Query DSL, bulk із зовнішньою версією; споживач черги |
| Search: presentation | `presentation/api/app.py`, `worker.py`, `manage.py` | `GET /api/v1/search`, `GET /api/v1/search/status`; індексатор; `ensure`/`recreate`/`status` |
| Deploy | `deploy/docker-compose.sharded.yml`, `frontend/nginx.conf`, `frontend/vite.config.ts` | ES (`-Xms512m -Xmx512m`, `mem_limit 1536m`, без xpack security/TLS), маршрут `/api/v1/search` |
| UI | `frontend/src/Search.tsx`, вкладка «Повнотекстовий пошук» (`/#search?q=…`) | Режими, фільтри, `_score`, підсвічування, плашка синтетичних записів, стани |

Сервіс Search **не читає MongoDB**: індекс будується лише з подій брокера. Тому повну переіндексацію запускає власник даних (Content).

### Ідемпотентність

- `_id` документа в ES дорівнює `document_id` (UUIDv5 корпусу).
- Індексатор пише з `version = version документа` і `version_type = external_gte`. Повторна доставка, replay чи backfill перезаписують документ тими самими даними. Старіша версія не може витіснити новішу: ES відповідає 409, і індексатор зараховує такий запис як `stale`, а не як помилку.
- Подія з outbox має детермінований `event_id = index:<batch_id>`. Повторна доставка того самого пакета в Content відповідає з квитанції (`committed_batches`) і другої події не створює.
- Content емітує подію для **всіх** документів пакета, включно з дублікатами (`$setOnInsert`). Тому звичайний replay знімка ще й «лікує» індекс, що відстав.

### Відмови

| Ситуація | Поведінка |
|---|---|
| ES недоступний під час пошуку | `503 {"status":"degraded","reason":…}`. UI показує плашку й резервний буквальний пошук MongoDB через Content |
| Часткова відповідь ES (`timed_out`, збій шардів) | `200`, `degraded: true`, UI показує попередження |
| ES недоступний під час індексації | Подія повертається в чергу (nack+requeue з паузою до 30 с) **без** збільшення лічильника спроб. Збій ES не призводить до карантину |
| Некоректна подія (схема, UUID, scope/flag) | Подія відхиляється до запису в ES. Після 5 спроб переходить у `search.index.failed` |
| Невідома помилка API | `500 {"status":"error"}` |
| Стек без `search_api` (основний) | Nginx резолвить upstream під час запиту → 502 → UI переходить у degraded. Контейнер `web` стартує, бо upstream не резолвиться під час запуску. `SEARCH_INDEX_EVENTS` там не ввімкнено, тому поведінка Content не змінилася |

## Індекс

`cs-documents-v1` за аліасом `cs-documents`, 1 primary shard, 0 реплік, `dynamic: strict`, аналізатор `cs_text` (`standard` + `lowercase` + `asciifolding`).

- Поля пошуку: `title`, `text`, `team1`, `team2`, `tournament`, `winner_team` (text + `.keyword`), `map_name` (keyword + `.text`), `player_names` (імена з `metadata.players`).
- Поля фільтрів: `id`, `corpus_scope`, `is_synthetic`, `document_type`, `played_at`, `best_of`, `version`, `template_version`.
- `metadata` зберігається повністю в `_source` з `enabled: false`: поле не індексується, тож вибуху мапінгу немає.

## Результати

### 100 000 документів в індексі (`index-status.json`, `backfill-*.json`)

| Показник | Значення |
|---|---|
| Документів у MongoDB / в індексі | **100 000 / 100 000** |
| `kaggle-cs` / `synthetic-cs` | 20 675 / 79 325 |
| `map` / `series` | 53 990 / 46 010 |
| `is_synthetic` true / false | 79 325 / 20 675 |
| Подій backfill (по 100 документів) | 1 000; публікація з підтвердженнями 18,2 с |
| Індексація (перша → остання подія в логах `search_worker`) | 15:05:48,5 → 15:07:02,3 = **73,8 с, ≈ 1 355 док/с** |
| Помилки / `search.index.failed` | 0 / 0 |
| Розмір індексу | 177,8 MB (green) |

Повторний backfill (`backfill-repeat-publish.json`) дав 200 000 операцій індексації, а документів так само 100 000. Зовнішня версія документа лишилася `1`, змінився лише `_seq_no`. Це доказ ідемпотентності за `document_id`.

### Шлях «збереження в Content → подія → індекс» (`event-path.json`, `replay-job.json`)

1. З ES напряму видалено 5 документів `kaggle-cs` (в індексі лишилося 20 670 документів цього корпусу).
2. Запущено звичайний replay `kaggle-cs` через Ingestion API: 20 675 документів, `inserted 0`, `duplicates 20 675`, 1 рядок CSV відхилено, як і очікувалося.
3. Content записав 207 індексних подій у транзакційний outbox, `search_worker` їх обробив (`origin=store`, `stale 0`). Остання подія проіндексована через 29 мс після завершення завдання.
4. Індекс знову містить 100 000 документів, усі 5 повернулися з версією 1. У Mongo `outbox` не лишилося рядків `search.index`, черги й карантини порожні.

Нюанс: прямий `DELETE` у ES підвищує внутрішню версію документа, а tombstone живе `index.gc_deletes` = 60 с. У цьому вікні подія з версією 1 коректно відкидається як `stale`. Тому replay запущено через 65 с після видалення.

### Приклади пошуку й таймінги (`search-examples.json`, `timings.json`)

Медіана 7 «теплих» запитів через Nginx. `ES` — час `took`, `e2e` — повний HTTP-запит із хоста.

| Сценарій | Запит | Стан | Знайдено | ES, мс | e2e, мс |
|---|---|---|---:|---:|---:|
| Команда + карта | `Vitality Mirage`, усі слова | found | 81 | 24 | 40 |
| Гравець | `s1mple`, карти | found | 142 | 14 | 28 |
| Турнір, точна фраза, без синтетики | `"IEM Katowice"` | found | 302 | 24 | 40 |
| Опечатка | `Natus Vincere Inferrno`, fuzzy | found | 77 | 193 | 214 |
| Будь-яке слово, Kaggle | `FaZe Astralis` | found | 1 317 | 34 | 52 |
| Фільтр карти + без синтетики | `NAVI`, `map_name=Nuke` | found | 1 | 6 | 16 |
| Синтетичний корпус | `Synthetic Team 039`, серії | found | 1 132 | 44 | 67 |
| Ті самі слова, синтетику виключено | `Synthetic Team 039`, `include_synthetic=false` | **empty** | 0 | 11 | 20 |
| Нічого не знайдено | `qwxzvj nonexistent` | **empty** | 0 | 6 | 15 |
| Лише фільтри | `q=''`, карти, `Ancient` | found | 15 369 | 15 | 29 |

Ранжування працює так. Для `Vitality Mirage` угорі карти Mirage з `Team Vitality` (`_score` ≈ 25,9): збіги є в `team1`/`team2` (^4), `map_name` (^3) і заголовку (^3). Для `s1mple` спрацьовує поле `player_names` (гравця немає в заголовку). Для fuzzy-запиту «Inferrno» підсвічено виправлене слово «Inferno».

Оптимізація під час прийняття:
- У режимі `fuzzy` спершу було ~1,1–1,4 с. Профілювання показало, що 95 % часу забирає підсвічування розгорнутих Левенштейн-термів: без highlight запит займав 19–46 мс.
- Fuzzy обмежено полями назв (без `text`) з `fuzziness: AUTO:5,9` і `max_expansions: 20`. Отримуємо ті самі 77 збігів за ~0,2 с.
- Перші «холодні» запити після старту ES тривають 0,4–1,9 с (видно на скриншотах).

Знайдений дефект: маркери підсвічування спершу були керівними символами U+0002/U+0003. Lucene обрізає фрагмент через `String.trim()`, тобто прибирає всі символи ≤ U+0020. У фрагментах, що починалися зі збігу (`s1mple…`), губився відкривальний маркер. Тепер використовуються символи з Private Use Area (U+E000/U+E001). Додано регресійний тест.

### Стан degraded (`degraded.json`, `ui-search-degraded.png`)

| Фаза | Запит | HTTP | Час |
|---|---|---|---:|
| ES зупинено | `/api/v1/search?q=Vitality+Mirage` | 503 `degraded`, `Elasticsearch unreachable: ConnectError` | 4,0 с |
| ES зупинено | `/api/v1/search/status` | 503 `degraded` | 3,8 с |
| ES зупинено | `/api/v1/documents?q=Vitality` (резервний пошук у UI) | 200, 636 документів | 77 мс |
| ES знову запущено | `/api/v1/search?q=Vitality+Mirage` | 200 `found`, 81 (холодний запит 0,9 с) | 1,1 с |
| ES знову запущено | `/api/v1/search/status` | 200, 100 000 документів (дані на томі збереглися) | 0,25 с |

### UI

- `ui-search-found.png` — режим «Усі слова»: `_score` зі смугою відносної релевантності, підсвічені збіги в заголовку та фрагментах, плашка `KAGGLE`, таймінги ES/сервісу.
- `ui-search-synthetic.png` — синтетичні записи з плашкою «СИНТЕТИЧНИЙ ЗАПИС» і заштрихованим фоном, фрагменти «Турнір / Текст / Гравці».
- `ui-search-empty.png` — стан Empty: синтетику виключено прапорцем.
- `ui-search-degraded.png` — стан degraded: ES зупинено, показано резервний буквальний пошук MongoDB без ранжування.

## Тести

- `tests/test_search_service.py` — 36 юніт-тестів: подія в тій самій транзакції та її відкат, відсутність події без прапорця, backfill пакетами, проєкція й валідація, ідемпотентність `external_gte`, класифікація помилок bulk, Query DSL для всіх режимів і фільтрів, розбір відповіді, мапінг транспортних помилок, HTTP-стани found/empty/degraded/error/422, регресійний тест маркерів.
- Ще 2 тести на стенді (`RUN_SEARCH_STACK_TESTS=1 pytest -m integration tests/test_search_service.py`) — пройдено: 100 000 документів у розбивці за scope, found/filter/empty на живих даних.
- Увесь набір: `128 passed, 11 skipped`.

## Відтворення

```sh
docker compose -f deploy/docker-compose.sharded.yml --env-file .env up -d --build --no-deps elasticsearch   # 1-й старт: pull ~670 MB
docker compose -f deploy/docker-compose.sharded.yml --env-file .env up -d --build --no-deps search_api search_worker content_api content_worker web
docker compose -f deploy/docker-compose.sharded.yml --env-file .env run --rm --no-deps -T content_worker python -m content_service.reindex
docker compose -f deploy/docker-compose.sharded.yml --env-file .env run --rm --no-deps -T search_api python -m search_service.manage status --wait-count 100000
python tools/search/collect_search_evidence.py   # index-status.json, search-examples.json, timings.json
```

## Обмеження

- Один вузол ES без реплік і без автентифікації/TLS. Це локальний демонстраційний стенд, не відмовостійка інсталяція.
- Синоніми й скорочення («NaVi» ↔ «Natus Vincere») не налаштовані: «NAVI» знаходить лише команди, у назві яких є це слово.
- Видалення документів у Content не реалізоване, тож події-tombstone теж немає. Для майбутнього видалення потрібен `delete` із зовнішньою версією.
- Пагінація обмежена першими 10 000 результатами (`index.max_result_window`).
