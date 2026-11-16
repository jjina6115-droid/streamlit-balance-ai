"""비밀번호 — 처음 설정, 학생 입장 비밀번호, 선생님 비밀번호, 모둠 비밀번호.

비밀번호는 그대로 저장하지 않고, 풀 수 없게 바꾼 값(해시)만 저장해요.
Streamlit Secrets에 ADMIN_PASSWORD, ACCESS_PASSWORD, OPENAI_API_KEY를 넣어 두면 '처음 설정' 화면 없이 바로 써요.
"""
import hashlib
import hmac
import secrets as pysecrets
import time

import streamlit as st

from . import ai, ui
from .env import secret
from .store import get_store

SETTINGS_KEY = "settings"


# ---------------- 설정 읽기·쓰기 ----------------
@st.cache_data(ttl=10, show_spinner=False)
def _cached_settings():
    return get_store().get(SETTINGS_KEY) or {}


def load_settings():
    return dict(_cached_settings())


def save_settings(settings):
    settings["updated"] = time.time()
    get_store().put(SETTINGS_KEY, settings)
    _cached_settings.clear()


def fresh_settings():
    _cached_settings.clear()
    return load_settings()


# ---------------- 비밀번호 ----------------
def pw_hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120_000).hex()


def make_pw(pw):
    salt = pysecrets.token_hex(16)
    return {"salt": salt, "hash": pw_hash(pw, salt)}


def check_pw(pw, rec):
    return bool(pw and rec and rec.get("hash")) and hmac.compare_digest(pw_hash(pw, rec["salt"]), rec["hash"])


def need_pw(value, label):
    pw = str(value or "").strip()
    if len(pw) < 4:
        raise ValueError(f"{label}는 4글자 이상으로 정해 주세요.")
    if len(pw) > 64:
        raise ValueError(f"{label}가 너무 길어요. 64글자까지 쓸 수 있어요.")
    return pw


def admin_configured(s):
    return bool(s.get("admin") or secret("ADMIN_PASSWORD"))


def access_required(s):
    return bool(s.get("access") or secret("ACCESS_PASSWORD"))


def is_admin_pw(pw, s):
    pw = str(pw or "").strip()
    env = secret("ADMIN_PASSWORD")
    if env and pw and hmac.compare_digest(pw, env):
        return True
    return check_pw(pw, s.get("admin"))


def is_access_pw(pw, s):
    pw = str(pw or "").strip()
    env = secret("ACCESS_PASSWORD")
    if env and pw and hmac.compare_digest(pw, env):
        return True
    return check_pw(pw, s.get("access")) or is_admin_pw(pw, s)


def access_token(s):
    """한 번 들어온 기기는 주소에 붙은 표(k)로 새로고침해도 다시 묻지 않아요. 입장 비밀번호를 바꾸면 표도 바뀌어요."""
    finger = (s.get("access") or {}).get("hash") or hashlib.sha256(("acc:" + secret("ACCESS_PASSWORD")).encode()).hexdigest()
    key = s.get("secret") or hashlib.sha256(("balance:" + secret("ADMIN_PASSWORD") + ":" + secret("ACCESS_PASSWORD")).encode()).hexdigest()
    return hmac.new(key.encode(), finger.encode(), "sha256").hexdigest()[:24]


# 비밀번호를 너무 많이 틀리면 잠깐 막아요 (같은 인터넷 주소 기준, 한 반이 함께 써도 넉넉하게)
@st.cache_resource(show_spinner=False)
def _fails():
    return {}


def _ip():
    try:
        return st.context.ip_address or "local"
    except Exception:
        return "local"


def throttle_check():
    f = _fails().get(_ip())
    if f and f.get("until", 0) > time.time():
        raise ValueError("비밀번호를 너무 많이 틀렸어요. 5분 뒤에 다시 해 주세요.")


def throttle_fail():
    now = time.time()
    f = _fails().setdefault(_ip(), {"count": 0, "since": now, "until": 0})
    if now - f["since"] > 600:
        f.update(count=0, since=now)
    f["count"] += 1
    if f["count"] >= 30:
        f.update(until=now + 300, count=0, since=now)


# ---------------- 화면: 처음 설정 · 입장 ----------------
def _center():
    _, mid, _ = st.columns([1, 1.6, 1])
    return mid


