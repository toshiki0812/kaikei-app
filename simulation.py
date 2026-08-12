"""120ヶ月（10年）分のキャッシュフロー・投資残高シミュレーションを構築するエンジン。

想定値・実績とも**すべて人ごと**に持ち、夫・妻を独立して試算してから合算する。
想定値はプランごと（プランA／プランB…）、実績は全プラン共通。
実績が入力されている月はDBの実績値を、入力されていない月はそのプランの
想定値を使う。「その他（現金支出）」は保存せず、読み取り時に毎回計算する。

金額はすべて整数（円）で扱う。小数が発生するのは投資の複利計算だけなので、
月ごとに丸めてから次の月へ持ち越す。
"""
from __future__ import annotations

import pandas as pd

import db

SIMULATION_MONTHS = 120  # 10年

# 人ごとに算出し、合計列としても持つ金額項目
MONEY_FIELDS = (
    "income", "credit_card", "rent", "investment_contribution", "other_expense",
    "planned_income", "planned_expense", "other_cash_expense", "cash_sweep",
    "cash_shortfall_withdrawal",
    "total_expense", "net_cash_flow", "cash_balance", "investment_balance",
    "investment_growth", "real_estate_payment", "real_estate_value",
)


def month_range(start_month: str, n: int = SIMULATION_MONTHS) -> list[str]:
    y, m = (int(x) for x in start_month.split("-"))
    months = []
    for i in range(n):
        total = m - 1 + i
        yy = y + total // 12
        mm = total % 12 + 1
        months.append(f"{yy:04d}-{mm:02d}")
    return months


def month_label(month: str) -> str:
    y, m = month.split("-")
    return f"{y}年{int(m)}月"


def _clean(v):
    """NaN/Noneを正規化し、数値はintに揃える。"""
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return int(v)


def _planned_items_for_month(planned_items: list[dict], month: str) -> list[dict]:
    """その月に該当する臨時収支アイテムを返す（単発 or 毎年繰り返し）。"""
    y, m = (int(x) for x in month.split("-"))
    matched = []
    for it in planned_items:
        if it["recurrence"] == "once":
            if it["month"] == month:
                matched.append(it)
        else:  # yearly
            if it["month_of_year"] != m:
                continue
            if it["start_year"] is not None and y < it["start_year"]:
                continue
            if it["end_year"] is not None and y > it["end_year"]:
                continue
            matched.append(it)
    return matched


def _month_diff(from_month: str, to_month: str) -> int:
    """from_month から to_month までの月数（to - from）。"""
    fy, fm = (int(x) for x in from_month.split("-"))
    ty, tm = (int(x) for x in to_month.split("-"))
    return (ty - fy) * 12 + (tm - fm)


def _assumption_value(periods_for_field: list[dict], month: str, base_value) -> int:
    """期間指定の上書きがあればそれを、無ければ基本の想定値を返す。

    同じ月に該当する行が複数あれば start_month が一番新しいものを優先する。
    """
    matched = [
        p for p in periods_for_field
        if p["start_month"] <= month and (p["end_month"] is None or month <= p["end_month"])
    ]
    if not matched:
        return int(base_value)
    return int(max(matched, key=lambda p: p["start_month"])["amount"])


