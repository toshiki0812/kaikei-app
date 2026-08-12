import pandas as pd
import streamlit as st

import db
import simulation
import theme
from theme import yen

plan_id = db.get_active_plan_id()
plan = db.get_plan(plan_id)

theme.page_header(
    "初期設定",
    "ここで登録した内容が、実績を入力していない月の「想定値」としてシミュレーションに使われます。",
)
st.info(f"編集中のプラン：**{plan['name']}**　"
        "（想定値・臨時収支はプランごと、氏名とカードは全プラン共通です）")

if db.get_state("household_split_review_needed"):
    st.warning(
        "**負担の内訳をご確認ください。**　これまで世帯でまとめて入力していた家賃・投資拠出・"
        "その他支出・開始残高は、自動では按分できないため、いったん先頭の方にすべて寄せてあります。"
        "「毎月の想定」「資産・運用」タブで、実際の負担に合わせて振り分け直してください。"
    )
    if st.button("確認したので、この案内を消す"):
        db.clear_state("household_split_review_needed")
        st.rerun()

people = db.get_people()
settings = db.get_settings(plan_id)
person_assumptions = db.get_person_assumptions(plan_id)

tab_plans, tab_monthly, tab_assets, tab_planned, tab_cards = st.tabs(
    ["プラン", "毎月の想定", "資産・運用", "臨時収支", "カード"]
)


# ══════════ プラン ══════════
with tab_plans:
    theme.section("プランの管理")
    st.caption(
        "「住宅を買う場合／買わない場合」のように前提の違うシナリオを複数作って比較できます。"
        "プランごとに変わるのは想定値と臨時収支だけで、入力した実績は全プランで共有されます。"
    )

    plans = db.get_plans()
    for p in plans:
        cols = st.columns([2.2, 2.6, 1.4, 1])
        label = f"**{p['name']}**" + ("　（表示中）" if p["id"] == plan_id else "")
        cols[0].markdown(label)
        cols[1].write(p["description"] or "")
        if p["id"] != plan_id and cols[2].button("切り替え", key=f"switch_plan_{p['id']}"):
            db.set_active_plan_id(p["id"])
            st.rerun()
        if len(plans) > 1 and cols[3].button("削除", key=f"delete_plan_{p['id']}"):
            db.delete_plan(p["id"])
            st.rerun()
    if len(plans) == 1:
        st.caption("プランが1つのときは削除できません。")

    st.write("")
    st.markdown("**新しいプランを作る**")
    with st.form("form_add_plan"):
        c1, c2 = st.columns([1.4, 2])
        new_name = c1.text_input("プラン名", placeholder="例：プランB（住宅購入）")
        new_desc = c2.text_input("メモ（任意）", placeholder="例：2029年に4,500万円の住宅を購入")
        copy_options = [None] + [p["id"] for p in plans]
        copy_from = st.selectbox(
            "コピー元", options=copy_options,
            index=copy_options.index(plan_id) if plan_id in copy_options else 0,
            format_func=lambda pid: "空のプラン（すべて0から）" if pid is None
            else f"{db.get_plan(pid)['name']} の内容をコピー",
            help="コピーすると想定値・臨時収支がそのまま複製されるので、違う部分だけ直せば済みます。",
        )
        if st.form_submit_button("プランを作成", type="primary"):
            if not new_name.strip():
                st.warning("プラン名を入力してください")
            else:
                new_id = db.create_plan(new_name.strip(), copy_from, new_desc.strip() or None)
                db.set_active_plan_id(new_id)
                st.success(f"「{new_name}」を作成し、表示を切り替えました")
                st.rerun()

    st.write("")
    st.markdown("**表示中のプランの名前を変える**")
    with st.form("form_rename_plan"):
        c1, c2 = st.columns([1.4, 2])
        rename = c1.text_input("プラン名", value=plan["name"], key=f"rename_name_{plan_id}")
        redesc = c2.text_input("メモ（任意）", value=plan["description"] or "",
                               key=f"rename_desc_{plan_id}")
        if st.form_submit_button("名前を保存"):
            if rename.strip():
                db.rename_plan(plan_id, rename.strip(), redesc.strip() or None)
                st.success("保存しました")
                st.rerun()
            else:
                st.warning("プラン名を入力してください")


