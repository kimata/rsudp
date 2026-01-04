"""SQLite スキーマユーティリティ."""

import pathlib
import sqlite3

_SCHEMA_FILE = pathlib.Path(__file__).parent.parent.parent / "schema" / "sqlite.schema"


def init_database(conn: sqlite3.Connection, table_name: str) -> None:
    """
    スキーマファイルから指定されたテーブルとインデックスを初期化する.

    Args:
        conn: SQLite 接続
        table_name: 初期化するテーブル名

    """
    schema_content = _SCHEMA_FILE.read_text(encoding="utf-8")

    # スキーマを個別のステートメントに分割
    statements = [s.strip() for s in schema_content.split(";") if s.strip()]

    for statement in statements:
        # コメント行のみの場合はスキップ
        lines = [line for line in statement.split("\n") if not line.strip().startswith("--")]
        clean_statement = "\n".join(lines).strip()
        if not clean_statement:
            continue

        # 指定されたテーブルに関連するステートメントのみ実行
        if f"TABLE IF NOT EXISTS {table_name}" in statement or f"ON {table_name}" in statement:
            conn.execute(statement)
