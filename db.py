"""PostgreSQL接続とCRUDヘルパー。

夫婦二人が外出先からも同じデータを見られるよう、保存先はクラウドのPostgreSQL。
接続先は次の順で探す:
  1. Streamlit の secrets（`database_url`）… クラウド・ローカルとも通常はこれ
  2. 環境変数 `DATABASE_URL` … テストやスクリプト実行用

接続情報が無い場合は例外 `DatabaseNotConfigured` を投げ、app.py が設定手順を表示する。
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime

import pandas as pd
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")

DEFAULT_PEOPLE = [(1, "夫", 0), (2, "妻", 1)]


class DatabaseNotConfigured(RuntimeError):
    """接続先が未設定。app.py が案内画面を出すために使う。"""


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    try:  # streamlit が無い環境（スクリプト実行）でも動くようにする
        import streamlit as st
        url = st.secrets.get("database_url")
    except Exception:
        url = None
    if not url or url.startswith("ここに"):
        raise DatabaseNotConfigured(
            "データベースの接続先が設定されていません。"
            ".streamlit/secrets.toml に database_url を設定してください。"
        )
    return url


_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """接続プール。毎回つなぎ直すとクラウドDBでは遅いので使い回す。"""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            _dsn(), min_size=1, max_size=4, open=True,
            kwargs={"row_factory": dict_row, "autocommit": False},
        )
    return _pool


@contextmanager
def get_connection():
    """`with get_connection() as conn:` で使う。正常終了時にコミットされる。"""
    with _get_pool().connection() as conn:
        yield conn


def reset_pool():
    """接続先を変えたときに使う（テスト用）。"""
    global _pool, _initialized
    if _pool is not None:
        _pool.close()
        _pool = None
    _initialized = False


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s",
        (name,),
    ).fetchone() is not None


def _sync_identity_sequences(conn):
    """明示idを入れたあと、自動採番の次の値を最大id+1に合わせる。

    これをしないと、移行で id=1,2 を直接入れたテーブルに後から追加したとき
    採番が1から始まって主キー衝突する。
    """
    tables = ("people", "plans", "monthly_person_actuals", "credit_cards",
              "csv_import_batches", "credit_card_transactions",
              "monthly_credit_card_actuals", "planned_items",
              "plan_assumption_periods", "plan_real_estate")
    for t in tables:
        if not _table_exists(conn, t):
            continue
        conn.execute(
            f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
            f"COALESCE((SELECT MAX(id) FROM {t}), 1), (SELECT COUNT(*) > 0 FROM {t}))"
        )


def _set_state(conn, key: str, value: str):
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, value),
    )


def _ensure_plan_rows(conn, plan_id: int):
    """プランに設定行・人ごとの想定値行が無ければデフォルトで作る。"""
    exists = conn.execute(
        "SELECT 1 FROM plan_settings WHERE plan_id = %s", (plan_id,)
    ).fetchone()
    if not exists:
        this_month = datetime.now().strftime("%Y-%m")
        conn.execute(
            """INSERT INTO plan_settings
               (plan_id, simulation_start_month, starting_balance_month,
                expected_annual_return_pct, compounding)
               VALUES (%s, %s, %s, 5.0, 'monthly')""",
            (plan_id, this_month, this_month),
        )
    for row in conn.execute("SELECT id FROM people").fetchall():
        conn.execute(
            "INSERT INTO plan_person_assumptions (plan_id, person_id) VALUES (%s, %s) "
            "ON CONFLICT (plan_id, person_id) DO NOTHING",
            (plan_id, row["id"]),
        )


_initialized = False


def init_db():
    """テーブル作成・初期データ確認を行う。

    app.py がページ操作のたびに毎回呼ぶため、同じプロセス内では最初の1回だけ
    実際にDBへ問い合わせる（テーブル作成は毎回やり直す必要が無く、クラウドDBへの
    往復が積み重なって体感速度を落とすため）。接続先を切り替えるテスト・スクリプトは
    reset_pool() とあわせてこのフラグもリセットする。
    """
    global _initialized
    if _initialized:
        return

    with get_connection() as conn:
        # plan_real_estate は公開前に「一括購入」モデルから「月々の返済額」モデルへ
        # 作り直した。まだ中身の入っていない暫定テーブルだったため、データ移行はせず
        # 旧カラムが残っていれば作り直す。
        if _table_exists(conn, "plan_real_estate"):
            has_old_col = conn.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'plan_real_estate' AND column_name = 'purchase_price'"
            ).fetchone()
            if has_old_col:
                conn.execute("DROP TABLE plan_real_estate")

        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.execute(f.read())

        if not conn.execute("SELECT 1 FROM people LIMIT 1").fetchone():
            for pid, name, order in DEFAULT_PEOPLE:
                conn.execute(
                    "INSERT INTO people (id, name, display_order) VALUES (%s, %s, %s)",
                    (pid, name, order),
                )

        if not conn.execute("SELECT 1 FROM plans LIMIT 1").fetchone():
            conn.execute(
                "INSERT INTO plans (name, description, display_order, created_at) "
                "VALUES (%s, %s, 0, %s)",
                ("プランA", "最初のプラン", datetime.now().isoformat(timespec="seconds")),
            )

        _sync_identity_sequences(conn)

        for row in conn.execute("SELECT id FROM plans").fetchall():
            _ensure_plan_rows(conn, row["id"])

        if not conn.execute(
            "SELECT 1 FROM app_state WHERE key = 'active_plan_id'"
        ).fetchone():
            first = conn.execute(
                "SELECT id FROM plans ORDER BY display_order, id LIMIT 1"
            ).fetchone()
            _set_state(conn, "active_plan_id", str(first["id"]))

    _initialized = True


# ---------- people ----------

def get_people() -> list[dict]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM people ORDER BY display_order, id").fetchall()


def update_person_name(person_id: int, name: str):
    with get_connection() as conn:
        conn.execute("UPDATE people SET name = %s WHERE id = %s", (name, person_id))


# ---------- plans ----------

def get_plans() -> list[dict]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM plans ORDER BY display_order, id").fetchall()


def get_plan(plan_id: int) -> dict | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM plans WHERE id = %s", (plan_id,)).fetchone()


def get_active_plan_id() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_state WHERE key = 'active_plan_id'"
        ).fetchone()
        if row:
            plan_id = int(row["value"])
            if conn.execute("SELECT 1 FROM plans WHERE id = %s", (plan_id,)).fetchone():
                return plan_id
        # 保存されたプランが消えている場合は先頭のプランに戻す
        first = conn.execute(
            "SELECT id FROM plans ORDER BY display_order, id LIMIT 1"
        ).fetchone()
        return int(first["id"])


def set_active_plan_id(plan_id: int):
    with get_connection() as conn:
        _set_state(conn, "active_plan_id", str(plan_id))


# シミュレーション期間は「どこまで先を見たいか」という見方の設定なので、
# プランごとではなくアプリ全体で1つ持つ（プラン比較でも期間が揃う）。
DEFAULT_HORIZON_YEARS = 10


def get_horizon_years() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_state WHERE key = 'horizon_years'").fetchone()
        return int(row["value"]) if row else DEFAULT_HORIZON_YEARS


def set_horizon_years(years: int):
    with get_connection() as conn:
        _set_state(conn, "horizon_years", str(int(years)))


def get_state(key: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM app_state WHERE key = %s", (key,)).fetchone()
        return row["value"] if row else None


def clear_state(key: str):
    with get_connection() as conn:
        conn.execute("DELETE FROM app_state WHERE key = %s", (key,))


PERSON_ASSUMPTION_FIELDS = (
    "monthly_income_assumption", "monthly_credit_card_assumption", "rent_assumption",
    "investment_contribution_assumption", "other_expense_assumption",
    "other_cash_expense_assumption", "starting_cash_balance",
    "starting_investment_balance", "cash_sweep_threshold",
)

# 期間指定で上書きできるのは毎月の想定額のみ（開始残高やしきい値は時点の値なので対象外）
ASSUMPTION_PERIOD_FIELDS = (
    "monthly_income_assumption", "monthly_credit_card_assumption", "rent_assumption",
    "investment_contribution_assumption", "other_expense_assumption",
    "other_cash_expense_assumption",
)


def create_plan(name: str, copy_from_plan_id: int | None = None,
                description: str | None = None) -> int:
    """新しいプランを作る。コピー元を指定すると想定値と臨時収支をまるごと複製する。"""
    with get_connection() as conn:
        order = conn.execute(
            "SELECT COALESCE(MAX(display_order), -1) + 1 AS n FROM plans"
        ).fetchone()["n"]
        new_id = conn.execute(
            "INSERT INTO plans (name, description, display_order, created_at) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (name, description, order, datetime.now().isoformat(timespec="seconds")),
        ).fetchone()["id"]

        if copy_from_plan_id is not None:
            conn.execute(
                """INSERT INTO plan_settings
                   (plan_id, simulation_start_month, starting_balance_month,
                    expected_annual_return_pct, compounding)
                   SELECT %s, simulation_start_month, starting_balance_month,
                          expected_annual_return_pct, compounding
                   FROM plan_settings WHERE plan_id = %s""",
                (new_id, copy_from_plan_id),
            )
            fields = ", ".join(PERSON_ASSUMPTION_FIELDS)
            conn.execute(
                f"""INSERT INTO plan_person_assumptions (plan_id, person_id, {fields})
                    SELECT %s, person_id, {fields}
                    FROM plan_person_assumptions WHERE plan_id = %s""",
                (new_id, copy_from_plan_id),
            )
            conn.execute(
                """INSERT INTO planned_items
                   (plan_id, item_type, label, amount, person_id, recurrence, month,
                    month_of_year, start_year, end_year, notes)
                   SELECT %s, item_type, label, amount, person_id, recurrence, month,
                          month_of_year, start_year, end_year, notes
                   FROM planned_items WHERE plan_id = %s""",
                (new_id, copy_from_plan_id),
            )
            conn.execute(
                """INSERT INTO plan_assumption_periods
                   (plan_id, person_id, field, start_month, end_month, amount)
                   SELECT %s, person_id, field, start_month, end_month, amount
                   FROM plan_assumption_periods WHERE plan_id = %s""",
                (new_id, copy_from_plan_id),
            )
            conn.execute(
                """INSERT INTO plan_real_estate
                   (plan_id, person_id, label, purchase_month, monthly_payment,
                    loan_term_months, annual_appreciation_pct, notes)
                   SELECT %s, person_id, label, purchase_month, monthly_payment,
                          loan_term_months, annual_appreciation_pct, notes
                   FROM plan_real_estate WHERE plan_id = %s""",
                (new_id, copy_from_plan_id),
            )

        _ensure_plan_rows(conn, new_id)
        return new_id


def rename_plan(plan_id: int, name: str, description: str | None = None):
    with get_connection() as conn:
        conn.execute("UPDATE plans SET name = %s, description = %s WHERE id = %s",
                     (name, description, plan_id))


def delete_plan(plan_id: int) -> bool:
    """プランを削除する。最後の1件は削除できない（戻り値 False）。"""
    with get_connection() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM plans").fetchone()["n"]
        if n <= 1:
            return False
        for table in ("planned_items", "plan_assumption_periods", "plan_real_estate",
                      "plan_person_assumptions", "plan_settings"):
            conn.execute(f"DELETE FROM {table} WHERE plan_id = %s", (plan_id,))
        conn.execute("DELETE FROM plans WHERE id = %s", (plan_id,))

        active = conn.execute(
            "SELECT value FROM app_state WHERE key = 'active_plan_id'").fetchone()
        if active and int(active["value"]) == plan_id:
            first = conn.execute(
                "SELECT id FROM plans ORDER BY display_order, id LIMIT 1").fetchone()
            _set_state(conn, "active_plan_id", str(first["id"]))
        return True


# ---------- settings（プランごと） ----------

def get_settings(plan_id: int) -> dict:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM plan_settings WHERE plan_id = %s", (plan_id,)).fetchone()


def update_settings(plan_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE plan_settings SET {cols} WHERE plan_id = %s",
                     list(fields.values()) + [plan_id])


# ---------- 人ごとの想定値（プラン×人） ----------

def get_person_assumptions(plan_id: int) -> dict:
    """{person_id: {項目名: 値}}"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM plan_person_assumptions WHERE plan_id = %s", (plan_id,)
        ).fetchall()
        return {r["person_id"]: r for r in rows}


