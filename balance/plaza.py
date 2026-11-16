"""AI 광장 — 모둠들이 올린 AI 고르기 · 💬 댓글(개선 표시) · 대화하기 · 👍👎

목록과 댓글은 6초마다 저절로 새로 고쳐져요. (새로고침 버튼을 누르지 않아도 돼요)
"""
import streamlit as st

from . import ai, auth, data, nav, ui
from .shared import LIMITS, compile_rules

LIVE = 6  # 초
STARTERS = ["안녕! 너는 어떤 AI야?", "너는 어떤 순서로 생각해서 답해?"]
SORTS = {"popular": "인기순", "score": "균형 점수순", "new": "최신순"}


def can_delete(bot, s):
    return auth.is_teacher(s) or (st.session_state.get("gid") and st.session_state.get("gid") == bot.get("gid"))


def sort_bots(bots, how):
    if how == "score":
        return sorted(bots, key=lambda b: b.get("score") or 0, reverse=True)
    if how == "new":
        return sorted(bots, key=lambda b: b.get("created") or 0, reverse=True)
    return sorted(bots, key=lambda b: (b.get("likes") or 0) * 3 + (b.get("chats") or 0) - (b.get("dislikes") or 0) * 2, reverse=True)


def open_bot(bot_id):
    st.session_state.pop("open_cmt", None)
    st.query_params["bot"] = bot_id


def back_to_list():
    if "bot" in st.query_params:
        del st.query_params["bot"]


# ---------------- 목록 ----------------
def card(b, s):
    bid = b["id"]
    with st.container(border=True, key=f"card_{bid}"):
        st.markdown(
            f'<div class="ba-card-head"><div class="ba-av">{ui.esc(b.get("emoji") or "🤖")}</div><div>'
            f'<div class="ba-card-name">{ui.esc(b["name"])}</div>'
            f'<div class="ba-card-by">만든 모둠 {ui.esc(b.get("author"))}{" (우리 모둠)" if st.session_state.get("gid") == b.get("gid") else ""}</div></div></div>'
            f'<div class="ba-card-desc">{ui.esc(b.get("description") or "소개가 아직 없어요.")}</div>'
            f'<div class="ba-stats">{ui.badge_html(b.get("score"))}<span>👍 {b.get("likes", 0)}</span><span>대화 {b.get("chats", 0)}</span></div>',
            unsafe_allow_html=True)
        row = st.container(horizontal=True, vertical_alignment="center")
        if row.button(f"💬 댓글 {b.get('comments', 0)}", key=f"cmt_{bid}", help="이 AI에 댓글 달기"):
            st.session_state.open_cmt = bid
            st.rerun()
        if b.get("improves"):
            row.markdown(f'<span class="ba-tag">개선 {b["improves"]}</span>', unsafe_allow_html=True)
        row.space("stretch")
        if row.button("대화하기", key=f"go_{bid}", type="primary"):
            open_bot(bid)
            st.rerun()  # 실시간 새로고침 칸 안의 버튼이라 화면 전체를 다시 그려요
        if can_delete(b, s):
            with row.popover("내리기"):
                st.write(f"‘{b['name']}’을(를) 광장에서 내릴까요? 내린 AI는 다시 되돌릴 수 없어요.")
                if st.button("내리기", key=f"del_{bid}", type="primary"):
                    data.delete_bot(bid)
                    st.rerun()


@st.fragment(run_every=LIVE)
def live_grid(s):
    bots = data.list_bots()
    if not bots:
        with st.container(border=True):
            st.markdown("<div style='text-align:center;font-size:3rem'>🤖</div>", unsafe_allow_html=True)
            st.markdown("<p style='text-align:center'>아직 광장에 올라온 AI가 없어요.<br>AI 훈련소에서 첫 번째 AI를 가르쳐 보세요.</p>", unsafe_allow_html=True)
            st.page_link(nav.page("studio"), label="AI 훈련소로 가기 →")
        return
    q = (st.session_state.get("plaza_q") or "").strip().lower()
    shown = [b for b in sort_bots(bots, st.session_state.get("plaza_sort") or "popular")
             if not q or q in " ".join([b.get("name", ""), b.get("author", ""), b.get("description", "")]).lower()]
    if not shown:
        st.caption(f"‘{st.session_state.get('plaza_q')}’와(과) 맞는 AI가 없어요.")
    for start in range(0, len(shown), 3):
        cols = st.columns(3)
        for col, b in zip(cols, shown[start:start + 3]):
            with col:
                card(b, s)


def list_page(s):
    st.markdown('<h1 style="margin-bottom:0">AI 광장 <span class="ba-live" title="새 AI와 댓글이 저절로 보여요"><i></i>실시간</span></h1>',
                unsafe_allow_html=True)
    c = auth.current_class(s)
    st.markdown(ui.class_chip(c["name"]) + '<p class="ba-lead">우리 반 친구들이 공정하게 훈련시킨 AI예요. 하나를 골라 대화하고, 💬 댓글로 느낀 점이나 고칠 점을 남겨 보세요.</p>',
                unsafe_allow_html=True)
    a, b = st.columns([1.3, 1], vertical_alignment="center")
    a.text_input("AI 찾기", key="plaza_q", placeholder="AI 이름이나 모둠 찾기", label_visibility="collapsed", persist_state="session")
    b.segmented_control("정렬", list(SORTS), key="plaza_sort", format_func=SORTS.get, required=True, default="popular",
                        label_visibility="collapsed", persist_state="session")
    live_grid(s)
    if auth.is_teacher(s):
        st.caption("선생님 메뉴가 켜져 있어요. 모든 AI에 '내리기', 모든 댓글에 '지우기'가 보여요.")


