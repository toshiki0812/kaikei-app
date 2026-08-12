"""クレジットカード利用明細CSVの取込処理。

日本のカード会社のCSVはエンコーディング（Shift-JIS率が高い）やヘッダー名が
バラバラなため、エンコーディング自動判定＋列マッピングUIを前提にした
パース関数を用意する。DB書き込みはプレビュー確定後のみ行う。
"""
from __future__ import annotations

import io
import re

import pandas as pd

import db

ENCODING_CANDIDATES = ["utf-8-sig", "cp932", "utf-8"]


def decode_csv(raw_bytes: bytes, encoding: str | None = None) -> tuple[pd.DataFrame, str]:
    """バイト列をDataFrameに変換する。encoding指定がなければ順に試す。"""
    candidates = [encoding] if encoding else ENCODING_CANDIDATES
    last_err = None
    for enc in candidates:
        try:
            df = pd.read_csv(io.BytesIO(raw_bytes), encoding=enc, dtype=str)
            return df, enc
        except (UnicodeDecodeError, UnicodeError, LookupError) as e:
            last_err = e
            continue
    raise ValueError(f"CSVの文字コードを判定できませんでした（試行: {candidates}）: {last_err}")


def parse_amount(raw) -> int | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s.lower() == "nan":
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = s.replace(",", "").replace("¥", "").replace("円", "").strip()
    s = re.sub(r"[^\d\-]", "", s)
    if s in ("", "-"):
        return None
    try:
        amount = int(s)
    except ValueError:
        return None
    return -amount if negative else amount


def build_transactions(df: pd.DataFrame, date_col: str, desc_col: str, amount_col: str):
    """列マッピングに従い、DB挿入用の行リストとエラー行を作る。"""
    rows = []
    error_rows = []
    for idx, r in df.iterrows():
        raw_date = r.get(date_col)
        dt = pd.to_datetime(raw_date, errors="coerce")
        amount = parse_amount(r.get(amount_col))
        if pd.isna(dt) or amount is None:
            error_rows.append({
                "row": idx + 1,
                "raw_date": raw_date,
                "raw_amount": r.get(amount_col),
                "reason": "日付を解釈できません" if pd.isna(dt) else "金額を解釈できません",
            })
            continue
        rows.append({
            "txn_date": dt.strftime("%Y-%m-%d"),
            "month": dt.strftime("%Y-%m"),
            "description": str(r.get(desc_col)) if desc_col else "",
            "amount": amount,
        })
    return rows, error_rows


def commit_import(card_id: int, filename: str, rows: list[dict]) -> dict:
    """取込を確定してDBに書き込み、影響を受けた月の該当カード保有者の実績を再集計する。"""
    total_amount = sum(r["amount"] for r in rows)
    batch_id = db.create_import_batch(card_id, filename, len(rows), 0, total_amount)
    inserted, skipped = db.insert_transactions(card_id, rows, batch_id)
    db.update_import_batch(batch_id, skipped_duplicate_count=skipped)

    card = db.get_credit_card(card_id)
    owner_person_id = card["owner_person_id"] if card else None

    months = sorted({r["month"] for r in rows})
    if owner_person_id is not None:
        for month in months:
            db.recompute_credit_card_actuals_for_month(month, owner_person_ids=[owner_person_id])

    return {
        "batch_id": batch_id,
        "inserted": inserted,
        "skipped": skipped,
        "months": months,
        "total_amount": total_amount,
        "owner_person_id": owner_person_id,
    }


def months_with_manual_credit_card(months: list[str], person_id: int) -> list[str]:
    """指定した月のうち、その人のcredit_card実績が既に手入力(manual)のものを返す。"""
    manual_months = []
    for month in months:
        actuals = db.get_month_credit_card_actuals(month)
        entry = actuals.get(person_id)
        if entry and entry.get("source") == "manual":
            manual_months.append(month)
    return manual_months