# ══════════ 毎月の想定 ══════════
with tab_monthly:
    theme.section("氏名")
    with st.form("form_people"):
        name_inputs = {}
        cols = st.columns(len(people))
        for i, p in enumerate(people):
            name_inputs[p["id"]] = cols[i].text_input(
                f"person_{p['id']}", value=p["name"], label_visibility="collapsed"
            )
        if st.form_submit_button("氏名を保存"):
            for pid, name in name_inputs.items():
                if name.strip():
                    db.update_person_name(pid, name.strip())
            st.success("保存しました")
            st.rerun()

    st.write("")
    theme.section("毎月の収入・支出（想定額）")
    st.caption(
        "夫婦それぞれで別々にシミュレーションするため、家賃なども"
        "**実際にどちらの口座から出ているか**に合わせて1人ずつ入力してください。世帯合計は自動で計算されます。"
    )

    ASSUMPTION_ROWS = [
        ("monthly_income_assumption", "収入（月収）", None),
        ("monthly_credit_card_assumption", "クレジットカード利用額", None),
        ("rent_assumption", "家賃", "自分が負担している分だけ入力します"),
        ("investment_contribution_assumption", "投資拠出額", None),
        ("other_expense_assumption", "その他の既知の固定費",
         "保険料・サブスクなど、家賃／クレカ／投資以外で金額が分かっている支出"),
        ("other_cash_expense_assumption", "その他（現金支出）",
         "実績未入力の将来月で使う仮の現金支出額。実績を入力した月は自動計算に置き換わります。"),
    ]

    with st.form("form_person_assumptions"):
        inputs = {p["id"]: {} for p in people}
        header = st.columns([1.6] + [1] * len(people))
        header[0].markdown("**項目**")
        for i, p in enumerate(people):
            header[i + 1].markdown(f"**{p['name']}**")

        for field, label, help_text in ASSUMPTION_ROWS:
            cols = st.columns([1.6] + [1] * len(people))
            cols[0].markdown(f"<div style='padding-top:.55rem'>{label}</div>",
                             unsafe_allow_html=True)
            for i, p in enumerate(people):
                current = person_assumptions.get(p["id"], {}).get(field) or 0
                inputs[p["id"]][field] = cols[i + 1].number_input(
                    p["name"], min_value=0, step=1000,
                    value=int(current), label_visibility="visible",
                    help=help_text, key=f"assume_{plan_id}_{field}_{p['id']}",
                )

        if st.form_submit_button("想定額を保存", type="primary"):
            for pid, fields in inputs.items():
                db.update_person_assumptions(plan_id, pid, **{k: int(v) for k, v in fields.items()})
            st.success("保存しました")
            st.rerun()

    totals = {
        label: sum(int(person_assumptions.get(p["id"], {}).get(field) or 0) for p in people)
        for field, label, _ in ASSUMPTION_ROWS
    }
    st.caption(
        "世帯合計：　"
        + "／".join(f"{label} {yen(v)}" for label, v in totals.items())
    )

    st.write("")
    theme.section("期間ごとの変更")
    st.caption(
        "「2026年4月〜2027年3月は月収35万円」のように、上の想定額を特定の期間だけ"
        "別の金額に差し替えられます。該当しない月は上の想定額がそのまま使われます。"
        "終了年月を空欄にすると、開始年月以降ずっと適用されます。"
    )

    period_months = simulation.month_range(settings["simulation_start_month"], simulation.INPUT_MONTHS)
    period_month_labels = {m: simulation.month_label(m) for m in period_months}
    label_to_month = {v: k for k, v in period_month_labels.items()}
    MONTH_OPTIONS = [""] + list(period_month_labels.values())
    FIELD_LABELS = {field: label for field, label, _ in ASSUMPTION_ROWS}
    field_label_to_key = {v: k for k, v in FIELD_LABELS.items()}
    id_to_name = {p["id"]: p["name"] for p in people}
    name_to_id = {p["name"]: p["id"] for p in people}
    BOTH_LABEL = "二人（折半）"
    PERSON_OPTIONS_WITH_BOTH = list(name_to_id.keys()) + [BOTH_LABEL]

    periods = db.get_assumption_periods(plan_id)
    # 対象者・項目・期間・金額がすべて一致する行は「二人（折半）」で登録されたものとみなす
    period_groups: dict[tuple, list[dict]] = {}
    for pr in periods:
        key = (pr["field"], pr["start_month"], pr["end_month"], pr["amount"])
        period_groups.setdefault(key, []).append(pr)

    period_editor_rows = []
    for (field, start_month, end_month, per_person_amount), rows in period_groups.items():
        pids = [r["person_id"] for r in rows]
        is_both = len(rows) == len(people) and len(people) > 1 and set(pids) == {p["id"] for p in people}
        display_amount = per_person_amount * len(people) if is_both else per_person_amount
        period_editor_rows.append({
            "対象者": BOTH_LABEL if is_both else id_to_name.get(pids[0], people[0]["name"]),
            "項目": FIELD_LABELS.get(field, field),
            "開始年月": period_month_labels.get(start_month, start_month),
            "終了年月": period_month_labels.get(end_month, end_month or ""),
            "金額": int(display_amount),
            "_ids": [r["id"] for r in rows],
        })

    period_editor_df = pd.DataFrame(
        period_editor_rows, columns=["対象者", "項目", "開始年月", "終了年月", "金額", "_ids"]
    ).astype({"対象者": "string", "項目": "string", "開始年月": "string",
              "終了年月": "string", "金額": "Int64"})

    period_edited = st.data_editor(
        period_editor_df,
        num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "対象者": st.column_config.SelectboxColumn(options=PERSON_OPTIONS_WITH_BOTH, required=True),
            "項目": st.column_config.SelectboxColumn(options=list(FIELD_LABELS.values()), required=True),
            "開始年月": st.column_config.SelectboxColumn(options=MONTH_OPTIONS, required=True),
            "終了年月": st.column_config.SelectboxColumn(
                options=MONTH_OPTIONS, help="空欄なら開始年月以降ずっと適用"),
            "金額": st.column_config.NumberColumn(
                format="localized", min_value=0, step=1000,
                help="「二人」を選んだ場合は世帯としての合計額を入力します（自動で2等分されます）"),
            "_ids": None,
        },
        key=f"assumption_period_editor_{plan_id}",
    )

    if st.button("期間ごとの変更を保存", type="primary"):
        errors = []
        parsed = []
        for i, row in period_edited.iterrows():
            person_choice = row["対象者"] if isinstance(row["対象者"], str) else ""
            field_label = row["項目"] if isinstance(row["項目"], str) else ""
            start_label = row["開始年月"] if isinstance(row["開始年月"], str) else ""
            if not person_choice and not field_label and not start_label:
                continue  # 空行は無視
            if person_choice not in PERSON_OPTIONS_WITH_BOTH:
                errors.append(f"{i + 1}行目：対象者を選んでください")
                continue
            if field_label not in field_label_to_key:
                errors.append(f"{i + 1}行目：項目を選んでください")
                continue
            if start_label not in label_to_month:
                errors.append(f"{i + 1}行目：開始年月を選んでください")
                continue
            end_label = row["終了年月"] if isinstance(row["終了年月"], str) else ""
            end_month = label_to_month.get(end_label)
            if end_label and end_month is None:
                errors.append(f"{i + 1}行目：終了年月の指定が正しくありません")
                continue
            start_month = label_to_month[start_label]
            if end_month is not None and end_month < start_month:
                errors.append(f"{i + 1}行目：終了年月は開始年月以降にしてください")
                continue
            total_amount = int(row["金額"]) if pd.notna(row["金額"]) else None
            if total_amount is None or total_amount < 0:
                errors.append(f"{i + 1}行目：金額を入力してください")
                continue
            existing_ids = list(row["_ids"]) if isinstance(row["_ids"], list) else []

            target_person_ids = (
                [p["id"] for p in people] if person_choice == BOTH_LABEL
                else [name_to_id[person_choice]]
            )
            n = len(target_person_ids)
            base_share = total_amount // n
            for j, pid in enumerate(target_person_ids):
                share = base_share + (total_amount - base_share * n if j == 0 else 0)
                parsed.append({
                    "id": existing_ids[j] if j < len(existing_ids) else None,
                    "person_id": pid,
                    "field": field_label_to_key[field_label],
                    "start_month": start_month,
                    "end_month": end_month,
                    "amount": share,
                })
            for extra_id in existing_ids[n:]:
                parsed.append({"id": extra_id, "_delete": True})

        if errors:
            for e in errors:
                st.warning(e)
        else:
            kept_ids = {p["id"] for p in parsed if p["id"] is not None and not p.get("_delete")}
            for pr in periods:
                if pr["id"] not in kept_ids:
                    db.delete_assumption_period(pr["id"])
            for p in parsed:
                if p.pop("_delete", False):
                    continue
                period_id = p.pop("id")
                if period_id is None:
                    db.add_assumption_period(plan_id, **p)
                else:
                    db.update_assumption_period(period_id, **p)
            st.success(f"{len(period_edited)}件を保存しました")
            st.rerun()

    st.write("")
    theme.section("住宅ローンへの切り替え（家賃の代わり）")
    st.caption(
        "賃貸から住宅購入に切り替える場合の設定です。ローン開始月から完済まで、家賃の代わりに"
        "毎月の返済額ぶん現金が減りますが、その返済額は消えずに（投資拠出と同じ仕組みで）"
        "年率の値動きを乗せながら資産として積み上がります。完済後は返済が止まり、"
        "評価額はそのまま年率で変動し続けます。金利・元利内訳・ローン残債は扱いません。"
    )
    st.caption(
        "住宅購入後は家賃が不要になる分、上の「期間ごとの変更」で家賃の想定額を"
        "ローン開始月から0円にしておくと、二重に計上されずに済みます。"
        "「対象者」で**二人**を選ぶと、返済額を2等分してそれぞれの持分として計上します。"
    )

    re_months = simulation.month_range(settings["simulation_start_month"], simulation.INPUT_MONTHS)
    re_month_labels = {m: simulation.month_label(m) for m in re_months}
    re_label_to_month = {v: k for k, v in re_month_labels.items()}
    BOTH_LABEL = "二人（折半）"
    re_person_options = [p["name"] for p in people] + [BOTH_LABEL]

    properties = db.get_real_estate(plan_id)
    # ラベル＋条件がすべて一致する行は「二人（折半）」で登録されたものとみなしてまとめて表示する
    groups: dict[tuple, list[dict]] = {}
    for pr in properties:
        key = (pr["label"], pr["purchase_month"], pr["monthly_payment"],
               pr["loan_term_months"], pr["annual_appreciation_pct"])
        groups.setdefault(key, []).append(pr)

    re_editor_rows = []
    for (label, purchase_month, per_person_payment, loan_term_months, rate), rows in groups.items():
        pids = [r["person_id"] for r in rows]
        is_both = len(rows) == len(people) and len(people) > 1 and set(pids) == {p["id"] for p in people}
        display_payment = per_person_payment * len(people) if is_both else per_person_payment
        re_editor_rows.append({
            "対象者": BOTH_LABEL if is_both else id_to_name.get(pids[0], people[0]["name"]),
            "内容": label,
            "ローン開始年月": re_month_labels.get(purchase_month, purchase_month),
            "毎月の返済額": int(display_payment),
            "返済年数": round(loan_term_months / 12, 1),
            "年間の値動き（%）": float(rate),
            "_ids": [r["id"] for r in rows],
        })

    re_editor_df = pd.DataFrame(
        re_editor_rows,
        columns=["対象者", "内容", "ローン開始年月", "毎月の返済額", "返済年数",
                "年間の値動き（%）", "_ids"],
    ).astype({"対象者": "string", "内容": "string", "ローン開始年月": "string",
              "毎月の返済額": "Int64", "返済年数": "float64", "年間の値動き（%）": "float64"})

    re_edited = st.data_editor(
        re_editor_df,
        num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "対象者": st.column_config.SelectboxColumn(options=re_person_options, required=True),
            "内容": st.column_config.TextColumn(required=True, help="例：東京の自宅マンション"),
            "ローン開始年月": st.column_config.SelectboxColumn(
                options=list(re_month_labels.values()), required=True),
            "毎月の返済額": st.column_config.NumberColumn(
                format="localized", min_value=0, step=10000,
                help="「二人」を選んだ場合は世帯としての合計返済額を入力します（自動で2等分されます）"),
            "返済年数": st.column_config.NumberColumn(min_value=1.0, max_value=50.0, step=1.0,
                                                    help="例：35年ローンなら35"),
            "年間の値動き（%）": st.column_config.NumberColumn(
                min_value=-100.0, max_value=100.0, step=0.1,
                help="値上がりなら正の値、値下がりなら負の値。0なら物件価値の変動を見込みません。"),
            "_ids": None,
        },
        key=f"real_estate_editor_{plan_id}",
    )

    if st.button("住宅ローンの登録を保存", type="primary"):
        errors = []
        parsed = []
        for i, row in re_edited.iterrows():
            label = row["内容"].strip() if isinstance(row["内容"], str) else ""
            if not label:
                continue  # 空行は無視
            person_choice = row["対象者"] if isinstance(row["対象者"], str) else ""
            if person_choice not in re_person_options:
                errors.append(f"{i + 1}行目「{label}」：対象者を選んでください")
                continue
            month_label_val = row["ローン開始年月"] if isinstance(row["ローン開始年月"], str) else ""
            if month_label_val not in re_label_to_month:
                errors.append(f"{i + 1}行目「{label}」：ローン開始年月を選んでください")
                continue
            total_payment = int(row["毎月の返済額"]) if pd.notna(row["毎月の返済額"]) else 0
            if total_payment <= 0:
                errors.append(f"{i + 1}行目「{label}」：毎月の返済額を入力してください")
                continue
            years = float(row["返済年数"]) if pd.notna(row["返済年数"]) else 0.0
            if years <= 0:
                errors.append(f"{i + 1}行目「{label}」：返済年数を入力してください")
                continue
            rate = float(row["年間の値動き（%）"]) if pd.notna(row["年間の値動き（%）"]) else 0.0
            existing_ids = list(row["_ids"]) if isinstance(row["_ids"], list) else []

            target_person_ids = (
                [p["id"] for p in people] if person_choice == BOTH_LABEL
                else [name_to_id[person_choice]]
            )
            n = len(target_person_ids)
            base_share = total_payment // n
            for j, pid in enumerate(target_person_ids):
                # 端数は最初の1人に寄せる（合計が入力額とずれないように）
                share = base_share + (total_payment - base_share * n if j == 0 else 0)
                parsed.append({
                    "id": existing_ids[j] if j < len(existing_ids) else None,
                    "person_id": pid,
                    "label": label,
                    "purchase_month": re_label_to_month[month_label_val],
                    "monthly_payment": share,
                    "loan_term_months": round(years * 12),
                    "annual_appreciation_pct": rate,
                })
            # 人数が減った場合（二人→一人など）に余った旧行を削除対象にする
            for extra_id in existing_ids[n:]:
                parsed.append({"id": extra_id, "_delete": True})

        if errors:
            for e in errors:
                st.warning(e)
        else:
            kept_ids = {p["id"] for p in parsed if p["id"] is not None and not p.get("_delete")}
            for pr in properties:
                if pr["id"] not in kept_ids:
                    db.delete_real_estate(pr["id"])
            for p in parsed:
                if p.pop("_delete", False):
                    continue
                re_id = p.pop("id")
                if re_id is None:
                    db.add_real_estate(plan_id, **p)
                else:
                    db.update_real_estate(re_id, **p)
            st.success(f"{len(re_edited)}件を保存しました")
            st.rerun()


