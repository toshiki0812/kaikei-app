"""合言葉によるアクセス制限と、未設定時の案内画面。

家計の中身は外に出したくないので、データを1文字でも描く前にここで止める。
Streamlit Cloud側の「閲覧できる人」の制限や、Cloud Runの認証と二重にかけて使う。
"""
from __future__ import annotations

import hmac
import os

import streamlit as st


def _secret(key: str, env_key: str) -> str | None:
    """環境変数（Cloud Run など）→ Streamlit secrets（ローカル／Streamlit Cloud）の順に探す。"""
    value = os.environ.get(env_key)
    if not value:
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
    if not value or str(value).startswith("ここに"):
        return None
    return str(value)


def require_database_configured() -> bool:
    """接続先が未設定なら設定手順を出して False を返す。"""
    import db
    try:
        db._dsn()
        return True
    except db.DatabaseNotConfigured:
        pass

    st.title("はじめに設定が必要です")
    st.warning("データベースの接続先が設定されていないため、まだ起動できません。")
    st.markdown(
        "**ローカルで動かす場合**\n\n"
        "1. `.streamlit/secrets.toml.example` を複製して `.streamlit/secrets.toml` を作る\n"
        "2. `database_url` と `app_password` を自分のものに書き換える\n"
        "3. アプリを再起動する\n\n"
        "**Streamlit Cloud で動かす場合**\n\n"
        "アプリの管理画面（⋮ → Settings → Secrets）に同じ内容を貼り付けて保存します。\n\n"
        "手順の詳細は同梱の `README.md` の「二人で使えるようにする」を参照してください。"
    )
    return False


def require_login() -> bool:
    """合言葉が合うまで中身を描かせない。合言葉が未設定なら止める。"""
    password = _secret("app_password", "APP_PASSWORD")
    if password is None:
        st.title("はじめに設定が必要です")
        st.warning("合言葉（app_password）が設定されていないため、開けません。")
        st.markdown(
            "`.streamlit/secrets.toml`（クラウドの場合は Secrets 欄）に "
            "`app_password` を設定してください。\n\n"
            "家計の中身を守るための鍵なので、**推測されにくい長めの文字列**にしてください。"
        )
        return False

    if st.session_state.get("authenticated"):
        return True

    st.markdown('<div style="max-width:460px;margin:3rem auto 0">', unsafe_allow_html=True)
    st.markdown("### 💰 夫婦家計管理")
    st.caption("合言葉を入力してください。")

    with st.form("login"):
        entered = st.text_input("合言葉", type="password", label_visibility="collapsed",
                                placeholder="合言葉")
        submitted = st.form_submit_button("開く", type="primary")

    if submitted:
        # 文字数の違いから中身を推測されないよう、定数時間で比較する
        if hmac.compare_digest(entered, password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("合言葉が違います。")

    st.markdown("</div>", unsafe_allow_html=True)
    return False


def logout_button():
    if st.sidebar.button("ログアウト"):
        st.session_state.pop("authenticated", None)
        st.rerun()
