"""デザイントークン・共通CSS・カード部品。

Instagram風の明るいトーン。ページ全体にごく淡いオーロラ状のグラデーションを敷き、
カードには微かな色味とアクセントを載せて、白一色になるのを避けている。

装飾は「面」だけに使い、文字は常に濃いインク色のまま置く。
ブランドのグラデーションはデータの色分けには使わない
（データの配色は charts.py の検証済みパレットが担当する）。

白文字を載せる面には、白に対して4.4:1以上を確保できる紫〜マゼンタの範囲だけを使う。
橙・黄（#F58529 / #FEDA77）は白文字だと2.5:1・1.4:1しかないため、
文字が乗らない装飾リングにのみ使用する。
"""
from __future__ import annotations

import html as _html

import streamlit as st

# --- カテゴリカル（グラフ用・検証済み。装飾には使わない） ---
BLUE = "#2a78d6"
AQUA = "#1baf7a"
YELLOW = "#eda100"
GREEN = "#008300"
VIOLET = "#4a3aa7"
RED = "#e34948"

# --- サーフェスとインク ---
SURFACE = "#ffffff"     # カード＝グラフの描画面
PAGE = "#f7f5fb"        # ページ背景（ほんのり紫みを帯びた白）
INK = "#0b0b0b"
INK_2 = "#4b4b4b"
MUTED = "#8a8a94"
GRID = "#eeeef3"
AXIS = "#d8d8e0"
GOOD = "#0a8a34"

# --- ブランドのグラデーション ---
# 文字を載せられる安全域（白文字で4.48:1以上）
BRAND_SAFE = "linear-gradient(135deg,#4C46C7 0%,#7B2FF7 30%,#A32BAF 62%,#DD2A7B 100%)"
# 装飾専用（文字は載せない）。Instagramのストーリーリング風
BRAND_FULL = "linear-gradient(135deg,#FEDA77 0%,#F58529 22%,#DD2A7B 52%,#8134AF 80%,#515BD4 100%)"

FONT_STACK = ('-apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic UI", '
              '"Segoe UI", system-ui, sans-serif')

# 装飾用の淡い色味（面に敷くだけで、文字色は常にインク）
TINTS = {
    "violet": ("#f6f2ff", "#7B2FF7"),
    "pink":   ("#fff1f7", "#DD2A7B"),
    "blue":   ("#eff3ff", "#4C46C7"),
    "green":  ("#edfaf2", "#0a8a34"),
    "amber":  ("#fff7ea", "#c47b00"),
}

