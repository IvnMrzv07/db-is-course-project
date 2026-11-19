# Партиціювання `replay_outbox` і `replay_batches` у PostgreSQL та retention (пункт 5 плану)

Дата: 19.11.2026. Стенд: Compose-проєкт `cs-sharded`, PostgreSQL 16.16 (контейнер `competition_db`, база `ingestion`). Томи не видалялися: `docker compose down -v` не запускався. Основний стек `cs-coursework` лишався зупиненим і не змінювався. Перезбиралися та перестворювалися лише `ingestion_api` та `ingestion_worker`:

```
docker compose -f deploy/docker-compose.sharded.yml --env-file .env up -d --no-deps --build ingestion_api ingestion_worker
```

Перед міграцією зроблено резервну копію бази: `pg_dump -Fc`, 34 MB. Файл: `artifacts/backups/ingestion-before-partitioning.dump` (каталог ігнорується git).

## Як працювали таблиці до змін

| Операція | Де | Запит |
|---|---|---|
| Створення батча й outbox-запису | `PostgresReplayStore.produce()`, одна транзакція під `FOR UPDATE` рядка job | `INSERT replay_batches`, `INSERT replay_outbox` |
| Відправка в RabbitMQ | `worker.dispatch()` | `SELECT … WHERE NOT sent ORDER BY created_at LIMIT 50 FOR UPDATE SKIP LOCKED`, потім `UPDATE … SET sent=true WHERE id=$1` |
| Обробка completion | `PostgresReplayStore.complete()` | `SELECT … FROM replay_batches WHERE id AND job_id FOR UPDATE`, `UPDATE status`, `min(start_offset)` для checkpoint |

- Записи лише додавалися; `sent` і `status` змінювалися в один бік.
- Нічого не видалялося, тому outbox ріс необмежено: 106 MB на 1001 батч (`before.txt`).
- У `replay_batches` не було колонки часу.

## Нова схема (`migrations/002_partitioning.sql`)

- `PARTITION BY RANGE (created_at)` для обох таблиць. Партиції подобові, межі за UTC: `<table>_pYYYYMMDD` = `[день 00:00, наступний день 00:00)`. Є також `<table>_default` (DEFAULT).
- PostgreSQL вимагає, щоб ключ партиціювання входив до кожного PK/UNIQUE. Тому ключі стали `(id, created_at)`, а в `replay_batches` додано `created_at`.
- FK переписано як складений: `replay_outbox(id, created_at) → replay_batches(id, created_at)`. Батч і його outbox-запис вставляються в одній транзакції з однаковим `created_at`. Тому вони завжди лежать у партиціях з однаковими межами, і retention видаляє їх парою.
- Глобальна унікальність `id` тепер не гарантується індексом, лише ключем `(id, created_at)`. Вона гарантується побудовою: `id = uuid5(job_id, start_offset)`, а `start_offset` = `produced` змінюється під блокуванням рядка job. Колишній `UNIQUE(job_id, start_offset)` став звичайним індексом. Content додатково дедуплікує батчі за `batch_id` (`committed_batches`).
- Часткові індекси `replay_outbox_pending` і `replay_batches_pending` збережено. Вони автоматично створюються в кожній партиції.

## Створення партицій

| Коли | Що робиться |
|---|---|
| Старт API/воркера | Міграція під advisory lock 912001, партиції на сьогодні та `REPLAY_PARTITION_AHEAD_DAYS` (1) наступних днів |
| Запис (`produce()`) | Якщо змінилася UTC-дата, перевіряється й створюється поточна партиція. Помилка тут не зупиняє запис: рядок прийме DEFAULT |
| Фонова задача воркера (`REPLAY_PARTITION_MAINTENANCE_SECONDS`, 3600 с) | Те саме плюс «порятунок» DEFAULT: для кожного дня з рядками в DEFAULT створюється окрема таблиця `LIKE`, рядки копіюються, видаляються з DEFAULT, після чого виконується `ATTACH PARTITION`. Інакше PostgreSQL відмовляє в `CREATE … PARTITION OF` для такого діапазону |

## Міграція наявних даних на стенді

Лог воркера `cs-sharded-ingestion_worker-1`:

