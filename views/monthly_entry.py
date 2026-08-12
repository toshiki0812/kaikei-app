from datetime import datetime

import streamlit as st

import csv_import
import db
import simulation
import theme
from theme import yen

plan_id = db.get_active_plan_id()

theme.page_header(
    "月次実績入力",
    "実際の金額を入力すると、その月は想定値ではなく実績としてシミュレーションに反映されます。"
    "空欄のままの項目は想定値が使われます。",
)
st.caption("ここで入力する実績は**全プラン共通**です。1回入力すれば、どのプランにも反映されます。")

settings = db.get_settings(plan_id)
people = db.get_people()
current_month = datetime.now().strftime("%Y-%m")

# 実績を入力するのは過去〜今月なので、開始月から今月の少し先までに絞る。
# 何十年も先まで並べるとスマホで選びづらいため。
start_month = settings["simulation_start_month"]
n_months = max(simulation.month_diff(start_month, current_month) + 4, 12)
months = simulation.month_range(start_month, n_months)
default_index = months.index(current_month) if current_month in months else 0

month = st.selectbox("入力する月", options=months, index=default_index,
                     format_func=simulation.month_label)

person_actuals = db.get_month_person_actuals(month)
cc_actuals = db.get_month_credit_card_actuals(month)

ACTUAL_ROWS = [
    ("income", "収入", None),
    ("rent", "家賃", "自分が負担した分だけ入力します"),
    ("investment_contribution", "投資拠出額", None),
    ("other_expense", "その他既知支出", None),
    ("bank_cash_balance_eom", "現金残高（銀行口座・月末）",
     "この値を入れると、収入と既知の支出から「その他（現金支出）」が自動算出されます。"),
    ("investment_balance_eom", "投資残高（証券口座・月末）",
     "実際の残高。入力すると想定利回りでの複利計算より優先され、以降の予測もこの残高から続きます。"),
]

st.write("")
theme.section("収入・固定費・残高")
st.caption("空欄のままにした項目は、その月は想定値が使われます。")

with st.form("form_monthly_actual"):
    inputs = {p["id"]: {} for p in people}
    header = st.columns([1.9] + [1] * len(people))
    header[0].markdown("**項目**")
    for i, p in enumerate(people):
        header[i + 1].markdown(f"**{p['name']}**")

    for field, label, help_text in ACTUAL_ROWS:
        cols = st.columns([1.9] + [1] * len(people))
        cols[0].markdown(f"<div style='padding-top:.55rem'>{label}</div>",
                         unsafe_allow_html=True)
        for i, p in enumerate(people):
            current = person_actuals.get(p["id"], {}).get(field)
            inputs[p["id"]][field] = cols[i + 1].number_input(
                f"{p['name']}の{label}（円）", min_value=0, step=1000,
                value=int(current) if current is not None else None,
                placeholder="未入力", label_visibility="collapsed",
                help=help_text, key=f"actual_{month}_{field}_{p['id']}",
            )

    note_cols = st.columns([1.9] + [1] * len(people))
    note_cols[0].markdown("<div style='padding-top:.55rem'>メモ（任意）</div>",
                          unsafe_allow_html=True)
    notes = {}
    for i, p in enumerate(people):
        notes[p["id"]] = note_cols[i + 1].text_input(
            f"{p['name']}のメモ", value=person_actuals.get(p["id"], {}).get("notes") or "",
            label_visibility="collapsed", key=f"actual_notes_{month}_{p['id']}",
        )

    if st.form_submit_button("この月の実績を保存", type="primary"):
        for pid, fields in inputs.items():
            db.upsert_person_actual(
                pid, month,
                notes=notes[pid] or None,
                **{k: (None if v is None else int(v)) for k, v in fields.items()},
            )
        st.success(f"{simulation.month_label(month)}の実績を保存しました")
        st.rerun()

st.divider()

theme.section("クレジットカード")
st.caption("カードは人ごとに管理しているため、クレカ合計も1人ずつ表示・入力します。")

cards = db.get_credit_cards()
people_by_id = {p["id"]: p["name"] for p in people}