_CSS = f"""
<style>
  html, body, [class*="css"] {{
    font-family: {FONT_STACK};
    -webkit-font-smoothing: antialiased;
  }}

  /* ── ページ全体：ごく淡いオーロラ ── */
  [data-testid="stAppViewContainer"] {{
    background-color: {PAGE};
    background-image:
      radial-gradient(60rem 32rem at 8% -8%, rgba(123,47,247,.11), transparent 60%),
      radial-gradient(52rem 30rem at 96% 4%, rgba(221,42,123,.10), transparent 62%),
      radial-gradient(46rem 34rem at 52% 108%, rgba(76,70,199,.09), transparent 64%);
    background-attachment: fixed;
  }}
  .block-container {{ max-width: 980px; padding-top: 2.2rem; padding-bottom: 5rem; }}

  /* ── 見出し ── */
  h1 {{ font-size: 1.72rem !important; font-weight: 800 !important;
       letter-spacing: -.025em; color: {INK}; margin-bottom: .1rem !important; }}
  h2 {{ font-size: 1.12rem !important; font-weight: 700 !important;
       letter-spacing: -.015em; color: {INK}; margin: .2rem 0 .6rem !important; }}
  h3 {{ font-size: .98rem !important; font-weight: 650 !important; color: {INK_2}; }}
  [data-testid="stCaptionContainer"] p {{ color: {MUTED}; font-size: .82rem; }}

  /* ── カード（フォーム・展開パネル） ── */
  [data-testid="stForm"] {{
    background-image: linear-gradient(168deg, #ffffff 0%, #fdfbff 55%, #fbf7fe 100%);
    border: 1px solid rgba(123,47,247,.10);
    border-radius: 20px;
    padding: 1.4rem 1.5rem 1.2rem;
    box-shadow: 0 1px 2px rgba(20,10,40,.05), 0 16px 34px -22px rgba(76,70,199,.45);
    position: relative; overflow: hidden;
  }}
  /* カード上端のアクセント帯 */
  [data-testid="stForm"]::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
    background-image: {BRAND_SAFE}; opacity: .85;
  }}
  [data-testid="stExpander"] details {{
    background-image: linear-gradient(168deg, #ffffff, #fdfbff);
    border: 1px solid rgba(123,47,247,.10);
    border-radius: 18px;
    box-shadow: 0 1px 2px rgba(20,10,40,.05);
  }}
  [data-testid="stExpander"] summary {{ font-weight: 650; border-radius: 18px; }}

  /* ── 数値カード（左に色帯） ── */
  [data-testid="stMetric"] {{
    background-image: linear-gradient(168deg, #ffffff, #fdfbff);
    border: 1px solid rgba(123,47,247,.10);
    border-radius: 18px;
    padding: 1rem 1.15rem 1.05rem 1.35rem;
    box-shadow: 0 1px 2px rgba(20,10,40,.05), 0 14px 30px -24px rgba(76,70,199,.55);
    transition: transform .16s ease, box-shadow .16s ease;
    position: relative; overflow: hidden;
  }}
  [data-testid="stMetric"]::before {{
    content: ""; position: absolute; inset: 0 auto 0 0; width: 4px;
    background-image: {BRAND_SAFE};
  }}
  [data-testid="stMetric"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 2px 5px rgba(20,10,40,.06), 0 22px 40px -26px rgba(76,70,199,.7);
  }}
  [data-testid="stMetricLabel"] p {{
    font-size: .76rem !important; color: {MUTED} !important;
    font-weight: 600 !important; letter-spacing: .01em;
  }}
  [data-testid="stMetricValue"] {{
    font-size: 1.62rem !important; font-weight: 750 !important;
    color: {INK} !important; letter-spacing: -.025em;
  }}

  /* ── ボタンは丸ピル。主ボタンはブランドグラデーション ── */
  .stButton button, [data-testid="stFormSubmitButton"] button {{
    border-radius: 999px !important;
    font-weight: 650 !important;
    padding: .48rem 1.35rem !important;
    border: 1px solid rgba(123,47,247,.18) !important;
    background-color: #fff;
    transition: transform .14s ease, box-shadow .14s ease, filter .14s ease;
  }}
  .stButton button:hover, [data-testid="stFormSubmitButton"] button:hover {{
    transform: translateY(-1px);
    border-color: rgba(123,47,247,.34) !important;
    box-shadow: 0 8px 18px -10px rgba(76,70,199,.6);
  }}
  [data-testid="stBaseButton-primary"],
  [data-testid="stBaseButton-primaryFormSubmit"] {{
    background-image: {BRAND_SAFE} !important;
    background-color: transparent !important;
    border: none !important;
    color: #fff !important;
    box-shadow: 0 10px 22px -8px rgba(129,52,175,.65) !important;
  }}
  [data-testid="stBaseButton-primary"]:hover,
  [data-testid="stBaseButton-primaryFormSubmit"]:hover {{
    filter: brightness(1.07);
    box-shadow: 0 12px 26px -8px rgba(129,52,175,.78) !important;
  }}

  /* ── 入力欄 ── */
  [data-baseweb="input"], [data-baseweb="base-input"],
  [data-baseweb="select"] > div, [data-baseweb="textarea"] {{
    border-radius: 12px !important;
  }}
  [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {{
    border-radius: 12px !important;
  }}

  /* ── セグメント切替 ── */
  [data-testid="stSegmentedControl"] button {{
    border-radius: 999px !important; font-weight: 650 !important;
    transition: transform .14s ease;
  }}
  [data-testid="stSegmentedControl"] button:hover {{ transform: translateY(-1px); }}

  /* ── タブ ── */
  [data-testid="stTabs"] [data-baseweb="tab-list"] {{
    gap: .1rem; border-bottom: 1px solid rgba(123,47,247,.14);
  }}
  [data-testid="stTabs"] [data-baseweb="tab"] {{ font-weight: 650; padding: .6rem 1rem; }}
  [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    background-image: {BRAND_SAFE} !important; height: 2.5px; border-radius: 3px;
  }}

  /* ── サイドバー ── */
  [data-testid="stSidebar"] {{
    background-image: linear-gradient(180deg, #ffffff 0%, #fbf8ff 100%);
    border-right: 1px solid rgba(123,47,247,.12);
  }}
  [data-testid="stSidebarNav"] a {{ border-radius: 12px; font-weight: 600; }}

  /* ── 表 ── */
  [data-testid="stDataFrame"] {{
    border-radius: 16px; overflow: hidden;
    border: 1px solid rgba(123,47,247,.14); font-variant-numeric: tabular-nums;
    box-shadow: 0 12px 28px -24px rgba(76,70,199,.6);
  }}

  /* ── グラフもカードに載せる ── */
  [data-testid="stPlotlyChart"] {{
    background-image: linear-gradient(168deg, #ffffff 0%, #fdfbff 100%);
    border: 1px solid rgba(123,47,247,.10);
    border-radius: 20px;
    padding: .5rem .4rem .2rem;
    box-shadow: 0 1px 2px rgba(20,10,40,.05), 0 18px 36px -26px rgba(76,70,199,.6);
    margin-bottom: 1rem;
    position: relative; overflow: hidden;
  }}
  [data-testid="stPlotlyChart"]::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
    background-image: {BRAND_SAFE}; opacity: .7;
  }}

  [data-testid="stAlert"] {{ border-radius: 16px; }}
  hr {{ border: none; height: 1px; margin: 1.8rem 0 1.4rem;
       background-image: linear-gradient(90deg, rgba(123,47,247,.28), rgba(221,42,123,.16), transparent); }}

  /* ══ 自作カード ══ */
  .ig-hero {{
    background-image: {BRAND_SAFE};
    border-radius: 24px; padding: 1.5rem 1.7rem 1.6rem; color: #fff;
    box-shadow: 0 18px 42px -18px rgba(129,52,175,.85);
    margin-bottom: 1.1rem;
    position: relative; overflow: hidden;
  }}
  /* 光のにじみで奥行きを出す（装飾のみ） */
  .ig-hero::after {{
    content: ""; position: absolute; width: 22rem; height: 22rem;
    top: -11rem; right: -6rem; border-radius: 50%;
    background: radial-gradient(circle, rgba(255,255,255,.30), transparent 68%);
    pointer-events: none;
  }}
  .ig-hero > * {{ position: relative; z-index: 1; }}
  .ig-hero-label {{ font-size: .8rem; font-weight: 600; opacity: .94; letter-spacing: .02em; }}
  .ig-hero-value {{ font-size: 2.5rem; font-weight: 800; letter-spacing: -.035em;
                    line-height: 1.15; margin-top: .15rem;
                    text-shadow: 0 2px 12px rgba(0,0,0,.16); }}
  .ig-hero-sub {{ font-size: .84rem; opacity: .94; margin-top: .5rem; }}
  .ig-hero-chips {{ display: flex; gap: .45rem; flex-wrap: wrap; margin-top: .9rem; }}
  .ig-chip {{
    background: rgba(255,255,255,.20); border: 1px solid rgba(255,255,255,.32);
    border-radius: 999px; padding: .3rem .8rem; font-size: .8rem; font-weight: 600;
    backdrop-filter: blur(4px);
  }}

  .ig-row {{ display: flex; gap: .85rem; flex-wrap: wrap; margin-bottom: 1rem; }}
  .ig-card {{
    flex: 1 1 220px;
    background-image: linear-gradient(168deg, #ffffff 0%, #fdfbff 60%, #fbf7fe 100%);
    border: 1px solid rgba(123,47,247,.12); border-radius: 20px;
    padding: 1.15rem 1.2rem;
    box-shadow: 0 1px 2px rgba(20,10,40,.05), 0 16px 34px -26px rgba(76,70,199,.65);
    transition: transform .18s ease, box-shadow .18s ease;
    position: relative; overflow: hidden;
  }}
  .ig-card::before {{
    content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
    background-image: {BRAND_SAFE}; opacity: .8;
  }}
  .ig-card:hover {{
    transform: translateY(-3px);
    box-shadow: 0 3px 7px rgba(20,10,40,.06), 0 26px 46px -28px rgba(76,70,199,.85);
  }}
  /* 色味つきカード */
  .ig-card.tint-violet {{ background-image: linear-gradient(168deg,#ffffff,{TINTS['violet'][0]}); }}
  .ig-card.tint-pink   {{ background-image: linear-gradient(168deg,#ffffff,{TINTS['pink'][0]}); }}
  .ig-card.tint-blue   {{ background-image: linear-gradient(168deg,#ffffff,{TINTS['blue'][0]}); }}
  .ig-card.tint-green  {{ background-image: linear-gradient(168deg,#ffffff,{TINTS['green'][0]}); }}
  .ig-card.tint-amber  {{ background-image: linear-gradient(168deg,#ffffff,{TINTS['amber'][0]}); }}

  .ig-person-head {{ display: flex; align-items: center; gap: .65rem; margin-bottom: .9rem; }}
  .ig-ring {{
    padding: 2.5px; border-radius: 50%;
    background-image: {BRAND_FULL}; display: inline-flex; flex: none;
    box-shadow: 0 6px 16px -8px rgba(221,42,123,.7);
  }}
  .ig-ring-inner {{
    width: 42px; height: 42px; border-radius: 50%; background: {SURFACE};
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 1.02rem; color: {INK};
  }}
  .ig-person-name {{ font-weight: 700; font-size: 1rem; color: {INK}; letter-spacing: -.01em; }}
  .ig-person-note {{ font-size: .75rem; color: {MUTED}; margin-top: .05rem; }}

  .ig-stat {{ display: flex; justify-content: space-between; align-items: baseline;
              padding: .42rem 0; border-top: 1px solid rgba(123,47,247,.10); }}
  .ig-stat:first-of-type {{ border-top: none; }}
  .ig-stat-label {{ font-size: .82rem; color: {MUTED}; font-weight: 550; }}
  .ig-stat-value {{ font-size: 1.02rem; font-weight: 700; color: {INK};
                    letter-spacing: -.02em; font-variant-numeric: tabular-nums; }}
  .ig-stat-value.pos {{ color: {GOOD}; }}
  .ig-stat-value.neg {{ color: {RED}; }}

  /* 見出しの前に置くグラデーションの点 */
  /* スマホ幅では補足を次の行へ折り返す。見出し自体が途中で改行されないようにする。 */
  .ig-section {{ display: flex; align-items: center; gap: .55rem; margin: 1.7rem 0 .7rem;
                 flex-wrap: wrap; }}
  .ig-section-dot {{
    width: 9px; height: 9px; border-radius: 3px; flex: none;
    background-image: {BRAND_SAFE};
    box-shadow: 0 3px 8px -2px rgba(129,52,175,.6);
  }}
  .ig-section-title {{ font-size: 1.08rem; font-weight: 750; letter-spacing: -.015em; color: {INK};
                       white-space: nowrap; }}
  .ig-section-sub {{ font-size: .8rem; color: {MUTED}; }}

  /* 状態バッジ */
  .ig-badge {{
    display: inline-block; border-radius: 999px; padding: .18rem .6rem;
    font-size: .72rem; font-weight: 700; letter-spacing: .01em;
  }}
</style>
"""


