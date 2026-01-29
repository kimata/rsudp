"""SQLite スキーマユーティリティ."""

import pathlib
import sqlite3

import my_lib.sqlite_util

_SCHEMA_FILE = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


def init_database(conn: sqlite3.Connection, table_name: str) -> None:
    """
    スキーマファイルから指定されたテーブルとインデックスを初期化する.

    Args:
        conn: SQLite 接続
        table_name: 初期化するテーブル名

    """
    my_lib.sqlite_util.init_table_from_schema(conn, table_name, _SCHEMA_FILE)
