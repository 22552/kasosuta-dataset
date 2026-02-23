import streamlit as st
import requests
import json
import gzip
import io

# JSON取得（キャッシュ）
@st.cache_data
def load_data():
    url = "https://github.com/22552/kasotest/raw/refs/heads/main/%E7%AC%AC%E4%BA%8C%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88.json.gz"
    
    r = requests.get(url)
    r.raise_for_status()

    with gzip.GzipFile(fileobj=io.BytesIO(r.content)) as f:
        return json.load(io.TextIOWrapper(f, encoding="utf-8"))

data = load_data()

# コメント平坦化
comments_list = []
for c in data.get("comments", []):
    comments_list.append({
        "id": c["id"],
        "user": c["user"],
        "datetime": c["datetime"],
        "content": c["content"],
        "is_reply": False,
        "parent_id": None
    })
    for r in c.get("replies", []):
        comments_list.append({
            "id": r["id"],
            "user": r["user"],
            "datetime": r["datetime"],
            "content": r["content"],
            "is_reply": True,
            "parent_id": c["id"]
        })

# Streamlit UI
st.title("Scratch コメント検索アプリ")
st.write("Created by ncyo")
user_q = st.text_input("ユーザー名で検索")
text_q = st.text_input("内容で検索")

# 検索ボタン
if st.button("検索"):
    results = comments_list
    if user_q:
        results = [c for c in results if user_q.lower() in c["user"].lower()]
    if text_q:
        results = [c for c in results if text_q.lower() in c["content"].lower()]

    st.write(f"検索結果: {len(results)} 件")

    # ページネーション
    page_size = 200
    total_pages = (len(results) + page_size - 1) // page_size
    if total_pages == 0:
        st.write("結果なし")
    else:
        page = st.number_input("ページ番号", min_value=1, max_value=total_pages, value=1)
        start = (page - 1) * page_size
        end = start + page_size

        # 表示中を上に表示
        st.write(f"表示中: {start+1} - {min(end, len(results))} / {len(results)}")

        # コメント表示
        for c in results[start:end]:
            prefix = "↳ " if c["is_reply"] else ""
            st.write(f"{prefix}ID:{c['id']} [{c['datetime']}] {c['user']}: {c['content']}")
