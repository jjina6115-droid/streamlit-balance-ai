"""선생님 메뉴 — OpenAI 키·비밀번호 바꾸기, 모둠 비밀번호 다시 정하기, 광장 관리"""
import time

import streamlit as st

from . import ai, auth, data
from .store import get_store


def render():
    s = auth.load_settings()
    st.title("선생님")
    if not auth.is_teacher(s):
        st.write("선생님 비밀번호로 들어가면 OpenAI 키와 비밀번호를 바꾸고, 모둠 비밀번호를 다시 정하고, 광장의 AI와 댓글을 지울 수 있어요.")
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

    conn = ai.connection(s)
    store = get_store()
    key_text = {"site": f"웹사이트에서 넣은 키 (sk-…{conn['key'][-4:]})", "secrets": "Streamlit Secrets의 OPENAI_API_KEY"}.get(conn["source"], "❗ 아직 없어요. 아래에서 키를 넣어 주세요.")
    with st.container(border=True):
        st.markdown("**지금 상태**")
        st.markdown(f"- **OpenAI 키**: {key_text}\n- **모델**: {conn['model']}\n- **저장소**: {store.label}\n"
                    f"- **학생 입장 비밀번호**: {'사용 중' if auth.access_required(s) else '없음'}")
        if store.kind == "file":
            st.warning("지금은 앱 폴더의 파일에 저장하고 있어요. 내 컴퓨터에서 실행할 때는 괜찮지만, Streamlit Cloud에서는 앱이 다시 시작되면 "
                       "모둠 작업·광장·댓글이 지워질 수 있어요. README의 'Supabase 연결하기'를 따라 하면 지워지지 않아요.")

    with st.container(border=True):
        st.markdown("**키와 비밀번호 바꾸기**")
        st.caption("바꿀 칸에만 넣고 저장해요. 키는 서버에만 저장되고 다시 보여 주지 않아요. 입장 비밀번호를 바꾸면 학생들은 새 비밀번호를 다시 넣어야 해요.")
        with st.form("admin_form", clear_on_submit=True):
            new_key = st.text_input("OpenAI API 키 " + ("바꾸기" if conn["key"] else "넣기"), type="password", placeholder="sk-...")
            remove_key = st.checkbox("웹사이트에서 넣은 키 지우기") if s.get("openai_key") else False
            new_access = st.text_input("새 학생 입장 비밀번호", max_chars=64)
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
                if str(new_access or "").strip():
                    latest["access"] = auth.make_pw(auth.need_pw(new_access, "학생 입장 비밀번호"))
                    changed = True
                if str(new_admin or "").strip():
                    latest["admin"] = auth.make_pw(auth.need_pw(new_admin, "선생님 비밀번호"))
                    changed = True
                if not changed:
                    raise ValueError("바꿀 내용을 넣어 주세요.")
                latest.setdefault("secret", __import__("secrets").token_hex(32))
                auth.save_settings(latest)
                st.session_state.teacher_fp = auth.admin_fp(latest)
                st.session_state.entered = auth.access_token(latest)
                st.query_params["k"] = auth.access_token(latest)
                st.success("저장했어요.")
            except ValueError as e:
                st.error(str(e))

    with st.container(border=True):
        st.markdown("**모둠 관리**")
        groups = sorted(data.list_groups(), key=lambda g: g.get("name", ""))
        if not groups:
            st.caption("아직 들어온 모둠이 없어요.")
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
