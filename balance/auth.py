"""비밀번호 — 처음 설정, 반 입장 비밀번호, 선생님 비밀번호, 모둠 비밀번호.

반마다 입장 비밀번호가 따로 있어요. 학생이 입장 비밀번호를 넣으면 그 비밀번호의 반으로 들어가서,
자기 반 모둠과 자기 반 광장만 봐요. 선생님 비밀번호로 들어오면 선생님 메뉴에서 반을 골라 볼 수 있어요.

비밀번호는 그대로 저장하지 않고, 풀 수 없게 바꾼 값(해시)만 저장해요.
Streamlit Secrets에 ADMIN_PASSWORD, OPENAI_API_KEY를 넣어 두면 '처음 설정' 화면 없이 바로 써요.
(ACCESS_PASSWORD를 넣어 두면 처음 한 번 그 비밀번호로 '우리 반'을 만들어 줘요)
"""
import hashlib
import hmac
import secrets as pysecrets
import time

import streamlit as st

from . import ai, data, ui
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


def is_admin_pw(pw, s):
    pw = str(pw or "").strip()
    env = secret("ADMIN_PASSWORD")
    if env and pw and hmac.compare_digest(pw, env):
        return True
    return check_pw(pw, s.get("admin"))


def _token_key(s):
    return s.get("secret") or hashlib.sha256(("balance:" + secret("ADMIN_PASSWORD")).encode()).hexdigest()


# ---------------- 반 ----------------
CLASS_NAME_MAX = 20


def classes(s):
    return [c for c in (s.get("classes") or []) if c.get("id")]


def find_class(s, cid):
    return next((c for c in classes(s) if c["id"] == cid), None)


def class_token(s, c):
    """한 번 들어온 기기는 주소에 붙은 표(k)로 새로고침해도 다시 묻지 않아요. 반 비밀번호를 바꾸면 표도 바뀌어요."""
    rec = (c.get("access") or {}).get("hash") or "none"
    sig = hmac.new(_token_key(s).encode(), f"cls:{c['id']}:{rec}".encode(), "sha256").hexdigest()[:20]
    return f"{c['id']}.{sig}"


def class_of_token(s, tok):
    tok = str(tok or "")
    if "." not in tok:
        return None
    c = find_class(s, tok.split(".", 1)[0])
    return c if c and hmac.compare_digest(class_token(s, c), tok) else None


def class_by_pw(s, pw):
    pw = str(pw or "").strip()
    return next((c for c in classes(s) if check_pw(pw, c.get("access"))), None) if pw else None


def need_class_name(name):
    name = " ".join(str(name or "").split())
    if not name:
        raise ValueError("반 이름을 적어 주세요. (예: 2학년 3반)")
    return name[:CLASS_NAME_MAX]


def check_class_pw(s, pw, skip_cid=None):
    """반 입장 비밀번호는 반마다, 그리고 선생님 비밀번호와 달라야 해요 (비밀번호로 반을 찾아서)."""
    pw = need_pw(pw, "반 입장 비밀번호")
    if is_admin_pw(pw, s):
        raise ValueError("선생님 비밀번호와 다른 비밀번호로 정해 주세요.")
    for c in classes(s):
        if c["id"] != skip_cid and check_pw(pw, c.get("access")):
            raise ValueError(f"‘{c['name']}’과(와) 같은 비밀번호예요. 반마다 다른 비밀번호로 정해 주세요.")
    return pw


def new_class(name, pw):
    return {"id": pysecrets.token_hex(4), "name": name, "access": make_pw(pw), "created": time.time()}


def enter_class(s, c):
    """이 화면(기기)을 c 반으로 들여보내요. 반이 바뀌면 들어가 있던 모둠에서는 나와요."""
    prev = st.session_state.get("cls")
    if prev and prev != c["id"]:
        for k in ("gid", "gpin", "open_cmt"):
            st.session_state.pop(k, None)
        if "bot" in st.query_params:
            del st.query_params["bot"]
    st.session_state.cls = c["id"]
    st.session_state.entered = class_token(s, c)
    st.query_params["k"] = st.session_state.entered


def current_class(s=None):
    s = s if s is not None else load_settings()
    return find_class(s, st.session_state.get("cls"))


