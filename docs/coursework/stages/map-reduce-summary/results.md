# Map-Reduce: розподілена агрегація по шардах MongoDB (пункт 6 плану)

Дата: 19.11.2026. Стенд `cs-sharded` (3 шарди + config server + `mongos`, MongoDB 7.0.48), порт 8082. Корпус: 100 000 документів `template_version = "2"` (`kaggle-cs` 20 675 + `synthetic-cs` 79 325). Основний стек `cs-coursework` не запускався, томи не змінювалися. Перезапущено лише контейнери `content_api` і `web` стенду `cs-sharded` (`up -d --no-deps`).

## Що реалізовано

| Шар | Файл | Призначення |
|---|---|---|
| DTO | `backend/content_service/application/dtos/distributed_query.py` | Параметри й правила: `top_players` вимагає `document_type`, `map_pool` — лише карти, `series_scores` — лише серії |
| Порт | `backend/content_service/application/ports/distributed_aggregation.py` | `count`, `execute(engine)`, `topology` |
| Сервіс | `backend/content_service/application/services/queries/distributed_aggregation_query_service.py` | Reduce-бік: похідні показники, порівняння рушіїв, перевірка повноти |
| Адаптер | `backend/content_service/infrastructure/database/distributed_aggregation.py` | Конвеєри, JS map/reduce, розбір `explain` по шардах, `$collStats` |
| API | `GET /api/v1/distributed/map-reduce` (`presentation/api/app.py`) | `metric`, `corpus_scope`, `document_type`, `engine`, `limit`, `explain` |
| Nginx | `frontend/nginx.conf` | Окремий `location /api/v1/distributed/` із `proxy_read_timeout 90s` |
| UI | `frontend/src/Distributed.tsx`, вкладка «Розподілені запити» (`/#distributed`) | Форма, результати, перевірки, розподіл по шардах, план map/reduce |

### Два рушії, однакова семантика

- **`aggregate`**: `mongos` ділить конвеєр на `shardsPart` (`$match` + частковий `$group` = map + combine на кожному шарді) і `mergerPart` (`$mergeCursors` + зливний `$group` + `$sort`, для `top_players` з `$limit` усередині сортування = reduce).
- **`mapreduce`**: команда `mapReduce` з JavaScript-функціями та `out: {inline: 1}`. У MongoDB 7 вона виконується як `$_internalJsEmit` → `$unwind` → `$group($_internalJsReduce)` з тим самим розбиттям на шарди/злиття. Сортувати чи обрізати результат вона не вміє, тому Content сортує його в тому ж порядку, що й `$sort` конвеєра.
- Обидва рушії однаково обробляють пропуски в даних v2: 78 карт без `map_name` (ключ `null`, в UI «Не вказано в джерелі»), 39 документів без рахунку (не входять у середні), `best_of = null`, 21 645 документів без масиву гравців.
- **Серії й карти не підсумовуються.** Статистика серії вже містить статистику її карт. Тому `top_players` без `document_type` повертає 422, а `document_types` лише рахує документи окремими рядками.

## Результати на 100 000 документах

Медіана трьох прогонів, час на сервері Content, `explain=false` (`timings.json`):

| Запит | Документів | Груп | Часткових груп на шард (1/2/3) | Повернуто застосунку: aggregate / mapReduce | aggregate, мс | mapReduce, мс | Рушії збігаються | Σ груп = документів |
|---|---:|---:|---|---:|---:|---:|:-:|:-:|
| `document_types`, усі | 100 000 | 4 | 4 / 4 / 4 | 4 / 4 | 480 | 1 645 | ✓ | ✓ |
| `map_pool`, усі | 53 990 | 10 | 10 / 10 / 10 | 10 / 10 | 222 | 1 131 | ✓ | ✓ |
| `series_scores`, усі | 46 010 | 16 | 14 / 14 / 15 | 16 / 16 | 168 | 765 | ✓ | ✓ |
| `top_players`, карти, усі, топ-10 | 53 990 | 10 | 2 164 / 2 149 / 2 149 | 10 / 2 312 | 1 468 | 5 603 | ✓ | — |
| `top_players`, серії, kaggle-cs, топ-10 | 9 922 | 10 | 1 053 / 1 052 / 1 035 | 10 / 1 192 | 160 | 743 | ✓ | — |