def update_person_assumptions(plan_id: int, person_id: int, **fields):
    unknown = set(fields) - set(PERSON_ASSUMPTION_FIELDS)
    if unknown:
        raise ValueError(f"未知の想定値項目: {sorted(unknown)}")
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO plan_person_assumptions (plan_id, person_id) VALUES (%s, %s) "
            "ON CONFLICT (plan_id, person_id) DO NOTHING",
            (plan_id, person_id),
        )
        conn.execute(
            f"UPDATE plan_person_assumptions SET {cols} "
            f"WHERE plan_id = %s AND person_id = %s",
            list(fields.values()) + [plan_id, person_id],
        )


# ---------- credit cards ----------

def get_credit_cards() -> list[dict]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM credit_cards ORDER BY id").fetchall()


def get_credit_card(card_id: int) -> dict | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM credit_cards WHERE id = %s", (card_id,)).fetchone()


def add_credit_card(name: str, owner_person_id: int | None):
    with get_connection() as conn:
        conn.execute("INSERT INTO credit_cards (name, owner_person_id) VALUES (%s, %s)",
                     (name, owner_person_id))


def update_credit_card(card_id: int, name: str, owner_person_id: int | None):
    with get_connection() as conn:
        conn.execute("UPDATE credit_cards SET name = %s, owner_person_id = %s WHERE id = %s",
                     (name, owner_person_id, card_id))


