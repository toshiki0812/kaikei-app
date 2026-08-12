import pandas as pd
import streamlit as st

import charts
import db
import simulation
import theme
from theme import yen

plan_id = db.get_active_plan_id()
plan = db.get_plan(plan_id)

theme.page_header(
    "シミュレーション",
    "入力済みの実績を反映しながら、今後10年間（120ヶ月）の推移を試算します。",
)
st.caption(f"表示中のプラン：**{plan['name']}**（左のサイドバーで切り替えられます）")

settings = db.get_settings(plan_id)
people = db.get_people()
full_df = simulation.build_projection(plan_id)

# --- 世帯合計／個人の切り替え ---
scope_labels = {"total": "世帯合計"} | {str(p["id"]): p["name"] for p in people}
scope_key = st.segmented_control(
    "対象", options=list(scope_labels.keys()), default="total",
    format_func=lambda k: scope_labels[k], label_visibility="collapsed",
) or "total"
scope = "total" if scope_key == "total" else int(scope_key)
df = simulation.view_frame(full_df, scope)
scope_people = people if scope == "total" else [p for p in people if p["id"] == scope]

n_actual = int((df["data_status"] == "actual").sum())
n_partial = int((df["data_status"] == "partial").sum())
n_projected = int((df["data_status"] == "projected").sum())

end = df.iloc[-1]
start = df.iloc[0]
theme.hero(
    f"{simulation.month_label(end['month'])}の資産（{scope_labels[scope_key]}）",
    yen(end["cash_balance"] + end["investment_balance"]),
    sub=f"現金 {yen(end['cash_balance'])}　＋　投資 {yen(end['investment_balance'])}",
    chips=[f"投資の増加 {yen(end['investment_balance'] - start['investment_balance'])}",
           f"120ヶ月の収支累計 {yen(df['net_cash_flow'].sum())}"],
)

st.caption(
    f"実績確定 {n_actual}ヶ月／一部実績 {n_partial}ヶ月／想定ベース {n_projected}ヶ月　—　"
    "グラフの実線は実績、破線は想定値にもとづく予測です。"
)

# 大きな支出を入れると現金が足りなくなることがある。見落とすと危ないので必ず知らせる。
shortfall = df[df["cash_balance"] < 0]
if not shortfall.empty:
    first = shortfall.iloc[0]
    worst = shortfall.loc[shortfall["cash_balance"].idxmin()]
    who = "" if scope == "total" else f"（{scope_labels[scope_key]}）"
    st.error(
        f"**現金が足りなくなる月があります{who}。**　"
        f"最初は {first['month_label']}、いちばん不足するのは {worst['month_label']} で "
        f"{yen(worst['cash_balance'])} です（全 {len(shortfall)}ヶ月）。"
        "　臨時支出の時期をずらす、投資拠出を減らす、現金の上限を上げるなどの調整をご検討ください。"
    )

st.write("")
# st.tabs は非表示側のコンテンツも先に描画するため、幅の広い表が正しく
# レイアウトされない。選択中のビューだけを描画する segmented_control を使う。
view = st.segmented_control("表示", ["グラフ", "月別一覧", "プラン比較"], default="グラフ",
                            label_visibility="collapsed")


# ══════════ グラフ ══════════
if view == "グラフ":
    st.plotly_chart(charts.cash_balance_chart(df), use_container_width=True)
    st.plotly_chart(
        charts.investment_chart(df, settings["expected_annual_return_pct"]),
        use_container_width=True,
    )
    st.plotly_chart(charts.expense_breakdown_chart(df, scope_people, 12),
                    use_container_width=True)

    swept = df[df["cash_sweep"] > 0]
    if not swept.empty:
        st.caption(
            f"現金の上限を超えた分を投資に回した月：{len(swept)}ヶ月　"
            f"（合計 {yen(swept['cash_sweep'].sum())}）"
        )

    upcoming = df[(df["planned_labels"] != "") & (df["data_status"] == "projected")].head(8)
    if not upcoming.empty:
        st.write("")
        theme.section("今後の臨時収支の予定")
        for _, r in upcoming.iterrows():
            st.write(f"- **{r['month_label']}**　{r['planned_labels']}")


