"""저장소 — 모둠 작업, 광장의 AI, 댓글, 선생님 설정을 모두 여기에 저장해요.

- Streamlit Secrets에 SUPABASE_URL, SUPABASE_KEY가 있으면 Supabase(무료 온라인 DB)에 저장해요.
  앱이 다시 시작돼도 지워지지 않아요. (Streamlit Cloud에서는 이걸 추천해요)
- 없으면 앱 폴더의 balance_data.db 파일(SQLite)에 저장해요.
  내 컴퓨터에서 실행할 때는 이걸로 충분해요. Streamlit Cloud에서는 앱이 다시 시작되면 지워질 수 있어요.

모든 데이터는 '이름표(key) → 내용(JSON)' 한 줄씩이에요.
  settings              선생님 설정 (OpenAI 키, 비밀번호 해시)
  group:<모둠ID>         모둠 작업 (규칙, 순서도, 평가 기록)
  bot:<AI ID>            광장에 올린 AI
  comment:<AI ID>:<댓글ID> 댓글 하나 (댓글ID 끝이 -i면 '개선' 댓글)
"""
import json
import os
import sqlite3
import threading
import time
from urllib.parse import quote

import requests
import streamlit as st

from .env import secret


class StoreError(Exception):
    pass


class SQLiteStore:
    kind = "file"
    label = "이 컴퓨터의 파일 (balance_data.db)"

    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        with self.lock:
            con = self._con()
            con.execute("create table if not exists kv (key text primary key, value text not null, updated real not null)")
            con.commit()
            con.close()

    def _con(self):
        return sqlite3.connect(self.path, timeout=15)

    def _run(self, sql, args=(), fetch=False):
        with self.lock:
            con = self._con()
            try:
                cur = con.execute(sql, args)
                rows = cur.fetchall() if fetch else None
                con.commit()
                return rows
            finally:
                con.close()

    def get(self, key):
        rows = self._run("select value from kv where key = ?", (key,), fetch=True)
        return json.loads(rows[0][0]) if rows else None

    def put(self, key, value):
        self._run("insert or replace into kv (key, value, updated) values (?, ?, ?)",
                  (key, json.dumps(value, ensure_ascii=False), time.time()))

    def delete(self, key):
        self._run("delete from kv where key = ?", (key,))

    def items(self, prefix):
        rows = self._run("select key, value from kv where key >= ? and key < ? order by key",
                         (prefix, prefix + "￿"), fetch=True)
        return [(k, json.loads(v)) for k, v in rows]

    def keys(self, prefix):
        rows = self._run("select key from kv where key >= ? and key < ? order by key",
                         (prefix, prefix + "￿"), fetch=True)
        return [r[0] for r in rows]


class SupabaseStore:
    """Supabase의 표 하나(balance_kv)를 이름표 → 내용 저장소로 써요. (README의 SQL로 표를 만들어요)"""
    kind = "supabase"
    label = "Supabase (온라인 저장소)"

    def __init__(self, url, key, table="balance_kv"):
        self.base = url.rstrip("/") + "/rest/v1/" + table
        self.headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):  # 예전 방식 키(service_role, JWT)는 Authorization에도 넣어요. 새 방식(sb_secret_…)은 apikey만.
            self.headers["Authorization"] = "Bearer " + key

    def _req(self, method, query="", body=None, extra=None):
        headers = dict(self.headers, **(extra or {}))
        try:
            r = requests.request(method, self.base + query, headers=headers,
                                 data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None, timeout=20)
        except requests.RequestException:
            raise StoreError("저장소(Supabase)에 연결하지 못했어요. 잠시 뒤 다시 해 주세요.")
        if r.status_code >= 400:
            raise StoreError(f"저장소(Supabase) 오류가 났어요 ({r.status_code}). SUPABASE_URL, SUPABASE_KEY와 표 이름을 확인해 주세요.")
        return r.json() if r.content else None

    def get(self, key):
        rows = self._req("GET", "?select=value&key=eq." + quote(key, safe=""))
        return rows[0]["value"] if rows else None

    def put(self, key, value):
        self._req("POST", "", {"key": key, "value": value, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                  {"Prefer": "resolution=merge-duplicates,return=minimal"})

    def delete(self, key):
        self._req("DELETE", "?key=eq." + quote(key, safe=""), extra={"Prefer": "return=minimal"})

    def items(self, prefix):
        rows = self._req("GET", "?select=key,value&order=key&key=like." + quote(prefix, safe="") + "*")
        return [(r["key"], r["value"]) for r in rows or []]

    def keys(self, prefix):
        rows = self._req("GET", "?select=key&order=key&key=like." + quote(prefix, safe="") + "*")
        return [r["key"] for r in rows or []]


@st.cache_resource(show_spinner=False)
def _make_store(url, key, path):
    if url and key:
        return SupabaseStore(url, key)
    return SQLiteStore(path)


def get_store():
    default_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "balance_data.db")
    return _make_store(secret("SUPABASE_URL"), secret("SUPABASE_KEY"), secret("BALANCE_DB", default_path))
