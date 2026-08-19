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
#
# 保存は on_change のときだけ。「画面の値と保存値がズレたら書き戻す」書き方だと、
# ユーザーが触っていない再実行でも発火して、二人が別々の端末で開いたときに
# 片方の設定をもう片方が上書きしてしまう。
HORIZON_KEY = "horizon_select"


def _save_horizon():
    db.set_horizon_years(st.session_state[HORIZON_KEY])


# 別の端末で変えられていたら、こちらの選択もそれに合わせる
if st.session_state.get("_horizon_stored") != horizon_years:
    st.session_state[HORIZON_KEY] = horizon_years
st.session_state["_horizon_stored"] = horizon_years

st.selectbox(
    "何年後まで試算するか", options=list(simulation.HORIZON_OPTIONS),
    key=HORIZON_KEY, on_change=_save_horizon,
    format_func=lambda y: f"{y}年後まで",
    help="35年ローンの完済後まで見たいときは長めに設定してください。全プラン共通の設定です。",
)

people = db.get_people()
full_df = simulation.build_projection(plan_id)
scope_labels = {"total": "世帯合計"} | {str(p["id"]): p["name"] for p in people}

n_actual = int((full_df["data_status"] == "actual").sum())
n_partial = int((full_df["data_status"] == "partial").sum())
n_projected = int((full_df["data_status"] == "projected").sum())

end = full_df.iloc[-1]
start = full_df.iloc[0]
end_asset_sub = f"現金 {yen(end['cash_balance'])}　＋　投資 {yen(end['investment_balance'])}"
if end["real_estate_value"]:
    end_asset_sub += f"　＋　不動産 {yen(end['real_estate_value'])}"
theme.hero(
    f"{simulation.month_label(end['month'])}の資産（世帯合計）",
    yen(end["total_assets"]),
    sub=end_asset_sub,
    chips=[f"投資の増加 {yen(end['investment_balance'] - start['investment_balance'])}",
           f"{len(full_df)}ヶ月の収支累計 {yen(full_df['net_cash_flow'].sum())}"],
)

# 誰がどれだけ持っているかは、切り替えずに一覧で見える方がいい。
# ここのカードの色は、下のグラフの線の色と揃えている。
household_end = int(end["total_assets"])
asset_cards = [{
    "label": "世帯合計", "value": yen(household_end), "icon": "✨", "tint": "blue",
    "sub": f"{horizon_years}年で {yen(household_end - int(start['total_assets']))} 増",
}]
PERSON_TINTS = ["amber", "green", "violet", "pink"]
for i, p in enumerate(people):
    person_end = int(end[f"total_assets_p{p['id']}"])
    share = f"世帯の {person_end / household_end * 100:.1f}%" if household_end else "—"
    asset_cards.append({
        "label": p["name"], "value": yen(person_end), "icon": "👤",
        "tint": PERSON_TINTS[i % len(PERSON_TINTS)], "sub": share,
    })
theme.stat_cards(asset_cards)

st.caption(
    f"実績確定 {n_actual}ヶ月／一部実績 {n_partial}ヶ月／想定ベース {n_projected}ヶ月　—　"
    "グラフの実線は実績、破線は想定値にもとづく予測です。"
)

# 大きな支出を入れると現金が足りなくなることがある。見落とすと危ないので、
# 世帯だけでなく一人ずつ調べて「誰の」現金が足りないのかまで出す。
for label, col in [("世帯全体", "cash_balance")] + [
        (p["name"], f"cash_balance_p{p['id']}") for p in people]:
    shortfall = full_df[full_df[col] < 0]
    if shortfall.empty:
        continue
    worst = shortfall.loc[shortfall[col].idxmin()]
    st.error(
        f"**{label}の現金が足りなくなる月があります。**　"
        f"最初は {shortfall.iloc[0]['month_label']}、いちばん不足するのは {worst['month_label']} で "
        f"{yen(worst[col])} です（全 {len(shortfall)}ヶ月）。"
        "　臨時支出の時期をずらす、投資拠出を減らす、現金の上限を上げるなどの調整をご検討ください。"
    )

st.write("")
# st.tabs は非表示側のコンテンツも先に描画するため、幅の広い表が正しく
# レイアウトされない。選択中のビューだけを描画する segmented_control を使う。
view = st.segmented_control("表示", ["グラフ", "月別一覧", "プラン比較"], default="グラフ",
                            label_visibility="collapsed")