# ══════════ プラン比較 ══════════
elif view == "プラン比較":
    plans = db.get_plans()
    if len(plans) < 2:
        st.info(
            "比較するにはプランが2つ以上必要です。"
            "「初期設定」ページの「プラン」タブで、今のプランをコピーして作成できます。"
        )
    else:
        shown = plans[:charts.MAX_COMPARED_PLANS]
        if len(plans) > charts.MAX_COMPARED_PLANS:
            st.caption(f"色を確実に見分けられる上限のため、先頭の{charts.MAX_COMPARED_PLANS}プランを表示しています。")

        frames = {p["name"]: simulation.build_projection(p["id"]) for p in shown}

        st.plotly_chart(
            charts.plan_comparison_chart(frames, "cash_balance", "現金残高の推移（プラン比較）"),
            use_container_width=True,
        )
        st.plotly_chart(
            charts.plan_comparison_chart(frames, "investment_balance", "投資残高の推移（プラン比較）"),
            use_container_width=True,
        )

        theme.section("10年後の比較")
        rows = []
        for p in shown:
            f = frames[p["name"]]
            s = db.get_settings(p["id"])
            last = f.iloc[-1]
            rows.append({
                "プラン": p["name"],
                "現金残高": int(last["cash_balance"]),
                "投資残高": int(last["investment_balance"]),
                "資産合計": int(last["cash_balance"] + last["investment_balance"]),
                "収支累計": int(f["net_cash_flow"].sum()),
                "想定年利": f"{s['expected_annual_return_pct']:g}%",
                "メモ": p["description"] or "",
            })
        comp = pd.DataFrame(rows)
        money_cols_cmp = ["現金残高", "投資残高", "資産合計", "収支累計"]
        st.caption("金額の単位は円です。")
        st.dataframe(
            comp, width="stretch", hide_index=True,
            column_config={c: st.column_config.NumberColumn(c, format="localized")
                           for c in money_cols_cmp},
        )

        best = comp.loc[comp["資産合計"].idxmax()]
        st.caption(
            f"10年後の資産合計が最も大きいのは「{best['プラン']}」で "
            f"{yen(best['資産合計'])}（現金＋投資）です。"
        )


# ══════════ 月別一覧 ══════════
else:
    status_labels = {"actual": "実績確定", "partial": "一部実績", "projected": "想定"}

    display = df.copy()
    display["状態"] = display["data_status"].map(status_labels)
    display["その他（現金）の根拠"] = display["other_cash_status"].map(
        {"actual": "実績から算出", "assumption": "想定値"})

    rename_map = {
        "month_label": "月",
        "rent": "家賃",
        "investment_contribution": "投資拠出",
        "cash_sweep": "投資へ自動振替",
        "other_expense": "その他既知支出",
        "planned_income": "臨時収入",
        "planned_expense": "臨時支出",
        "planned_labels": "臨時収支の内容",
        "other_cash_expense": "その他（現金）",
        "income_total": "収入合計",
        "credit_card_total": "クレジットカード",
        "total_expense": "支出合計",
        "net_cash_flow": "月次収支",
        "cash_balance": "現金残高",
        "investment_balance": "投資残高",
    }
    for p in scope_people:
        rename_map[f"income_p{p['id']}"] = f"{p['name']}の収入"
        rename_map[f"credit_card_p{p['id']}"] = f"{p['name']}のクレカ"

    display = display.rename(columns=rename_map)

    money_cols = (
        [f"{p['name']}の収入" for p in scope_people]
        + ["臨時収入", "収入合計", "家賃"]
        + [f"{p['name']}のクレカ" for p in scope_people]
        + ["投資拠出", "投資へ自動振替", "その他既知支出", "臨時支出", "その他（現金）",
           "支出合計", "月次収支", "現金残高", "投資残高"]
    )
    columns_order = ["月", "状態"] + money_cols + ["その他（現金）の根拠", "臨時収支の内容"]

    st.caption("金額の単位は円です。横にスクロールすると全項目を確認できます。")
    st.dataframe(
        display[columns_order],
        width="stretch", hide_index=True, height=560,
        column_config={c: st.column_config.NumberColumn(c, format="localized")
                       for c in money_cols},
    )

    csv_bytes = display[columns_order].to_csv(index=False).encode("utf-8-sig")
    st.download_button("CSVダウンロード", data=csv_bytes,
                       file_name="kakei_10year_simulation.csv", mime="text/csv")