# ---------------- 댓글 창 ----------------
def close_comments():
    st.session_state.pop("open_cmt", None)


@st.fragment(run_every=LIVE)
def comment_list(bot_id, s):
    comments = data.list_comments(bot_id)
    n, m = len(comments), sum(1 for c in comments if c.get("improve"))
    fk = f"cf_{bot_id}"
    st.segmented_control("댓글 보기", ["all", "improve"], key=fk, required=True, default="all", label_visibility="collapsed",
                         format_func=lambda v: f"전체 {n}" if v == "all" else f"개선 {m}")
    shown = [c for c in comments if st.session_state.get(fk, "all") == "all" or c.get("improve")]
    if not shown:
        st.caption("아직 개선 댓글이 없어요." if st.session_state.get(fk) == "improve" else "아직 댓글이 없어요. 첫 댓글을 남겨 보세요.")
        return
    mine = st.session_state.setdefault("my_comments", set())
    teacher = auth.is_teacher(s)
    for c in shown:
        st.markdown(ui.comment_html(c), unsafe_allow_html=True)
        if c["id"] in mine or teacher:
            ask_key = f"cdel_{c['id']}"
            row = st.container(horizontal=True, horizontal_alignment="right", vertical_alignment="center")
            if st.session_state.get(ask_key):
                row.caption("이 댓글을 지울까요?")
                if row.button("취소", key=f"no_{c['id']}"):
                    st.session_state.pop(ask_key, None)
                    st.rerun(scope="fragment")
                if row.button("지우기", key=f"yes_{c['id']}", type="primary"):
                    data.delete_comment(bot_id, c["id"])
                    mine.discard(c["id"])
                    st.session_state.pop(ask_key, None)
                    st.toast("댓글을 지웠어요.")
                    st.rerun(scope="fragment")
            elif row.button("지우기", key=f"ask_{c['id']}", type="tertiary"):
                st.session_state[ask_key] = True
                st.rerun(scope="fragment")


@st.dialog("댓글", width="large", on_dismiss=close_comments)
def comment_dialog(bot_id, s):
    b = data.get_bot(bot_id)
    if not b:
        st.warning("이 AI를 찾을 수 없어요. 광장에서 내려갔을 수 있어요.")
        if st.button("닫기"):
            close_comments()
            st.rerun()
        return
    st.markdown(f'<div class="ba-card-head"><div class="ba-av">{ui.esc(b.get("emoji"))}</div><div>'
                f'<div class="ba-card-name">{ui.esc(b["name"])}</div><div class="ba-card-by">만든 모둠 {ui.esc(b.get("author"))}</div></div></div>',
                unsafe_allow_html=True)
    with st.form(f"cmt_form_{bot_id}", clear_on_submit=True):
        text = st.text_area("댓글 쓰기", max_chars=LIMITS["comment"], placeholder="이 AI와 대화해 본 느낌을 남겨 주세요.")
        improve = st.checkbox("**개선** — 고칠 점이 있어요")
        x, y = st.columns([3, 1], vertical_alignment="bottom")
        author = x.text_input("쓴 사람", value=st.session_state.get("cmt_author", ""), max_chars=LIMITS["author"], placeholder="예: 2모둠")
        sent = y.form_submit_button("댓글 달기", type="primary", use_container_width=True)
    if sent:
        try:
            c = data.add_comment(bot_id, author, text, improve)
            st.session_state.setdefault("my_comments", set()).add(c["id"])
            st.session_state.cmt_author = c["author"]
            st.toast("개선 댓글을 남겼어요." if improve else "댓글을 남겼어요.")
        except ValueError as e:
            st.error(str(e))
    comment_list(bot_id, s)
    row = st.container(horizontal=True, horizontal_alignment="right")
    if row.button("대화하러 가기", key=f"dlg_go_{bot_id}"):
        open_bot(bot_id)
        st.rerun()
    if row.button("닫기", key=f"dlg_close_{bot_id}", type="primary"):
        close_comments()
        st.rerun()


# ---------------- 대화 화면 ----------------
def rate(bot_id, key):
    rated = st.session_state.setdefault("rated", set())
    v = st.session_state.get(key)
    if v is None or key in rated:
        return
    rated.add(key)
    data.bump(bot_id, "likes" if v == 1 else "dislikes")
    st.toast("평가 고마워요. 공정했다고 남겼어요." if v == 1 else "평가 고마워요. 만든 모둠이 규칙을 고치는 데 도움이 돼요.")


