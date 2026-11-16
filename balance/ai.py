"""AI 부르기 — 키는 서버(선생님 설정 또는 Streamlit Secrets)에만 있고 학생 화면으로 보내지 않아요.

키 모양으로 어디에 물을지 정해요.
  sk-…            → OpenAI (수업용)
  AQ.… / AIza…    → 구글 Gemini (선생님 혼자 시험해 볼 때만. 18세 미만이 쓰는 앱에는 쓰면 안 돼요)
"""
import re

import requests

from .env import secret
from .shared import PLATFORM_RULES

OPENAI_BASE = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-5.6-luna"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_DEFAULT_MODEL = "gemini-3.8-flash"
GEMINI_FALLBACK_MODEL = "gemini-flash-latest"

OPENAI_KEY_RE = re.compile(r"sk-[A-Za-z0-9_\-]{20,}")
GEMINI_KEY_RE = re.compile(r"(AQ\.[A-Za-z0-9_\-.]{20,}|AIza[A-Za-z0-9_\-]{20,})")


class AIError(Exception):
    pass


def provider_of(key):
    key = (key or "").strip()
    if key.startswith("AQ.") or key.startswith("AIza"):
        return "gemini"
    return "openai"


def _is_gemini_model(name):
    return str(name or "").strip().lower().removeprefix("models/").startswith(("gemini", "gemma"))


def connection(settings):
    """지금 쓸 키·주소·모델. 웹사이트(선생님 설정)에서 넣은 키가 먼저, 없으면 Secrets의 OPENAI_API_KEY."""
    key, source = "", None
    if settings.get("openai_key"):
        key, source = settings["openai_key"], "site"
    elif secret("OPENAI_API_KEY"):
        key, source = secret("OPENAI_API_KEY").strip(), "secrets"
    provider = provider_of(key)
    want_model = secret("OPENAI_MODEL")
    if provider == "gemini":
        base = secret("GEMINI_BASE_URL", GEMINI_BASE)
        model = want_model if _is_gemini_model(want_model) else secret("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
    else:
        base = secret("OPENAI_BASE_URL", OPENAI_BASE)
        if "googleapis.com" in base:  # 시험용 Gemini 주소가 남아 있어도 OpenAI 키는 OpenAI로 보내요
            base = OPENAI_BASE
        model = want_model if want_model and not _is_gemini_model(want_model) else OPENAI_DEFAULT_MODEL
    return {
        "key": key,
        "source": source,
        "provider": provider,
        "base": base.rstrip("/"),
        "model": model.strip().removeprefix("models/"),
    }


def key_label(conn):
    """선생님 화면에 보여 줄 키 이름 (키 전체는 보여 주지 않아요)."""
    if not conn.get("key"):
        return ""
    name = "Gemini 시험용 키" if conn.get("provider") == "gemini" else "OpenAI 키"
    head = "AQ." if conn["key"].startswith("AQ.") else conn["key"][:4] if conn.get("provider") == "gemini" else "sk-"
    return f"{name} ({head}…{conn['key'][-4:]})"


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
        raise AIError("AI API 키가 아직 없어요. 선생님이 '선생님' 메뉴에서 키를 넣어 주세요.")
    if conn.get("provider") == "gemini":
        return _gemini_complete(conn, messages)
    return _openai_complete(conn, messages)


def _openai_complete(conn, messages):
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


def _gemini_body(messages):
    """OpenAI 모양 메시지 → Gemini 모양 (system은 systemInstruction으로, assistant는 model로)."""
    system = "\n\n".join(m["content"] for m in messages if m.get("role") == "system" and m.get("content"))
    contents = []
    for m in messages:
        role = {"user": "user", "assistant": "model"}.get(m.get("role"))
        if not role or not m.get("content"):
            continue
        if contents and contents[-1]["role"] == role:  # 같은 쪽 말이 이어지면 한 덩어리로
            contents[-1]["parts"][0]["text"] += "\n\n" + m["content"]
        else:
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
    body = {"contents": contents}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


def _gemini_complete(conn, messages):
    body = _gemini_body(messages)
    models = [conn["model"]]
    if conn["model"] != GEMINI_FALLBACK_MODEL:
        models.append(GEMINI_FALLBACK_MODEL)  # 모델 이름이 바뀌었으면 최신 Flash로 한 번 더 시도해요
    for i, model in enumerate(models):
        try:
            r = requests.post(f"{conn['base']}/models/{model}:generateContent",
                              headers={"x-goog-api-key": conn["key"], "Content-Type": "application/json"},
                              json=body, timeout=90)
        except requests.RequestException:
            raise AIError("Gemini에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.")
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code == 404 and i + 1 < len(models):
            continue
        if r.status_code >= 400:
            err = data.get("error") or {}
            msg = err.get("message") or f"HTTP {r.status_code}"
            if r.status_code in (401, 403) or (r.status_code == 400 and "key" in msg.lower()):
                raise AIError("Gemini 키가 올바르지 않아요. 선생님 메뉴에서 키를 다시 넣어 주세요. (" + msg[:120] + ")")
            if r.status_code == 429:
                raise AIError("Gemini 무료 사용 한도에 걸렸어요. 1분쯤 기다렸다가 다시 해 주세요.")
            if r.status_code == 404:
                raise AIError(f'모델 "{conn["model"]}"을(를) 쓸 수 없어요. Secrets의 OPENAI_MODEL을 확인해 주세요.')
            raise AIError("Gemini 오류: " + msg[:200])
        cands = data.get("candidates") or []
        parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict) and not p.get("thought")).strip()
        if not text:
            blocked = (data.get("promptFeedback") or {}).get("blockReason") or (cands and cands[0].get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"))
            if blocked:
                raise AIError("AI가 이 질문에는 답하지 않았어요(안전 필터). 질문을 조금 바꿔서 다시 해 보세요.")
            raise AIError("AI가 빈 답을 보냈어요. 다시 해 주세요.")
        return text
    raise AIError("Gemini에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.")


def test_key(key):
    """키가 맞는지 한 번 물어봐요. (틀린 키만 막고, 잠깐 연결이 안 되는 건 넘어가요)"""
    key = (key or "").strip()
    if GEMINI_KEY_RE.fullmatch(key):
        base = secret("GEMINI_BASE_URL", GEMINI_BASE).rstrip("/")
        try:
            r = requests.get(base + "/models", headers={"x-goog-api-key": key}, timeout=15)
            if r.status_code in (400, 401, 403):
                raise ValueError("구글이 이 Gemini 키를 받아 주지 않았어요. AI Studio에서 키를 다시 복사해서 넣어 주세요.")
        except requests.RequestException:
            pass
        return key
    if not OPENAI_KEY_RE.fullmatch(key):
        raise ValueError("API 키는 sk-로 시작하는 OpenAI 키예요. (시험용 Gemini 키는 AQ. 또는 AIza로 시작해요) 빈칸 없이 그대로 붙여 넣어 주세요.")
    base = secret("OPENAI_BASE_URL", OPENAI_BASE).rstrip("/")
    if "googleapis.com" in base:
        base = OPENAI_BASE
    try:
        r = requests.get(base + "/models", headers={"Authorization": "Bearer " + key}, timeout=15)
        if r.status_code == 401:
            raise ValueError("OpenAI가 이 키를 받아 주지 않았어요. 키를 다시 복사해서 넣어 주세요.")
    except requests.RequestException:
        pass
    return key
