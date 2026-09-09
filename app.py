import streamlit as st
import pandas as pd
import os
from datetime import datetime

DB_FILE = "shift_exchange.csv"

# 初始化資料表
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=[
        "id", "name", "month", "current_shift", "wanted_shift", "pin", "status", "created_at"
    ])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

st.set_page_config(page_title="年度抽班交換看板", layout="wide")
st.title("🔄 換班許願看板")

df = load_data()

# 頁籤分類：瀏覽尋找 vs 登記管理
tab1, tab2, tab3 = st.tabs(["🔍 尋找/交換清單", "➕ 刊登換班需求", "⚙️ 管理我的刊登"])

# ----------------- 需求三：快速搜尋 -----------------
with tab1:
    st.subheader("即時換班看板")
    col1, col2 = st.columns(2)
    with col1:
        search_month = st.selectbox("篩選月份", ["全部"] + [f"{i}月" for i in range(1, 13)])
    with col2:
        search_shift = st.selectbox("我想換到的班別（他在找的原始班）", ["全部", "A班", "E班", "N班"])

    filtered_df = df[df["status"] == "刊登中"] if "status" in df.columns else df

    if search_month != "全部":
        filtered_df = filtered_df[filtered_df["month"] == search_month]
    if search_shift != "全部":
        filtered_df = filtered_df[filtered_df["current_shift"] == search_shift]

    if not filtered_df.empty:
        display_cols = ["id", "name", "month", "current_shift", "wanted_shift", "created_at"]
        st.dataframe(
            filtered_df[display_cols].rename(columns={
                "id": "編號", "name": "姓名/代號", "month": "月份",
                "current_shift": "現有班別", "wanted_shift": "希望換成", "created_at": "刊登時間"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("目前沒有符合條件的換班需求。")

# ----------------- 需求二：刊登需求 -----------------
with tab2:
    st.subheader("登記你的換班需求")
    with st.form("exchange_form", clear_on_submit=True):
        name = st.text_input("姓名或員工編號 *")
        col_m, col_c, col_w = st.columns(3)
        with col_m:
            month = st.selectbox("月份 *", [f"{i}月" for i in range(1, 13)])
        with col_c:
            current_shift = st.selectbox("目前持有的班別 *", ["A班", "E班", "N班"])
        with col_w:
            wanted_shift = st.selectbox("希望能換到的班別 *", ["A班", "E班", "N班"])
        
        pin = st.text_input("設定4位數密碼（供日後修改/下架驗證）*", type="password", max_chars=4)
        
        submitted = st.form_submit_button("送出刊登")
        if submitted:
            if not name or not pin:
                st.error("請完整填寫姓名及管理密碼！")
            elif current_shift == wanted_shift:
                st.warning("原始班別與目標班別不能相同！")
            else:
                new_id = int(df["id"].max() + 1) if not df.empty and df["id"].dropna().any() else 1
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_row = pd.DataFrame([{
                    "id": new_id, "name": name, "month": month,
                    "current_shift": current_shift, "wanted_shift": wanted_shift,
                    "pin": str(pin), "status": "刊登中", "created_at": now
                }])
                df = pd.concat([df, new_row], ignore_index=True)
                save_data(df)
                st.success(f"刊登成功！請記住你的需求編號：{new_id}")
                st.rerun()

# ----------------- 需求四：編輯與下架 -----------------
with tab3:
    st.subheader("編輯或下架我的需求")
    with st.form("edit_auth_form"):
        req_id = st.number_input("輸入你的需求編號", min_value=1, step=1)
        input_pin = st.text_input("輸入刊登時設定的密碼", type="password")
        check_btn = st.form_submit_button("讀取我的資料")

    match = df[(df["id"] == req_id) & (df["pin"] == str(input_pin))] if req_id and input_pin else pd.DataFrame()

    if not match.empty:
        item = match.iloc[0]
        st.write(f"當前狀態：**{item['status']}**｜姓名：**{item['name']}**")
        
        with st.form("update_form"):
            new_curr = st.selectbox("修改現有班別", ["A班", "E班", "N班"], index=["A班", "E班", "N班"].index(item["current_shift"]))
            new_want = st.selectbox("修改想換班別", ["A班", "E班", "N班"], index=["A班", "E班", "N班"].index(item["wanted_shift"]))
            action = st.radio("動作選擇", ["僅更新班別", "直接下架（已換到或取消）"])
            
            update_btn = st.form_submit_button("確認送出變更")
            if update_btn:
                idx = match.index[0]
                if action == "直接下架（已換到或取消）":
                    df.at[idx, "status"] = "已下架"
                    st.success("已成功將該筆需求下架！")
                else:
                    df.at[idx, "current_shift"] = new_curr
                    df.at[idx, "wanted_shift"] = new_want
                    st.success("需求班別已成功更新！")
                save_data(df)
                st.rerun()
    elif check_btn:
        st.error("編號不存在或密碼錯誤！")
