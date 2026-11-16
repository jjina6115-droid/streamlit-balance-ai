"""화면 꾸미기 — 원래 밸런스 AI 디자인(모눈종이 바탕, 남색 글자)을 Streamlit에 입혀요."""
import html

import streamlit as st

from .shared import clean_flow, score_class, verdict


def esc(text):
    return html.escape(str(text if text is not None else ""))


BRAND_SVG = ('<svg viewBox="0 0 34 34" aria-hidden="true" width="30" height="30"><rect width="34" height="34" rx="10" fill="#1B2B4B"/>'
             '<rect x="7" y="20" width="20" height="3.2" rx="1.6" fill="#FFFFFF"/><circle cx="12" cy="14.5" r="4" fill="#14836A"/>'
             '<circle cx="22" cy="14.5" r="4" fill="#FFD45A"/></svg>')

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Gaegu:wght@400;700&family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
:root{ --paper:#F5F7FB; --grid:#E3E9F2; --sheet:#FFFFFF; --ink:#1B2B4B; --ink-2:#3B4B68; --muted:#66748C; --line:#D2DBE7;
  --red:#E03A3A; --red-soft:#FDEDED; --green:#14836A; --green-soft:#E5F3EE; --amber:#C88A06; --amber-soft:#FFF5DC; }
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea { font-family:'IBM Plex Sans KR', system-ui, sans-serif; }
.stApp{ background-color:var(--paper);
  background-image:linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size:26px 26px; }
[data-testid="stMainBlockContainer"]{ max-width:1100px; padding-top:4.5rem; }
h1, h2, h3{ color:var(--ink); letter-spacing:-.02em; }
.stMarkdown p, .stMarkdown li{ word-break:keep-all; }
[data-testid="stHeader"]{ background:rgba(245,247,251,.95); border-bottom:1px solid var(--line); }

.ba-brand{ display:flex; align-items:center; gap:9px; font-weight:700; font-size:1.1rem; color:var(--ink); }
.ba-hand{ font-family:'Gaegu', cursive; color:var(--red); font-size:1.3rem; line-height:1; }
.ba-lead{ color:var(--ink-2); font-size:1.05rem; }
.ba-muted{ color:var(--muted); }
.ba-badge{ display:inline-flex; align-items:center; gap:.35em; font-size:.85rem; font-weight:700; padding:.15em .75em; border-radius:999px; background:#EEF2F8; white-space:nowrap; }
.ba-badge .v{ font-weight:500; }
.ba-badge.s-great{ background:var(--green-soft); color:#0D5E4C; } .ba-badge.s-good{ background:#E8F1FB; color:#1D4E89; }
.ba-badge.s-mid{ background:var(--amber-soft); color:#8A5C00; } .ba-badge.s-low{ background:var(--red-soft); color:#A21F1F; }
.ba-tag{ display:inline-flex; align-items:center; font-size:.8rem; font-weight:700; color:#8A5C00; background:var(--amber-soft); border:1px solid #EBCB7A; border-radius:999px; padding:.05em .65em; white-space:nowrap; }
.ba-live{ display:inline-flex; align-items:center; gap:6px; vertical-align:middle; margin-left:8px; font-size:.82rem; font-weight:600; color:var(--green); background:var(--green-soft); border-radius:999px; padding:.2em .75em; }
.ba-live i{ width:8px; height:8px; border-radius:50%; background:var(--green); animation:balive 1.6s ease-in-out infinite; }
@keyframes balive{ 0%,100%{opacity:1} 50%{opacity:.25} }

/* 첫 화면 입구 */
.st-key-door_studio, .st-key-door_plaza{ border-radius:16px; padding:26px 28px; min-height:320px; }
.st-key-door_studio{ background:var(--sheet); border:1.5px solid var(--ink); }
.st-key-door_plaza{ background:var(--ink); }
.st-key-door_plaza a, .st-key-door_plaza a p, .st-key-door_plaza a span{ color:#fff !important; }
.st-key-door_studio [data-testid="stPageLink"] a, .st-key-door_plaza [data-testid="stPageLink"] a{ font-weight:700; font-size:1.05rem; }
.ba-door{ display:flex; flex-direction:column; gap:12px; }
.ba-door h2{ margin:0; font-size:1.9rem; }
.ba-door ol{ margin:0; padding-left:1.3em; }
.ba-door.plaza h2{ color:#fff; } .ba-door.plaza p{ color:#D4DCEB; }
.ba-door .who{ font-family:'Gaegu', cursive; font-size:1.3rem; line-height:1; }
.ba-door.studio .who{ color:var(--red); } .ba-door.plaza .who{ color:#FFD45A; }

/* 훈련소 단계 제목 */
.ba-step{ font-family:'Gaegu', cursive; color:var(--red); font-size:1.35rem; line-height:1; margin-bottom:-.3rem; }

/* 선택된 버튼 색: 단계·질문 번호는 남색, 기록 0은 빨강·1은 초록 */
[class*="st-key-step_"] button[aria-checked="true"], [class*="st-key-cur_"] button[aria-checked="true"]{ background:var(--ink) !important; color:#fff !important; border-color:var(--ink) !important; }
[class*="st-key-lab_"] button:first-of-type[aria-checked="true"]{ background:var(--red-soft) !important; color:#A21F1F !important; border-color:#F3B4B4 !important; font-weight:700; }
[class*="st-key-lab_"] button:last-of-type[aria-checked="true"]{ background:var(--green-soft) !important; color:#0D5E4C !important; border-color:#9ED5C3 !important; font-weight:700; }
.ba-hand{ font-size:1.15rem !important; }

/* 광장 카드 */
.ba-card-head{ display:flex; gap:12px; align-items:center; }
.ba-av{ width:54px; height:54px; border-radius:16px; background:var(--paper); border:1.5px solid var(--line); display:grid; place-items:center; font-size:1.8rem; flex:none; }
.ba-card-name{ font-size:1.15rem; font-weight:700; color:var(--ink); line-height:1.35; }
.ba-card-by{ font-size:.86rem; color:var(--muted); }
.ba-card-desc{ font-size:.93rem; color:var(--ink-2); min-height:2.8em; margin:.5rem 0; }
.ba-stats{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; font-size:.86rem; color:var(--muted); }

/* 댓글 */
.ba-cmt{ border:1px solid var(--line); border-left:4px solid #C3CEDF; border-radius:10px; padding:12px 14px; background:var(--sheet); margin-bottom:4px; }
.ba-cmt.improve{ border-color:#EBCB7A; border-left-color:var(--amber); background:#FFFBEF; }
.ba-cmt-head{ display:flex; align-items:center; gap:8px; }
.ba-cmt-av{ width:2em; height:2em; border-radius:50%; background:#EEF2F8; color:var(--ink-2); display:inline-grid; place-items:center; font-weight:700; font-size:.85rem; flex:none; }
.ba-cmt.improve .ba-cmt-av{ background:var(--amber-soft); color:#8A5C00; }
.ba-cmt-time{ margin-left:auto; font-size:.82rem; color:var(--muted); white-space:nowrap; }
.ba-cmt-text{ font-size:1rem; line-height:1.75; color:var(--ink); margin-top:6px; }

/* 순서도 그림 */
.fc{ display:flex; flex-direction:column; align-items:center; max-width:440px; margin:0 auto; }
.fc-term{ background:var(--ink); color:#fff; border-radius:999px; padding:.35em 1.2em; font-weight:600; font-size:.9rem; }
.fc-arrow{ width:2px; height:24px; background:var(--ink); position:relative; flex:none; }
.fc-arrow::after{ content:""; position:absolute; bottom:-2px; left:50%; transform:translateX(-50%); border-left:6px solid transparent; border-right:6px solid transparent; border-top:8px solid var(--ink); }
.fc-do{ background:var(--sheet); border:1.5px solid var(--ink); border-radius:6px; padding:.55em 1em; width:100%; text-align:center; font-size:.93rem; margin-top:4px; }
.fc-check{ position:relative; width:100%; min-height:104px; display:grid; place-items:center; padding:22px 21%; text-align:center; font-size:.92rem; margin-top:4px; }
.fc-check::before, .fc-check::after{ content:""; position:absolute; clip-path:polygon(50% 0,100% 50%,50% 100%,0 50%); }
.fc-check::before{ inset:0; background:var(--ink); } .fc-check::after{ inset:2px 3px; background:var(--amber-soft); }
.fc-check span{ position:relative; z-index:1; line-height:1.45; }
.fc-branch{ display:grid; grid-template-columns:1fr 1fr; gap:8px; width:100%; margin-top:8px; }
.fc-yes, .fc-no{ border-radius:8px; padding:.45em .7em; font-size:.85rem; background:var(--sheet); border:1.5px solid; line-height:1.45; }
.fc-yes{ border-color:#9ED5C3; } .fc-yes b{ color:var(--green); margin-right:6px; }
.fc-no{ border-color:#F3B4B4; } .fc-no b{ color:var(--red); margin-right:6px; }
.fc-empty{ text-align:center; color:var(--muted); }

/* 입장 화면 */
.ba-gate-title{ font-size:1.6rem; font-weight:700; color:var(--ink); margin:.4rem 0 .2rem; letter-spacing:-.02em; }
@media (max-width: 640px){ .fc-branch{ grid-template-columns:1fr; } .ba-door{ min-height:0; } }
@media (prefers-reduced-motion: reduce){ .ba-live i{ animation:none; } }
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def brand():
    st.markdown(f'<div class="ba-brand">{BRAND_SVG}밸런스 AI</div>', unsafe_allow_html=True)


def badge_html(score):
    if score is None:
        return '<span class="ba-badge s-none">평가 전</span>'
    return f'<span class="ba-badge {score_class(score)}">기준 충족 {score}% <span class="v">{verdict(score)}</span></span>'


def flow_html(flow):
    steps = clean_flow(flow)
    if not steps:
        return '<p class="fc-empty">아직 순서도가 없어요. 단계를 추가하면 여기에 순서도가 그려져요.</p>'
    h = '<div class="fc"><div class="fc-term">시작: 질문 읽기</div>'
    for i, s in enumerate(steps, 1):
        h += '<div class="fc-arrow"></div>'
        if s["type"] == "check":
            h += (f'<div class="fc-check"><span><b>{i}.</b> {esc(s["text"])}</span></div>'
                  f'<div class="fc-branch"><div class="fc-yes"><b>예</b>{esc(s.get("yes") or "다음 단계로")}</div>'
                  f'<div class="fc-no"><b>아니오</b>{esc(s.get("no") or "다음 단계로")}</div></div>')
        else:
            h += f'<div class="fc-do"><b>{i}.</b> {esc(s["text"])}</div>'
    return h + '<div class="fc-arrow"></div><div class="fc-term">끝: 답하기</div></div>'


def when(ts):
    import time
    if not ts:
        return ""
    m = int((time.time() - ts) // 60)
    if m < 1:
        return "방금"
    if m < 60:
        return f"{m}분 전"
    if m < 60 * 24:
        return f"{m // 60}시간 전"
    t = time.localtime(ts)
    return f"{t.tm_mon}월 {t.tm_mday}일"


def comment_html(c):
    initial = (str(c.get("author") or "?").strip() or "?")[0]
    tag = '<span class="ba-tag">개선</span>' if c.get("improve") else ""
    text = esc(c.get("text")).replace("\n", "<br>")
    return (f'<div class="ba-cmt{" improve" if c.get("improve") else ""}"><div class="ba-cmt-head">'
            f'<span class="ba-cmt-av">{esc(initial)}</span><b>{esc(c.get("author"))}</b>{tag}'
            f'<span class="ba-cmt-time">{esc(when(c.get("created")))}</span></div>'
            f'<div class="ba-cmt-text">{text}</div></div>')