def delete_credit_card(card_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM credit_card_transactions WHERE card_id = %s", (card_id,))
        conn.execute("DELETE FROM csv_import_batches WHERE card_id = %s", (card_id,))
        conn.execute("DELETE FROM credit_cards WHERE id = %s", (card_id,))


# ---------- 月次実績（人ごと・全プラン共通） ----------

PERSON_ACTUAL_FIELDS = ("income", "rent", "investment_contribution", "other_expense",
                        "bank_cash_balance_eom", "investment_balance_eom", "notes")


def get_month_person_actuals(month: str) -> dict:
    """{person_id: {項目名: 値}}。未入力の項目は None。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM monthly_person_actuals WHERE month = %s", (month,)
        ).fetchall()
        return {r["person_id"]: r for r in rows}


def upsert_person_actual(person_id: int, month: str, **fields):
    """渡したフィールドだけ更新する（部分更新）。None を渡すと未入力に戻る。"""
    unknown = set(fields) - set(PERSON_ACTUAL_FIELDS)
    if unknown:
        raise ValueError(f"未知の実績項目: {sorted(unknown)}")
    if not fields:
        return
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO monthly_person_actuals (person_id, month) VALUES (%s, %s) "
            "ON CONFLICT (person_id, month) DO NOTHING",
            (person_id, month),
        )
        cols = ", ".join(f"{k} = %s" for k in fields)
        conn.execute(
            f"UPDATE monthly_person_actuals SET {cols} WHERE person_id = %s AND month = %s",
            list(fields.values()) + [person_id, month],
        )


def get_all_person_actuals() -> pd.DataFrame:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM monthly_person_actuals").fetchall()
    return pd.DataFrame(rows, columns=["id", "person_id", "month", *PERSON_ACTUAL_FIELDS])


# ---------- credit card transactions / CSV import ----------

def create_import_batch(card_id: int, filename: str, row_count: int,
                        skipped_duplicate_count: int, total_amount: int) -> int:
    with get_connection() as conn:
        return conn.execute(
            """INSERT INTO csv_import_batches
               (card_id, imported_at, filename, row_count, skipped_duplicate_count, total_amount)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (card_id, datetime.now().isoformat(timespec="seconds"), filename,
             row_count, skipped_duplicate_count, total_amount),
        ).fetchone()["id"]