# ══════════ グラフ ══════════
if view == "グラフ":
    st.plotly_chart(
        charts.scoped_balance_chart(full_df, people, "total_assets",
                                    "資産合計の推移（現金＋投資＋不動産）"),
        use_container_width=True,
    )
    st.plotly_chart(
        charts.scoped_balance_chart(full_df, people, "cash_balance", "現金残高の推移"),
        use_container_width=True,
    )
    st.plotly_chart(
        charts.scoped_balance_chart(
            full_df, people, "investment_balance",
            f"投資残高の推移（想定利回り{settings['expected_annual_return_pct']:g}%）"),
        use_container_width=True,
    )
    if (full_df["real_estate_value"] > 0).any():
        st.plotly_chart(
            charts.scoped_balance_chart(full_df, people, "real_estate_value",
                                        "不動産評価額の推移"),
            use_container_width=True,
        )
    st.plotly_chart(charts.expense_breakdown_chart(full_df, people, 12),
                    use_container_width=True)

    swept = full_df[full_df["cash_sweep"] > 0]
    if not swept.empty:
        st.caption(
            f"現金の上限を超えた分を投資に回した月：{len(swept)}ヶ月　"
            f"（合計 {yen(swept['cash_sweep'].sum())}）"
        )

    upcoming = full_df[(full_df["planned_labels"] != "")
                       & (full_df["data_status"] == "projected")].head(8)
    if not upcoming.empty:
        st.write("")
        theme.section("今後の臨時収支の予定")
        for _, r in upcoming.iterrows():
            st.write(f"- **{r['month_label']}**　{r['planned_labels']}")


# ══════════ プラン比較 ══════════
elif view == "プラン比較":
    plans = db.get_plans()
    shown: list[dict] = []
    if len(plans) < 2:
        st.info(
            "比較するにはプランが2つ以上必要です。"
            "「初期設定」ページの「プラン」タブで、今のプランをコピーして作成できます。"
        )
    else:
        # 色を確実に見分けられる本数に上限があるため、全プランは同時に出せない。
        # 以前は先頭から機械的に切っていて、後から作ったプランが黙って消えていた。
        # 「今見ているプラン」を必ず入れたうえで、あとは自分で入れ替えられるようにする。
        max_n = charts.MAX_COMPARED_PLANS
        name_by_id = {p["id"]: p["name"] for p in plans}
        default_ids = ([plan_id] if plan_id in name_by_id else []) + [
            p["id"] for p in plans if p["id"] != plan_id]
        picked_ids = st.multiselect(
            "比較するプラン", options=[p["id"] for p in plans],
            default=default_ids[:max_n], format_func=lambda i: name_by_id[i],
            max_selections=max_n,
            help=f"色を見分けられる上限のため、同時に比較できるのは{max_n}プランまでです。"
                 "見たいプランに入れ替えてください。",
        )
        shown = [p for p in plans if p["id"] in picked_ids]
        if len(shown) < 2:
            st.info("比較するプランを2つ以上選んでください。")

    if len(shown) >= 2:
        # 試算はプランごとに1回だけ。切り口（世帯／各自）は view_frame で切り出す。
        # 想定値はテーブルごとに1回でまとめて読む（プランごとに読むと往復が増えて遅い）。
        shown_ids = [p["id"] for p in shown]
        bundle = db.get_plan_bundle(shown_ids)
        plan_settings = {pid: bundle[pid]["settings"] for pid in shown_ids}
        by_id = simulation.build_projections(shown_ids, bundle=bundle)
        projections = {p["name"]: by_id[p["id"]] for p in shown}

        st.caption(
            "世帯合計・"
            + "・".join(p["name"] for p in people)
            + "の順に並べています。プランの色はどの切り口でも同じです。"
        )

        for scope_key, scope_label in scope_labels.items():
            scope = "total" if scope_key == "total" else int(scope_key)
            frames = {name: simulation.view_frame(pdf, scope)
                      for name, pdf in projections.items()}

            theme.section(scope_label, f"{horizon_years}年後まで・4項目")

            # 想定がまったく同じプランは線が完全に重なって1本にしか見えない。
            # 「グラフが描かれていない」と誤解されるので先に伝えておく。
            overlaps = []
            names = list(frames.keys())
            for i, a in enumerate(names):
                for b in names[i + 1:]:
                    if frames[a]["total_assets"].equals(frames[b]["total_assets"]):
                        overlaps.append(f"{a}と{b}")
            if overlaps:
                st.caption(f"{scope_label}では想定が同じため、{'、'.join(overlaps)}の線は完全に重なっています。")

            st.plotly_chart(
                charts.plan_comparison_chart(
                    frames, "total_assets", f"資産合計の推移（{scope_label}）"),
                use_container_width=True,
            )
            st.plotly_chart(
                charts.plan_comparison_chart(
                    frames, "investment_balance", f"投資残高の推移（{scope_label}）"),
                use_container_width=True,
            )
            st.plotly_chart(
                charts.plan_comparison_chart(
                    frames, "cash_balance", f"現金残高の推移（{scope_label}）"),
                use_container_width=True,
            )
            if any((f["real_estate_value"] > 0).any() for f in frames.values()):
                st.plotly_chart(
                    charts.plan_comparison_chart(
                        frames, "real_estate_value", f"不動産評価額の推移（{scope_label}）"),
                    use_container_width=True,
                )

            # --- 資産合計の逆転（損益分岐点） ---
            if len(shown) == 2:
                name_a, name_b = [p["name"] for p in shown]
                diff = frames[name_a]["total_assets"] - frames[name_b]["total_assets"]
                leader_first = name_a if diff.iloc[0] >= 0 else name_b
                crossover_month = None
                for idx in range(1, len(diff)):
                    if (diff.iloc[idx] >= 0) != (diff.iloc[0] >= 0):
                        crossover_month = frames[name_a]["month_label"].iloc[idx]
                        leader_after = name_b if leader_first == name_a else name_a
                        break
                if crossover_month:
                    st.info(
                        f"**{crossover_month}ごろ、{scope_label}の資産合計の大小が"
                        f"「{leader_first}」→「{leader_after}」で逆転します。**"
                    )
                else:
                    st.caption(
                        f"この{horizon_years}年間では、{scope_label}の資産合計は"
                        f"常に「{leader_first}」が上回ったままです。"
                    )

            rows = []
            for p in shown:
                f = frames[p["name"]]
                last = f.iloc[-1]
                rows.append({
                    "プラン": p["name"],
                    "現金残高": int(last["cash_balance"]),
                    "投資残高": int(last["investment_balance"]),
                    "不動産評価額": int(last["real_estate_value"]),
                    "資産合計": int(last["total_assets"]),
                    "収支累計": int(f["net_cash_flow"].sum()),
                    "想定年利": f"{plan_settings[p['id']]['expected_annual_return_pct']:g}%",
                })
            comp = pd.DataFrame(rows)
            money_cols_cmp = ["現金残高", "投資残高", "不動産評価額", "資産合計", "収支累計"]
            st.dataframe(
                comp, width="stretch", hide_index=True,
                column_config={c: st.column_config.NumberColumn(c, format="localized")
                               for c in money_cols_cmp},
            )
            best = comp.loc[comp["資産合計"].idxmax()]
            st.caption(
                f"{scope_label}で{horizon_years}年後の資産合計が最も大きいのは"
                f"「{best['プラン']}」で {yen(best['資産合計'])}（金額の単位は円）。"
            )
            st.write("")


