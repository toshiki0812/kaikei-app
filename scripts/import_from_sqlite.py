"""ローカルのSQLite（data/kakei.db）から、クラウドのPostgreSQLへ一回だけデータを移す。

クラウド化より前にこのアプリを使っていて、家計データが data/kakei.db に
残っている場合に使う。Postgres側が既にデータを持っているテーブルはスキップする
（誤って上書き・重複させないため）。

使い方:
    export DATABASE_URL="postgresql://..."   # 移行先（Cloud SQL など）
    ./venv/bin/python scripts/import_from_sqlite.py [data/kakei.dbのパス]
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

# (テーブル名, 列名リスト) を外部キーの依存順に並べる
TABLES = [
    ("people", ["id", "name", "display_order"]),
    ("plans", ["id", "name", "description", "display_order", "created_at"]),
    ("app_state", ["key", "value"]),
    ("plan_settings", ["plan_id", "simulation_start_month", "starting_balance_month",
                       "expected_annual_return_pct", "compounding"]),
    ("plan_person_assumptions", ["plan_id", "person_id", "monthly_income_assumption",
                                 "monthly_credit_card_assumption", "rent_assumption",
                                 "investment_contribution_assumption", "other_expense_assumption",
                                 "other_cash_expense_assumption", "starting_cash_balance",
                                 "starting_investment_balance", "cash_sweep_threshold"]),
    ("monthly_person_actuals", ["id", "person_id", "month", "income", "rent",
                                "investment_contribution", "other_expense",
                                "bank_cash_balance_eom", "investment_balance_eom", "notes"]),
    ("credit_cards", ["id", "name", "owner_person_id"]),
    ("csv_import_batches", ["id", "card_id", "imported_at", "filename", "row_count",
                            "skipped_duplicate_count", "total_amount"]),
    ("credit_card_transactions", ["id", "card_id", "txn_date", "month", "description",
                                  "amount", "category", "import_batch_id"]),
    ("monthly_credit_card_actuals", ["id", "person_id", "month", "amount", "source"]),
    ("planned_items", ["id", "plan_id", "item_type", "label", "amount", "person_id",
                       "recurrence", "month", "month_of_year", "start_year", "end_year", "notes"]),
]


def main():
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else "data/kakei.db"
    if not os.path.exists(sqlite_path):
        print(f"SQLiteファイルが見つかりません: {sqlite_path}")
        return 1

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row

    with db.get_connection() as conn:
        # db.init_db() は呼ばない。デフォルト値が先に入ると「既にデータあり」と
        # 判定されて本来の移行データがスキップされてしまうため、テーブル定義だけを作る。
        with open(db.SCHEMA_PATH, encoding="utf-8") as f:
            conn.execute(f.read())

        existing_tables = {
            r["table_name"] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
            ).fetchall()
        }

        for table, cols in TABLES:
            if not src.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                print(f"  スキップ: {table}（SQLite側に無い）")
                continue
            if table not in existing_tables:
                print(f"  スキップ: {table}（移行先に無い）")
                continue

            already = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            if already > 0:
                print(f"  スキップ: {table}（移行先に既に{already}件あり、二重取込を避けるため）")
                continue

            rows = src.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
            if not rows:
                print(f"  0件: {table}")
                continue

            placeholders = ", ".join("%s" for _ in cols)
            for r in rows:
                conn.execute(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                    tuple(r[c] for c in cols),
                )
            print(f"  {len(rows)}件を移行: {table}")

        db._sync_identity_sequences(conn)

    src.close()
    db.init_db()  # 移行後、足りない行（デフォルトプランの設定など）があれば補う
    print("\n完了しました。アプリを開いて内容を確認してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
