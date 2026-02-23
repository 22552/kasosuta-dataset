import streamlit as st
import requests
import gzip
import io
import json

URL = "https://github.com/22552/kasotest/raw/refs/heads/main/%E7%AC%AC%E4%BA%8C%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88.json.gz"

# =========================
# データ読み込み（キャッシュ）
# =========================
@st.cache_data
def load_data():
    with requests.get(URL, stream=True) as r:
        r.raise_for_status()
        with gzip.GzipFile(fileobj=r.raw) as f:
            return json.load(io.TextIOWrapper(f, encoding="utf-8"))

# =========================
# コメントを1件ずつ生成
# =========================
def iter_comments(data):
    for c in data.get("comments", []):
        yield {
            "id": c["id"],
            "user": c["user"],
            "datetime": c["datetime"],
            "content": c["content"],
            "is_reply": False,
        }

        for r in c.get("replies", []):
            yield {
                "id": r["id"],
                "user": r["user"],
                "datetime": r["datetime"],
                "content": r["content"],
                "is_reply": True,
            }

# =========================
# UI
# =========================
st.title("Scratch コメント検索アプリ")
st.write("Created by ncyo")

user_q = st.text_input("ユーザー名で検索")
text_q = st.text_input("内容で検索")

if st.button("検索"):

    data = load_data()

    # 🔥 ここで一気にリスト化しない
    results = []

    for c in iter_comments(data):
        if user_q and user_q.lower() not in c["user"].lower():
            continue
        if text_q and text_q.lower() not in c["content"].lower():
            continue
        results.append(c)

    st.write(f"検索結果: {len(results)} 件")

    # ページネーション
    page_size = 200
    total_pages = (len(results) + page_size - 1) // page_size

    if total_pages == 0:
        st.write("結果なし")
    else:
        page = st.number_input(
            "ページ番号",
            min_value=1,
            max_value=total_pages,
            value=1
        )

        start = (page - 1) * page_size
        end = start + page_size

        st.write(f"表示中: {start+1} - {min(end, len(results))} / {len(results)}")

        for c in results[start:end]:
            prefix = "↳ " if c["is_reply"] else ""
            st.write(f"{prefix}ID:{c['id']} [{c['datetime']}] {c['user']}: {c['content']}")ime']}] {c['user']}: {c['content']}")
