import pandas as pd
import streamlit as st

import charts
import db
import simulation
import theme
from theme import yen

plan_id = db.get_active_plan_id()
plan = db.get_plan(plan_id)
settings = db.get_settings(plan_id)
horizon_years = db.get_horizon_years()

theme.page_header(
    "シミュレーション",
    f"入力済みの実績を反映しながら、今後{horizon_years}年間（{horizon_years * 12}ヶ月）の推移を試算します。",
)
st.caption(f"表示中のプラン：**{plan['name']}**（左のサイドバーで切り替えられます）")

# 期間は「どこまで先を見たいか」という見方の設定なので、プランごとではなくここで切り替える。
# スマホでも片手で選べるよう、スライダーではなく選択式にしている。
horizon_options = list(simulation.HORIZON_OPTIONS)
picked_horizon = st.selectbox(
    "何年後まで試算するか", options=horizon_options,
    index=horizon_options.index(horizon_years) if horizon_years in horizon_options else 1,
    format_func=lambda y: f"{y}年後まで",
    help="35年ローンの完済後まで見たいときは長めに設定してください。全プラン共通の設定です。",
)
if picked_horizon != horizon_years:
    db.set_horizon_years(picked_horizon)
    st.rerun()

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
end_total_assets = end["cash_balance"] + end["investment_balance"] + end["real_estate_value"]
end_asset_sub = f"現金 {yen(end['cash_balance'])}　＋　投資 {yen(end['investment_balance'])}"
if end["real_estate_value"]:
    end_asset_sub += f"　＋　不動産 {yen(end['real_estate_value'])}"
theme.hero(
    f"{simulation.month_label(end['month'])}の資産（{scope_labels[scope_key]}）",
    yen(end_total_assets),
    sub=end_asset_sub,
    chips=[f"投資の増加 {yen(end['investment_balance'] - start['investment_balance'])}",
           f"{len(df)}ヶ月の収支累計 {yen(df['net_cash_flow'].sum())}"],
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
    if (df["real_estate_value"] > 0).any():
        st.plotly_chart(charts.real_estate_chart(df), use_container_width=True)
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

        plan_settings = {p["id"]: db.get_settings(p["id"]) for p in shown}
        # 期間は全プラン共通なので、どのプランも同じ時点で比較できる
        compare_horizon_years = horizon_years
        frames = {
            p["name"]: simulation.view_frame(simulation.build_projection(p["id"]), scope)
            for p in shown
        }
        compare_scope_label = scope_labels[scope_key]

        st.plotly_chart(
            charts.plan_comparison_chart(
                frames, "cash_balance", f"現金残高の推移（プラン比較・{compare_scope_label}）"),
            use_container_width=True,
        )
        st.plotly_chart(
            charts.plan_comparison_chart(
                frames, "investment_balance", f"投資残高の推移（プラン比較・{compare_scope_label}）"),
            use_container_width=True,
        )
        if any((f["real_estate_value"] > 0).any() for f in frames.values()):
            st.plotly_chart(
                charts.plan_comparison_chart(
                    frames, "real_estate_value", f"不動産評価額の推移（プラン比較・{compare_scope_label}）"),
                use_container_width=True,
            )

        # --- 資産合計の逆転（損益分岐点） ---
        if len(shown) == 2:
            name_a, name_b = [p["name"] for p in shown]

            def _total_assets_series(f):
                return f["cash_balance"] + f["investment_balance"] + f["real_estate_value"]

            diff = _total_assets_series(frames[name_a]) - _total_assets_series(frames[name_b])
            leader_first = name_a if diff.iloc[0] >= 0 else name_b
            crossover_month = None
            for idx in range(1, len(diff)):
                if (diff.iloc[idx] >= 0) != (diff.iloc[0] >= 0):
                    crossover_month = frames[name_a]["month_label"].iloc[idx]
                    leader_after = name_b if leader_first == name_a else name_a
                    break
            if crossover_month:
                st.info(
                    f"**{crossover_month}ごろ、資産合計の大小が「{leader_first}」→「{leader_after}」で逆転します。**"
                )
            else:
                st.caption(
                    f"この{compare_horizon_years}年間では、資産合計は常に「{leader_first}」が上回ったままです。"
                )

        theme.section(f"{compare_horizon_years}年後の比較（{compare_scope_label}）")
        rows = []
        for p in shown:
            f = frames[p["name"]]
            s = plan_settings[p["id"]]
            last = f.iloc[-1]
            rows.append({
                "プラン": p["name"],
                "現金残高": int(last["cash_balance"]),
                "投資残高": int(last["investment_balance"]),
                "不動産評価額": int(last["real_estate_value"]),
                "資産合計": int(last["cash_balance"] + last["investment_balance"]
                              + last["real_estate_value"]),
                "収支累計": int(f["net_cash_flow"].sum()),
                "想定年利": f"{s['expected_annual_return_pct']:g}%",
                "メモ": p["description"] or "",
            })
        comp = pd.DataFrame(rows)
        money_cols_cmp = ["現金残高", "投資残高", "不動産評価額", "資産合計", "収支累計"]
        st.caption("金額の単位は円です。")
        st.dataframe(
            comp, width="stretch", hide_index=True,
            column_config={c: st.column_config.NumberColumn(c, format="localized")
                           for c in money_cols_cmp},
        )

        best = comp.loc[comp["資産合計"].idxmax()]
        st.caption(
            f"{compare_horizon_years}年後の資産合計が最も大きいのは「{best['プラン']}」で "
            f"{yen(best['資産合計'])}（現金＋投資＋不動産）です。"
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
        "cash_shortfall_withdrawal": "投資から取り崩し",
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
        "real_estate_payment": "住宅ローン返済",
        "real_estate_value": "不動産評価額",
    }
    for p in scope_people:
        rename_map[f"income_p{p['id']}"] = f"{p['name']}の収入"
        rename_map[f"credit_card_p{p['id']}"] = f"{p['name']}のクレカ"

    display = display.rename(columns=rename_map)

    money_cols = (
        [f"{p['name']}の収入" for p in scope_people]
        + ["臨時収入", "収入合計", "家賃"]
        + [f"{p['name']}のクレカ" for p in scope_people]
        + ["投資拠出", "投資へ自動振替", "投資から取り崩し", "その他既知支出", "臨時支出", "住宅ローン返済",
           "その他（現金）", "支出合計", "月次収支", "現金残高", "投資残高", "不動産評価額"]
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
