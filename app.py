"""エントリポイント。設定確認 → ログイン → プラン選択 → ページ表示。

家計の中身はログインを通過するまで一切描かない。
"""
import streamlit as st

import auth
import theme

theme.configure()

# 接続先と合言葉が揃うまで、データには触れない
if not auth.require_database_configured():
    st.stop()
if not auth.require_login():
    st.stop()

import db  # noqa: E402  ログイン後に初めてDBへ接続する

db.init_db()

# --- プラン選択（全ページ共通・選択はDBに保存されるので再起動しても残る） ---
plans = db.get_plans()
plan_ids = [p["id"] for p in plans]
plan_names = {p["id"]: p["name"] for p in plans}
active_id = db.get_active_plan_id()

# 保存は on_change のときだけ。「画面の値と保存値がズレたら書き戻す」書き方だと、
# ユーザーが触っていない再実行でも発火して、二人が別々の端末で開いたときに
# 片方の選択をもう片方が上書きしてしまう。
PLAN_KEY = "plan_select"


def _save_plan():
    db.set_active_plan_id(st.session_state[PLAN_KEY])


# 別の端末で切り替えられていたら、こちらの選択もそれに合わせる
if st.session_state.get("_plan_stored") != active_id:
    st.session_state[PLAN_KEY] = active_id
st.session_state["_plan_stored"] = active_id

with st.sidebar:
    st.caption("シミュレーションのプラン")
    st.selectbox(
        "プラン", options=plan_ids, key=PLAN_KEY, on_change=_save_plan,
        format_func=lambda pid: plan_names[pid], label_visibility="collapsed",
    )
    st.caption("想定値はプランごと／実績と臨時収支は全プラン共通です。")
    st.divider()

pages = [
    st.Page("views/home.py", title="ホーム", icon="🏠", default=True),
    st.Page("views/setup.py", title="初期設定", icon="⚙️"),
    st.Page("views/monthly_entry.py", title="月次実績入力", icon="📝"),
    st.Page("views/simulation_view.py", title="シミュレーション", icon="📊"),
]

st.navigation(pages).run()

auth.logout_button()
