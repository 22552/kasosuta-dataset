import streamlit as st
import requests
import gzip
import io
import json

URL = "https://github.com/22552/kasotest/raw/refs/heads/main/%E7%AC%AC%E4%BA%8C%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88.json.gz"

@st.cache_data
def load_data():
    with requests.get(URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        with gzip.GzipFile(fileobj=r.raw) as f:
            return json.load(io.TextIOWrapper(f, encoding="utf-8"))

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

st.title("Scratch コメント検索アプリ")
st.write("八戸市にいこう")

user_q = st.text_input("ユーザー名で検索")
text_q = st.text_input("内容で検索")

# 検索ボタン
if st.button("検索"):
    data = load_data()

    results = [
        c for c in iter_comments(data)
        if (not user_q or user_q.lower() in c["user"].lower())
        and (not text_q or text_q.lower() in c["content"].lower())
    ]

    st.session_state["results"] = results
    st.session_state["page"] = 1

# 結果がある場合のみ表示
if "results" in st.session_state:

    results = st.session_state["results"]

    page_size = 200
    total_pages = (len(results) + page_size - 1) // page_size

    if total_pages > 0:

        page = st.number_input(
            "ページ番号",
            min_value=1,
            max_value=total_pages,
            value=st.session_state.get("page", 1),
            key="page_input"
        )

        start = (page - 1) * page_size
        end = start + page_size

        st.write(f"表示中: {start+1} - {min(end, len(results))} / {len(results)}")

        for c in results[start:end]:
            prefix = "↳ " if c["is_reply"] else ""
            st.write(f"{prefix}ID:{c['id']} [{c['datetime']}] {c['user']}: {c['content']}")
