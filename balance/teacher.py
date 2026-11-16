"""선생님 메뉴 — 반 관리(반 만들기·고르기·비밀번호·결과 CSV·지우기), 키·선생님 비밀번호 바꾸기, 모둠 관리"""
import time

import streamlit as st

from . import ai, auth, data, ui
from .store import get_store


def flash(msg):
    st.session_state["teacher_flash"] = msg


def show_class(cid):
    latest = auth.fresh_settings()
    c = auth.find_class(latest, cid)
    if c:
        auth.enter_class(latest, c)
        flash(f"이제 ‘{c['name']}’의 훈련소와 광장을 보고 있어요.")


# ---------------- 반 관리 ----------------
def class_box(s):
    cur = auth.current_class(s)
    classes = auth.classes(s)
    with st.container(border=True):
        st.markdown("**반 관리**")
        st.caption("반마다 입장 비밀번호가 따로 있어요. 학생은 자기 반 비밀번호로 들어와서 자기 반 모둠과 광장만 봐요. "
                   "선생님은 아래에서 ‘이 반 보기’를 누르면 그 반의 훈련소와 광장을 볼 수 있어요.")
        if not classes:
            st.warning("아직 반이 없어요. 아래에서 첫 번째 반을 만들어 주세요.")
        for c in classes:
            cid = c["id"]
            n = data.class_counts(cid)
            with st.container(border=True):
                row = st.container(horizontal=True, vertical_alignment="center")
                now_tag = ' <span class="ba-tag" style="color:#0D5E4C;background:#E5F3EE;border-color:#9ED5C3">지금 보는 반</span>' if cur and cur["id"] == cid else ""
                row.markdown(f"**{ui.esc(c['name'])}**{now_tag} · 모둠 {n['groups']}개 · 광장 AI {n['bots']}개", unsafe_allow_html=True)
                row.space("stretch")
                if not (cur and cur["id"] == cid):
                    row.button("이 반 보기", key=f"cview_{cid}", type="primary", on_click=show_class, args=(cid,))
                safe = "".join(ch if ch.isalnum() else "_" for ch in c["name"])
                row.download_button("결과 CSV", data.class_csv_bytes(cid), file_name=f"밸런스AI_{safe}_모둠별결과.csv",
                                    mime="text/csv", on_click="ignore", key=f"ccsv_{cid}", disabled=not n["groups"],
                                    help="이 반 모든 모둠의 기준별 지킨 개수(가장 최근 차수)를 한 파일로 받아요.")
                with row.popover("이름·비밀번호 바꾸기"):
                    st.caption("바꿀 칸에만 넣어요. 입장 비밀번호를 바꾸면 이 반 학생들은 새 비밀번호를 다시 넣어야 해요.")
                    new_name = st.text_input("새 반 이름", key=f"cname_{cid}", max_chars=auth.CLASS_NAME_MAX, placeholder=c["name"])
                    pw = st.text_input("새 입장 비밀번호", key=f"cpw_{cid}", max_chars=64)
                    if st.button("저장", key=f"cpwsave_{cid}", type="primary"):
                        try:
                            latest = auth.fresh_settings()
                            target = auth.find_class(latest, cid)
                            if not target:
                                raise ValueError("이 반을 찾을 수 없어요. 새로고침해 주세요.")
                            done = []
                            if str(new_name or "").strip():
                                name = auth.need_class_name(new_name)
                                if any(x["name"] == name and x["id"] != cid for x in auth.classes(latest)):
                                    raise ValueError(f"‘{name}’ 반이 이미 있어요. 다른 이름으로 정해 주세요.")
                                target["name"] = name
                                done.append("이름")
                            if str(pw or "").strip():
                                target["access"] = auth.make_pw(auth.check_class_pw(latest, pw, skip_cid=cid))
                                done.append("입장 비밀번호")
                            if not done:
                                raise ValueError("바꿀 내용을 넣어 주세요.")
                            auth.save_settings(latest)
                            if cur and cur["id"] == cid:
                                auth.enter_class(latest, target)
                            flash(f"‘{target['name']}’ {'와 '.join(done)}을(를) 바꿨어요." + (" 학생들에게 새 비밀번호를 알려 주세요." if "입장 비밀번호" in done else ""))
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                with row.popover("반 지우기"):
                    st.write(f"‘{c['name']}’과(와) 이 반의 **모둠 작업·평가 기록·광장 AI·댓글을 모두** 지울까요? 지운 뒤에는 되돌릴 수 없어요.")
                    st.caption("평가 기록이 필요하면 먼저 ‘결과 CSV’를 받아 두세요.")
                    sure = st.checkbox("정말 지울게요", key=f"cdelok_{cid}")
                    if st.button("반 지우기", key=f"cdel_{cid}", type="primary", disabled=not sure):
                        data.delete_class_data(cid)
                        latest = auth.fresh_settings()
                        latest["classes"] = [x for x in auth.classes(latest) if x["id"] != cid]
                        auth.save_settings(latest)
                        if cur and cur["id"] == cid:
                            for k in ("entered", "cls", "gid", "gpin", "open_cmt"):
                                st.session_state.pop(k, None)
                            if "k" in st.query_params:
                                del st.query_params["k"]
                            rest = auth.classes(latest)
                            if rest:
                                auth.enter_class(latest, rest[0])
                        flash(f"‘{c['name']}’을(를) 지웠어요.")
                        st.rerun()

        st.markdown("**새 반 만들기**")
        with st.form("new_class_form", clear_on_submit=True):
            a, b = st.columns(2)
            name = a.text_input("반 이름", max_chars=auth.CLASS_NAME_MAX, placeholder="예: 2학년 4반")
            pw = b.text_input("이 반 입장 비밀번호", max_chars=64, placeholder="반마다 다르게")
            ok = st.form_submit_button("반 만들기", type="primary")
        if ok:
            try:
                latest = auth.fresh_settings()
                name = auth.need_class_name(name)
                if any(x["name"] == name for x in auth.classes(latest)):
                    raise ValueError(f"‘{name}’ 반이 이미 있어요. 다른 이름으로 정해 주세요.")
                c = auth.new_class(name, auth.check_class_pw(latest, pw))
                latest["classes"] = auth.classes(latest) + [c]
                auth.save_settings(latest)
                if not cur:
                    auth.enter_class(latest, c)
                flash(f"‘{name}’을(를) 만들었어요. 이 반 학생들에게 입장 비밀번호를 알려 주세요.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


# ---------------- 화면 ----------------
def render():
    s = auth.load_settings()
    st.title("선생님")
    if not auth.is_teacher(s):
        st.write("선생님 비밀번호로 들어가면 반을 만들고 고르고, 키와 비밀번호를 바꾸고, 모둠 비밀번호를 다시 정하고, 광장의 AI와 댓글을 지울 수 있어요.")
        _, mid, _ = st.columns([1, 1.6, 1])
        with mid, st.container(border=True):
            with st.form("teacher_login"):
                pw = st.text_input("선생님 비밀번호", type="password")
                ok = st.form_submit_button("들어가기", type="primary", use_container_width=True)
            if ok:
                try:
                    auth.teacher_login(pw, s)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        return

    top = st.container(horizontal=True, vertical_alignment="center")
    top.success("선생님 메뉴가 켜져 있어요. 광장의 모든 AI에 '내리기', 모든 댓글에 '지우기'가 보여요.")
    if top.button("선생님 메뉴 끄기"):
        st.session_state.pop("teacher_fp", None)
        st.rerun()
    msg = st.session_state.pop("teacher_flash", None)
    if msg:
        st.toast(msg)

    conn = ai.connection(s)
    store = get_store()
    cur = auth.current_class(s)
    key_text = {"site": "웹사이트에서 넣은 " + ai.key_label(conn), "secrets": "Streamlit Secrets의 OPENAI_API_KEY — " + ai.key_label(conn)}.get(conn["source"], "❗ 아직 없어요. 아래에서 키를 넣어 주세요.")
    with st.container(border=True):
        st.markdown("**지금 상태**")
        st.markdown(f"- **지금 보는 반**: {ui.esc(cur['name']) if cur else '없음'} (반 {len(auth.classes(s))}개)\n"
                    f"- **AI 키**: {key_text}\n- **모델**: {conn['model']}\n- **저장소**: {store.label}")
        if conn.get("provider") == "gemini":
            st.warning("지금은 **선생님 시험용 Gemini 무료 키**를 쓰고 있어요. Gemini 약관상 18세 미만이 쓰는 앱에는 쓸 수 없고, "
                       "무료 사용분은 입력 내용이 구글 제품 개선에 쓰일 수 있어요. 학생들에게 주소를 알려 주기 전에 아래에서 OpenAI 키(sk-…)로 바꿔 주세요.")
        if store.kind == "file":
            st.warning("지금은 앱 폴더의 파일에 저장하고 있어요. 내 컴퓨터에서 실행할 때는 괜찮지만, Streamlit Cloud에서는 앱이 다시 시작되면 "
                       "모둠 작업·광장·댓글이 지워질 수 있어요. README의 'Supabase 연결하기'를 따라 하면 지워지지 않아요.")

    class_box(s)

    with st.container(border=True):
        st.markdown("**키와 선생님 비밀번호 바꾸기**")
        st.caption("바꿀 칸에만 넣고 저장해요. 키는 서버에만 저장되고 다시 보여 주지 않아요. 반 입장 비밀번호는 위 ‘반 관리’에서 바꿔요.")
        with st.form("admin_form", clear_on_submit=True):
            new_key = st.text_input("AI API 키 " + ("바꾸기" if conn["key"] else "넣기"), type="password", placeholder="OpenAI 키 sk-...  (선생님 시험용 Gemini 키 AQ.… 도 돼요)",
                                    autocomplete="off")
            remove_key = st.checkbox("웹사이트에서 넣은 키 지우기") if s.get("openai_key") else False
            new_admin = st.text_input("새 선생님 비밀번호", type="password", max_chars=64)
            ok = st.form_submit_button("저장", type="primary")
        if ok:
            try:
                latest = auth.fresh_settings()
                changed = False
                if str(new_key or "").strip():
                    latest["openai_key"] = ai.test_key(new_key)
                    changed = True
                elif remove_key and latest.get("openai_key"):
                    latest.pop("openai_key")
                    changed = True
                if str(new_admin or "").strip():
                    pw = auth.need_pw(new_admin, "선생님 비밀번호")
                    if auth.class_by_pw(latest, pw):
                        raise ValueError("반 입장 비밀번호와 다른 비밀번호로 정해 주세요.")
                    latest["admin"] = auth.make_pw(pw)
                    changed = True
                if not changed:
                    raise ValueError("바꿀 내용을 넣어 주세요.")
                latest.setdefault("secret", __import__("secrets").token_hex(32))
                auth.save_settings(latest)
                st.session_state.teacher_fp = auth.admin_fp(latest)
                flash("저장했어요.")
                st.rerun()  # 위쪽 '지금 상태'에 바뀐 키가 바로 보이게 다시 그려요
            except ValueError as e:
                st.error(str(e))

    with st.container(border=True):
        st.markdown(f"**모둠 관리** — {ui.esc(cur['name'])}" if cur else "**모둠 관리**")
        if not cur:
            st.caption("위 ‘반 관리’에서 반을 고르면 그 반의 모둠이 보여요.")
            return
        groups = sorted(data.list_groups(), key=lambda g: g.get("name", ""))
        if not groups:
            st.caption("이 반에는 아직 들어온 모둠이 없어요.")
        for g in groups:
            row = st.container(horizontal=True, vertical_alignment="center")
            last = g["rounds"][-1]
            st_ = data.round_stats(last)
            row.markdown(f"**{g['name']}** · {last['no']}차 평가 기록 {st_['count']}개" + (" · 광장에 올림" if g.get("bot_id") else ""))
            row.space("stretch")
            row.caption(time.strftime("%m/%d %H:%M", time.localtime(g.get("updated", 0))))
            with row.popover("모둠 비밀번호 다시 정하기"):
                pin = st.text_input("새 모둠 비밀번호", key=f"pin_{g['gid']}", max_chars=32)
                if st.button("저장", key=f"pinsave_{g['gid']}", type="primary"):
                    try:
                        latest = data.load_group(g["gid"])
                        latest["pin"] = auth.make_pw(auth.need_pw(pin, "모둠 비밀번호"))
                        data.save_group(latest)
                        st.success("새 비밀번호를 모둠에 알려 주세요.")
                    except ValueError as e:
                        st.error(str(e))
            with row.popover("지우기"):
                st.write(f"‘{g['name']}’ 모둠의 규칙·순서도·평가 기록을 모두 지울까요? (광장에 올린 AI는 그대로 있어요)")
                if st.button("모둠 지우기", key=f"gdel_{g['gid']}", type="primary"):
                    data.delete_group(g["gid"])
                    st.rerun()