def insert_transactions(card_id: int, rows: list[dict], import_batch_id: int) -> tuple[int, int]:
    """rows: [{'txn_date','month','description','amount'}]
    戻り値: (挿入件数, 重複でスキップされた件数)
    """
    inserted = 0
    with get_connection() as conn:
        for r in rows:
            cur = conn.execute(
                """INSERT INTO credit_card_transactions
                   (card_id, txn_date, month, description, amount, import_batch_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (card_id, txn_date, description, amount) DO NOTHING""",
                (card_id, r["txn_date"], r["month"], r["description"], r["amount"],
                 import_batch_id),
            )
            if cur.rowcount > 0:
                inserted += 1
    return inserted, len(rows) - inserted


def update_import_batch(batch_id: int, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE csv_import_batches SET {cols} WHERE id = %s",
                     list(fields.values()) + [batch_id])


def get_months_touched_by_batch(import_batch_id: int) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT month FROM credit_card_transactions WHERE import_batch_id = %s",
            (import_batch_id,),
        ).fetchall()
        return [r["month"] for r in rows]


def get_credit_card_transactions_for_month(month: str) -> pd.DataFrame:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT t.*, c.name AS card_name FROM credit_card_transactions t
               JOIN credit_cards c ON c.id = t.card_id
               WHERE t.month = %s ORDER BY t.txn_date""",
            (month,),
        ).fetchall()
    return pd.DataFrame(rows)


# ---------- credit card actuals（人ごと） ----------

def get_month_credit_card_actuals(month: str) -> dict:
    """month -> {person_id: {'amount': int, 'source': 'manual'|'csv'}}"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT person_id, amount, source FROM monthly_credit_card_actuals WHERE month = %s",
            (month,),
        ).fetchall()
        return {r["person_id"]: {"amount": r["amount"], "source": r["source"]} for r in rows}