def setup_screen(s):
    with _center(), st.container(border=True):
        ui.brand()
        st.markdown('<div class="ba-gate-title">처음 설정</div>', unsafe_allow_html=True)
        st.write("선생님이 처음 한 번만 하면 돼요. 학생들에게 주소를 알려 주기 전에 먼저 설정해 주세요.")
        env_key = bool(secret("OPENAI_API_KEY"))
        with st.form("setup_form"):
            key = st.text_input("OpenAI API 키", type="password", placeholder="sk-...",
                                help="비워 두면 Streamlit Secrets에 넣어 둔 키를 써요." if env_key else None)
            st.caption("비워 두면 Secrets에 넣어 둔 키를 써요." if env_key else "키는 서버 저장소에만 저장되고, 학생들 화면에는 보이지 않아요.")
            access = st.text_input("학생 입장 비밀번호", max_chars=64)
            st.caption("이 비밀번호를 아는 사람만 사이트를 쓸 수 있어요. 학생들에게 알려 줄 비밀번호예요.")
            admin = st.text_input("선생님 비밀번호", type="password", max_chars=64)
            st.caption("키와 비밀번호를 바꿀 때, 광장에서 아무 AI나 내릴 때 써요. 학생들에게는 알려 주지 마세요.")
            admin2 = st.text_input("선생님 비밀번호 한 번 더", type="password", max_chars=64)
            ok = st.form_submit_button("저장하고 시작하기", type="primary", use_container_width=True)
        if ok:
            try:
                latest = fresh_settings()
                if admin_configured(latest):
                    raise ValueError("이미 처음 설정을 마쳤어요. 새로고침해 주세요.")
                access_pw = need_pw(access, "학생 입장 비밀번호")
                admin_pw = need_pw(admin, "선생님 비밀번호")
                if admin_pw != str(admin2 or "").strip():
                    raise ValueError("선생님 비밀번호 두 칸이 서로 달라요.")
                if admin_pw == access_pw:
                    raise ValueError("선생님 비밀번호와 입장 비밀번호는 서로 다르게 정해 주세요.")
                new = dict(latest, admin=make_pw(admin_pw), access=make_pw(access_pw), secret=latest.get("secret") or pysecrets.token_hex(32))
                if str(key or "").strip():
                    new["openai_key"] = ai.test_key(key)
                elif not env_key:
                    raise ValueError("OpenAI API 키를 넣어 주세요.")
                save_settings(new)
                st.session_state.entered = access_token(new)
                st.session_state.teacher_fp = admin_fp(new)
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def lock_screen(s, note=None):
    with _center(), st.container(border=True):
        ui.brand()
        st.markdown('<div class="ba-gate-title">입장 비밀번호</div>', unsafe_allow_html=True)
        st.write(note or "선생님께 받은 비밀번호를 넣으면 AI 훈련소와 AI 광장을 쓸 수 있어요.")
        with st.form("lock_form"):
            pw = st.text_input("입장 비밀번호", type="password", label_visibility="collapsed", placeholder="입장 비밀번호")
            ok = st.form_submit_button("들어가기", type="primary", use_container_width=True)
        if ok:
            try:
                throttle_check()
                if not is_access_pw(pw, s):
                    throttle_fail()
                    raise ValueError("비밀번호가 맞지 않아요. 다시 확인해 주세요.")
                st.session_state.entered = access_token(s)
                st.query_params["k"] = access_token(s)
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def gate():
    """모든 화면 앞에서 불러요. 설정이 없으면 '처음 설정', 비밀번호를 모르면 '입장 비밀번호' 화면만 보여요."""
    s = load_settings()
    if not admin_configured(s):
        setup_screen(s)
        st.stop()
    if not access_required(s):
        return s
    token = access_token(s)
    if st.session_state.get("entered") != token:
        q = st.query_params.get("k")
        if q and hmac.compare_digest(str(q), token):
            st.session_state.entered = token
        else:
            changed = bool(st.session_state.get("entered"))
            st.session_state.pop("entered", None)
            lock_screen(s, "비밀번호가 바뀌었어요. 새 비밀번호를 넣어 주세요." if changed else None)
            st.stop()
    if st.query_params.get("k") != token:
        st.query_params["k"] = token
    return s


def admin_fp(s):
    return (s.get("admin") or {}).get("hash") or hashlib.sha256(("adm:" + secret("ADMIN_PASSWORD")).encode()).hexdigest()


def teacher_login(pw, s):
    throttle_check()
    if not is_admin_pw(pw, s):
        throttle_fail()
        raise ValueError("선생님 비밀번호가 맞지 않아요.")
    st.session_state.teacher_fp = admin_fp(s)


def is_teacher(s=None):
    """선생님 비밀번호로 들어온 화면인지 (비밀번호를 바꾸면 다시 들어와야 해요)"""
    fp = st.session_state.get("teacher_fp")
    return bool(fp) and fp == admin_fp(s if s is not None else load_settings())
