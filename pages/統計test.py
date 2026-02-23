import streamlit as st
import requests
import gzip
import io
import json
import pandas as pd
import matplotlib.pyplot as plt

URL = "https://github.com/22552/kasotest/raw/refs/heads/main/%E7%AC%AC%E4%BA%8C%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88.json.gz"

st.title("統計ダッシュボード")

# =========================
# データ読み込み（キャッシュ）
# =========================
@st.cache_data
def load_data():
    with requests.get(URL, stream=True, timeout=60) as r:
        r.raise_for_status()
        with gzip.GzipFile(fileobj=r.raw) as f:
            return json.load(io.TextIOWrapper(f, encoding="utf-8"))

data = load_data()

# =========================
# 平坦化
# =========================
comments = []

for c in data.get("comments", []):
    comments.append({
        "id": c["id"],
        "user": c["user"],
        "datetime": c["datetime"],
        "is_reply": False
    })

    for r in c.get("replies", []):
        comments.append({
            "id": r["id"],
            "user": r["user"],
            "datetime": r["datetime"],
            "is_reply": True
        })

df = pd.DataFrame(comments)
df["datetime"] = pd.to_datetime(df["datetime"])

# =========================
# 基本統計
# =========================
st.subheader("基本統計")

st.write("総コメント数:", len(df))
st.write("元コメント:", len(df[df["is_reply"] == False]))
st.write("返信:", len(df[df["is_reply"] == True]))

# =========================
# ユーザーランキング
# =========================
st.subheader("ユーザー投稿数ランキング")

ranking = df["user"].value_counts().head(20)
st.dataframe(ranking)

# =========================
# 日別推移
# =========================
st.subheader("日別コメント数")

daily = df.groupby(df["datetime"].dt.date).size()

fig, ax = plt.subplots()
daily.plot(ax=ax)
ax.set_xlabel("Date")
ax.set_ylabel("Comments")
st.pyplot(fig)

# =========================
# 返信率
# =========================
st.subheader("返信率")

total = len(df)
replies = len(df[df["is_reply"] == True])

if total > 0:
    st.write("返信率:", round(replies / total * 100, 2), "%")
else:
    st.write("返信率: 0%")