```
14:19:25,482 INFO … Renamed legacy replay tables for partitioning migration
14:19:25,598 INFO … Created partitions for 2026-11-19: ['replay_batches_p20261119', 'replay_outbox_p20261119']
14:19:26,930 INFO … Migrated legacy replay rows into partitions: {'replay_batches': 1001, 'replay_outbox': 1001} days=['2026-11-19']
14:19:26,978 INFO … Created partitions for 2026-11-20: ['replay_batches_p20261120', 'replay_outbox_p20261120']
```

- Міграція виконалася в одній транзакції за ≈ 1,5 с:
  1. legacy-таблиці та їхні індекси перейменовано на `*_legacy`;
  2. створено партиції для днів, які є в даних;
  3. рядки скопійовано;
  4. кількість звірено;
  5. legacy-таблиці видалено.
- `created_at` для старих батчів узято з їхнього outbox-запису.
- API стартував паралельно. Він дочекався advisory lock і нічого не повторював.

Порівняння (`before.txt` ↔ `after-migration.txt`):

| Показник | До | Після |
|---|---|---|
| Тип таблиць | `r` (heap) | `p` (partitioned) |
| `replay_batches` / `replay_outbox`, рядків | 1001 / 1001 | 1001 / 1001 |
| unsent | 0 | 0 |
| md5 вмісту батчів | `b3050616c318257c845fdd9dc5462f08` | `b3050616c318257c845fdd9dc5462f08` |
| md5 вмісту outbox (id, sent, created_at, md5(payload)) | `93d7681bf548008184def51d4650d491` | `93d7681bf548008184def51d4650d491` |
| Пар batch/outbox з однаковим `created_at` | — | 1001 |
| Залишки `*_legacy` | — | 0 |

## Структура та розмір партицій

Стан після повторного replay `kaggle-cs` (`cleanup-public.json`):

| Партиція | Межі | Рядків | unsent / pending | Розмір |
|---|---|---:|---:|---:|
| `replay_batches_p20261119` | 2026-11-19 → 2026-11-20 | 1208 | 0 | 360 KiB |
| `replay_batches_p20261120` | 2026-11-20 → 2026-11-21 | 0 | 0 | 32 KiB |
| `replay_batches_default` | DEFAULT | 0 | 0 | 32 KiB |
| `replay_outbox_p20261119` | 2026-11-19 → 2026-11-20 | 1208 | 0 | 128,9 MiB |
| `replay_outbox_p20261120` | 2026-11-20 → 2026-11-21 | 0 | 0 | 24 KiB |
| `replay_outbox_default` | DEFAULT | 0 | 0 | 24 KiB |

Наскрізна перевірка шляху запису на партиціях (`replay-after-partitioning.json`):

- новий replay `kaggle-cs` (id `a8776ae9…`, 5000 док/с) завершився зі статусом `completed`: 20 675 / 20 675, `duplicates = 20 675`, `inserted = 0`, checkpoint 20 675;
- у лозі воркера 0 помилок;
- MongoDB, як і раніше, має 100 000 документів.

Плани запитів (`explain.txt`):

- dispatcher: `Merge Append` по часткових індексах `created_at` кожної партиції;
- `UPDATE … WHERE id AND created_at`: одна партиція;
- пошук батча в `complete()` з `created_at >= job.created_at`: старші партиції відсікаються.

## Retention (очищення старих партицій)

- **Політика:** день видаляється, якщо його кінець старший за `REPLAY_PARTITION_RETENTION_DAYS` (7) **і** виконано обидві умови:
  - у партиції outbox немає `sent = false`;
  - у партиції батчів немає `pending`-батчів. Інакше пізній completion не знайшов би батч.
- **Порядок видалення.** Перевірено на PG 16: пряме `DROP` партиції, на яку посилається FK, завершується помилкою `cannot drop table … because other objects depend on it`. Тому порядок такий:
  1. `DROP TABLE replay_outbox_pD`;
  2. `ALTER TABLE replay_batches DETACH PARTITION replay_batches_pD`;
  3. `DROP TABLE replay_batches_pD`.
- **Транзакції й блокування.** Кожен день обробляється в окремій короткій транзакції:
  1. advisory lock 912002;
  2. `LOCK TABLE replay_batches, replay_outbox IN ACCESS EXCLUSIVE MODE` із `lock_timeout` 5 с. Батьківські таблиці блокуються першими, у тому ж порядку, що й у воркера, щоб уникнути deadlock;
  3. повторна перевірка умов;
  4. DROP.

  Якщо блокування не вдалося, день отримує `skipped` і обробляється наступного циклу.
