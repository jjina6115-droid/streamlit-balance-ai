"""모둠 작업 · 광장의 AI · 댓글을 저장소에서 읽고 쓰는 함수들."""
import hashlib
import secrets as pysecrets
import time
import uuid

from .shared import CRITERIA, LIMITS, compile_rules, label_stats
from .store import get_store


def now():
    return time.time()


# ---------------- 모둠 작업 ----------------
def group_id(name):
    norm = " ".join(str(name).split()).lower()
    return hashlib.sha1(norm.encode()).hexdigest()[:12]


def blank_item(q=""):
    return {"q": q, "answer": None, "summary": "", "labels": [None] * len(CRITERIA)}


def new_round(no, questions=None):
    n = max(LIMITS["min_tests"], len(questions or []))
    qs = list(questions or []) + [""] * n
    return {"no": no, "key": None, "items": [blank_item(qs[i]) for i in range(n)], "created": now()}


def new_group(name, pin_rec):
    return {
        "gid": group_id(name), "name": " ".join(str(name).split())[:LIMITS["author"]], "pin": pin_rec,
        "ai_name": "", "emoji": "🦉", "rules": "", "flow": [], "rounds": [new_round(1)],
        "bot_id": None, "published_key": None, "description": "", "created": now(), "updated": now(),
    }


def load_group(gid):
    return get_store().get("group:" + gid)


def save_group(ws):
    ws["updated"] = now()
    get_store().put("group:" + ws["gid"], ws)


def list_groups():
    return [v for _, v in get_store().items("group:")]


def delete_group(gid):
    get_store().delete("group:" + gid)


def new_step(kind):
    step = {"id": uuid.uuid4().hex[:8], "type": kind, "text": ""}
    if kind == "check":
        step.update(yes="", no="")
    return step


def compiled(ws):
    return compile_rules(ws.get("rules"), ws.get("flow"))


def started(rnd):
    return any(it.get("answer") for it in rnd["items"])


def answered(rnd):
    return [it for it in rnd["items"] if it.get("answer")]


def round_stats(rnd):
    return label_stats(answered(rnd))


def fresh(ws, rnd=None):
    """지금 규칙·순서도로 물어본 최신 차수인지"""
    rnd = rnd or ws["rounds"][-1]
    return started(rnd) and rnd.get("key") == compiled(ws)


# ---------------- 광장의 AI ----------------
def comment_counts():
    counts = {}
    for key in get_store().keys("comment:"):
        parts = key.split(":")
        if len(parts) != 3:
            continue
        c = counts.setdefault(parts[1], {"comments": 0, "improves": 0})
        c["comments"] += 1
        if parts[2].endswith("-i"):
            c["improves"] += 1
    return counts


def list_bots():
    counts = comment_counts()
    bots = []
    for _, b in get_store().items("bot:"):
        c = counts.get(b["id"], {})
        b["comments"] = c.get("comments", 0)
        b["improves"] = c.get("improves", 0)
        bots.append(b)
    return bots


def get_bot(bot_id):
    b = get_store().get("bot:" + bot_id) if bot_id else None
    if b:
        c = comment_counts().get(bot_id, {})
        b["comments"] = c.get("comments", 0)
        b["improves"] = c.get("improves", 0)
    return b


def publish(ws, description):
    """모둠 작업을 광장에 올려요. 이미 올린 AI가 있으면 그 AI를 새 규칙으로 바꿔요."""
    rnd = ws["rounds"][-1]
    st_ = round_stats(rnd)
    store = get_store()
    old = store.get("bot:" + ws["bot_id"]) if ws.get("bot_id") else None
    bot = old or {"id": pysecrets.token_hex(5), "likes": 0, "dislikes": 0, "chats": 0, "created": now()}
    bot.update({
        "gid": ws["gid"], "author": ws["name"], "name": ws["ai_name"].strip()[:LIMITS["name"]],
        "emoji": ws.get("emoji") or "🦉", "description": description.strip()[:LIMITS["description"]],
        "prompt": ws.get("rules", "").strip()[:LIMITS["prompt"]], "flow": [{k: v for k, v in s.items() if k != "id"} for s in ws.get("flow", [])],
        "score": st_["score"], "tests": st_["count"], "round": rnd["no"], "updated": now(),
    })
    store.put("bot:" + bot["id"], bot)
    ws["bot_id"] = bot["id"]
    ws["published_key"] = compiled(ws)
    ws["description"] = description.strip()[:LIMITS["description"]]
    save_group(ws)
    return bot


def delete_bot(bot_id):
    store = get_store()
    store.delete("bot:" + bot_id)
    for key in store.keys(f"comment:{bot_id}:"):
        store.delete(key)


def bump(bot_id, field):
    store = get_store()
    b = store.get("bot:" + bot_id)
    if b:
        b[field] = int(b.get(field) or 0) + 1
        store.put("bot:" + bot_id, b)


# ---------------- 댓글 ----------------
def list_comments(bot_id):
    items = [v for _, v in get_store().items(f"comment:{bot_id}:")]
    return sorted(items, key=lambda c: c.get("created", 0), reverse=True)


def add_comment(bot_id, author, text, improve):
    author = " ".join(str(author or "").split())[:LIMITS["author"]]
    text = str(text or "").strip()[:LIMITS["comment"]]
    if not text:
        raise ValueError("댓글 내용을 적어 주세요.")
    if not author:
        raise ValueError("쓴 사람(이름이나 모둠)을 적어 주세요.")
    cid = f"{int(time.time() * 1000):x}-{pysecrets.token_hex(3)}-{'i' if improve else 'c'}"
    c = {"id": cid, "bot_id": bot_id, "author": author, "text": text, "improve": bool(improve), "created": now()}
    get_store().put(f"comment:{bot_id}:{cid}", c)
    return c


def delete_comment(bot_id, cid):
    get_store().delete(f"comment:{bot_id}:{cid}")
