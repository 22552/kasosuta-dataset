import streamlit as st
import requests
import sqlite3
import gzip
import shutil
import os

DB_GZ_URL = "https://github.com/22552/kasosuta-dataset/releases/download/dai2v1/cmt.db.gz"
DB_FILE = "comments.db"
GZ_FILE = "cmt.db.gz"

# =========================
# DB準備
# =========================
def ensure_db():
    if os.path.exists(DB_FILE):
        return

    # ダウンロード
    if not os.path.exists(GZ_FILE):
        r = requests.get(DB_GZ_URL, stream=True, timeout=120)
        r.raise_for_status()
        with open(GZ_FILE, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    # 展開
    with gzip.open(GZ_FILE, "rb") as f_in:
        with open(DB_FILE, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

ensure_db()

# =========================
# SQLite接続
# =========================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

# =========================
# UI
# =========================
st.title("Scratch コメント検索アプリ")
st.write("八戸市にいこう!")

user_q = st.text_input("ユーザー名")
text_q = st.text_input("内容")

if st.button("検索"):

    query = """
    SELECT id,user,datetime,content,is_reply,parent_id
    FROM comments
    WHERE 1=1
    """

    params = []

    if user_q:
        query += " AND user LIKE ?"
        params.append(f"%{user_q}%")

    if text_q:
        query += " AND content LIKE ?"
        params.append(f"%{text_q}%")

    # 🔥 親 → 返信 の順になる並び
    query += """
    ORDER BY
        COALESCE(parent_id, id),
        datetime DESC
    """

    rows = cur.execute(query, params).fetchall()

    st.session_state["rows"] = rows
    st.session_state["page"] = 1

# =========================
# ページ表示
# =========================
if "rows" in st.session_state:

    rows = st.session_state["rows"]

    page_size = 200
    total_pages = max(1, (len(rows) + page_size - 1) // page_size)

    page = st.number_input(
        "ページ",
        min_value=1,
        max_value=total_pages,
        value=st.session_state.get("page", 1),
        key="page_input"
    )

    start = (page - 1) * page_size
    end = start + page_size

    st.write(f"表示中: {start+1} - {min(end, len(rows))} / {len(rows)}")

    for r in rows[start:end]:
        prefix = "↳ " if r[4] == 1 else ""
        parent = f"(返信先: {r[5]})" if r[4] == 1 else ""
        st.write(f"{prefix}ID:{r[0]} [{r[2]}] {r[1]}: {r[3]} {parent}")
