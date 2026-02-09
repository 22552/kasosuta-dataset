import streamlit as st
import requests
import json

# URLからJSONを取得（キャッシュ）
@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/hd3a/kasosuta-dataset/refs/heads/main/scratch_shinya_all.json"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

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

user_q = st.text_input("ユーザー名で検索")
text_q = st.text_input("内容で検索")

# フィルタリング
results = comments_list
if user_q:
    results = [c for c in results if user_q.lower() in c["user"].lower()]
if text_q:
    results = [c for c in results if text_q.lower() in c["content"].lower()]

st.write(f"検索結果: {len(results)} 件")

for c in results:
    prefix = "↳ " if c["is_reply"] else ""
    st.write(f"{prefix}ID:{c['id']} [{c['datetime']}] {c['user']}: {c['content']}")
