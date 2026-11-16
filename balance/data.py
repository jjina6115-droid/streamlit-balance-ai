"""모둠 작업 · 광장의 AI · 댓글을 저장소에서 읽고 쓰는 함수들.

반마다 따로 저장해요. 이름표(key) 앞에 반 ID가 붙어요.
  g:<반ID>:<모둠ID>            모둠 작업
  b:<반ID>:<AI ID>             광장에 올린 AI
  c:<반ID>:<AI ID>:<댓글ID>     댓글 (댓글ID 끝이 -i면 '개선' 댓글)
지금 어느 반인지는 화면(세션)의 st.session_state["cls"]로 알아요. 선생님 메뉴처럼 다른 반을 다룰 때는 cid를 직접 넘겨요.
"""
import hashlib
import secrets as pysecrets
import time
import uuid

import streamlit as st

from .shared import CN, CRITERIA, LIMITS, compile_rules, label_stats
from .store import get_store


def now():
    return time.time()


def cur_cls():
    return st.session_state.get("cls") or "_"


def _g(cid=None):
    return f"g:{cid or cur_cls()}:"


def _b(cid=None):
    return f"b:{cid or cur_cls()}:"


def _c(bot_id="", cid=None):
    return f"c:{cid or cur_cls()}:" + (f"{bot_id}:" if bot_id else "")


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


def load_group(gid, cid=None):
    return get_store().get(_g(cid) + gid)


def save_group(ws, cid=None):
    ws["updated"] = now()
    get_store().put(_g(cid) + ws["gid"], ws)


def list_groups(cid=None):
    return [v for _, v in get_store().items(_g(cid))]


def delete_group(gid, cid=None):
    get_store().delete(_g(cid) + gid)


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
def comment_counts(cid=None):
    counts = {}
    for key in get_store().keys(_c(cid=cid)):
        parts = key.split(":")
        if len(parts) != 4:
            continue
        c = counts.setdefault(parts[2], {"comments": 0, "improves": 0})
        c["comments"] += 1
        if parts[3].endswith("-i"):
            c["improves"] += 1
    return counts


def list_bots(cid=None):
    counts = comment_counts(cid)
    bots = []
    for _, b in get_store().items(_b(cid)):
        c = counts.get(b["id"], {})
        b["comments"] = c.get("comments", 0)
        b["improves"] = c.get("improves", 0)
        bots.append(b)
    return bots


def get_bot(bot_id):
    b = get_store().get(_b() + bot_id) if bot_id else None
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
    old = store.get(_b() + ws["bot_id"]) if ws.get("bot_id") else None
    bot = old or {"id": pysecrets.token_hex(5), "likes": 0, "dislikes": 0, "chats": 0, "created": now()}
    bot.update({
        "gid": ws["gid"], "author": ws["name"], "name": ws["ai_name"].strip()[:LIMITS["name"]],
        "emoji": ws.get("emoji") or "🦉", "description": description.strip()[:LIMITS["description"]],
        "prompt": ws.get("rules", "").strip()[:LIMITS["prompt"]], "flow": [{k: v for k, v in s.items() if k != "id"} for s in ws.get("flow", [])],
        "score": st_["score"], "tests": st_["count"], "round": rnd["no"], "updated": now(),
    })
    store.put(_b() + bot["id"], bot)
    ws["bot_id"] = bot["id"]
    ws["published_key"] = compiled(ws)
    ws["description"] = description.strip()[:LIMITS["description"]]
    save_group(ws)
    return bot


def delete_bot(bot_id):
    store = get_store()
    store.delete(_b() + bot_id)
    for key in store.keys(_c(bot_id)):
        store.delete(key)


def bump(bot_id, field):
    store = get_store()
    b = store.get(_b() + bot_id)
    if b:
        b[field] = int(b.get(field) or 0) + 1
        store.put(_b() + bot_id, b)


# ---------------- 댓글 ----------------
def list_comments(bot_id):
    items = [v for _, v in get_store().items(_c(bot_id))]
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
    get_store().put(_c(bot_id) + cid, c)
    return c


def delete_comment(bot_id, cid):
    get_store().delete(_c(bot_id) + cid)


# ---------------- 반 전체 ----------------
def class_counts(cid):
    store = get_store()
    return {"groups": len(store.keys(_g(cid))), "bots": len(store.keys(_b(cid)))}


def delete_class_data(cid):
    """그 반의 모둠 작업·광장 AI·댓글을 모두 지워요."""
    store = get_store()
    for prefix in (_g(cid), _b(cid), _c(cid=cid)):
        for key in store.keys(prefix):
            store.delete(key)


def class_csv_bytes(cid):
    """반 전체 결과 CSV: 첫 줄은 제목, 그다음 모둠마다 한 줄 — 모둠명, 기준 5가지의 지킨 개수(1의 개수), 차수.
    모둠마다 기록이 있는 가장 최근 차수를 써요."""
    def cell(v):
        t = str(v)
        return '"' + t.replace('"', '""') + '"' if any(ch in t for ch in ',"\r\n') else t
    lines = ["모둠명," + ",".join(f"{CN[i]} {c['name']}" for i, c in enumerate(CRITERIA)) + ",차수"]
    for ws in sorted(list_groups(cid), key=lambda g: g.get("name", "")):
        pick = None
        for rnd in reversed(ws.get("rounds") or []):
            if round_stats(rnd)["count"]:
                pick = rnd
                break
        sums = round_stats(pick)["sums"] if pick else [0] * len(CRITERIA)
        lines.append(",".join([cell(ws.get("name", ""))] + [str(n) for n in sums] + [f"{pick['no']}차" if pick else "기록 없음"]))
    return ("\ufeff" + "\r\n".join(lines) + "\r\n").encode("utf-8")


def migrate_legacy(cid):
    """반 기능 전에 저장된 데이터(group:, bot:, comment:)를 cid 반으로 옮겨요. 옮긴 개수를 돌려줘요."""
    store = get_store()
    moved = 0
    for key, v in store.items("group:"):
        store.put(_g(cid) + key[len("group:"):], v)
        store.delete(key)
        moved += 1
    for key, v in store.items("bot:"):
        store.put(_b(cid) + key[len("bot:"):], v)
        store.delete(key)
        moved += 1
    for key, v in store.items("comment:"):
        rest = key[len("comment:"):]
        if rest.count(":") == 1:
            store.put(_c(cid=cid) + rest, v)
        store.delete(key)
        moved += 1
    return moved