# ══════════ 資産・運用 ══════════
with tab_assets:
    theme.section("投資の運用条件")
    with st.form("form_investment"):
        c1, c2 = st.columns(2)
        return_pct = c1.number_input("想定年利（%）", min_value=-100.0, max_value=100.0, step=0.1,
                                     value=float(settings["expected_annual_return_pct"]),
                                     key=f"return_pct_{plan_id}")
        compounding = c2.selectbox(
            "複利の頻度", options=["monthly", "annually"],
            index=["monthly", "annually"].index(settings["compounding"]),
            format_func=lambda v: "毎月複利" if v == "monthly" else "年1回複利",
            key=f"compounding_{plan_id}")
        if st.form_submit_button("運用条件を保存"):
            db.update_settings(plan_id, expected_annual_return_pct=float(return_pct), compounding=compounding)
            st.success("保存しました")
            st.rerun()

    st.write("")
    theme.section("シミュレーションの開始月")
    st.caption(
        "何年後まで試算するかは、「シミュレーション」ページの上部で切り替えます"
        "（全プラン共通の設定です）。"
    )
    with st.form("form_period"):
        c1, c2 = st.columns(2)
        sim_start = c1.text_input("シミュレーション開始月（YYYY-MM）",
                                  value=settings["simulation_start_month"],
                                  key=f"sim_start_{plan_id}")
        balance_month = c2.text_input("残高の基準月（YYYY-MM・通常は開始月の前月）",
                                      value=settings["starting_balance_month"],
                                      key=f"balance_month_{plan_id}")
        if st.form_submit_button("開始月を保存"):
            db.update_settings(
                plan_id,
                simulation_start_month=sim_start.strip(),
                starting_balance_month=balance_month.strip(),
            )
            st.success("保存しました")
            st.rerun()

    st.write("")
    theme.section("開始残高（人ごと）")
    st.caption("シミュレーション開始月の前月末時点の残高を、1人ずつ入力してください。")
    with st.form("form_balances"):
        balance_inputs = {p["id"]: {} for p in people}
        header = st.columns([1.6] + [1] * len(people))
        header[0].markdown("**項目**")
        for i, p in enumerate(people):
            header[i + 1].markdown(f"**{p['name']}**")

        for field, label in (("starting_cash_balance", "開始時点の現金残高"),
                             ("starting_investment_balance", "開始時点の投資残高")):
            cols = st.columns([1.6] + [1] * len(people))
            cols[0].markdown(f"<div style='padding-top:.55rem'>{label}</div>",
                             unsafe_allow_html=True)
            for i, p in enumerate(people):
                current = person_assumptions.get(p["id"], {}).get(field) or 0
                balance_inputs[p["id"]][field] = cols[i + 1].number_input(
                    p["name"], min_value=0, step=1000,
                    value=int(current), label_visibility="visible",
                    key=f"balance_{plan_id}_{field}_{p['id']}",
                )

        if st.form_submit_button("開始残高を保存", type="primary"):
            for pid, fields in balance_inputs.items():
                db.update_person_assumptions(plan_id, pid, **{k: int(v) for k, v in fields.items()})
            st.success("保存しました")
            st.rerun()

    st.write("")
    theme.section("現金がたまったら自動で投資に回す")
    st.caption(
        "現金残高がここで決めた額を超えたら、超過分を自動的に投資へ回します。"
        "空欄（0）にすると自動振替は行いません。実績の現金残高を入力した月には適用されません"
        "（実際の残高がそのまま正になるため）。"
    )
    with st.form("form_sweep"):
        sweep_inputs = {}
        cols = st.columns(len(people))
        for i, p in enumerate(people):
            current = person_assumptions.get(p["id"], {}).get("cash_sweep_threshold")
            sweep_inputs[p["id"]] = cols[i].number_input(
                f"{p['name']}の現金の上限（円）", min_value=0, step=100000,
                value=int(current) if current is not None else 0,
                help="例：200万円を超えた分は投資に回す",
                key=f"sweep_{plan_id}_{p['id']}",
            )
        if st.form_submit_button("自動振替の設定を保存"):
            for pid, amount in sweep_inputs.items():
                db.update_person_assumptions(
                    plan_id, pid, cash_sweep_threshold=int(amount) if amount > 0 else None)
            st.success("保存しました")
            st.rerun()