def upsert_credit_card_actual(person_id: int, month: str, amount: int, source: str = "manual"):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO monthly_credit_card_actuals (person_id, month, amount, source)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (person_id, month)
               DO UPDATE SET amount = EXCLUDED.amount, source = EXCLUDED.source""",
            (person_id, month, amount, source),
        )


def delete_credit_card_actual(person_id: int, month: str):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM monthly_credit_card_actuals WHERE person_id = %s AND month = %s",
            (person_id, month),
        )


def get_all_credit_card_actuals() -> pd.DataFrame:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT person_id, month, amount, source FROM monthly_credit_card_actuals"
        ).fetchall()
    return pd.DataFrame(rows, columns=["person_id", "month", "amount", "source"])


def recompute_credit_card_actuals_for_month(month: str, owner_person_ids: list[int] | None = None):
    """指定した月について、カードの保有者ごとに明細を集計してCSV由来の実績を更新する。
    保有者未設定（owner_person_id IS NULL）のカードの取引は対象外。
    """
    with get_connection() as conn:
        query = """
            SELECT c.owner_person_id AS person_id, COALESCE(SUM(t.amount), 0) AS total
            FROM credit_card_transactions t
            JOIN credit_cards c ON c.id = t.card_id
            WHERE t.month = %s AND c.owner_person_id IS NOT NULL
        """
        params: list = [month]
        if owner_person_ids:
            placeholders = ", ".join("%s" for _ in owner_person_ids)
            query += f" AND c.owner_person_id IN ({placeholders})"
            params.extend(owner_person_ids)
        query += " GROUP BY c.owner_person_id"

        totals = {r["person_id"]: r["total"] for r in conn.execute(query, params).fetchall()}
        target_ids = owner_person_ids if owner_person_ids else list(totals.keys())
        for pid in target_ids:
            conn.execute(
                """INSERT INTO monthly_credit_card_actuals (person_id, month, amount, source)
                   VALUES (%s, %s, %s, 'csv')
                   ON CONFLICT (person_id, month)
                   DO UPDATE SET amount = EXCLUDED.amount, source = 'csv'""",
                (pid, month, totals.get(pid, 0)),
            )


# ---------- planned items（臨時収入・イベント出費） ----------

def get_planned_items(plan_id: int) -> list[dict]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM planned_items WHERE plan_id = %s "
            "ORDER BY recurrence, month, month_of_year, id",
            (plan_id,),
        ).fetchall()


def add_planned_item(plan_id: int, item_type: str, label: str, amount: int, person_id: int,
                     recurrence: str, month: str | None = None, month_of_year: int | None = None,
                     start_year: int | None = None, end_year: int | None = None,
                     notes: str | None = None) -> int:
    """臨時収支を1件追加する。人ごとに集計するため person_id は必須。"""
    with get_connection() as conn:
        return conn.execute(
            """INSERT INTO planned_items
               (plan_id, item_type, label, amount, person_id, recurrence, month,
                month_of_year, start_year, end_year, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (plan_id, item_type, label, amount, person_id, recurrence, month, month_of_year,
             start_year, end_year, notes),
        ).fetchone()["id"]