- **DEFAULT-партиції** ніколи не видаляються. Залишки в них потрапляють у звіт як WARNING.

### Реальне очищення на `public` (`cleanup-public.json`)

- Запуск `--cleanup` із TTL 7 днів нічого не видалив: усі дані сьогоднішні. Це очікуваний результат.
- `--cleanup --dry-run --now 2026-11-27T12:00:00+00:00` (`cleanup-public-dry-run-plus8d.*`) показує, що через 8 днів день 19.11 буде видалено:

  ```
  Partition retention day=2026-11-19 action=would_drop rows={'replay_batches': 1208, 'replay_outbox': 1208} unsent=0 pending=0 bytes=135495680
  ```

  Отже, звільниться ≈ 129 MiB.

### Видалення з backdated-даними на тій самій PostgreSQL (`retention-demo.*`)

`tools/partitioning/retention_demo.py` працює в окремій схемі `partition_retention_demo`, яку видаляє після завершення. Скрипт робить таке:

1. створює **старі** heap-таблиці з 240 батчами за 6 днів (вік 12, 10, 9, 8, 3 і 0 днів);
2. запускає ту саму міграцію, що й сервіс;
3. виконує цикли retention.

| День | Стан | Цикл 1 | Цикл 2 (після `sent=true` і completion) |
|---|---|---|---|
| 2026-11-07 (12 дн.) | усе відправлено | **dropped** | — |
| 2026-11-09 (10 дн.) | усе відправлено | **dropped** | — |
| 2026-11-10 (9 дн.) | 1 рядок `sent=false` | skipped (unsent=1) | **dropped** |
| 2026-11-11 (8 дн.) | 1 батч `pending` | skipped (pending=1) | **dropped** |
| 2026-11-16 (3 дн.) | у межах TTL | kept | kept |
| 2026-11-19 (сьогодні) | у межах TTL | kept | kept |

- Наприкінці лишилося 80 / 80 рядків: два дні в межах TTL.
- Третій цикл не мав що видаляти (ідемпотентність).
- Повний лог — у `retention-demo.log`.

## Тести

| Тест | Що перевіряє | Результат |
|---|---|---|
| `tests/test_partitioning.py` (7, без БД) | імена й межі партицій за UTC, TTL за кінцем дня, політика/env, порядок `DROP → DETACH → DROP`, пропуск днів із unsent/pending, dry-run без DDL, створення поточної, наступної та «застряглої в DEFAULT» партиції, ідемпотентність | 7 passed |
| `tests/test_postgres_runtime.py::test_partition_migration_default_rescue_and_retention` (реальна PG) | конвертація legacy-таблиць із backdated-даними (дві паралельні ініціалізації), відсутність `*_legacy`, рядок у DEFAULT → перенос у нову партицію, retention з обома запобіжниками, dry-run, повторне видалення | passed |
| `tests/test_postgres_runtime.py::test_postgres_jobs_outbox_reordering_and_restart` (реальна PG) | колишній сценарій produce/complete/restart уже на партиційованій схемі | passed |
| Повний набір `python -m pytest -q` | — | 71 passed, 4 skipped (тести реальної БД без `TEST_POSTGRES_URL`/`TEST_MONGO_URL`) |

Тести з реальною PG запускалися в одноразовому контейнері з образу ingestion у мережі `cs-sharded_default` з `TEST_POSTGRES_URL=postgresql://ingestion:…@competition_db:5432/ingestion`. Вони працюють в ізольованих схемах `test_*` і після завершення видаляють їх. Результат: 9 passed.

## Обмеження

- Партиції подобові. При нинішньому темпі (до ~130 MB/день під час повного імпорту) вистачило б і помісячних. Але подобові дають дрібніший крок retention, і DROP звільняє місце одразу, без `VACUUM`.
- Збій з'єднання між `DROP` outbox і `DETACH` батчів неможливий: усе виконується в одній транзакції дня.
- `DETACH … CONCURRENTLY` не використовується, бо він не працює в транзакції. Блокування батьківських таблиць триває мілісекунди.
- Ім'я FK `replay_batches_job_id_fkey1` на стенді має суфікс `1`, бо під час міграції ще існувало старе обмеження з тим самим ім'ям. На роботу це не впливає.
