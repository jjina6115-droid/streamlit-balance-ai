"""처음 화면 — AI 훈련소 / AI 광장 입구"""
import streamlit as st

from . import auth, nav, ui


def render():
    c = auth.current_class()
    if c:
        st.markdown(ui.class_chip(c["name"]), unsafe_allow_html=True)
    st.markdown('<h1 style="font-size:clamp(2.2rem,5vw,3.6rem);line-height:1.15;letter-spacing:-.035em;margin-bottom:.4rem">'
                '공정한 AI,<br>우리 모둠이 직접 가르쳐요</h1>'
                '<p class="ba-lead">AI는 받은 규칙대로 말해요. 모둠이 규칙과 응답 순서도를 써서 AI가 한쪽으로 치우치지 않게 가르치고, '
                '그렇게 훈련된 AI를 모두가 함께 써요.</p>', unsafe_allow_html=True)
    st.space("medium")
    a, b = st.columns(2, gap="large")
    with a, st.container(key="door_studio"):
        st.markdown('<div class="ba-door studio"><span class="who">AI를 가르치는 곳</span><h2>AI 훈련소</h2><ol>'
                    '<li>AI에게 줄 규칙을 직접 써요</li><li>답하는 순서를 순서도로 정해요</li>'
                    '<li>편향된 질문으로 AI를 평가하고 기록해요</li><li>데이터를 보고 스스로 고친 뒤 광장에 올려요</li></ol></div>',
                    unsafe_allow_html=True)
        st.page_link(nav.page("studio"), label="AI 훈련 시작하기 →")
    with b, st.container(key="door_plaza"):
        st.markdown('<div class="ba-door plaza"><span class="who">AI를 쓰는 곳</span><h2>AI 광장</h2>'
                    '<p>여러 모둠이 훈련시킨 AI가 모여 있어요. 마음에 드는 AI를 골라 대화하고, 💬 댓글로 느낀 점이나 고칠 점을 남겨요. '
                    '어떤 규칙과 순서도로 가르쳤는지도 볼 수 있어요.</p></div>', unsafe_allow_html=True)
        st.page_link(nav.page("plaza"), label="AI 만나러 가기 →")
