"""OpenAI 부르기 — 키는 서버(선생님 설정 또는 Streamlit Secrets)에만 있고 학생 화면으로 보내지 않아요."""
import requests

from .env import secret
from .shared import PLATFORM_RULES


class AIError(Exception):
    pass


def connection(settings):
    """지금 쓸 키·주소·모델. 웹사이트(선생님 설정)에서 넣은 키가 먼저, 없으면 Secrets의 OPENAI_API_KEY."""
    key, source = "", None
    if settings.get("openai_key"):
        key, source = settings["openai_key"], "site"
    elif secret("OPENAI_API_KEY"):
        key, source = secret("OPENAI_API_KEY"), "secrets"
    return {
        "key": key,
        "source": source,
        "base": secret("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "model": secret("OPENAI_MODEL", "gpt-5.6-luna"),
    }


def bot_messages(compiled, history, question):
    msgs = [{"role": "system", "content": PLATFORM_RULES},
            {"role": "system", "content": "[모둠이 쓴 규칙]\n" + compiled}]
    for h in (history or [])[-10:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": h["content"][:3000]})
    msgs.append({"role": "user", "content": question})
    return msgs


def complete(conn, messages):
    """conn은 connection()이 준 값이에요. (여러 질문을 동시에 물을 때도 쓸 수 있게 미리 받아 둬요)"""
    if not conn["key"]:
        raise AIError("OpenAI API 키가 아직 없어요. 선생님이 '선생님' 메뉴에서 키를 넣어 주세요.")
    try:
        r = requests.post(conn["base"] + "/chat/completions",
                          headers={"Authorization": "Bearer " + conn["key"], "Content-Type": "application/json"},
                          json={"model": conn["model"], "messages": messages}, timeout=90)
    except requests.RequestException:
        raise AIError("OpenAI에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.")
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        msg = (data.get("error") or {}).get("message") or f"HTTP {r.status_code}"
        if r.status_code == 401:
            raise AIError("OpenAI API 키가 올바르지 않아요. 선생님 메뉴에서 키를 다시 넣어 주세요.")
        if r.status_code == 429:
            raise AIError("OpenAI 사용 한도에 걸렸어요. 잠시 뒤 다시 하거나 결제 한도를 확인해 주세요.")
        if r.status_code == 404:
            raise AIError(f'모델 "{conn["model"]}"을(를) 쓸 수 없어요. Secrets의 OPENAI_MODEL을 확인해 주세요.')
        raise AIError("OpenAI 오류: " + msg)
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        text = ""
    if not text:
        raise AIError("AI가 빈 답을 보냈어요. 다시 해 주세요.")
    return text


def test_key(key):
    """키가 맞는지 OpenAI에 한 번 물어봐요. (틀린 키만 막고, 잠깐 연결이 안 되는 건 넘어가요)"""
    key = (key or "").strip()
    import re
    if not re.fullmatch(r"sk-[A-Za-z0-9_\-]{20,}", key):
        raise ValueError("OpenAI API 키는 sk-로 시작하는 긴 글자예요. 빈칸 없이 그대로 붙여 넣어 주세요.")
    base = secret("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    try:
        r = requests.get(base + "/models", headers={"Authorization": "Bearer " + key}, timeout=15)
        if r.status_code == 401:
            raise ValueError("OpenAI가 이 키를 받아 주지 않았어요. 키를 다시 복사해서 넣어 주세요.")
    except requests.RequestException:
        pass
    return key
