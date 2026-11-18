#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path
import asyncpg


def setup_logging() -> logging.Logger:
    log_dir = Path(os.getenv("LOG_DIR", "/app/logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "competition_smoke_test.log"

    logger = logging.getLogger("competition_service.smoke_test")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def mask_db_url(url: str) -> str:
    if "@" in url and ":" in url.split("@")[0]:
        prefix, rest = url.split("://", 1)
        user_pass, host_part = rest.split("@", 1)
        user = user_pass.split(":")[0]
        return f"{prefix}://{user}:***@{host_part}"
    return url


async def run_smoke_test():
    logger = setup_logging()
    logger.info("==================================================================")
    logger.info("Ініціалізація процедури Smoke Test для competition_service (CS2)")
    logger.info("==================================================================")

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@competition_db:5432/cs2_db",
    )
    logger.info(f"Цільова адреса підключення до PostgreSQL: {mask_db_url(database_url)}")

    conn = None
    retries = 15
    retry_delay = 2.0
    for attempt in range(1, retries + 1):
        try:
            conn = await asyncpg.connect(database_url)
            logger.info(f"TCP-з'єднання з базою даних успішно встановлено (спроба {attempt}/{retries})")
            break
        except Exception as e:
            logger.warning(
                f"Очікування готовності PostgreSQL (спроба {attempt}/{retries}): {e}. "
                f"Повторний запит через {retry_delay} сек..."
            )
            await asyncio.sleep(retry_delay)

    if not conn:
        logger.error("Критична помилка: не вдалося встановити підключення до PostgreSQL після вичерпання спроб.")
        sys.exit(1)

    try:
        logger.info("Створення/перевірка цілісності схеми таблиці 'players'...")
        ddl_query = """
        CREATE TABLE IF NOT EXISTS players (
            id UUID PRIMARY KEY,
            version INT NOT NULL DEFAULT 1,
            nickname VARCHAR(64) NOT NULL,
            real_name VARCHAR(128),
            country_code VARCHAR(3),
            role VARCHAR(32),
            external_source VARCHAR(64),
            external_player_id VARCHAR(64)
        );
        """
        await conn.execute(ddl_query)
        logger.debug("DDL-запит успішно виконано (схема таблиці 'players' валідована).")

        test_player_id = uuid.uuid4()
        test_player = {
            "id": test_player_id,
            "version": 1,
            "nickname": "s1mple",
            "real_name": "Oleksandr Kostyliev",
            "country_code": "UA",
            "role": "AWPer",
            "external_source": "kaggle_counter_strike_pro_matches",
            "external_player_id": "7998",
        }

        logger.info(f"Виконання операції запису (INSERT) гравця: '{test_player['nickname']}' (UUID: {test_player_id})")
        insert_query = """
        INSERT INTO players (id, version, nickname, real_name, country_code, role, external_source, external_player_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, nickname;
        """
        inserted_row = await conn.fetchrow(
            insert_query,
            test_player["id"],
            test_player["version"],
            test_player["nickname"],
            test_player["real_name"],
            test_player["country_code"],
            test_player["role"],
            test_player["external_source"],
            test_player["external_player_id"],
        )
        logger.info(f"Запис успішно зафіксовано в PostgreSQL: ID={inserted_row['id']}, Нікнейм='{inserted_row['nickname']}'")

        logger.info(f"Виконання операції зчитування (SELECT) за ідентифікатором UUID: {test_player_id}")
        select_query = """
        SELECT id, version, nickname, real_name, country_code, role, external_source, external_player_id
        FROM players
        WHERE id = $1;
        """
        selected_row = await conn.fetchrow(select_query, test_player_id)

        if not selected_row:
            logger.error("Невідповідність даних: запит SELECT не повернув щойно створений запис!")
            raise AssertionError("Запис не знайдено в базі даних після вставки.")

        logger.info("Результат зчитування з бази даних:")
        logger.info(f"   • ID гравця:        {selected_row['id']}")
        logger.info(f"   • Нікнейм:          {selected_row['nickname']}")
        logger.info(f"   • Справжнє ім'я:    {selected_row['real_name']}")
        logger.info(f"   • Країна:           {selected_row['country_code']}")
        logger.info(f"   • Роль:             {selected_row['role']}")
        logger.info(f"   • Джерело даних:    {selected_row['external_source']} (ID: {selected_row['external_player_id']})")

        assert str(selected_row["id"]) == str(test_player["id"]), "Помилка валідації поля 'id'"
        assert selected_row["nickname"] == test_player["nickname"], "Помилка валідації поля 'nickname'"
        assert selected_row["real_name"] == test_player["real_name"], "Помилка валідації поля 'real_name'"
        assert selected_row["country_code"] == test_player["country_code"], "Помилка валідації поля 'country_code'"
        assert selected_row["role"] == test_player["role"], "Помилка валідації поля 'role'"
        logger.info("Валідація цілісності атрибутів: УСПІШНО (100% відповідність збережених полів).")

        logger.info("==================================================================")
        logger.info("Smoke Test завершено успішно: зв'язок App <-> PostgreSQL підтверджено.")
        logger.info("Персистентний лог збережено за шляхом: /app/logs/competition_smoke_test.log")
        logger.info("==================================================================")

    except Exception as ex:
        logger.exception(f"Критичний збій під час виконання тестового сценарію: {ex}")
        sys.exit(1)
    finally:
        await conn.close()
        logger.debug("Асинхронне TCP-з'єднання з базою даних закрито.")


if __name__ == "__main__":
    asyncio.run(run_smoke_test())