def build_person_projection(person_id: int, months: list[str], settings: dict,
                             assumptions: dict, planned_items: list[dict],
                             actuals: dict, cc_actuals: dict,
                             assumption_periods: dict | None = None,
                             real_estate: list[dict] | None = None) -> list[dict]:
    """1人分の月次シミュレーション。呼び出し側でDBアクセスを済ませて渡す。"""
    annual_rate = settings["expected_annual_return_pct"] / 100.0
    compounding = settings["compounding"]
    monthly_rate = (1 + annual_rate) ** (1 / 12) - 1 if compounding == "monthly" else None

    threshold = assumptions.get("cash_sweep_threshold")
    cash_balance = int(assumptions.get("starting_cash_balance") or 0)
    investment_balance = int(assumptions.get("starting_investment_balance") or 0)

    assumption_periods = assumption_periods or {}
    my_items = [it for it in planned_items if it["person_id"] == person_id]

    # 住宅・不動産：家賃の代わりにローンを返済し、その返済額が投資拠出と同じ仕組みで
    # 年率の値動きを乗せながら資産として積み上がる（金利・残債は扱わない単純化モデル）。
    my_properties = [re for re in (real_estate or []) if re["person_id"] == person_id]
    property_values = {re["id"]: 0 for re in my_properties}
    property_monthly_rate = {
        re["id"]: (1 + re["annual_appreciation_pct"] / 100.0) ** (1 / 12) - 1
        for re in my_properties
    }

    rows = []
    for i, month in enumerate(months):
        act = actuals.get(month, {})
        income_actual = _clean(act.get("income"))
        rent_actual = _clean(act.get("rent"))
        inv_contrib_actual = _clean(act.get("investment_contribution"))
        other_exp_actual = _clean(act.get("other_expense"))
        bank_cash_actual = _clean(act.get("bank_cash_balance_eom"))
        inv_balance_actual = _clean(act.get("investment_balance_eom"))

        cc_entry = cc_actuals.get(month)
        cc_actual = _clean(cc_entry["amount"]) if cc_entry else None

        income = income_actual if income_actual is not None else _assumption_value(
            assumption_periods.get("monthly_income_assumption", []), month,
            assumptions["monthly_income_assumption"])
        credit_card = cc_actual if cc_actual is not None else _assumption_value(
            assumption_periods.get("monthly_credit_card_assumption", []), month,
            assumptions["monthly_credit_card_assumption"])
        rent = rent_actual if rent_actual is not None else _assumption_value(
            assumption_periods.get("rent_assumption", []), month, assumptions["rent_assumption"])
        investment_contribution = (
            inv_contrib_actual if inv_contrib_actual is not None
            else _assumption_value(assumption_periods.get("investment_contribution_assumption", []),
                                   month, assumptions["investment_contribution_assumption"])
        )
        other_expense = (
            other_exp_actual if other_exp_actual is not None
            else _assumption_value(assumption_periods.get("other_expense_assumption", []),
                                   month, assumptions["other_expense_assumption"])
        )

        # --- 臨時収支（ボーナス・イベント出費） ---
        month_planned = _planned_items_for_month(my_items, month)
        planned_income = sum(it["amount"] for it in month_planned if it["item_type"] == "income")
        planned_expense = sum(it["amount"] for it in month_planned if it["item_type"] == "expense")
        planned_labels = "、".join(
            f"{it['label']}（{'+' if it['item_type'] == 'income' else '-'}¥{it['amount']:,.0f}）"
            for it in month_planned
        )
        income_total = income + planned_income

        # --- 住宅・不動産（ローン返済中は家賃の代わりに現金が減り、返済額が資産に積み上がる） ---
        real_estate_payment = 0
        for re in my_properties:
            rid = re["id"]
            months_since_purchase = _month_diff(re["purchase_month"], month)
            in_loan_period = 0 <= months_since_purchase < re["loan_term_months"]
            payment = re["monthly_payment"] if in_loan_period else 0
            real_estate_payment += payment
            property_values[rid] = round(
                (property_values[rid] + payment) * (1 + property_monthly_rate[rid]))
        real_estate_value = sum(property_values.values())

        # --- その他（現金支出）と現金残高 ---
        prev_cash_balance = cash_balance
        known_actuals_complete = (
            income_actual is not None and cc_actual is not None and rent_actual is not None
            and inv_contrib_actual is not None and other_exp_actual is not None
        )

        cash_sweep = 0
        cash_shortfall = 0
        if bank_cash_actual is not None:
            # 実績の残高が正。自動振替は現実の結果に含まれているので適用しない。
            cash_balance = bank_cash_actual
            if known_actuals_complete:
                delta_cash = bank_cash_actual - prev_cash_balance
                other_cash_expense = (
                    income_total - rent - credit_card - investment_contribution
                    - other_expense - planned_expense - real_estate_payment - delta_cash
                )
                other_cash_status = "actual"
            else:
                other_cash_expense = _assumption_value(
                    assumption_periods.get("other_cash_expense_assumption", []), month,
                    assumptions["other_cash_expense_assumption"])
                other_cash_status = "assumption"
        else:
            other_cash_expense = int(assumptions["other_cash_expense_assumption"])
            other_cash_status = "assumption"
            net_flow = (
                income_total - rent - credit_card - investment_contribution
                - other_expense - planned_expense - real_estate_payment - other_cash_expense
            )
            cash_balance = prev_cash_balance + net_flow
            # 一定ラインを超えた現金は投資へ回す
            if threshold is not None and cash_balance > threshold:
                cash_sweep = cash_balance - int(threshold)
                cash_balance = int(threshold)
            elif cash_balance < 0:
                # 現金が足りない月は、まず今月の投資拠出を止めて現金に回す。
                # 足りないのに積み立てて同じ月に取り崩す、という無駄な往復を避けるため。
                # 実績を入力済みの拠出額は「実際に積み立てた事実」なので減らさない。
                if inv_contrib_actual is None and investment_contribution > 0:
                    skipped = min(-cash_balance, investment_contribution)
                    investment_contribution -= skipped
                    cash_balance += skipped
                # 拠出を止めても足りなければ、投資残高からその不足分だけ取り崩して埋める
                # （投資残高を超えて取り崩すことはしない。埋まらなければ現金はマイナスのまま）
                if cash_balance < 0:
                    cash_shortfall = min(-cash_balance, investment_balance)
                    cash_balance += cash_shortfall

        # --- 投資残高の複利計算 ---
        growth = 0
        contribution_total = investment_contribution + cash_sweep - cash_shortfall
        if inv_balance_actual is not None:
            investment_balance = inv_balance_actual
        elif compounding == "monthly":
            new_balance = (investment_balance + contribution_total) * (1 + monthly_rate)
            growth = round(new_balance) - investment_balance - contribution_total
            investment_balance = round(new_balance)
        else:  # annually
            investment_balance += contribution_total
            if (i + 1) % 12 == 0:
                new_balance = investment_balance * (1 + annual_rate)
                growth = round(new_balance) - investment_balance
                investment_balance = round(new_balance)

        total_expense = (
            rent + credit_card + investment_contribution + other_expense
            + planned_expense + real_estate_payment + other_cash_expense + cash_sweep
            - cash_shortfall
        )
        net_cash_flow = income_total - total_expense

        all_fields_present = known_actuals_complete and bank_cash_actual is not None
        any_actual_present = any(v is not None for v in (
            income_actual, cc_actual, rent_actual, inv_contrib_actual,
            other_exp_actual, bank_cash_actual))
        if all_fields_present:
            data_status = "actual"
        elif any_actual_present:
            data_status = "partial"
        else:
            data_status = "projected"

        rows.append({
            "month": month,
            "data_status": data_status,
            "income": int(income_total),
            "credit_card": int(credit_card),
            "rent": int(rent),
            "investment_contribution": int(investment_contribution),
            "other_expense": int(other_expense),
            "planned_income": int(planned_income),
            "planned_expense": int(planned_expense),
            "planned_labels": planned_labels,
            "other_cash_expense": int(other_cash_expense),
            "other_cash_status": other_cash_status,
            "cash_sweep": int(cash_sweep),
            "cash_shortfall_withdrawal": int(cash_shortfall),
            "total_expense": int(total_expense),
            "net_cash_flow": int(net_cash_flow),
            "cash_balance": int(cash_balance),
            "investment_balance": int(investment_balance),
            "investment_growth": int(growth),
            "real_estate_payment": int(real_estate_payment),
            "real_estate_value": int(real_estate_value),
        })
    return rows