# ══════════ 臨時収支 ══════════
with tab_planned:
    theme.section("ボーナス・イベント出費")
    st.caption(
        "毎月の想定額とは別に、特定の月にだけ発生する収入・支出を登録します。"
        "ボーナスのように毎年同じ月に繰り返すものと、旅行などの単発の両方に対応しています。"
    )

    st.caption(
        "表に直接入力して、複数まとめて追加・編集できます。行の追加は一番下の空行へ、"
        "削除は行を選んで Delete キーです。入力し終えたら「保存」を押します。"
    )

    months = simulation.month_range(settings["simulation_start_month"], simulation.INPUT_MONTHS)
    people_names = [p["name"] for p in people]
    name_to_id = {p["name"]: p["id"] for p in people}
    id_to_name = {p["id"]: p["name"] for p in people}
    BOTH_LABEL = "二人（折半）"
    PLANNED_PERSON_OPTIONS = people_names + [BOTH_LABEL]

    # 「時期」1列で単発／毎年の両方を表す。空欄（null）を作らないための設計で、
    # 表の中に "None" が並ぶのを避ける。
    YEARLY_OPTIONS = [f"毎年{m}月" for m in range(1, 13)]
    once_label_to_month = {simulation.month_label(m): m for m in months}
    TIMING_OPTIONS = YEARLY_OPTIONS + list(once_label_to_month.keys())

    def _timing_of(it) -> str:
        if it["recurrence"] == "yearly":
            return f"毎年{it['month_of_year']}月"
        return simulation.month_label(it["month"]) if it["month"] else TIMING_OPTIONS[0]

    def _years_of(it) -> str:
        if it["recurrence"] != "yearly" or not (it["start_year"] or it["end_year"]):
            return ""
        return f"{it['start_year'] or ''}-{it['end_year'] or ''}"

    items = db.get_planned_items(plan_id)
    # 種類・内容・金額・時期・対象期間がすべて一致する行は「二人（折半）」で登録されたものとみなす
    item_groups: dict[tuple, list[dict]] = {}
    for it in items:
        key = (it["item_type"], it["label"], it["amount"], it["recurrence"],
               it["month"], it["month_of_year"], it["start_year"], it["end_year"])
        item_groups.setdefault(key, []).append(it)

    editor_rows = []
    for (item_type, label, per_person_amount, recurrence, month, moy, sy, ey), rows in item_groups.items():
        pids = [r["person_id"] for r in rows]
        is_both = len(rows) == len(people) and len(people) > 1 and set(pids) == {p["id"] for p in people}
        display_amount = per_person_amount * len(people) if is_both else per_person_amount
        editor_rows.append({
            "種類": "収入" if item_type == "income" else "支出",
            "内容": label,
            "金額": int(display_amount),
            "対象者": BOTH_LABEL if is_both else id_to_name.get(pids[0], people_names[0]),
            "時期": _timing_of(rows[0]),
            "対象期間": _years_of(rows[0]),
            "_ids": [r["id"] for r in rows],
        })

    editor_df = pd.DataFrame(
        editor_rows, columns=["種類", "内容", "金額", "対象者", "時期", "対象期間", "_ids"]
    ).astype({"種類": "string", "内容": "string", "対象者": "string",
              "時期": "string", "対象期間": "string", "金額": "Int64"})

    edited = st.data_editor(
        editor_df,
        num_rows="dynamic", width="stretch", hide_index=True,
        column_config={
            "種類": st.column_config.SelectboxColumn(options=["収入", "支出"], required=True),
            "内容": st.column_config.TextColumn(required=True, help="例：夏季賞与、家族旅行"),
            "金額": st.column_config.NumberColumn(
                format="localized", min_value=0, step=10000,
                help="「二人」を選んだ場合は世帯としての合計額を入力します（自動で2等分されます）"),
            "対象者": st.column_config.SelectboxColumn(
                options=PLANNED_PERSON_OPTIONS, required=True,
                help="人ごとに集計するため、どちらが受け取る／支払うかを選びます。二人で折半する場合は「二人」を選びます"),
            "時期": st.column_config.SelectboxColumn(
                options=TIMING_OPTIONS, required=True,
                help="ボーナスなど毎年繰り返すものは「毎年◯月」、旅行など1回だけのものは年月を選びます"),
            "対象期間": st.column_config.TextColumn(
                help="「毎年◯月」を特定の期間だけに限る場合のみ。例：2027-2031、2029-（以降ずっと）"),
            "_ids": None,  # 内部用のため非表示
        },
        key=f"planned_editor_{plan_id}",
    )

    if st.button("臨時収支を保存", type="primary"):
        errors = []
        parsed = []
        for i, row in edited.iterrows():
            label = row["内容"].strip() if isinstance(row["内容"], str) else ""
            if not label:
                continue  # 空行は無視
            total_amount = int(row["金額"]) if pd.notna(row["金額"]) else 0
            if total_amount <= 0:
                errors.append(f"{i + 1}行目「{label}」：金額を入力してください")
                continue
            person_choice = row["対象者"] if isinstance(row["対象者"], str) else ""
            if person_choice not in PLANNED_PERSON_OPTIONS:
                errors.append(f"{i + 1}行目「{label}」：対象者を選んでください")
                continue
            timing = row["時期"] if isinstance(row["時期"], str) else ""
            if timing not in TIMING_OPTIONS:
                errors.append(f"{i + 1}行目「{label}」：時期を選んでください")
                continue

            if timing in YEARLY_OPTIONS:
                recurrence, month = "yearly", None
                moy = YEARLY_OPTIONS.index(timing) + 1
                years = row["対象期間"].strip() if isinstance(row["対象期間"], str) else ""
                start_year = end_year = None
                if years:
                    parts = years.replace("〜", "-").replace("~", "-").split("-")
                    try:
                        start_year = int(parts[0]) if parts[0].strip() else None
                        end_year = int(parts[1]) if len(parts) > 1 and parts[1].strip() else None
                    except ValueError:
                        errors.append(
                            f"{i + 1}行目「{label}」：対象期間は「2027-2031」の形式で入力してください")
                        continue
            else:
                recurrence, moy = "once", None
                month = once_label_to_month[timing]
                start_year = end_year = None

            existing_ids = list(row["_ids"]) if isinstance(row["_ids"], list) else []
            target_person_ids = (
                [p["id"] for p in people] if person_choice == BOTH_LABEL
                else [name_to_id[person_choice]]
            )
            n = len(target_person_ids)
            base_share = total_amount // n
            for j, pid in enumerate(target_person_ids):
                share = base_share + (total_amount - base_share * n if j == 0 else 0)
                parsed.append({
                    "id": existing_ids[j] if j < len(existing_ids) else None,
                    "item_type": "income" if row["種類"] == "収入" else "expense",
                    "label": label,
                    "amount": share,
                    "person_id": pid,
                    "recurrence": recurrence,
                    "month": month,
                    "month_of_year": moy,
                    "start_year": start_year,
                    "end_year": end_year,
                })
            for extra_id in existing_ids[n:]:
                parsed.append({"id": extra_id, "_delete": True})

        if errors:
            for e in errors:
                st.warning(e)
        else:
            kept_ids = {p["id"] for p in parsed if p["id"] is not None and not p.get("_delete")}
            for it in items:
                if it["id"] not in kept_ids:
                    db.delete_planned_item(it["id"])
            for p in parsed:
                if p.pop("_delete", False):
                    continue
                item_id = p.pop("id")
                if item_id is None:
                    db.add_planned_item(plan_id, **p)
                else:
                    db.update_planned_item(item_id, **p)
            st.success(f"{len(edited)}件を保存しました")
            st.rerun()