def configure():
    """アプリ全体のページ設定＋CSS適用。エントリポイント（app.py）で1回だけ呼ぶ。"""
    st.set_page_config(page_title="夫婦家計管理", page_icon="💰", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)


def page_header(title: str, description: str | None = None):
    st.title(title)
    if description:
        st.caption(description)
    st.write("")


def yen(value) -> str:
    """金額は常に整数の円で表示する（小数は出さない）。"""
    return f"¥{round(float(value)):,d}"


def _esc(s) -> str:
    return _html.escape(str(s))


# ══════════ カード部品 ══════════

def hero(label: str, value, sub: str | None = None, chips: list[str] | None = None):
    """画面の主役になるグラデーションカード。"""
    chip_html = ""
    if chips:
        chip_html = ('<div class="ig-hero-chips">'
                     + "".join(f'<span class="ig-chip">{_esc(c)}</span>' for c in chips)
                     + "</div>")
    sub_html = f'<div class="ig-hero-sub">{_esc(sub)}</div>' if sub else ""
    st.markdown(
        f'<div class="ig-hero">'
        f'<div class="ig-hero-label">{_esc(label)}</div>'
        f'<div class="ig-hero-value">{_esc(value)}</div>'
        f'{sub_html}{chip_html}</div>',
        unsafe_allow_html=True,
    )


