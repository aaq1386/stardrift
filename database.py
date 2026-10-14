"""SQLite persistence layer for STARDRIFT."""

import json
import os
import shutil
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from settings import SAVE_FILE


PROJECT_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = 1


def _default_database_path():
    """Use project data in development and writable user data when frozen."""
    if not getattr(sys, "frozen", False):
        return PROJECT_DIR / "data" / "stardrift.db"

    if os.name == "nt":
        data_home = Path(
            os.environ.get(
                "LOCALAPPDATA",
                Path.home() / "AppData" / "Local",
            )
        )
    else:
        data_home = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
    user_data_dir = data_home / "stardrift"
    user_database = user_data_dir / "stardrift.db"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    # Seed the user's database from the packaged copy on first launch only.
    bundled_root = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
    bundled_database = bundled_root / "data" / "stardrift.db"

    if not user_database.exists() and bundled_database.is_file():
        shutil.copy2(bundled_database, user_database)

    return user_database


DATABASE_FILE = _default_database_path()


class Database:
    """Manages persistent player data, upgrades and credit transactions."""

    def __init__(self, database_path=DATABASE_FILE):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize()
        self._migrate_legacy_save()

    def _connect(self):
        connection = sqlite3.connect(
            str(self.database_path),
            timeout=10,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self):
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS player_profile (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        credits INTEGER NOT NULL DEFAULT 0
                            CHECK (credits >= 0),
                        high_score INTEGER NOT NULL DEFAULT 0
                            CHECK (high_score >= 0),
                        best_level INTEGER NOT NULL DEFAULT 1
                            CHECK (best_level >= 1),
                        games_played INTEGER NOT NULL DEFAULT 0,
                        bricks_destroyed INTEGER NOT NULL DEFAULT 0,
                        stages_cleared INTEGER NOT NULL DEFAULT 0,
                        paddle_hits INTEGER NOT NULL DEFAULT 0
                    )
                """)

                connection.execute("""
                    CREATE TABLE IF NOT EXISTS upgrades (
                        upgrade_key TEXT PRIMARY KEY,
                        level INTEGER NOT NULL DEFAULT 0
                            CHECK (level >= 0)
                    )
                """)

                connection.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        amount INTEGER NOT NULL,
                        kind TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT
                            (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    )
                """)

                connection.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    )
                """)

                connection.execute("""
                    INSERT OR IGNORE INTO player_profile (id)
                    VALUES (1)
                """)

                connection.execute("""
                    INSERT OR IGNORE INTO metadata (key, value)
                    VALUES ('schema_version', ?)
                """, (str(SCHEMA_VERSION),))

    def _migrate_legacy_save(self):
        """Import the old JSON save once, without overwriting existing data."""
        legacy_file = PROJECT_DIR / SAVE_FILE

        with closing(self._connect()) as connection:
            with connection:
                migrated = connection.execute(
                    "SELECT value FROM metadata WHERE key = 'legacy_json_migrated'"
                ).fetchone()

                if migrated is not None:
                    return

                profile = connection.execute(
                    "SELECT high_score, best_level FROM player_profile WHERE id = 1"
                ).fetchone()

                if profile["high_score"] == 0 and profile["best_level"] == 1:
                    try:
                        with legacy_file.open("r", encoding="utf-8") as file:
                            old_data = json.load(file)

                        high_score = max(
                            0, int(old_data.get("high_score", 0))
                        )
                        best_level = max(
                            1, int(old_data.get("best_level", 1))
                        )
                    except (
                        OSError,
                        ValueError,
                        TypeError,
                        json.JSONDecodeError,
                    ):
                        high_score = 0
                        best_level = 1

                    connection.execute("""
                        UPDATE player_profile
                        SET high_score = ?, best_level = ?
                        WHERE id = 1
                    """, (high_score, best_level))

                connection.execute("""
                    INSERT INTO metadata (key, value)
                    VALUES ('legacy_json_migrated', '1')
                """)

    def get_profile(self):
        with closing(self._connect()) as connection:
            row = connection.execute("""
                SELECT credits, high_score, best_level,
                       games_played, bricks_destroyed,
                       stages_cleared, paddle_hits
                FROM player_profile
                WHERE id = 1
            """).fetchone()
            return dict(row)

    def get_upgrades(self):
        with closing(self._connect()) as connection:
            rows = connection.execute("""
                SELECT upgrade_key, level
                FROM upgrades
                ORDER BY upgrade_key
            """).fetchall()
            return {row["upgrade_key"]: row["level"] for row in rows}

    def get_setting(self, key, default=None):
        """Read a persistent key/value setting from metadata."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?", (str(key),)
            ).fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        """Persist a key/value setting in metadata."""
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    INSERT INTO metadata (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (str(key), str(value)))

    def save_progress(self, high_score, best_level):
        """Persist personal records without ever lowering them."""
        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    UPDATE player_profile
                    SET high_score = MAX(high_score, ?),
                        best_level = MAX(best_level, ?)
                    WHERE id = 1
                """, (
                    max(0, int(high_score)),
                    max(1, int(best_level)),
                ))

    def add_credits(self, amount, reason):
        """Atomically add credits and record the transaction."""
        amount = int(amount)
        if amount <= 0:
            raise ValueError("Credit reward must be a positive integer.")

        with closing(self._connect()) as connection:
            with connection:
                connection.execute("""
                    UPDATE player_profile
                    SET credits = credits + ?
                    WHERE id = 1
                """, (amount,))

                connection.execute("""
                    INSERT INTO transactions (amount, kind, reason)
                    VALUES (?, 'earning', ?)
                """, (amount, str(reason)))

    def record_stat(self, stat_name, amount=1):
        """Increment an allowed cumulative player statistic."""
        allowed_stats = {
            "games_played",
            "bricks_destroyed",
            "stages_cleared",
            "paddle_hits",
        }

        if stat_name not in allowed_stats:
            raise ValueError(f"Unsupported statistic: {stat_name}")

        amount = int(amount)
        if amount < 0:
            raise ValueError("Statistic increment cannot be negative.")

        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    f"UPDATE player_profile "
                    f"SET {stat_name} = {stat_name} + ? WHERE id = 1",
                    (amount,),
                )

    def spend_credits(self, amount, reason):
        """Atomically spend credits and record the transaction."""
        amount = int(amount)
        if amount <= 0:
            raise ValueError("Credit cost must be a positive integer.")

        with closing(self._connect()) as connection:
            with connection:
                debit = connection.execute("""
                    UPDATE player_profile
                    SET credits = credits - ?
                    WHERE id = 1 AND credits >= ?
                """, (amount, amount))

                if debit.rowcount != 1:
                    return False

                connection.execute("""
                    INSERT INTO transactions (amount, kind, reason)
                    VALUES (?, 'purchase', ?)
                """, (-amount, str(reason)))

        return True

    def purchase_upgrade(self, upgrade_key, expected_level, price, max_level):
        """Atomically charge credits and upgrade a player's item."""
        upgrade_key = str(upgrade_key)
        expected_level = int(expected_level)
        price = int(price)
        max_level = int(max_level)

        if not upgrade_key or expected_level < 0 or price <= 0:
            return False, "invalid_purchase"

        if max_level < 1 or expected_level >= max_level:
            return False, "max_level"

        with closing(self._connect()) as connection:
            with connection:
                current = connection.execute(
                    "SELECT level FROM upgrades WHERE upgrade_key = ?",
                    (upgrade_key,),
                ).fetchone()

                current_level = current["level"] if current else 0

                if current_level != expected_level:
                    return False, "level_changed"

                if current_level >= max_level:
                    return False, "max_level"

                debit = connection.execute("""
                    UPDATE player_profile
                    SET credits = credits - ?
                    WHERE id = 1 AND credits >= ?
                """, (price, price))

                if debit.rowcount != 1:
                    return False, "insufficient_credits"

                connection.execute("""
                    INSERT INTO upgrades (upgrade_key, level)
                    VALUES (?, ?)
                    ON CONFLICT(upgrade_key)
                    DO UPDATE SET level = excluded.level
                """, (upgrade_key, current_level + 1))

                connection.execute("""
                    INSERT INTO transactions (amount, kind, reason)
                    VALUES (?, 'purchase', ?)
                """, (-price, f"upgrade:{upgrade_key}:level:{current_level + 1}"))

        return True, current_level + 1