def _status_rank(statuses: list[str]) -> str:
    """世帯としての状態。全員実績なら actual、誰も無ければ projected、途中は partial。"""
    if all(s == "actual" for s in statuses):
        return "actual"
    if all(s == "projected" for s in statuses):
        return "projected"
    return "partial"


def build_projection(plan_id: int, n_months: int | None = None) -> pd.DataFrame:
    """人ごとの試算と世帯合計を1つのDataFrameにまとめて返す。

    列は合計（`income_total` `cash_balance` …）と人別（`cash_balance_p1` …）の両方。
    n_months を省略すると、そのプランの「シミュレーション期間」設定（年数）を使う。
    """
    settings = db.get_settings(plan_id)
    if n_months is None:
        n_months = int(settings.get("horizon_years") or 10) * 12
    people = db.get_people()
    assumptions = db.get_person_assumptions(plan_id)
    planned_items = db.get_planned_items(plan_id)
    real_estate = db.get_real_estate(plan_id)

    periods_by_person: dict = {p["id"]: {} for p in people}
    for row in db.get_assumption_periods(plan_id):
        periods_by_person.setdefault(row["person_id"], {}).setdefault(row["field"], []).append(row)

    actuals_df = db.get_all_person_actuals()
    actuals_by_person: dict = {p["id"]: {} for p in people}
    for _, r in actuals_df.iterrows():
        actuals_by_person.setdefault(r["person_id"], {})[r["month"]] = r.to_dict()

    cc_df = db.get_all_credit_card_actuals()
    cc_by_person: dict = {p["id"]: {} for p in people}
    for _, r in cc_df.iterrows():
        cc_by_person.setdefault(r["person_id"], {})[r["month"]] = {
            "amount": r["amount"], "source": r["source"]}

    months = month_range(settings["simulation_start_month"], n_months)

    per_person = {}
    for p in people:
        pid = p["id"]
        per_person[pid] = build_person_projection(
            pid, months, settings, assumptions.get(pid, _blank_assumptions()),
            planned_items, actuals_by_person.get(pid, {}), cc_by_person.get(pid, {}),
            assumption_periods=periods_by_person.get(pid, {}), real_estate=real_estate,
        )

    rows = []
    for i, month in enumerate(months):
        row = {"month": month, "month_label": month_label(month)}
        statuses = []
        labels = []
        for p in people:
            pid = p["id"]
            r = per_person[pid][i]
            statuses.append(r["data_status"])
            if r["planned_labels"]:
                labels.append(f"{p['name']}：{r['planned_labels']}")
            for f in MONEY_FIELDS:
                row[f"{f}_p{pid}"] = r[f]
            row[f"data_status_p{pid}"] = r["data_status"]
            row[f"other_cash_status_p{pid}"] = r["other_cash_status"]
            row[f"planned_labels_p{pid}"] = r["planned_labels"]

        for f in MONEY_FIELDS:
            row[f] = sum(row[f"{f}_p{p['id']}"] for p in people)
        # 既存のグラフ・表が使う列名に合わせる
        row["income_total"] = row["income"]
        row["credit_card_total"] = row["credit_card"]
        row["data_status"] = _status_rank(statuses)
        row["planned_labels"] = " / ".join(labels)
        row["other_cash_status"] = (
            "actual" if all(per_person[p["id"]][i]["other_cash_status"] == "actual" for p in people)
            else "assumption"
        )
        rows.append(row)

    return pd.DataFrame(rows)


def _blank_assumptions() -> dict:
    return {f: 0 for f in db.PERSON_ASSUMPTION_FIELDS} | {"cash_sweep_threshold": None}


def view_frame(df: pd.DataFrame, scope) -> pd.DataFrame:
    """`scope` が "total" なら合計、person_id ならその人の列を正規名に付け替えて返す。

    これにより charts.py は世帯合計と個人で同じコードのまま描き分けられる。
    """
    if scope == "total":
        return df

    pid = int(scope)
    out = df[["month", "month_label"]].copy()
    for f in MONEY_FIELDS:
        out[f] = df[f"{f}_p{pid}"]
        # 人別列も残す（支出内訳グラフが人別の列名で参照するため）
        out[f"{f}_p{pid}"] = df[f"{f}_p{pid}"]
    out["income_total"] = out["income"]
    out["credit_card_total"] = out["credit_card"]
    out["data_status"] = df[f"data_status_p{pid}"]
    out["other_cash_status"] = df[f"other_cash_status_p{pid}"]
    out["planned_labels"] = df[f"planned_labels_p{pid}"]
    return out
