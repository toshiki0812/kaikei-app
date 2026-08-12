from datetime import datetime

import streamlit as st

import db
import simulation
import theme
from theme import yen

plan_id = db.get_active_plan_id()
plan = db.get_plan(plan_id)

settings = db.get_settings(plan_id)
people = db.get_people()
df = simulation.build_projection(plan_id)

current_month = datetime.now().strftime("%Y-%m")
row = df[df["month"] == current_month]

st.markdown("# 夫婦家計管理")
st.caption(f"{plan['name']}　—　毎月の実績を記録しながら、今後10年間の資産の推移を見通します。")
st.write("")

if row.empty:
    st.info(
        f"今月（{simulation.month_label(current_month)}）はシミュレーション期間の範囲外です。"
        "「初期設定」ページでシミュレーション開始月をご確認ください。"
    )
    st.stop()

r = row.iloc[0]
status_label = {"actual": "実績確定", "partial": "一部実績", "projected": "想定ベース"}[r["data_status"]]

# ══════════ 主役：世帯の総資産 ══════════
total_assets = r["cash_balance"] + r["investment_balance"]
theme.hero(
    f"{simulation.month_label(current_month)}時点の世帯資産",
    yen(total_assets),
    sub=f"現金 {yen(r['cash_balance'])}　＋　投資 {yen(r['investment_balance'])}",
    chips=[status_label,
           f"今月の収支 {yen(r['net_cash_flow'])}",
           f"想定利回り {settings['expected_annual_return_pct']:g}%"],
)

# ══════════ 夫婦それぞれ ══════════
theme.section("夫婦それぞれ", "今月の収支と、いま持っている資産")
PERSON_TINTS = ["violet", "pink", "blue", "amber"]


def _person_card(p: dict, i: int) -> dict:
    pid = p["id"]
    net = r[f"net_cash_flow_p{pid}"]
    cash = r[f"cash_balance_p{pid}"]
    invest = r[f"investment_balance_p{pid}"]
    return {
        "name": p["name"],
        "initial": p["name"][0],
        "note": f"資産合計 {yen(cash + invest)}",
        "tint": PERSON_TINTS[i % len(PERSON_TINTS)],
        "rows": [
            ("月次収支", yen(net), "pos" if net >= 0 else "neg"),
            ("現金残高", yen(cash)),
            ("投資残高", yen(invest)),
        ],
    }


theme.person_cards([_person_card(p, i) for i, p in enumerate(people)])

# ══════════ 今月の収支 ══════════
theme.section("今月の収支", status_label)
theme.stat_cards([
    {"label": "収入合計", "value": yen(r["income_total"]), "icon": "💴", "tint": "blue"},
    {"label": "支出合計", "value": yen(r["total_expense"]), "icon": "🧾", "tint": "pink"},
    {"label": "月次収支", "value": yen(r["net_cash_flow"]), "icon": "⚖️",
     "tint": "green" if r["net_cash_flow"] >= 0 else "amber",
     "tone": "pos" if r["net_cash_flow"] >= 0 else "neg"},
])

with st.expander("この月の内訳を見る"):
    lines = [f"収入合計　{yen(r['income_total'])}"]
    for p in people:
        lines.append(f"　・{p['name']}の収入　{yen(r['income_p' + str(p['id'])])}")
    if r["planned_income"]:
        lines.append(f"　（うち臨時収入　{yen(r['planned_income'])}）")
    lines.append("")
    lines.append(f"支出合計　{yen(r['total_expense'])}")
    lines.append(f"　・家賃　{yen(r['rent'])}")
    for p in people:
        lines.append(f"　・{p['name']}のクレカ　{yen(r['credit_card_p' + str(p['id'])])}")
    lines.append(f"　・投資拠出　{yen(r['investment_contribution'])}")
    if r["cash_sweep"]:
        lines.append(f"　・投資へ自動振替　{yen(r['cash_sweep'])}")
    lines.append(f"　・その他既知支出　{yen(r['other_expense'])}")
    if r["planned_expense"]:
        lines.append(f"　・臨時支出　{yen(r['planned_expense'])}")
    cash_note = "実績から算出" if r["other_cash_status"] == "actual" else "想定値"
    lines.append(f"　・その他（現金・{cash_note}）　{yen(r['other_cash_expense'])}")
    st.text("\n".join(lines))

# ══════════ 10年後 ══════════
end = df.iloc[-1]
start = df.iloc[0]
theme.section("10年後の見通し", simulation.month_label(end["month"]))
theme.stat_cards([
    {"label": "現金残高", "value": yen(end["cash_balance"]), "icon": "🏦", "tint": "blue"},
    {"label": "投資残高", "value": yen(end["investment_balance"]), "icon": "📈", "tint": "green",
     "sub": f"開始時から {yen(end['investment_balance'] - start['investment_balance'])} 増",
     "tone": "pos"},
    {"label": "資産合計", "value": yen(end["cash_balance"] + end["investment_balance"]),
     "icon": "✨", "tint": "violet"},
])

n_actual = int((df["data_status"] == "actual").sum())
n_partial = int((df["data_status"] == "partial").sum())
st.caption(
    f"実績確定 {n_actual}ヶ月／一部実績 {n_partial}ヶ月／残りは想定値ベース。"
    "実績を入力するほど見通しの精度が上がります。"
)

theme.section("使い方")
st.markdown(
    "1. **初期設定** — 夫婦それぞれの想定値、開始残高、臨時収支、カードを登録します\n"
    "2. **月次実績入力** — 毎月の実際の金額を入力します（クレカはCSV取込で自動集計）\n"
    "3. **シミュレーション** — 世帯合計と個人を切り替えて10年間の推移を確認します"
)