# ══════════ カード ══════════
with tab_cards:
    theme.section("クレジットカードの登録")
    st.caption(
        "夫婦それぞれが使うカードを個別に登録します。登録したカードに対して"
        "「月次実績入力」ページでCSV明細を取り込むと、保有者本人の実績として集計されます。"
    )

    cards = db.get_credit_cards()
    if cards:
        for c in cards:
            owner_name = next((p["name"] for p in people if p["id"] == c["owner_person_id"]), "未設定")
            cols = st.columns([3, 1.2, 0.8])
            cols[0].write(f"**{c['name']}**")
            cols[1].write(owner_name)
            if cols[2].button("削除", key=f"delete_card_{c['id']}"):
                db.delete_credit_card(c["id"])
                st.rerun()
        st.caption("カードを削除すると、そのカードの取込済み明細もあわせて削除されます。")
    else:
        st.caption("まだ登録がありません。")

    st.write("")
    with st.form("form_add_card"):
        c1, c2, c3 = st.columns([2, 1, 1])
        new_card_name = c1.text_input("カード名")
        owner_choice = c2.selectbox("保有者", options=[p["name"] for p in people])
        submitted = c3.form_submit_button("カードを追加")
        if submitted:
            if new_card_name.strip():
                owner_id = next(p["id"] for p in people if p["name"] == owner_choice)
                db.add_credit_card(new_card_name.strip(), owner_id)
                st.success(f"「{new_card_name}」を追加しました")
                st.rerun()
            else:
                st.warning("カード名を入力してください")
