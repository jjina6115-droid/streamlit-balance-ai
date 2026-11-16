"""밸런스 AI — Streamlit 버전 (시작 파일)

실행:  streamlit run streamlit_app.py
화면:  처음 · AI 훈련소 · AI 광장 · 선생님
"""
import streamlit as st

st.set_page_config(page_title="밸런스 AI", page_icon="🦉", layout="wide", initial_sidebar_state="collapsed")

from balance import auth, home, nav, plaza, studio, teacher, ui  # noqa: E402

ui.inject_css()
auth.gate()  # 처음 설정 / 입장 비밀번호 화면 (통과해야 아래 화면이 보여요)

nav.PAGES.update(
    home=st.Page(home.render, title="처음", icon=":material/home:", url_path="home", default=True),
    studio=st.Page(studio.render, title="AI 훈련소", icon=":material/school:", url_path="studio"),
    plaza=st.Page(plaza.render, title="AI 광장", icon=":material/forum:", url_path="plaza"),
    teacher=st.Page(teacher.render, title="선생님", icon=":material/key:", url_path="teacher"),
)
st.navigation(list(nav.PAGES.values()), position="top").run()