# ══════════ 月別一覧 ══════════
else:
    # 表は3人分を横に並べると列が3倍になってスマホで読めないので、
    # ここだけは「誰の表を見るか」の切り替えを残す。
    table_scope_key = st.segmented_control(
        "対象", options=list(scope_labels.keys()), default="total",
        format_func=lambda k: scope_labels[k], label_visibility="collapsed",
    ) or "total"
    table_scope = "total" if table_scope_key == "total" else int(table_scope_key)
    df = simulation.view_frame(full_df, table_scope)
    scope_people = people if table_scope == "total" else [
        p for p in people if p["id"] == table_scope]

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
        "total_assets": "資産合計",
    }
    for p in scope_people:
        rename_map[f"income_p{p['id']}"] = f"{p['name']}の収入"
        rename_map[f"credit_card_p{p['id']}"] = f"{p['name']}のクレカ"

    display = display.rename(columns=rename_map)

    # まず全体の流れが追える列だけを出す。内訳は必要なときだけ開く。
    SUMMARY_COLS = ["収入合計", "支出合計", "月次収支", "現金残高", "投資残高",
                    "不動産評価額", "資産合計"]
    detail_money_cols = (
        [f"{p['name']}の収入" for p in scope_people]
        + ["臨時収入", "収入合計", "家賃"]
        + [f"{p['name']}のクレカ" for p in scope_people]
        + ["投資拠出", "投資へ自動振替", "投資から取り崩し", "その他既知支出", "臨時支出", "住宅ローン返済",
           "その他（現金）", "支出合計", "月次収支", "現金残高", "投資残高", "不動産評価額", "資産合計"]
    )
    all_columns = ["月", "状態"] + detail_money_cols + ["その他（現金）の根拠", "臨時収支の内容"]

    show_detail = st.checkbox(
        "内訳の列も表示する", value=False,
        help="家賃・クレカ・臨時収支など、支出の中身まで見たいときに開いてください。",
    )
    if show_detail:
        columns_order, money_cols = all_columns, detail_money_cols
    else:
        columns_order, money_cols = ["月", "状態"] + SUMMARY_COLS, SUMMARY_COLS

    st.caption("金額の単位は円です。CSVには内訳を含む全項目が入ります。")
    st.dataframe(
        display[columns_order],
        width="stretch", hide_index=True, height=560,
        column_config={c: st.column_config.NumberColumn(c, format="localized")
                       for c in money_cols},
    )

    csv_bytes = display[all_columns].to_csv(index=False).encode("utf-8-sig")
    st.download_button("CSVダウンロード", data=csv_bytes,
                       file_name="kakei_simulation.csv", mime="text/csv")
