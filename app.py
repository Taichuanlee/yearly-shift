import streamlit as st
import pandas as pd
import os
from datetime import datetime

DB_FILE = "shift_exchange.csv"
ADMIN_PIN = "8888"  # 管理者登入密碼

# ----------------- 資料庫讀寫 -----------------
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

# 初始化 session 狀態
if "num_shifts" not in st.session_state:
    st.session_state.num_shifts = 1
if "last_submission" not in st.session_state:
    st.session_state.last_submission = None

tabs = st.tabs(["🔍 即時換班看板", "➕ 刊登換班需求", "⚙️ 我的刊登管理", "🛡️ 管理者後台"])

# ----------------- 即時換班看板（簡潔3欄位 + 班別勾選過濾） -----------------
with tabs[0]:
    col_t, col_r = st.columns([5, 1])
    with col_t:
        st.subheader("即時換班需求")
    with col_r:
        if st.button("🔄 重新整理", use_container_width=True):
            st.rerun()

    # 上層快速條件搜尋
    col1, col2 = st.columns(2)
    with col1:
        search_month = st.selectbox("篩選月份", ["全部"] + [f"{i}月" for i in range(1, 13)])
    with col2:
        search_shift = st.selectbox("我想換到的班別（對方的原始班）", ["全部", "A班", "E班", "N班"])

    # 基礎篩選
    filtered_df = df[df["status"] == "刊登中"] if "status" in df.columns else df

    if search_month != "全部":
        filtered_df = filtered_df[filtered_df["month"] == search_month]
    if search_shift != "全部":
        filtered_df = filtered_df[filtered_df["current_shift"] == search_shift]

    st.divider()

    # 表格顯示設定：自訂要顯示的「希望換成班別」
    selected_target_shifts = st.multiselect(
        "📌 下方表格只顯示「希望換成」為以下班別的項目（可複選，預設全選）：",
        options=["A班", "E班", "N班"],
        default=["A班", "E班", "N班"]
    )

    if selected_target_shifts:
        filtered_df = filtered_df[filtered_df["wanted_shift"].isin(selected_target_shifts)]
    else:
        filtered_df = filtered_df.iloc[0:0]  # 若全部取消勾選則不顯示

    # 底下表格：維持最精簡的 3 欄資訊
    if not filtered_df.empty:
        display_df = filtered_df[["name", "month", "wanted_shift"]].rename(columns={
            "name": "姓名 ",
            "month": "月份",
            "wanted_shift": "希望換成班別"
        })
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("目前沒有符合條件的換班需求。")

