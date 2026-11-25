# Коміт 4: `docs`

Файли: `docs/`, `README.md`, `CLAUDE.md`, `tools/README.md`, `tools/documentation/update_query_catalog.py`, ця нотатка.

| Файл | Що змінилось |
|---|---|
| `docs/coursework/high-load-plan.md` | новий: вимоги, знайдені проблеми, етапи, прогони, ресурси, ризики (без бонусів) |
| `docs/project-decisions.md` | рішення D71–D77 |
| `docs/stages9-12-runtime.md` | новий розділ «High-load writing», оновлені правила черг, темпу й outbox |
| `docs/stages9-12-queries.md` | перегенеровано скриптом, тому diff великий; вручну змінено лише кілька абзаців |
| `README.md`, `CLAUDE.md`, `tools/README.md` | короткі інструкції |
| `update_query_catalog.py` | бере в каталог нові функції |

## Рішення коротко

- **D71** навантажувальні дані в окремому scope `load-cs`
- **D72** документ є функцією від `(job, номер)`, ID відтворюється
- **D73** bulk у тій самій транзакції, лічильник на 64 слоти
- **D74** outbox PostgreSQL зберігає посилання, а не тексти
- **D75** збій кластера не витрачає спроб
- **D76** часткове видалення лише для `load-cs`
- **D77** бонуси не робимо

## Чого тут немає

- Звіт DOCX не змінював: для нього потрібні числа прогонів.
- Діаграми топології та модулів не оновлені (новий `content_dispatcher`, `/cluster/status`): це етап 7.
- `docs/code-inventory.md` і `service-structure.md` генеруються окремим скриптом, його не запускав.
