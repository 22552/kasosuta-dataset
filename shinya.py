import html
import os
import re
import sqlite3
import subprocess
import urllib.parse

import requests
import streamlit as st

DB_ZST_URL = "https://raw.githubusercontent.com/22552/kasotest/main/%E7%AC%AC%E4%BA%8C%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88.sqlite.zst"
DB_FILE = "comments.db"
ZST_FILE = "comments.sqlite.zst"
PAGE_SIZE = 200


# =========================
# DB準備
# =========================
def _valid_sqlite(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < 4096:
        return False
    con = None
    try:
        con = sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)
        con.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
        return True
    except sqlite3.Error:
        return False
    finally:
        if con is not None:
            con.close()


@st.cache_resource(show_spinner="最新コメントDBを準備しています…")
def ensure_db() -> str:
    if not _valid_sqlite(DB_FILE):
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)

        # 最新の maximally-compressed SQLite を取得
        if not os.path.exists(ZST_FILE) or os.path.getsize(ZST_FILE) < 90 * 1024 * 1024:
            zst_tmp = ZST_FILE + ".tmp"
            if os.path.exists(zst_tmp):
                os.remove(zst_tmp)

            with requests.get(DB_ZST_URL, stream=True, timeout=(15, 300)) as r:
                r.raise_for_status()
                with open(zst_tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                        if chunk:
                            f.write(chunk)
            os.replace(zst_tmp, ZST_FILE)

        db_tmp = DB_FILE + ".tmp"
        if os.path.exists(db_tmp):
            os.remove(db_tmp)

        try:
            # DBは zstd --ultra -22 --long=31 で圧縮されているため、
            # 展開側でも --long=31 を明示する。
            subprocess.run(
                ["zstd", "-d", "--long=31", "-f", ZST_FILE, "-o", db_tmp],
                check=True,
            )
            if not _valid_sqlite(db_tmp):
                raise RuntimeError("展開したSQLite DBが壊れています")
            os.replace(db_tmp, DB_FILE)
        except Exception:
            if os.path.exists(db_tmp):
                os.remove(db_tmp)
            raise

    # 親コメント→返信の並び替えを高速化。
    # 最新DBには検索用index/FTS5が既に入っているので、追加は表示順用だけ。
    con = None
    try:
        con = sqlite3.connect(DB_FILE)
        con.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_comments_thread_datetime
            ON comments(COALESCE(parent_id, id) DESC, datetime ASC)
            """
        )
        con.execute("PRAGMA optimize")
        con.commit()
    except sqlite3.Error:
        pass
    finally:
        if con is not None:
            con.close()

    return os.path.abspath(DB_FILE)


DB_PATH = ensure_db()


# =========================
# SQLite接続
# =========================
def open_db() -> sqlite3.Connection:
    uri = f"file:{DB_PATH}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True, timeout=10)
    con.execute("PRAGMA query_only=ON")
    con.execute("PRAGMA temp_store=MEMORY")
    con.execute("PRAGMA cache_size=-65536")
    try:
        con.execute("PRAGMA mmap_size=268435456")
    except sqlite3.Error:
        pass
    return con


# =========================
# 検索SQL生成
# =========================
def _variants(value: str) -> list[str]:
    """通常 / HTML escape / URL encode を重複なしで返す。"""
    values = [value, html.escape(value), urllib.parse.quote(value)]
    return list(dict.fromkeys(values))


def build_where(user_q: str, text_q: str) -> tuple[str, list[str]]:
    clauses: list[str] = []
    params: list[str] = []

    user_q = (user_q or "").strip()
    text_q = (text_q or "").strip()

    if user_q:
        clauses.append("user LIKE ?")
        params.append(f"%{user_q}%")

    if text_q:
        for word in re.split(r"\s+", text_q):
            if not word:
                continue

            is_exclude = word.startswith("-") and len(word) > 1
            search_word = word[1:] if is_exclude else word

            if "|" in search_word and not is_exclude:
                groups = []
                for part in (p for p in search_word.split("|") if p):
                    variants = _variants(part)
                    groups.append("(" + " OR ".join("content LIKE ?" for _ in variants) + ")")
                    params.extend(f"%{v}%" for v in variants)
                if groups:
                    clauses.append("(" + " OR ".join(groups) + ")")
                continue

            variants = _variants(search_word)
            if is_exclude:
                clauses.append("(" + " AND ".join("content NOT LIKE ?" for _ in variants) + ")")
            else:
                clauses.append("(" + " OR ".join("content LIKE ?" for _ in variants) + ")")
            params.extend(f"%{v}%" for v in variants)

    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params


@st.cache_data(show_spinner=False, max_entries=128)
def count_matches(user_q: str, text_q: str) -> int:
    where, params = build_where(user_q, text_q)
    con = open_db()
    try:
        row = con.execute("SELECT COUNT(*) FROM comments" + where, params).fetchone()
        return int(row[0])
    finally:
        con.close()


@st.cache_data(show_spinner=False, max_entries=512)
def fetch_page(user_q: str, text_q: str, page: int):
    page = max(1, int(page))
    offset = (page - 1) * PAGE_SIZE
    where, params = build_where(user_q, text_q)

    sql = (
        "SELECT id,user,datetime,content,is_reply,parent_id "
        "FROM comments"
        + where
        + " ORDER BY COALESCE(parent_id, id) DESC, datetime ASC LIMIT ? OFFSET ?"
    )

    con = open_db()
    try:
        return con.execute(sql, [*params, PAGE_SIZE, offset]).fetchall()
    finally:
        con.close()


def set_result_page(page: int) -> None:
    st.session_state["result_page"] = int(page)


# =========================
# UI
# =========================
st.title("Scratch コメント高度検索")
st.write("八戸市にいこう!")
st.caption("最新版データセットをDB全体から検索。表示だけ1ページ200件です。")

with st.expander("🔍 検索の使いかた", expanded=False):
    st.markdown(
        """
- **AND検索**: スペース区切り（例: `scratch 猫`）
- **除外検索**: `-単語`（例: `scratch -宣伝`）
- **OR検索**: `|` 区切り（例: `バグ|不具合`）
- **記号・絵文字**: 通常 / HTMLエスケープ / URLエンコードを自動で検索
        """
    )

with st.form("search_form"):
    user_q = st.text_input("ユーザー名")
    text_q = st.text_input("検索（内容）", placeholder="例: りんご バナナ -スイカ")
    submitted = st.form_submit_button("検索", type="primary")

if submitted:
    clean_user = user_q.strip()
    clean_text = text_q.strip()
    with st.spinner("全体から検索しています…"):
        total = count_matches(clean_user, clean_text)

    st.session_state["search_user"] = clean_user
    st.session_state["search_text"] = clean_text
    st.session_state["search_total"] = total
    st.session_state["result_page"] = 1


# =========================
# ページ表示
# =========================
if "search_total" in st.session_state:
    total = int(st.session_state["search_total"])
    search_user = st.session_state.get("search_user", "")
    search_text = st.session_state.get("search_text", "")
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    current_page = int(st.session_state.get("result_page", 1))
    current_page = max(1, min(current_page, total_pages))
    st.session_state["result_page"] = current_page

    col_prev, col_page, col_next = st.columns([1, 2, 1])

    with col_prev:
        st.button(
            "← 前の200件",
            disabled=current_page <= 1,
            use_container_width=True,
            on_click=set_result_page,
            args=(current_page - 1,),
        )

    with col_page:
        st.number_input(
            "ページ",
            min_value=1,
            max_value=total_pages,
            step=1,
            key="result_page",
        )

    with col_next:
        st.button(
            "次の200件 →",
            disabled=current_page >= total_pages,
            use_container_width=True,
            on_click=set_result_page,
            args=(current_page + 1,),
        )

    current_page = int(st.session_state["result_page"])

    if total == 0:
        st.info("該当するコメントはありません。")
    else:
        start = (current_page - 1) * PAGE_SIZE + 1
        end = min(current_page * PAGE_SIZE, total)
        st.write(
            f"**{total:,} 件ヒット** — {start:,}〜{end:,}件 / "
            f"{current_page:,}/{total_pages:,}ページ"
        )

        with st.spinner("ページを読み込んでいます…"):
            rows = fetch_page(search_user, search_text, current_page)

        for r in rows:
            prefix = "↳ " if r[4] == 1 else ""
            parent = f" (返信先: {r[5]})" if r[4] == 1 else ""
            display_content = html.unescape(r[3] or "")
            try:
                display_content = urllib.parse.unquote(display_content)
            except Exception:
                pass

            st.write(f"{prefix}ID:{r[0]} [{r[2]}] {r[1]}: {display_content}{parent}")