status_cols = st.columns(len(people))
for i, p in enumerate(people):
    entry = cc_actuals.get(p["id"])
    if entry:
        source = "CSV取込" if entry["source"] == "csv" else "手入力"
        status_cols[i].metric(f"{p['name']}のクレカ（{source}）", yen(entry["amount"]))
    else:
        status_cols[i].metric(f"{p['name']}のクレカ", "未入力")

with st.expander("手入力で修正する"):
    with st.form("form_cc_manual"):
        manual_inputs = {}
        cols = st.columns(len(people))
        for i, p in enumerate(people):
            entry = cc_actuals.get(p["id"])
            manual_inputs[p["id"]] = cols[i].number_input(
                f"{p['name']}のクレカ合計（円）", min_value=0, step=1000,
                value=int(entry["amount"]) if entry else None, placeholder="未入力",
            )
        if st.form_submit_button("手入力で保存"):
            for pid, amount in manual_inputs.items():
                if amount is None:
                    db.delete_credit_card_actual(pid, month)
                else:
                    db.upsert_credit_card_actual(pid, month, int(amount), source="manual")
            st.success("保存しました")
            st.rerun()

st.write("")
st.markdown("**CSV明細の取込**")

if not cards:
    st.info("CSV取込を使うには、先に「初期設定」ページの「カード」タブでクレジットカードを登録してください。")
else:
    card_names = {c["id"]: f"{c['name']}（{people_by_id.get(c['owner_person_id'], '未設定')}）"
                  for c in cards}
    c1, c2 = st.columns(2)
    card_id = c1.selectbox("取込先のカード", options=list(card_names.keys()),
                           format_func=lambda cid: card_names[cid])
    encoding_choice = c2.selectbox("文字コード（判定できない場合のみ変更）",
                                   options=["自動判定", "utf-8-sig", "cp932 (Shift-JIS)", "utf-8"])
    encoding_map = {"自動判定": None, "utf-8-sig": "utf-8-sig",
                    "cp932 (Shift-JIS)": "cp932", "utf-8": "utf-8"}
    card_owner_id = next(c["owner_person_id"] for c in cards if c["id"] == card_id)

    if card_owner_id is None:
        st.warning("このカードには保有者が設定されていません。「初期設定」ページで登録し直してください。")
    else:
        uploaded = st.file_uploader("カード会社サイトからダウンロードしたCSVファイル", type=["csv"])

        if uploaded is not None:
            raw = uploaded.getvalue()
            try:
                df, used_encoding = csv_import.decode_csv(raw, encoding_map[encoding_choice])
            except ValueError as e:
                st.error(str(e))
                df, used_encoding = None, None

            if df is not None:
                st.caption(f"文字コード: {used_encoding}／{len(df)}行")
                st.dataframe(df.head(5), width="stretch")

                cols_available = list(df.columns)
                c3, c4, c5 = st.columns(3)
                date_col = c3.selectbox("日付の列", options=cols_available, key="date_col")
                desc_col = c4.selectbox("内容（店名など）の列", options=cols_available, key="desc_col")
                amount_col = c5.selectbox("金額の列", options=cols_available, key="amount_col")

                rows, errors = csv_import.build_transactions(df, date_col, desc_col, amount_col)
                total = sum(r["amount"] for r in rows)
                st.write(f"読み込み可能 {len(rows)}件（合計 {yen(total)}）／読み込めなかった行 {len(errors)}件")
                if errors:
                    with st.expander("読み込めなかった行を見る"):
                        st.dataframe(errors, width="stretch")

                touched_months = sorted({r["month"] for r in rows})
                manual_months = csv_import.months_with_manual_credit_card(touched_months, card_owner_id)
                if manual_months:
                    st.warning(
                        f"次の月は{people_by_id[card_owner_id]}のクレカ合計が手入力済みです。"
                        "取り込むとCSVの集計値で上書きされます：　"
                        + "、".join(simulation.month_label(m) for m in manual_months)
                    )

                if rows and st.button("この内容で取り込む", type="primary"):
                    summary = csv_import.commit_import(card_id, uploaded.name, rows)
                    st.success(
                        f"取込完了：新規 {summary['inserted']}件／重複スキップ {summary['skipped']}件"
                        f"（対象月：{'、'.join(simulation.month_label(m) for m in summary['months'])}）"
                    )
                    st.rerun()
