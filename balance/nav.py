"""화면(페이지) 목록 — streamlit_app.py가 채워 넣고, 다른 화면에서 링크를 만들 때 꺼내 써요."""
PAGES = {}


def page(name):
    return PAGES[name]
