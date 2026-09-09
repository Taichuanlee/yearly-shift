import streamlit as st
import pandas as pd
import os
from datetime import datetime

DB_FILE = "shift_exchange.csv"
ADMIN_PIN = "8888"  # 可自訂你的管理者萬用密碼

# ----------------- 資料庫函式 -----------------
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE, dtype={"emp_id": str, "pin": str})
    return pd.DataFrame(columns=[
        "emp_id", "name", "month", "current_shift", "wanted_shift", "pin", "status", "created_at"
    ])

def save_data(df):
    df.to_csv(DB_FILE, index=False)

st.set_page_config(page_title="年度抽班交換看板", layout="wide")
st.title("🔄 換班許願看板")

df = load_data()

# 初始化動態表單列數
if "num_shifts" not in st.session_state:
    st.session_state.num_shifts = 1

tabs = st.tabs(["🔍 即時換班看板", "➕ 刊登換班需求", "⚙️ 我的刊登管理", "🛡️ 管理者後台"])

# ----------------- 修改點一 & 二：即時換班看板 -----------------
with tabs[0]:
    st.subheader("即時換班需求")
    
    col1, col2 = st.columns(2)
    with col1:
        search_month = st.selectbox("篩選月份", ["全部"] + [f"{i}月" for i in range(1, 13)])
    with col2:
        search_shift = st.selectbox("我想換到的班別（對方的原始班）", ["全部", "A班", "E班", "N班"])

    filtered_df = df[df["status"] == "刊登中"] if "status" in df.columns else df

    if search_month != "全部":
        filtered_df = filtered_df[filtered_df["month"] == search_month]
    if search_shift != "全部":
        filtered_df = filtered_df[filtered_df["current_shift"] == search_shift]

    if not filtered_df.empty:
        # 只保留姓名、月份、希望換成班別
        display_df = filtered_df[["name", "month", "wanted_shift"]].rename(columns={
            "name": "姓名/代號",
            "month": "月份",
            "wanted_shift": "希望換成班別"
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有符合條件的換班需求。")

# ----------------- 修改點三：刊登換班需求（支援多筆） -----------------
with tabs[1]:
    st.subheader("登記換班需求")
    
    col_n, col_e = st.columns(2)
    with col_n:
        name = st.text_input("姓名 *", placeholder="例如：王小明")
    with col_e:
        emp_id = st.text_input("員工編號 *（當作帳號管理使用）", placeholder="例如：E12345")
    
    st.divider()
    st.write("📋 **換班細節設定**")
    
    shift_inputs = []
    months_list = [f"{i}月" for i in range(1, 13)]
    shift_options = ["A班", "E班", "N班"]

    # 動態產生多組月份與班別
    for i in range(st.session_state.num_shifts):
        st.caption(f"項目 #{i + 1}")
        c1, c2, c3 = st.columns(3)
        with c1:
            m = st.selectbox(f"月份", months_list, key=f"month_{i}")
        with c2:
            curr = st.selectbox(f"原始班別", shift_options, key=f"curr_{i}")
        with c3:
            want = st.selectbox(f"想要班別", shift_options, key=f"want_{i}")
        shift_inputs.append((m, curr, want))
    
    # 增加欄位按鈕
    if st.button("➕ 新增更多月份需求"):
        st.session_state.num_shifts += 1
        st.rerun()

    st.divider()
    pin = st.text_input("設定 4 位數密碼（修改/下架時驗證使用）*", type="password", max_chars=4)

    if st.button("確認送出刊登", type="primary"):
        if not name.strip() or not emp_id.strip() or not pin.strip():
            st.error("請完整填寫姓名、員工編號及密碼！")
        else:
            has_conflict = any(c == w for _, c, w in shift_inputs)
            if has_conflict:
                st.warning("有項目的原始班別與想要班別相同，請檢查修正！")
            else:
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                new_rows = []
                for m, curr, want in shift_inputs:
                    new_rows.append({
                        "emp_id": emp_id.strip(),
                        "name": name.strip(),
                        "month": m,
                        "current_shift": curr,
                        "wanted_shift": want,
                        "pin": str(pin).strip(),
                        "status": "刊登中",
                        "created_at": now
                    })
                df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                save_data(df)
                st.session_state.num_shifts = 1  # 重設表單數量
                st.success(f"成功刊登 {len(new_rows)} 筆需求！")
                st.rerun()

# ----------------- 修改點四：個人管理（員工編號 + 密碼） -----------------
with tabs[2]:
    st.subheader("管理我的項目")
    
    with st.form("user_login"):
        input_emp = st.text_input("輸入員工編號")
        input_pin = st.text_input("輸入 4 位數密碼", type="password")
        login_btn = st.form_submit_button("查詢我的刊登項目")

    if input_emp and input_pin:
        user_records = df[(df["emp_id"] == input_emp.strip()) & (df["pin"] == str(input_pin).strip()) & (df["status"] == "刊登中")]
        
        if not user_records.empty:
            st.write(f"Hello, **{user_records.iloc[0]['name']}**！以下是你目前正在刊登的需求：")
            
            for idx, row in user_records.iterrows():
                with st.expander(f"📌 {row['month']}：原【{row['current_shift']}】欲換【{row['wanted_shift']}】", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        new_curr = st.selectbox("修改持有班別", ["A班", "E班", "N班"], 
                                                index=["A班", "E班", "N班"].index(row["current_shift"]), key=f"u_c_{idx}")
                    with c2:
                        new_want = st.selectbox("修改想要班別", ["A班", "E班", "N班"], 
                                                index=["A班", "E班", "N班"].index(row["wanted_shift"]), key=f"u_w_{idx}")
                    with c3:
                        action = st.radio("動作", ["儲存變更", "下架此項目"], key=f"u_a_{idx}")
                    
                    if st.button("確認變更", key=f"btn_{idx}"):
                        if action == "下架此項目":
                            df.at[idx, "status"] = "已下架"
                            st.success(f"{row['month']} 需求已下架！")
                        else:
                            df.at[idx, "current_shift"] = new_curr
                            df.at[idx, "wanted_shift"] = new_want
                            st.success(f"{row['month']} 需求已更新！")
                        save_data(df)
                        st.rerun()
        else:
            st.error("查無刊登中的項目，或員工編號/密碼輸入錯誤。")

# ----------------- 修改點五：管理者後台 -----------------
with tabs[3]:
    st.subheader("🛡️ 系統管理者專案後台")
    admin_auth = st.text_input("請輸入管理員金鑰密碼", type="password")
    
    if admin_auth == ADMIN_PIN:
        st.success("身分驗證通過：管理者模式")
        
        # 允許直接在線上表格修改所有欄位
        edited_df = st.data_editor(
            df,
            column_config={
                "status": st.column_config.SelectboxColumn(
                    "狀態", options=["刊登中", "已下架", "已鎖定"], required=True
                ),
                "month": st.column_config.SelectboxColumn(
                    "月份", options=[f"{i}月" for i in range(1, 13)], required=True
                ),
                "current_shift": st.column_config.SelectboxColumn(
                    "原始班", options=["A班", "E班", "N班"], required=True
                ),
                "wanted_shift": st.column_config.SelectboxColumn(
                    "想要班", options=["A班", "E班", "N班"], required=True
                )
            },
            disabled=["created_at"],
            num_rows="dynamic",
            use_container_width=True
        )
        
        if st.button("儲存後台全部異動", type="primary"):
            save_data(edited_df)
            st.success("所有修改與更新已成功儲存！")
            st.rerun()
    elif admin_auth:
        st.error("密碼錯誤，拒絕存取管理者後台。")