Висновки:

- **Map-фаза справді розподілена.** Кожен шард обробляє лише свою третину: наприклад, для `map_pool` — 18 001 / 17 947 / 18 042 документи. Сума збігається з `countDocuments` (53 990). План на кожному шарді: `PROJECTION_DEFAULT → SHARDING_FILTER → FETCH → IXSCAN(corpus_scope_1_metadata.document_type_1__id_1)`. Фільтр `$in` за обома scope зберігає використання індексу навіть для «усіх» документів.
- **Combine зменшує мережевий обмін.** На злиття йде не 53 990 документів, а 3 × 10 часткових груп (`map_pool`) або ≈ 3 × 2 150 (`top_players`).
- **Злиття.** `mergeType: anyShard`: через `allowDiskUse` reduce виконує один із шардів, а не `mongos`.
- **`aggregate` швидший за `mapReduce` у 3,8–5 разів.** `mapReduce` викликає JavaScript для кожного документа на кожному шарді. До того ж він не може обрізати результат: для `top_players` застосунку передаються всі 2 312 груп замість 10.
- **Коректність.** На всіх запитах обидва рушії дали ідентичні рядки. Цілі суми збігаються точно, суми ADR/KAST — з відносною похибкою ≤ 1e-9 (різний порядок додавання на шардах). Сума лічильників груп дорівнює `countDocuments` того самого фільтра. Отже жоден шард не загубився і жоден документ не порахувався двічі.

Приклади результатів:
- Пул карт: Mirage 20 920 (38,8 %), Ancient 15 369, Inferno 9 016.
- Найкращі гравці за серіями `kaggle-cs`: m0NESY 8 356 вбивств (K/D 1,38), donk 8 168 (ADR 98,8), ZywOo 8 090 (K/D 1,46).

## Файли доказів

- `document-types-all.json`, `map-pool-all.json`, `series-scores-all.json`, `top-players-map-all.json`, `top-players-series-kaggle.json` — повні відповіді API (`engine=both`, `explain=true`): рядки, порівняння, повнота, план по шардах, топологія.
- `timings.json` — 3 прогони кожного рушія, медіани, часткові групи по шардах.
- `ui-distributed-tab.png` — вкладка «Розподілені запити» на живому стенді (headless Edge, 1440 px).

## Тести

- `tests/test_distributed_aggregation.py`, юніт-тести (без БД): валідація параметрів, форма конвеєрів, порядок сортування (null < числа < рядки, як у BSON), розбір `explain` (шардований, mapReduce, без шардування), похідні показники, порівняння, перевірка повноти, HTTP 200/422/503.
- Реальна MongoDB (`TEST_MONGO_URL`): документи з пропусками і з `template_version = "1"`; рушії збігаються, очікувані суми. Виконано через `mongos` стенду в тимчасовій базі `test_<uuid>`, яка видаляється після тесту.
- Живий стенд (`SHARDED_BASE_URL=http://localhost:8082`, маркер `integration`): 4 запити. Перевіряє 3 шарди, суму `matched` по шардах = `matched_documents`, 100 000 документів, збіг рушіїв.
- Загальний набір `python -m pytest -q`: 92 passed, 9 skipped.

## Відтворення

```sh
docker compose -f deploy/docker-compose.sharded.yml --env-file .env build content_api web
docker compose -f deploy/docker-compose.sharded.yml --env-file .env up -d --no-deps content_api web
SHARDED_BASE_URL=http://localhost:8082 python -m pytest -m integration tests/test_distributed_aggregation.py
python tools/sharding/collect_map_reduce_evidence.py --base-url http://localhost:8082
# UI: http://localhost:8082/#distributed
```
