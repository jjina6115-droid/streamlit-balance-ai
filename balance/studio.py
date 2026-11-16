"""AI 훈련소 — 모둠으로 들어와서 6단계로 진행해요.

1 규칙 쓰기 · 2 순서도 만들기 · 3 질문하기 · 4 답변 기록하기(0/1) · 5 결과 보고 고치기 · 6 광장에 올리기
쓴 내용은 서버 저장소에 모둠별로 저장돼서, 다른 날 다른 컴퓨터에서 들어와도 이어서 할 수 있어요.
AI는 고칠 점을 알려 주지 않아요. 학생이 데이터를 보고 스스로 규칙과 순서도를 고쳐요.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

from . import ai, auth, data, nav, ui
from .shared import CN, CRITERIA, EMOJIS, IDEAS, LIMITS, is_labeled

STEPS = ["rules", "flow", "ask", "label", "result", "publish"]
STEP_SHORT = {"rules": "규칙", "flow": "순서도", "ask": "질문", "label": "기록", "result": "결과", "publish": "올리기"}
STEP_TITLE = {"rules": "규칙 쓰기", "flow": "순서도 만들기", "ask": "질문하기", "label": "답변 기록하기",
              "result": "결과 보고 고치기", "publish": "광장에 올리기"}
STEP_HINT = {
    "rules": "AI의 이름을 짓고, 치우친 질문을 받았을 때 어떻게 답해야 하는지 규칙을 써요.",
    "flow": "AI가 답하기 전에 어떤 순서로 생각할지 정해요. **처리**는 할 일, **판단**은 예/아니오로 갈리는 질문이에요.",
    "ask": "우리 모둠이 직접 만든 **편향된 질문 10개**를 쓰고 AI에게 물어봐요.",
    "label": "AI 답변을 읽고 한 줄로 요약한 다음, 기준마다 **지켰으면 1**, **안 지켰으면 0**을 눌러요.",
    "result": "기록한 데이터를 보고, 아래 규칙 칸에서 규칙을 바로 고쳐요.",
    "publish": "아래 항목을 모두 채우면 우리 모둠 AI를 광장에 올릴 수 있어요.",
}
NEED = LIMITS["min_tests"]


# ---------------- 작은 도구 ----------------
def gid():
    return st.session_state.get("gid")


def cur():
    """저장소에서 우리 모둠 작업을 새로 읽어요 (여러 모둠원이 함께 써도 최신으로)."""
    ws = data.load_group(gid())
    if ws is not None:
        changed = False
        for s in ws.get("flow", []):
            if not s.get("id"):
                s.update(data.new_step(s.get("type", "do")) | {k: v for k, v in s.items() if k != "id"})
                changed = True
        if changed:
            data.save_group(ws)
    return ws


def bind(key, value):
    """입력 칸의 처음 값을 저장된 내용으로 채워요."""
    if key not in st.session_state:
        st.session_state[key] = value
    return key


def save_field(field, key):
    ws = cur()
    ws[field] = st.session_state[key]
    data.save_group(ws)


def go(step):
    st.session_state[f"step_{gid()}"] = step


def flash(kind, msg):
    st.session_state[f"flash_{gid()}"] = (kind, msg)


def show_flash():
    f = st.session_state.pop(f"flash_{gid()}", None)
    if f:
        getattr(st, f[0])(f[1])


def scroll_top():
    """단계를 바꾸면 화면 맨 위로 올라가요."""
    st.iframe("<script>try{const d=window.parent.document;"
              "['[data-testid=\"stMain\"]','[data-testid=\"stAppViewContainer\"]'].forEach(s=>{const e=d.querySelector(s);if(e)e.scrollTop=0});"
              "window.parent.scrollTo(0,0);}catch(e){}</script>", height=1)


def step_done(ws):
    last = ws["rounds"][-1]
    s = data.round_stats(last)
    ok = data.fresh(ws, last)
    return {
        "rules": bool(ws.get("ai_name", "").strip()) and len(ws.get("rules", "").strip()) >= LIMITS["min_prompt"],
        "flow": any(x.get("text", "").strip() for x in ws.get("flow", [])),
        "ask": ok and len(data.answered(last)) >= NEED,
        "label": ok and s["count"] >= NEED,
        "result": ok and s["count"] >= NEED,
        "publish": bool(ws.get("bot_id")) and ws.get("published_key") == data.compiled(ws),
    }


def nav_buttons(prev, nxt, key):
    a, b = st.columns(2)
    if prev:
        a.button("← " + STEP_TITLE[prev], on_click=go, args=(prev,), key=f"prev_{key}")
    if nxt:
        with b.container(horizontal=True, horizontal_alignment="right"):
            st.button(f"다음: {STEP_TITLE[nxt]} →", type="primary", on_click=go, args=(nxt,), key=f"next_{key}")


# ---------------- 모둠 입장 ----------------
def group_login():
    st.title("AI 훈련소")
    st.write("모둠 이름과 모둠 비밀번호로 들어가요. 쓴 내용은 서버에 저장돼서, 다른 날 다른 컴퓨터에서 들어와도 이어서 할 수 있어요.")
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid, st.container(border=True):
        with st.form("group_form"):
            name = st.text_input("만든 모둠", max_chars=LIMITS["author"], placeholder="예: 2학년 3반 1모둠")
            pin = st.text_input("모둠 비밀번호", type="password", max_chars=32)
            st.caption("처음 들어오는 모둠은 지금 넣은 비밀번호가 모둠 비밀번호가 돼요. 모둠원끼리만 알고 있어요. 잊어버리면 선생님이 다시 정해 줄 수 있어요.")
            ok = st.form_submit_button("들어가기", type="primary", use_container_width=True)
        if ok:
            try:
                name = " ".join(str(name or "").split())
                if not name:
                    raise ValueError("만든 모둠(모둠 이름)을 적어 주세요.")
                pw = auth.need_pw(pin, "모둠 비밀번호")
                auth.throttle_check()
                ws = data.load_group(data.group_id(name))
                if ws is None:
                    ws = data.new_group(name, auth.make_pw(pw))
                    data.save_group(ws)
                    st.toast(f"'{ws['name']}' 모둠을 새로 만들었어요.")
                elif not auth.check_pw(pw, ws["pin"]):
                    auth.throttle_fail()
                    raise ValueError("모둠 비밀번호가 맞지 않아요. 잊어버렸다면 선생님께 말해 주세요.")
                st.session_state.gid = ws["gid"]
                st.session_state.gpin = ws["pin"]["hash"]
                st.session_state.cmt_author = ws["name"]
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def logout_group():
    st.session_state.pop("gid", None)
    st.session_state.pop("gpin", None)


def reset_work():
    ws = cur()
    ws.update(ai_name="", rules="", flow=[], rounds=[data.new_round(1)], description="")
    data.save_group(ws)
    for k in [k for k in st.session_state.keys() if str(k).endswith("_" + ws["gid"]) or f"_{ws['gid']}_" in str(k)]:
        if not str(k).startswith("step_"):
            del st.session_state[k]
    go("rules")


# ---------------- 차수 (1차, 2차 …) ----------------
def view_index(ws):
    k = f"view_{ws['gid']}"
    if k not in st.session_state or not (0 <= st.session_state[k] < len(ws["rounds"])):
        st.session_state[k] = len(ws["rounds"]) - 1
    return k


def round_picker(ws):
    k = view_index(ws)
    rounds = ws["rounds"]
    if len(rounds) > 1:
        st.segmented_control("평가 차수", list(range(len(rounds))), key=k, required=True,
                             format_func=lambda i: f"{rounds[i]['no']}차 평가", label_visibility="collapsed")
    else:
        st.caption("1차 평가")
    return st.session_state[k]


def can_ask(ws, view):
    last = ws["rounds"][-1]
    return view == len(ws["rounds"]) - 1 and (not data.started(last) or last.get("key") == data.compiled(ws))


def start_next_round():
    ws = cur()
    last = ws["rounds"][-1]
    ws["rounds"].append(data.new_round(last["no"] + 1, [it["q"] for it in last["items"]]))
    data.save_group(ws)
    st.session_state[f"view_{ws['gid']}"] = len(ws["rounds"]) - 1
    st.session_state[f"autoask_{ws['gid']}"] = True
    go("ask")


def round_note(ws, view, where):
    last = ws["rounds"][-1]
    if data.started(last) and last.get("key") != data.compiled(ws):
        with st.container(border=True):
            st.warning(f"규칙이나 순서도가 바뀌었어요. {last['no']}차 결과는 그대로 남아 있어요. "
                       "바뀐 규칙이 나아졌는지 같은 질문으로 확인해 보세요.")
            st.button(f"{last['no'] + 1}차 평가 시작", type="primary", on_click=start_next_round, key=f"nr_{where}")
    elif view != len(ws["rounds"]) - 1:
        st.info(f"지금은 지난 {ws['rounds'][view]['no']}차 평가를 보고 있어요. 기록(0/1)은 고칠 수 있지만 질문을 새로 물어볼 수는 없어요.")


# ---------------- 1단계: 규칙 ----------------
def add_idea(key):
    label = st.session_state.get(key)
    idea = next((d for d in IDEAS if d["label"] == label), None)
    if not idea:
        return
    ws = cur()
    r = ws.get("rules", "")
    sep = "" if not r or r.endswith("\n") else "\n"
    ws["rules"] = (r + sep + idea["starter"])[:LIMITS["prompt"]]
    data.save_group(ws)
    st.session_state[f"rules1_{ws['gid']}"] = ws["rules"]


def step_rules(ws):
    g = ws["gid"]
    left, right = st.columns([1.6, 1], gap="large")
    with left, st.container(border=True):
        a, b = st.columns([1, 3])
        k = bind(f"emoji_{g}", ws.get("emoji") or EMOJIS[0])
        a.selectbox("얼굴", EMOJIS, key=k, on_change=save_field, args=("emoji", k))
        k = bind(f"ainame_{g}", ws.get("ai_name", ""))
        b.text_input("AI 이름", key=k, max_chars=LIMITS["name"], placeholder="예: 공정한 부엉이", on_change=save_field, args=("ai_name", k))
        st.text_input("만든 모둠", value=ws["name"], disabled=True, key=f"gname_{g}")
        k = bind(f"rules1_{g}", ws.get("rules", ""))
        st.text_area("AI에게 줄 규칙", key=k, height=330, max_chars=LIMITS["prompt"], on_change=save_field, args=("rules", k),
                     placeholder="예)\n너는 중학생의 궁금증을 함께 풀어 주는 AI야.\n- 질문이 한쪽으로 치우쳐 있으면 …\n- 의견이 갈리는 주제는 …",
                     help="AI는 이 글을 읽고 그대로 행동해요. 치우친 질문을 받았을 때 어떻게 답해야 하는지 가르쳐 주세요.")
        st.caption("칸 밖을 누르면 자동으로 저장돼요.")
    with right, st.container(border=True):
        st.markdown("**아이디어 카드**")
        st.caption("막히면 눌러 보세요. 문장의 앞부분을 규칙 칸 끝에 넣어 줄게요. 뒷부분은 직접 완성해요.")
        k = f"idea_{g}"
        choice = st.pills("아이디어", [d["label"] for d in IDEAS], key=k, on_change=add_idea, args=(k,), label_visibility="collapsed")
        idea = next((d for d in IDEAS if d["label"] == choice), None)
        if idea:
            with st.container(border=True):
                if idea["ex"]:
                    st.caption("이런 질문이 오면")
                    st.markdown(f"**“{ui.esc(idea['ex'])}”**")
                st.markdown(f'<div class="ba-hand">{ui.esc(idea["ask"])}</div>', unsafe_allow_html=True)
                st.caption(f"규칙 칸에 “{idea['starter'].strip()}”를 넣었어요. 뒷부분을 이어서 써 보세요.")
    nav_buttons(None, "flow", "rules")


# ---------------- 2단계: 순서도 ----------------
def flow_set(step_id, field, key):
    ws = cur()
    for s in ws["flow"]:
        if s["id"] == step_id:
            s[field] = st.session_state[key]
    data.save_group(ws)


def flow_move(step_id, d):
    ws = cur()
    f = ws["flow"]
    i = next((n for n, s in enumerate(f) if s["id"] == step_id), None)
    if i is not None and 0 <= i + d < len(f):
        f[i], f[i + d] = f[i + d], f[i]
        data.save_group(ws)


def flow_del(step_id):
    ws = cur()
    ws["flow"] = [s for s in ws["flow"] if s["id"] != step_id]
    data.save_group(ws)


def flow_add(kind):
    ws = cur()
    if len(ws["flow"]) < LIMITS["flow_steps"]:
        ws["flow"].append(data.new_step(kind))
        data.save_group(ws)


def step_flow(ws):
    flow = ws.get("flow", [])
    left, right = st.columns([1.15, 1], gap="large")
    with left, st.container(border=True):
        st.markdown("**단계 쓰기**")
        if not flow:
            st.caption("아직 단계가 없어요. 아래 버튼으로 첫 단계를 추가해 보세요.")
        for i, s in enumerate(flow):
            sid, check = s["id"], s.get("type") == "check"
            with st.container(border=True):
                head = st.container(horizontal=True, vertical_alignment="center")
                head.markdown(f"**{i + 1}단계** · {'🟨 판단' if check else '🟦 처리'}")
                head.space("stretch")
                head.button("↑", key=f"up_{sid}", disabled=i == 0, on_click=flow_move, args=(sid, -1), help="위로")
                head.button("↓", key=f"dn_{sid}", disabled=i == len(flow) - 1, on_click=flow_move, args=(sid, 1), help="아래로")
                head.button("지우기", key=f"rm_{sid}", on_click=flow_del, args=(sid,))
                k = bind(f"ft_{sid}", s.get("text", ""))
                st.text_input(f"{i + 1}단계 내용", key=k, label_visibility="collapsed", max_chars=LIMITS["step_text"],
                              placeholder="예: 질문에 한쪽으로 치우친 표현이 있나?" if check else "예: 질문의 핵심을 한 문장으로 정리한다",
                              on_change=flow_set, args=(sid, "text", k))
                if check:
                    y, n = st.columns(2)
                    k = bind(f"fy_{sid}", s.get("yes", ""))
                    y.text_input("✅ 예이면", key=k, max_chars=LIMITS["step_text"], placeholder="예: 치우친 부분을 먼저 부드럽게 알려 준다",
                                 on_change=flow_set, args=(sid, "yes", k))
                    k = bind(f"fn_{sid}", s.get("no", ""))
                    n.text_input("❌ 아니오이면", key=k, max_chars=LIMITS["step_text"], placeholder="예: 다음 단계로 간다",
                                 on_change=flow_set, args=(sid, "no", k))
        full = len(flow) >= LIMITS["flow_steps"]
        row = st.container(horizontal=True)
        row.button("+ 처리 추가", on_click=flow_add, args=("do",), disabled=full)
        row.button("+ 판단 추가", on_click=flow_add, args=("check",), disabled=full)
        if full:
            st.caption(f"순서도는 {LIMITS['flow_steps']}단계까지 만들 수 있어요.")
    with right, st.container(border=True):
        st.markdown("**미리보기**")
        st.markdown(ui.flow_html(flow), unsafe_allow_html=True)
    nav_buttons("rules", "ask", "flow")


# ---------------- 3단계: 질문 ----------------
def set_q(view, i, key):
    ws = cur()
    it = ws["rounds"][view]["items"][i]
    if not it.get("answer"):
        it["q"] = st.session_state[key]
        data.save_group(ws)


def clear_q(view, i):
    ws = cur()
    rnd = ws["rounds"][view]
    rnd["items"][i] = data.blank_item("")
    data.save_group(ws)
    st.session_state[f"q_{ws['gid']}_{rnd['no']}_{i}"] = ""


def ask_all(view):
    ws = cur()
    rnd = ws["rounds"][view]
    comp = data.compiled(ws)
    if len(comp) < LIMITS["min_prompt"]:
        st.error(f"먼저 1단계에서 규칙이나 순서도를 {LIMITS['min_prompt']}자 이상 써 주세요.")
        return
    todo = [i for i, it in enumerate(rnd["items"]) if it["q"].strip() and not it.get("answer")]
    if not todo:
        return
    conn = ai.connection(auth.load_settings())
    if not conn["key"]:
        st.error("OpenAI API 키가 아직 없어요. 선생님이 '선생님' 메뉴에서 키를 넣어 주세요.")
        return
    rnd["key"] = comp
    data.save_group(ws)
    bar = st.progress(0.0, text=f"AI가 답하는 중이에요… (0 / {len(todo)})")
    errors, got = [], 0
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(ai.complete, conn, ai.bot_messages(comp, [], rnd["items"][i]["q"].strip())): i for i in todo}
        for n, fut in enumerate(as_completed(futs), 1):
            i = futs[fut]
            try:
                answer = fut.result()
                latest = cur()
                r2 = latest["rounds"][view]
                if r2["items"][i]["q"].strip() == rnd["items"][i]["q"].strip():
                    r2["items"][i]["answer"] = answer
                    r2["key"] = comp
                    data.save_group(latest)
                    got += 1
            except Exception as e:  # 한 질문이 실패해도 나머지는 계속
                errors.append(str(e))
            bar.progress(n / len(todo), text=f"AI가 답하는 중이에요… ({n} / {len(todo)})")
    bar.empty()
    if errors:
        flash("error", f"{len(errors)}개 질문은 답을 받지 못했어요. ({errors[0]}) 다시 'AI에게 물어보기'를 눌러 주세요.")
    elif all(it.get("answer") or not it["q"].strip() for it in cur()["rounds"][view]["items"]):
        flash("success", "답변을 모두 받았어요. 4단계에서 답변을 기록해요.")
    st.rerun()


def step_ask(ws):
    g = ws["gid"]
    view = round_picker(ws)
    round_note(ws, view, "ask")
    rnd = ws["rounds"][view]
    ask = can_ask(ws, view)
    with st.expander("선생님이 정한 평가 기준 5가지 보기"):
        for i, c in enumerate(CRITERIA):
            st.markdown(f"**{CN[i]} {c['name']}** — {c['desc']}")
    with st.container(border=True):
        filled = sum(1 for it in rnd["items"] if it["q"].strip())
        head = st.container(horizontal=True, vertical_alignment="center")
        head.markdown("**편향된 질문**")
        head.space("stretch")
        head.caption(f"{filled} / {len(rnd['items'])}개 씀 · 답변 {len(data.answered(rnd))}개")
        for i, it in enumerate(rnd["items"]):
            row = st.container(horizontal=True, vertical_alignment="center")
            row.markdown(f"**{i + 1}**")
            k = bind(f"q_{g}_{rnd['no']}_{i}", it["q"])
            row.text_input(f"질문 {i + 1}", key=k, label_visibility="collapsed", max_chars=300,
                           disabled=bool(it.get("answer")) or not ask,
                           placeholder="예: 숙제 대신 해줘" if i == 0 else f"편향된 질문 {i + 1}",
                           on_change=set_q, args=(view, i, k))
            if it.get("answer"):
                row.markdown(":green[✓ 답변 받음]")
                if ask:
                    row.button("✕", key=f"clr_{g}_{rnd['no']}_{i}", on_click=clear_q, args=(view, i), help="질문과 답변 지우기")
        todo = sum(1 for it in rnd["items"] if it["q"].strip() and not it.get("answer"))
        if ask:
            clicked = st.button(f"AI에게 물어보기 ({todo}개)" if todo else "AI에게 물어보기", type="primary", disabled=not todo, key=f"ask_{g}")
            if not todo:
                st.caption("모든 질문에 답을 받았어요. 다음 단계에서 기록해요." if filled == len(rnd["items"]) else "질문을 써야 물어볼 수 있어요.")
            if clicked or (st.session_state.pop(f"autoask_{g}", False) and todo):
                ask_all(view)
    nav_buttons("flow", "label", "ask")


# ---------------- 4단계: 기록 ----------------
def set_summary(view, i, key):
    ws = cur()
    ws["rounds"][view]["items"][i]["summary"] = st.session_state[key]
    data.save_group(ws)


def set_label(view, i, ci, key):
    ws = cur()
    ws["rounds"][view]["items"][i]["labels"][ci] = st.session_state[key]
    data.save_group(ws)


def set_cur(key, value):
    st.session_state[key] = value


def step_label(ws):
    g = ws["gid"]
    view = round_picker(ws)
    rnd = ws["rounds"][view]
    items = rnd["items"]
    idx = [i for i, it in enumerate(items) if it.get("answer")]
    if not idx:
        st.info("아직 AI 답변이 없어요. 3단계에서 질문을 쓰고 'AI에게 물어보기'를 눌러 주세요.")
        st.button("질문하러 가기", on_click=go, args=("ask",))
        return
    ck = f"cur_{g}_{rnd['no']}"
    if st.session_state.get(ck) not in idx:
        st.session_state[ck] = next((i for i in idx if not is_labeled(items[i]["labels"])), idx[0])
    top = st.container(horizontal=True, vertical_alignment="center")
    top.segmented_control("질문 고르기", idx, key=ck, required=True, label_visibility="collapsed",
                          format_func=lambda i: f"{i + 1}" + (" ✓" if is_labeled(items[i]["labels"]) else ""))
    top.space("stretch")
    top.caption(f"기록 완료 {data.round_stats(rnd)['count']} / {len(idx)}")
    i = st.session_state[ck]
    it = items[i]
    with st.container(border=True):
        st.markdown(f'<div style="font-size:1.25rem;font-weight:700;line-height:1.45">{i + 1}. {ui.esc(it["q"])}</div>', unsafe_allow_html=True)
        a, b = st.columns(2, gap="large")
        with a:
            st.caption("AI 답변")
            with st.container(border=True):
                st.markdown(it["answer"])
        with b:
            k = bind(f"sum_{g}_{rnd['no']}_{i}", it.get("summary", ""))
            st.text_input("답변 요약 (직접 쓰기)", key=k, max_chars=200, placeholder="예: AI가 무비판적으로 대신 작성해 줌",
                          on_change=set_summary, args=(view, i, k))
            for ci, c in enumerate(CRITERIA):
                with st.container(border=True):
                    x, y = st.columns([1.5, 1], vertical_alignment="center")
                    x.markdown(f"**{CN[ci]} {c['name']}**")
                    x.caption(c["desc"])
                    k = bind(f"lab_{g}_{rnd['no']}_{i}_{ci}", it["labels"][ci])
                    y.segmented_control(c["name"], [0, 1], key=k, label_visibility="collapsed",
                                        format_func=lambda v: "0 안 지킴" if v == 0 else "1 지킴",
                                        on_change=set_label, args=(view, i, ci, k))
        pos = idx.index(i)
        row = st.columns([1, 1, 1], vertical_alignment="center")
        if pos > 0:
            row[0].button("← 이전 질문", on_click=set_cur, args=(ck, idx[pos - 1]), key=f"pv_{g}")
        labels = it["labels"]
        row[1].markdown(f"<div style='text-align:center'>합계 <b>{sum(labels)}</b> / 5</div>" if is_labeled(labels)
                        else f"<div style='text-align:center' class='ba-muted'>남은 기준 {sum(1 for v in labels if v is None)}개</div>",
                        unsafe_allow_html=True)
        with row[2].container(horizontal=True, horizontal_alignment="right"):
            if pos < len(idx) - 1:
                st.button("다음 질문 →", type="primary", on_click=set_cur, args=(ck, idx[pos + 1]), key=f"nx_{g}")
            else:
                st.button("결과 보기 →", type="primary", on_click=go, args=("result",), key=f"rs_{g}")
    nav_buttons("ask", "result", "label")


# ---------------- 5단계: 결과 ----------------
def csv_bytes(ws, rnd):
    """CSV: 첫 줄 '모둠명, 모둠 이름', 그다음 한 줄에 기준 하나씩 — A열 기준 이름, B열 지킨 개수(1의 개수)."""
    s = data.round_stats(rnd)

    def cell(v):
        t = str(v)
        return '"' + t.replace('"', '""') + '"' if any(ch in t for ch in ',"\r\n') else t
    lines = ["모둠명," + cell(ws["name"])] + [f"{CN[i]} {c['name']},{s['sums'][i]}" for i, c in enumerate(CRITERIA)]
    return ("﻿" + "\r\n".join(lines) + "\r\n").encode("utf-8")


def step_result(ws):
    g = ws["gid"]
    view = round_picker(ws)
    rnd = ws["rounds"][view]
    s = data.round_stats(rnd)
    with st.container(border=True):
        head = st.container(horizontal=True, vertical_alignment="center")
        head.markdown("**평가 데이터 표**")
        head.space("stretch")
        safe = "".join(ch if ch.isalnum() else "_" for ch in ws["name"])
        head.download_button("CSV 파일로 저장", csv_bytes(ws, rnd), file_name=f"밸런스AI_평가데이터_{safe}_{rnd['no']}차.csv",
                             mime="text/csv", on_click="ignore", disabled=not s["count"], key=f"csv_{g}")
        cols = ["번호", "질문", "답변 요약"] + [f"{CN[i]} {c['short']}" for i, c in enumerate(CRITERIA)] + ["합계"]
        rows = []
        for i, it in enumerate(rnd["items"]):
            if not it.get("answer"):
                continue
            lab = it["labels"]
            rows.append([str(i + 1), it["q"], it.get("summary", "")] + ["" if v is None else str(v) for v in lab]
                        + [str(sum(lab)) if is_labeled(lab) else ""])
        if s["count"]:
            rows.append(["지킨 개수", f"답변 {s['count']}개", ""] + [str(n) for n in s["sums"]] + [str(sum(s["sums"]))])
            rows.append(["충족률", "", ""] + [f"{r}%" for r in s["rates"]] + [f"{s['score']}%"])
        if rows:
            st.dataframe(pd.DataFrame(rows, columns=cols), hide_index=True, use_container_width=True)
        else:
            st.caption("아직 기록한 답변이 없어요.")
        st.caption("CSV 파일 첫 줄에는 모둠명이, 그 아래에는 지금 보고 있는 차수의 기준 5가지와 기준마다 지킨 개수(1의 개수)가 들어가요. "
                   "표 오른쪽 위 버튼으로 표 전체를 내려받거나, 칸을 골라 복사(Ctrl+C)할 수도 있어요.")
    with st.container(border=True):
        st.markdown("**규칙 고치기**")
        st.caption("1단계에서 쓴 규칙과 같은 칸이에요. 여기서 고치면 바로 저장되고 1단계에도 똑같이 바뀌어요.")
        k = bind(f"rules5_{g}", ws.get("rules", ""))
        st.text_area("규칙", key=k, height=260, max_chars=LIMITS["prompt"], label_visibility="collapsed",
                     on_change=save_field, args=("rules", k))
        round_note(ws, view, "result")
        st.button("순서도도 고치기", on_click=go, args=("flow",), key=f"toflow_{g}")
    nav_buttons("label", "publish", "result")


# ---------------- 6단계: 올리기 ----------------
def do_publish(desc_key):
    ws = cur()
    bot = data.publish(ws, st.session_state.get(desc_key, ""))
    flash("success", f"‘{bot['name']}’이(가) AI 광장에 올라갔어요. 친구들이 대화해 볼 거예요.")


def step_publish(ws):
    g = ws["gid"]
    last = ws["rounds"][-1]
    s = data.round_stats(last)
    ok = data.fresh(ws, last)
    comp = data.compiled(ws)
    checks = [
        ("AI 이름을 정했어요", bool(ws.get("ai_name", "").strip()), "rules"),
        (f"규칙이나 순서도를 {LIMITS['min_prompt']}자 이상 썼어요", len(comp) >= LIMITS["min_prompt"], "rules"),
        (f"지금 규칙으로 편향된 질문 {NEED}개를 물어봤어요 (지금 {len(data.answered(last)) if ok else 0}개)",
         ok and len(data.answered(last)) >= NEED, "ask"),
        (f"답변 {NEED}개에 0/1 기록을 모두 마쳤어요 (지금 {s['count'] if ok else 0}개)", ok and s["count"] >= NEED, "label"),
    ]
    with st.container(border=True):
        st.markdown("**확인할 것**")
        for n, (text, good, step) in enumerate(checks):
            row = st.container(horizontal=True, vertical_alignment="center")
            row.markdown(("✅ " if good else "⚠️ ") + text)
            if not good:
                row.space("stretch")
                row.button(f"{STEPS.index(step) + 1}단계로 가기", key=f"chk_{n}", on_click=go, args=(step,))
        round_note(ws, len(ws["rounds"]) - 1, "publish")
    if not all(c[1] for c in checks):
        nav_buttons("result", None, "publish")
        return
    with st.container(border=True):
        st.markdown("**고친 내용으로 다시 올리기**" if ws.get("bot_id") else "**광장에 올라갈 모습**")
        st.markdown(
            f'<div class="ba-card-head"><div class="ba-av">{ui.esc(ws.get("emoji"))}</div><div style="flex:1">'
            f'<div class="ba-card-name">{ui.esc(ws["ai_name"])}</div><div class="ba-card-by">만든 모둠 {ui.esc(ws["name"])} · {last["no"]}차 평가 결과</div></div>'
            f'{ui.badge_html(s["score"])}</div>', unsafe_allow_html=True)
        k = bind(f"desc_{g}", ws.get("description", ""))
        st.text_input("한 줄 소개", key=k, max_chars=LIMITS["description"], placeholder="예: 어떤 질문이든 양쪽 이야기를 함께 들려주는 AI",
                      on_change=save_field, args=("description", k))
        st.caption("광장에서는 누구나 이 AI와 대화하고, 우리 모둠의 규칙과 순서도를 볼 수 있어요.")
        if ws.get("bot_id") and ws.get("published_key") == comp:
            st.success("✓ 지금 규칙으로 이미 광장에 올라가 있어요.")
        row = st.container(horizontal=True)
        row.button("다시 올리기" if ws.get("bot_id") else "광장에 올리기", type="primary", on_click=do_publish, args=(k,), key=f"pub_{g}")
        if ws.get("bot_id"):
            row.page_link(nav.page("plaza"), label="광장에서 보기", query_params={"bot": ws["bot_id"]})
    nav_buttons("result", None, "publish")


# ---------------- 화면 ----------------
VIEWS = {"rules": step_rules, "flow": step_flow, "ask": step_ask, "label": step_label, "result": step_result, "publish": step_publish}


def render():
    if not gid():
        group_login()
        return
    ws = cur()
    if ws is None or ws["pin"]["hash"] != st.session_state.get("gpin"):
        logout_group()
        st.warning("모둠 정보가 바뀌었어요. 다시 들어와 주세요.")
        group_login()
        return
    g = ws["gid"]

    head = st.container(horizontal=True, vertical_alignment="bottom")
    with head.container():
        st.title("AI 훈련소")
        st.caption(f"**{ws['name']}** 모둠으로 들어와 있어요. 쓴 내용은 자동으로 저장돼요.")
    head.space("stretch")
    with head.popover("모둠"):
        st.button("다른 모둠으로 들어가기", on_click=logout_group, use_container_width=True)
        st.divider()
        st.caption("규칙, 순서도, 평가 기록을 모두 지우고 처음부터 다시 써요. (광장에 올린 AI는 그대로 있어요)")
        sure = st.checkbox("정말 처음부터 다시 쓸게요", key=f"resetok_{g}")
        st.button("처음부터 다시 쓰기", disabled=not sure, on_click=reset_work, use_container_width=True)

    if ws.get("bot_id"):
        st.info(f"광장에 올린 **{ws.get('ai_name') or '우리 모둠 AI'}**를 고치는 중이에요. 다시 올리면 광장의 AI가 새 규칙과 순서도로 바뀌어요.")

    done = step_done(ws)
    sk = f"step_{g}"
    if st.session_state.get(sk) not in STEPS:
        st.session_state[sk] = "rules"
    st.segmented_control("훈련 단계", STEPS, key=sk, required=True, label_visibility="collapsed", width="stretch",
                         format_func=lambda s: f"{'✓' if done[s] else STEPS.index(s) + 1} {STEP_SHORT[s]}")
    step = st.session_state[sk]
    if st.session_state.get(f"laststep_{g}") != step:
        st.session_state[f"laststep_{g}"] = step
        scroll_top()

    st.markdown(f'<div class="ba-step">{STEPS.index(step) + 1}단계</div>', unsafe_allow_html=True)
    st.subheader(STEP_TITLE[step])
    st.markdown(STEP_HINT[step])
    show_flash()
    VIEWS[step](ws)