def migrate(s):
    """반 기능 전에 쓰던 데이터가 있으면 '우리 반'으로 옮겨요. (한 번만)"""
    if "classes" in s:
        return s
    latest = fresh_settings()
    if "classes" in latest:
        return latest
    rec = latest.get("access") or (make_pw(secret("ACCESS_PASSWORD")) if secret("ACCESS_PASSWORD") else None)
    store = get_store()
    made = []
    if rec or store.keys("group:") or store.keys("bot:"):
        c = {"id": pysecrets.token_hex(4), "name": "우리 반", "access": rec, "created": time.time()}
        data.migrate_legacy(c["id"])
        made.append(c)
    latest["classes"] = made
    latest.pop("access", None)
    latest.setdefault("secret", pysecrets.token_hex(32))
    save_settings(latest)
    return latest


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
            key = st.text_input("AI API 키", type="password", placeholder="OpenAI 키 sk-...  (선생님 시험용 Gemini 키 AQ.… 도 돼요)",
                                autocomplete="off",
                                help="비워 두면 Streamlit Secrets에 넣어 둔 키를 써요." if env_key else None)
            st.caption("비워 두면 Secrets에 넣어 둔 키를 써요." if env_key else "키는 서버 저장소에만 저장되고, 학생들 화면에는 보이지 않아요.")
            st.markdown("**첫 번째 반**")
            cname = st.text_input("반 이름", max_chars=CLASS_NAME_MAX, placeholder="예: 2학년 3반")
            access = st.text_input("반 입장 비밀번호", max_chars=64)
            st.caption("이 반 학생들에게 알려 줄 비밀번호예요. 반마다 비밀번호가 달라서, 학생들은 자기 반 모둠과 광장만 봐요. 다른 반은 나중에 선생님 메뉴에서 만들어요.")
            st.markdown("**선생님**")
            admin = st.text_input("선생님 비밀번호", type="password", max_chars=64)
            st.caption("키와 비밀번호를 바꿀 때, 광장에서 아무 AI나 내릴 때 써요. 학생들에게는 알려 주지 마세요.")
            admin2 = st.text_input("선생님 비밀번호 한 번 더", type="password", max_chars=64)
            ok = st.form_submit_button("저장하고 시작하기", type="primary", use_container_width=True)
        if ok:
            try:
                latest = fresh_settings()
                if admin_configured(latest):
                    raise ValueError("이미 처음 설정을 마쳤어요. 새로고침해 주세요.")
                class_name = need_class_name(cname)
                access_pw = need_pw(access, "반 입장 비밀번호")
                admin_pw = need_pw(admin, "선생님 비밀번호")
                if admin_pw != str(admin2 or "").strip():
                    raise ValueError("선생님 비밀번호 두 칸이 서로 달라요.")
                if admin_pw == access_pw:
                    raise ValueError("선생님 비밀번호와 반 입장 비밀번호는 서로 다르게 정해 주세요.")
                first = new_class(class_name, access_pw)
                new = dict(latest, admin=make_pw(admin_pw), classes=[first], secret=latest.get("secret") or pysecrets.token_hex(32))
                new.pop("access", None)
                if str(key or "").strip():
                    new["openai_key"] = ai.test_key(key)
                elif not env_key:
                    raise ValueError("AI API 키를 넣어 주세요. (OpenAI 키 sk-…, 선생님 혼자 시험할 때는 Gemini 키 AQ.…)")
                save_settings(new)
                enter_class(new, first)
                st.session_state.teacher_fp = admin_fp(new)
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def lock_screen(s, note=None):
    with _center(), st.container(border=True):
        ui.brand()
        st.markdown('<div class="ba-gate-title">입장 비밀번호</div>', unsafe_allow_html=True)
        st.write(note or "선생님께 받은 우리 반 입장 비밀번호를 넣으면 AI 훈련소와 AI 광장을 쓸 수 있어요.")
        with st.form("lock_form"):
            pw = st.text_input("입장 비밀번호", type="password", label_visibility="collapsed", placeholder="입장 비밀번호")
            ok = st.form_submit_button("들어가기", type="primary", use_container_width=True)
        st.caption("선생님은 선생님 비밀번호를 넣어도 들어올 수 있어요.")
        if ok:
            try:
                throttle_check()
                c = class_by_pw(s, pw)
                if c:
                    enter_class(s, c)
                elif is_admin_pw(pw, s):
                    st.session_state.teacher_fp = admin_fp(s)
                    if classes(s):
                        enter_class(s, classes(s)[0])
                else:
                    throttle_fail()
                    raise ValueError("비밀번호가 맞지 않아요. 다시 확인해 주세요.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))


def gate():
    """모든 화면 앞에서 불러요. 설정이 없으면 '처음 설정', 비밀번호를 모르면 '입장 비밀번호' 화면만 보여요."""
    s = load_settings()
    if not admin_configured(s):
        setup_screen(s)
        st.stop()
    s = migrate(s)
    c = class_of_token(s, st.session_state.get("entered"))
    if not c:
        c = class_of_token(s, st.query_params.get("k"))
        if c:
            enter_class(s, c)
    if c:
        st.session_state.cls = c["id"]
        if st.query_params.get("k") != st.session_state.entered:
            st.query_params["k"] = st.session_state.entered
        return s
    if is_teacher(s):  # 선생님은 반을 아직 안 골랐어도 들어와요 (선생님 메뉴에서 반 만들기·고르기)
        st.session_state.pop("cls", None)
        return s
    changed = bool(st.session_state.get("entered"))
    for k in ("entered", "cls", "gid", "gpin"):
        st.session_state.pop(k, None)
    lock_screen(s, "반 비밀번호가 바뀌었거나 반이 없어졌어요. 선생님께 받은 비밀번호를 다시 넣어 주세요." if changed else None)
    st.stop()


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