def _stat_rows_html(rows: list[tuple]) -> str:
    out = []
    for label, value, *rest in rows:
        tone = rest[0] if rest else ""
        cls = f"ig-stat-value {tone}".strip()
        out.append(f'<div class="ig-stat"><span class="ig-stat-label">{_esc(label)}</span>'
                   f'<span class="{cls}">{_esc(value)}</span></div>')
    return "".join(out)


def person_cards(cards: list[dict]):
    """[{name, initial, note, rows, tint}] を横並びのカードで描く。

    rows は (ラベル, 値, 色調) のリスト。色調は "pos" / "neg" / 省略。
    """
    blocks = []
    for c in cards:
        note = f'<div class="ig-person-note">{_esc(c["note"])}</div>' if c.get("note") else ""
        tint = f' tint-{c["tint"]}' if c.get("tint") else ""
        blocks.append(
            f'<div class="ig-card{tint}">'
            f'<div class="ig-person-head">'
            f'<span class="ig-ring"><span class="ig-ring-inner">{_esc(c["initial"])}</span></span>'
            f'<span><div class="ig-person-name">{_esc(c["name"])}</div>{note}</span>'
            f'</div>{_stat_rows_html(c["rows"])}</div>'
        )
    st.markdown(f'<div class="ig-row">{"".join(blocks)}</div>', unsafe_allow_html=True)