@st.fragment(run_every=LIVE)
def live_stats(bot_id):
    b = data.get_bot(bot_id) or {}
    st.markdown(f'<div class="ba-stats">👍 {b.get("likes", 0)} · 👎 {b.get("dislikes", 0)} · 대화 {b.get("chats", 0)}</div>',
                unsafe_allow_html=True)


def send(b, text, history):
    text = text.strip()[:LIMITS["message"]]
    if not text:
        return
    conn = ai.connection(auth.load_settings())
    history.append({"role": "user", "content": text})
    try:
        with st.spinner("답을 쓰는 중이에요…"):
            answer = ai.complete(conn, ai.bot_messages(compile_rules(b.get("prompt"), b.get("flow")), history[:-1][-10:], text))
        history.append({"role": "assistant", "content": answer})
        data.bump(b["id"], "chats")
    except ai.AIError as e:
        history.append({"role": "assistant", "content": str(e), "error": True, "retry": text})


def bot_page(bot_id, s):
    st.button("← 뒤로 가기", on_click=back_to_list, key="back_btn")
    b = data.get_bot(bot_id)
    if not b:
        st.warning("이 AI를 찾을 수 없어요. 광장에서 내려갔을 수 있어요.")
        return
    left, right = st.columns([1, 2.4], gap="large")
    with left:
        st.markdown(f'<div class="ba-av" style="width:76px;height:76px;font-size:2.6rem;border-color:#1B2B4B">{ui.esc(b.get("emoji"))}</div>'
                    f'<h2 style="margin:.6rem 0 0">{ui.esc(b["name"])}</h2>'
                    f'<div class="ba-card-by">만든 모둠 {ui.esc(b.get("author"))}</div>'
                    f'<div style="margin:.6rem 0">{ui.badge_html(b.get("score"))}</div>'
                    + (f'<p>{ui.esc(b["description"])}</p>' if b.get("description") else ""), unsafe_allow_html=True)
        live_stats(bot_id)
        with st.popover("규칙과 순서도 보기", use_container_width=True):
            st.caption(f"{b.get('author')}이(가) AI 훈련소에서 쓴 내용이에요. 이 규칙과 순서도가 AI에게 함께 전달돼요.")
            st.markdown("**규칙**")
            st.code(b.get("prompt") or "(규칙 없음)", language=None, wrap_lines=True)
            st.markdown("**응답 순서도**")
            st.markdown(ui.flow_html(b.get("flow")), unsafe_allow_html=True)
        if st.session_state.get("gid") == b.get("gid"):
            st.page_link(nav.page("studio"), label="훈련소에서 고치기")
    with right:
        history = st.session_state.setdefault(f"chat_{bot_id}", [])
        box = st.container(border=True, height=520)
        with box:
            if not history:
                st.markdown(f"<div style='text-align:center;font-size:2.6rem;margin-top:3rem'>{ui.esc(b.get('emoji'))}</div>"
                            f"<p style='text-align:center'><b>{ui.esc(b['name'])}</b>에게 무엇이든 물어보세요.<br>"
                            "한쪽으로 치우친 질문을 던져서 잘 훈련됐는지 확인해 봐도 좋아요.</p>", unsafe_allow_html=True)
                with st.container(horizontal=True, horizontal_alignment="center"):
                    for n, q in enumerate(STARTERS):
                        if st.button(q, key=f"st_{bot_id}_{n}"):
                            st.session_state["starter_q"] = q
                            st.rerun()
            for idx, m in enumerate(history):
                with st.chat_message(m["role"], avatar=(b.get("emoji") or "🤖") if m["role"] == "assistant" else "🙂"):
                    if m.get("error"):
                        st.error(m["content"])
                        if st.button("다시 보내기", key=f"retry_{bot_id}_{idx}"):
                            q = m.get("retry", "")
                            del history[idx - 1:idx + 1]
                            st.session_state["starter_q"] = q
                            st.rerun()
                    else:
                        st.markdown(m["content"])
                        if m["role"] == "assistant":
                            fk = f"fb_{bot_id}_{idx}"
                            c = st.container(horizontal=True, vertical_alignment="center")
                            c.caption("이 답은 공정했나요?")
                            c.feedback("thumbs", key=fk, on_change=rate, args=(bot_id, fk),
                                       disabled=fk in st.session_state.get("rated", set()))
        prompt = st.chat_input("AI에게 물어보세요", key=f"ci_{bot_id}", max_chars=LIMITS["message"])
        prompt = prompt or st.session_state.pop("starter_q", None)
        if prompt:
            with box:
                with st.chat_message("user", avatar="🙂"):
                    st.markdown(prompt)
                with st.chat_message("assistant", avatar=b.get("emoji") or "🤖"):
                    send(b, prompt, history)
            st.rerun()


# ---------------- 화면 ----------------
def render():
    s = auth.load_settings()
    if not auth.current_class(s):
        ui.no_class_notice("AI 광장")
        return
    bot_id = st.query_params.get("bot")
    if bot_id:
        bot_page(bot_id, s)
    else:
        list_page(s)
    if st.session_state.get("open_cmt") and not bot_id:
        comment_dialog(st.session_state["open_cmt"], s)
