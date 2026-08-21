"""資料と予実管理シートが使う数字を、エンジンから一括で書き出す。

前提（2026年9月開始・2027年6月同棲・1年目は家賃以外9万円・2年目以降11万円・
投資拠出は2027年2月から月20万円）をここに集約する。
"""
from __future__ import annotations

import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import db
import simulation

P, T, S = 1, 1, 2
SC = ("/private/tmp/claude-502/-Users-Office-Desktop-Claude-private/"
      "86f3df5d-53be-453b-aeb3-b23831f5312a/scratchpad")

START = "2026-09"
MOVE = "2027-06"          # 同棲の開始
Y1_END = "2027-08"        # 1年目の最終月
LOW_END = "2027-03"       # 低収入期の最終月
BIRTH, LEAVE_S, LEAVE_E = "2030-06", "2030-04", "2031-05"
Y1_TAX = [("2026-09", 80000), ("2026-12", 80000), ("2027-03", 380000), ("2027-06", 60000)]


def ev(pid, label, month, amount, kind="expense"):
    return {"id": 0, "plan_id": P, "item_type": kind, "label": label, "amount": amount,
            "person_id": pid, "recurrence": "once", "month": month, "month_of_year": None,
            "start_year": None, "end_year": None, "notes": None}


def build(n_months, card_y1=30000, card_y2=47500, food=60000, contrib=200000,
          move=MOVE, keep_bad_habit=False):
    st = dict(db.get_settings(P))
    st["simulation_start_month"] = START
    A = db.get_person_assumptions(P)
    RE = db.get_real_estate(P)
    months = simulation.month_range(START, n_months)

    src = db.get_planned_items(P)
    events = [dict(it) for it in src
              if it["label"] not in ("引越し", "違約金")
              and not (it["recurrence"] == "yearly" and it["person_id"] == T
                       and it["label"] in ("住民税", "所得税"))]
    # 資料の税金（住民税・所得税）は2027年9月以降だけ効かせる
    for it in src:
        if (it["recurrence"] == "yearly" and it["person_id"] == T
                and it["label"] in ("住民税", "所得税")):
            d = dict(it)
            d["start_year"] = 2028 if it["month_of_year"] < 9 else 2027
            events.append(d)
    for m, a in Y1_TAX:
        events.append(ev(T, "税金", m, a))
    events += [ev(T, "C-LinC 1〜3月分報酬", "2027-04", 750000, kind="income"),
               ev(T, "引越し費用", move, 600000),
               ev(T, "第一子・一時費用", BIRTH, 150000),
               ev(S, "第一子・一時費用", BIRTH, 150000)]

    rent_end = simulation.month_range(move, 1)[0]
    prev_month = f"{int(move[:4]) - (1 if move[5:] == '01' else 0)}-" \
                 f"{12 if move[5:] == '01' else int(move[5:]) - 1:02d}"

    out = {}
    for pid in (T, S):
        x = copy.deepcopy(A[pid])
        per = {}
        if pid == T:
            x.update(starting_cash_balance=0, starting_investment_balance=0,
                     cash_sweep_threshold=1000000, monthly_income_assumption=500000,
                     rent_assumption=80000, monthly_credit_card_assumption=card_y2,
                     other_cash_expense_assumption=food,
                     investment_contribution_assumption=contrib)
            per["monthly_income_assumption"] = [
                {"start_month": START, "end_month": START, "amount": 2440000},
                {"start_month": "2026-10", "end_month": LOW_END, "amount": 260000}]
            per["rent_assumption"] = [
                {"start_month": START, "end_month": prev_month, "amount": 167000}]
            per["monthly_credit_card_assumption"] = [
                {"start_month": START, "end_month": Y1_END, "amount": card_y1}]
            per["investment_contribution_assumption"] = [
                {"start_month": START, "end_month": START, "amount": 1000000},
                {"start_month": "2026-10", "end_month": "2027-01", "amount": 0}]
            per["other_cash_expense_assumption"] = [
                {"start_month": BIRTH, "end_month": LEAVE_E, "amount": food + 7500}]
            if keep_bad_habit:   # 食費の見直しが続かなかった場合
                x["other_cash_expense_assumption"] = 132820
                x["monthly_credit_card_assumption"] = 47500
                per["monthly_credit_card_assumption"] = []
                per["other_cash_expense_assumption"] = [
                    {"start_month": BIRTH, "end_month": LEAVE_E, "amount": 132820 + 7500}]
        else:
            x.update(rent_assumption=80000, monthly_credit_card_assumption=100000)
            per["monthly_credit_card_assumption"] = [
                {"start_month": move, "end_month": None, "amount": 97500}]
            per["monthly_income_assumption"] = [
                {"start_month": LEAVE_S, "end_month": LEAVE_E, "amount": 150000}]
            per["other_cash_expense_assumption"] = [
                {"start_month": BIRTH, "end_month": LEAVE_E, "amount": 7500}]
        out[pid] = simulation.build_person_projection(
            pid, months, st, x, events, {}, {}, assumption_periods=per, real_estate=RE)
    return months, out


def main():
    F = ("income", "rent", "credit_card", "other_cash_expense", "investment_contribution",
         "planned_income", "planned_expense", "cash_balance", "investment_balance",
         "total_assets", "cash_sweep", "cash_shortfall_withdrawal", "real_estate_value")
    m12, y1 = build(12)
    m60, y5 = build(60)
    json.dump({
        "m12": m12, "m60": m60,
        "y1": {"T": [{k: int(r[k]) for k in F} for r in y1[T]],
               "S": [{k: int(r[k]) for k in F} for r in y1[S]],
               "labelsT": [r["planned_labels"] for r in y1[T]],
               "labelsS": [r["planned_labels"] for r in y1[S]]},
        "y5": {"T": [int(r["total_assets"]) for r in y5[T]],
               "S": [int(r["total_assets"]) for r in y5[S]],
               "Tcash": [int(r["cash_balance"]) for r in y5[T]],
               "Tinv": [int(r["investment_balance"]) for r in y5[T]],
               "Scash": [int(r["cash_balance"]) for r in y5[S]],
               "Sinv": [int(r["investment_balance"]) for r in y5[S]],
               "Tre": [int(r["real_estate_value"]) for r in y5[T]],
               "Sre": [int(r["real_estate_value"]) for r in y5[S]]}},
        open(f"{SC}/deck.json", "w"), ensure_ascii=False)

    last = lambda o: o[T][-1]["total_assets"] + o[S][-1]["total_assets"]
    _, ok = build(60)
    _, bad = build(60, keep_bad_habit=True)
    json.dump({"plan": last(ok), "bad": last(bad),
               "gap": last(ok) - last(bad)},
              open(f"{SC}/compare.json", "w"))
    print("5年後 世帯 %s円 ／ 食費が続かなかった場合 %s円 ／ 差 %s円"
          % (format(last(ok), ","), format(last(bad), ","),
             format(last(ok) - last(bad), ",")))
    return m60, y5


if __name__ == "__main__":
    main()
