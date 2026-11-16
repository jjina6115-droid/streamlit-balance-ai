"""설정값 읽기: Streamlit Secrets → 환경변수 순서로 찾아요."""
import os

import streamlit as st


def secret(name, default=''):
    value = None
    try:
        value = st.secrets.get(name)
    except Exception:  # secrets.toml이 없으면 여기로 와요
        value = None
    if value in (None, ''):
        value = os.environ.get(name, default)
    return str(value) if value is not None else default