# ----------------- 刊登換班需求 -----------------
with tabs[1]:
    st.subheader("登記換班需求")

    if st.session_state.last_submission:
        sub = st.session_state.last_submission
        st.success("🎉 刊登成功！以下為您本次新增的換班明細：")
        
        st.write(f"**姓名：** {sub['name']} ｜ **員工編號：** {sub['emp_id']}")
        st.write(f"**已設定的密碼：** `{sub['pin']}` （請牢記，後續修改或下架需使用）")
        
        detail_df = pd.DataFrame(sub["records"]).rename(columns={
            "month": "月份", "current_shift": "持有的原始班", "wanted_shift": "希望換成"
        })
        st.table(detail_df)
        
        if st.button("繼續新增下一筆", type="primary"):
            st.session_state.last_submission = None
            st.session_state.num_shifts = 1
            st.rerun()

    else:
        col_n, col_e = st.columns(2)
        with col_n:
            name = st.text_input("姓名 *", placeholder="例如：王小明")
        with col_e:
            emp_id = st.text_input("員工編號 *（當作帳號管理使用）", placeholder="例如：a12345")

        st.divider()
        st.write("📋 **換班細節設定**")

        shift_inputs = []
        months_list = [f"{i}月" for i in range(1, 13)]
        shift_options = ["A班", "E班", "N班"]

        for i in range(st.session_state.num_shifts):
            c1, c2, c3 = st.columns(3)
            with c1:
                m = st.selectbox(f"月份", months_list, key=f"month_{i}")
            with c2:
                curr = st.selectbox(f"持有原始班", shift_options, key=f"curr_{i}")
            with c3:
                want = st.selectbox(f"想要換成", shift_options, key=f"want_{i}")
            shift_inputs.append((m, curr, want))

        btn_col1, btn_col2, _ = st.columns([2, 2, 6])
        with btn_col1:
            if st.button("➕ 新增更多月份", use_container_width=True):
                st.session_state.num_shifts += 1
                st.rerun()
        with btn_col2:
            if st.button("➖ 減少最後一筆", use_container_width=True, disabled=(st.session_state.num_shifts <= 1)):
                st.session_state.num_shifts -= 1
                st.rerun()

        st.divider()
        pin = st.text_input("設定密碼（不限長度，供後續編輯/下架使用）*", type="password")

        if st.button("確認送出刊登", type="primary", use_container_width=True):
            if not name.strip() or not emp_id.strip() or not pin.strip():
                st.error("請完整填寫姓名、員工編號及密碼！")
            else:
                has_conflict = any(c == w for _, c, w in shift_inputs)
                if has_conflict:
                    st.warning("有項目的持有班與想要班相同，請檢查修正！")
                else:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_rows = []
                    detail_log = []
                    for m, curr, want in shift_inputs:
                        row_data = {
                            "emp_id": emp_id.strip(),
                            "name": name.strip(),
                            "month": m,
                            "current_shift": curr,
                            "wanted_shift": want,
                            "pin": str(pin).strip(),
                            "status": "刊登中",
                            "created_at": now
                        }
                        new_rows.append(row_data)
                        detail_log.append({"month": m, "current_shift": curr, "wanted_shift": want})

                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_data(df)

                    st.session_state.last_submission = {
                        "name": name.strip(),
                        "emp_id": emp_id.strip(),
                        "pin": pin.strip(),
                        "records": detail_log
                    }
                    st.rerun()

# ----------------- 個人管理（員工編號 + 密碼） -----------------
with tabs[2]:
    st.subheader("管理我的刊登項目")

    with st.form("user_login"):
        input_emp = st.text_input("輸入員工編號")
        input_pin = st.text_input("輸入您設定的管理密碼", type="password")
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

# ----------------- 管理者後台 -----------------
with tabs[3]:
    st.subheader("🛡️ 系統管理者專案後台")

    admin_auth = st.text_input("請輸入管理員密碼", type="password")

    if admin_auth == ADMIN_PIN:
        st.success("管理者驗證成功")

        column_labels = {
            "emp_id": "員工編號",
            "name": "同仁姓名",
            "month": "月份",
            "current_shift": "持有班別",
            "wanted_shift": "想要班別",
            "pin": "同仁密碼",
            "status": "刊登狀態",
            "created_at": "登記時間"
        }

        edited_df = st.data_editor(
            df.rename(columns=column_labels),
            column_config={
                "刊登狀態": st.column_config.SelectboxColumn("狀態", options=["刊登中", "已下架", "已鎖定"], required=True),
                "月份": st.column_config.SelectboxColumn("月份", options=[f"{i}月" for i in range(1, 13)], required=True),
                "持有班別": st.column_config.SelectboxColumn("持有班", options=["A班", "E班", "N班"], required=True),
                "想要班別": st.column_config.SelectboxColumn("想要班", options=["A班", "E班", "N班"], required=True),
            },
            disabled=["登記時間"],
            num_rows="dynamic",
            use_container_width=True
        )

        if st.button("儲存後台全部異動", type="primary"):
            reverse_labels = {v: k for k, v in column_labels.items()}
            save_data(edited_df.rename(columns=reverse_labels))
            st.success("資料庫已同步更新！")
            st.rerun()
    elif admin_auth:
        st.error("管理員密碼錯誤！")
