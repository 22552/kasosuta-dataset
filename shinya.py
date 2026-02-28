import streamlit as st
import requests
import sqlite3
import gzip
import shutil
import os
import html
import urllib.parse
import re

DB_GZ_URL = "https://github.com/22552/kasosuta-dataset/releases/download/dai2v1/cmt.db.gz"
DB_FILE = "comments.db"
GZ_FILE = "cmt.db.gz"

# =========================
# DB準備
# =========================
def ensure_db():
    if os.path.exists(DB_FILE):
        return

    if not os.path.exists(GZ_FILE):
        r = requests.get(DB_GZ_URL, stream=True, timeout=120)
        r.raise_for_status()
        with open(GZ_FILE, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

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
st.title("Scratch コメント高度検索")
st.write("八戸市にいこう!")

with st.expander("🔍 検索の使いかた", expanded=False):
    st.markdown("""
    - **AND検索**: スペースで区切ると「すべて含む」になります（例: `scratch 猫`）
    - **除外検索**: 単語の前に `-` をつけると除外します（例: `scratch -宣伝`）
    - **OR検索**: `|` (縦棒) で区切ると「いずれかを含む」になります（例: `バグ|不具合`）
    - **記号・絵文字**: `>>` や絵文字も自動変換して検索します
    """)

user_q = st.text_input("ユーザー名")
text_q = st.text_input("検索（内容）", placeholder="例: りんご バナナ -スイカ")

if st.button("検索"):
    query = "SELECT id,user,datetime,content,is_reply,parent_id FROM comments WHERE 1=1"
    params = []

    if user_q:
        query += " AND user LIKE ?"
        params.append(f"%{user_q}%")

    if text_q:
        # スペース（全角半角）で分割
        words = re.split(r'\s+', text_q.strip())
        
        for word in words:
            if not word: continue
            
            # 除外検索 (先頭がマイナス)
            is_exclude = word.startswith('-') and len(word) > 1
            search_word = word[1:] if is_exclude else word
            operator = "NOT LIKE" if is_exclude else "LIKE"
            conjunction = "AND" if is_exclude else "AND" # AND条件の中でLIKEかNOT LIKEか

            # OR検索 (縦棒 | が含まれる場合)
            if '|' in search_word and not is_exclude:
                or_parts = search_word.split('|')
                or_clauses = []
                for p in or_parts:
                    # 各パーツに対して通常・HTML・URLの3パターン作成
                    p_esc = html.escape(p)
                    p_url = urllib.parse.quote(p)
                    or_clauses.append("(content LIKE ? OR content LIKE ? OR content LIKE ?)")
                    params.extend([f"%{p}%", f"%{p_esc}%", f"%{p_url}%"])
                query += f" AND ({' OR '.join(or_clauses)})"
            
            else:
                # 通常のAND/除外検索 (通常・HTML・URLの3パターン対応)
                w_esc = html.escape(search_word)
                w_url = urllib.parse.quote(search_word)
                
                if is_exclude:
                    # 除外の場合は「どれにも含まれない」必要がある
                    query += f" AND (content NOT LIKE ? AND content NOT LIKE ? AND content NOT LIKE ?)"
                else:
                    # 含む場合は「どれかに含まれれば良い」
                    query += f" AND (content LIKE ? OR content LIKE ? OR content LIKE ?)"
                
                params.extend([f"%{search_word}%", f"%{w_esc}%", f"%{w_url}%"])

    # 並び替え
    query += " ORDER BY COALESCE(parent_id, id) DESC, datetime ASC"

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

    page = st.number_input("ページ", min_value=1, max_value=total_pages, 
                           value=st.session_state.get("page", 1), key="page_input")

    start = (page - 1) * page_size
    end = start + page_size

    st.write(f"結果: {len(rows)} 件 ( {start+1} - {min(end, len(rows))} 表示 )")

    for r in rows[start:end]:
        prefix = "↳ " if r[4] == 1 else ""
        parent = f"(返信先: {r[5]})" if r[4] == 1 else ""
        
        # デコードして表示
        display_content = html.unescape(r[3])
        try:
            display_content = urllib.parse.unquote(display_content)
        except:
            pass
            
        st.write(f"{prefix}ID:{r[0]} [{r[2]}] {r[1]}: {display_content} {parent}")