def stat_cards(cards: list[dict]):
    """[{label, value, sub, tone, tint, icon}] を横並びのカードで描く。"""
    blocks = []
    for c in cards:
        tone = c.get("tone", "")
        tint = f' tint-{c["tint"]}' if c.get("tint") else ""
        icon = f'{_esc(c["icon"])}　' if c.get("icon") else ""
        sub = f'<div class="ig-person-note">{_esc(c["sub"])}</div>' if c.get("sub") else ""
        blocks.append(
            f'<div class="ig-card{tint}">'
            f'<div class="ig-stat-label">{icon}{_esc(c["label"])}</div>'
            f'<div class="ig-stat-value {tone}" style="font-size:1.5rem;display:block;'
            f'margin-top:.25rem">{_esc(c["value"])}</div>{sub}</div>'
        )
    st.markdown(f'<div class="ig-row">{"".join(blocks)}</div>', unsafe_allow_html=True)


def section(title: str, sub: str | None = None):
    sub_html = f'<span class="ig-section-sub">{_esc(sub)}</span>' if sub else ""
    st.markdown(
        f'<div class="ig-section"><span class="ig-section-dot"></span>'
        f'<span class="ig-section-title">{_esc(title)}</span>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, tint: str = "violet") -> str:
    """状態を表す色つきの丸バッジ（HTML文字列を返す）。"""
    bg, fg = TINTS.get(tint, TINTS["violet"])
    return (f'<span class="ig-badge" style="background:{bg};color:{fg}">'
            f'{_esc(text)}</span>')