def update_planned_item(item_id: int, **fields):
    allowed = {"item_type", "label", "amount", "person_id", "recurrence",
               "month", "month_of_year", "start_year", "end_year", "notes"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"未知の臨時収支項目: {sorted(unknown)}")
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE planned_items SET {cols} WHERE id = %s",
                     list(fields.values()) + [item_id])


def delete_planned_item(item_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM planned_items WHERE id = %s", (item_id,))


# ---------- 想定額の期間指定上書き（プラン×人×項目） ----------

def get_assumption_periods(plan_id: int) -> list[dict]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM plan_assumption_periods WHERE plan_id = %s "
            "ORDER BY person_id, field, start_month",
            (plan_id,),
        ).fetchall()


def add_assumption_period(plan_id: int, person_id: int, field: str, start_month: str,
                          end_month: str | None, amount: int) -> int:
    if field not in ASSUMPTION_PERIOD_FIELDS:
        raise ValueError(f"未知の想定額項目: {field}")
    with get_connection() as conn:
        return conn.execute(
            """INSERT INTO plan_assumption_periods
               (plan_id, person_id, field, start_month, end_month, amount)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
            (plan_id, person_id, field, start_month, end_month, amount),
        ).fetchone()["id"]


def update_assumption_period(period_id: int, **fields):
    allowed = {"person_id", "field", "start_month", "end_month", "amount"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"未知の想定額期間項目: {sorted(unknown)}")
    if "field" in fields and fields["field"] not in ASSUMPTION_PERIOD_FIELDS:
        raise ValueError(f"未知の想定額項目: {fields['field']}")
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE plan_assumption_periods SET {cols} WHERE id = %s",
                     list(fields.values()) + [period_id])


def delete_assumption_period(period_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM plan_assumption_periods WHERE id = %s", (period_id,))


# ---------- 住宅・不動産（プラン×人） ----------

def get_real_estate(plan_id: int) -> list[dict]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM plan_real_estate WHERE plan_id = %s "
            "ORDER BY person_id, purchase_month",
            (plan_id,),
        ).fetchall()


def add_real_estate(plan_id: int, person_id: int, label: str, purchase_month: str,
                    monthly_payment: int, loan_term_months: int,
                    annual_appreciation_pct: float = 0.0,
                    notes: str | None = None) -> int:
    with get_connection() as conn:
        return conn.execute(
            """INSERT INTO plan_real_estate
               (plan_id, person_id, label, purchase_month, monthly_payment,
                loan_term_months, annual_appreciation_pct, notes)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (plan_id, person_id, label, purchase_month, monthly_payment,
             loan_term_months, annual_appreciation_pct, notes),
        ).fetchone()["id"]


def update_real_estate(real_estate_id: int, **fields):
    allowed = {"person_id", "label", "purchase_month", "monthly_payment",
               "loan_term_months", "annual_appreciation_pct", "notes"}
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"未知の不動産項目: {sorted(unknown)}")
    if not fields:
        return
    cols = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as conn:
        conn.execute(f"UPDATE plan_real_estate SET {cols} WHERE id = %s",
                     list(fields.values()) + [real_estate_id])


def delete_real_estate(real_estate_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM plan_real_estate WHERE id = %s", (real_estate_id,))
