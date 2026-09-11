import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from huggingface_hub import HfApi, hf_hub_download

# ----------------- 設定與金鑰 -----------------
HF_TOKEN = st.secrets.get("HF_TOKEN", "")
HF_REPO_ID = st.secrets.get("HF_REPO_ID", "")
DATA_FILE = "shift_exchange.csv"
ADMIN_PIN = "117493"

# ----------------- HF Dataset 讀寫函式 -----------------
def load_data():
    empty_df = pd.DataFrame(columns=[
        "req_id", "emp_id", "name", "month", "current_shift", "wanted_shift", "notes", "pin", "status", "created_at"
    ])
    if not HF_TOKEN or not HF_REPO_ID:
        if os.path.exists(DATA_FILE):
            df = pd.read_csv(DATA_FILE, dtype={"req_id": str, "emp_id": str, "pin": str})
            if "req_id" not in df.columns:
                df["req_id"] = [str(i+1) for i in range(len(df))]
            if "notes" not in df.columns:
                df["notes"] = ""
            return df
        return empty_df

    try:
        file_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            filename=DATA_FILE,
            repo_type="dataset",
            token=HF_TOKEN
        )
        df = pd.read_csv(file_path, dtype={"req_id": str, "emp_id": str, "pin": str})
        if "req_id" not in df.columns:
            df["req_id"] = [str(i+1) for i in range(len(df))]
        if "notes" not in df.columns:
            df["notes"] = ""
        return df
    except Exception:
        return empty_df

def save_data(df):
    if not HF_TOKEN or not HF_REPO_ID:
        df.to_csv(DATA_FILE, index=False)
        return

    api = HfApi(token=HF_TOKEN)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    api.upload_file(
        path_or_fileobj=csv_buffer.getvalue().encode("utf-8"),
        path_in_repo=DATA_FILE,
        repo_id=HF_REPO_ID,
        repo_type="dataset",
        commit_message=f"Update shift data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

st.set_page_config(page_title="年度抽班交換看板", layout="wide")
st.title("🔄 換班許願看板")

df = load_data()

# 初始化 session 狀態
if "num_shifts" not in st.session_state:
    st.session_state.num_shifts = 1
if "last_submission" not in st.session_state:
    st.session_state.last_submission = None

tabs = st.tabs(["🔍 即時換班看板", "➕ 刊登換班需求", "⚙️ 我的刊登管理", "🛡️ 管理者後台"])

# ----------------- 1. 即時換班看板 -----------------
with tabs[0]:
    col_t, col_r = st.columns([5, 1])
    with col_t:
        st.subheader("即時換班需求")
    with col_r:
        if st.button("🔄 重新整理", use_container_width=True):
            st.rerun()

    # ----------------- 自動媒合運算 -----------------
    active_df = df[df["status"] == "刊登中"] if "status" in df.columns else df
    matches = []
    seen_pairs = set()

    if not active_df.empty:
        records = active_df.to_dict('records')
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                a = records[i]
                b = records[j]
                if (a["month"] == b["month"] and
                    a["emp_id"] != b["emp_id"] and
                    a["current_shift"] == b["wanted_shift"] and
                    b["current_shift"] == a["wanted_shift"]):
                    pair_key = tuple(sorted([a["req_id"], b["req_id"]]))
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        matches.append((a, b))

    # 公共看板：預設收起的媒合區塊
    match_count_text = f"🔥 系統智慧媒合成功 ({len(matches)} 組可互換)" if matches else "🔥 系統智慧媒合專區"
    with st.expander(match_count_text, expanded=False):
        if matches:
            st.caption("以下配對組合雙向需求完全吻合，確認私下講好後，可直接在此輸入任一人密碼完成一鍵下架。")
            for idx, (user_a, user_b) in enumerate(matches):
                st.markdown(f"#### 🎯 配對 #{idx + 1}：【{user_a['month']}】")
                c1, c2 = st.columns(2)
                with c1:
                    st.info(
                        f"👤 **{user_a['name']}**\n\n"
                        f"- 持有班別：`{user_a['current_shift']}`\n"
                        f"- 想換班別：`{user_a['wanted_shift']}`\n"
                        f"- 備註：{user_a['notes'] if user_a['notes'] else '無'}"
                    )
                with c2:
                    st.success(
                        f"👤 **{user_b['name']}**\n\n"
                        f"- 持有班別：`{user_b['current_shift']}`\n"
                        f"- 想換班別：`{user_b['wanted_shift']}`\n"
                        f"- 備註：{user_b['notes'] if user_b['notes'] else '無'}"
                    )

                # 做法 B：雙向一鍵換出下架
                with st.popover(f"🤝 我們講好了，確認換班（下架此組需求）", use_container_width=True):
                    st.write(f"即將同步將 **{user_a['name']}** 與 **{user_b['name']}** 的 {user_a['month']} 需求標記為「已換出」。")
                    auth_pin = st.text_input("輸入任一方刊登密碼以核銷：", type="password", key=f"auth_pin_{idx}")
                    if st.button("確認核銷並下架", key=f"confirm_match_{idx}", type="primary"):
                        if auth_pin.strip() in [str(user_a["pin"]).strip(), str(user_b["pin"]).strip()]:
                            idx_a = df[df["req_id"] == user_a["req_id"]].index
                            idx_b = df[df["req_id"] == user_b["req_id"]].index
                            df.loc[idx_a, "status"] = "已換出"
                            df.loc[idx_b, "status"] = "已換出"
                            save_data(df)
                            st.success(f"🎉 換班完成！已將 {user_a['name']} 與 {user_b['name']} 的該筆需求同步標記為【已換出】！")
                            st.rerun()
                        else:
                            st.error("密碼不符合任一方設定之密碼！")
                st.divider()
        else:
            st.info("目前尚無雙向完全吻合的需求組合，持續等待好消息！")

    # 上層搜尋條件
    col1, col2 = st.columns(2)
    with col1:
        search_month = st.selectbox("篩選月份", ["全部"] + [f"{i}月" for i in range(1, 13)])
    with col2:
        search_shift = st.selectbox("我想換到的班別（對方的原始班）", ["全部", "A班", "E班", "N班"])

    filtered_df = active_df.copy()

    if search_month != "全部":
        filtered_df = filtered_df[filtered_df["month"] == search_month]
    if search_shift != "全部":
        filtered_df = filtered_df[filtered_df["current_shift"] == search_shift]

    st.divider()

    selected_target_shifts = st.multiselect(
        "📌 篩選希望換成的班別：",
        options=["A班", "E班", "N班"],
        default=["A班", "E班", "N班"]
    )

    if selected_target_shifts:
        filtered_df = filtered_df[filtered_df["wanted_shift"].isin(selected_target_shifts)]
    else:
        filtered_df = filtered_df.iloc[0:0]

    # 卡片式手機排版
    if not filtered_df.empty:
        st.caption(f"共找到 {len(filtered_df)} 筆待交換需求：")
        for _, row in filtered_df.iterrows():
            card_title = f"📌 {row['month']}：{row['current_shift']} ➔ 換 {row['wanted_shift']}（{row['name']}）"
            with st.expander(card_title, expanded=False):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.markdown(f"**同仁：** {row['name']}")
                    st.markdown(f"**月份：** {row['month']}")
                    st.markdown(f"**持有原始班：** `{row['current_shift']}`")
                    st.markdown(f"**希望能換成：** `{row['wanted_shift']}`")
                with c_b:
                    st.markdown(f"**刊登時間：** {row['created_at']}")
                    note_display = row['notes'] if pd.notna(row['notes']) and str(row['notes']).strip() else "無特定備註"
                    st.markdown(f"**備註說明：**\n> {note_display}")
    else:
        st.info("目前沒有符合條件的換班需求。")

# ----------------- 2. 刊登換班需求 -----------------
with tabs[1]:
    st.subheader("登記換班需求")

    if st.session_state.last_submission:
        sub = st.session_state.last_submission
        st.success("🎉 刊登成功！以下為您本次新增的換班明細：")
        
        st.write(f"**姓名：** {sub['name']} ｜ **員工編號：** {sub['emp_id']}")
        st.write(f"**設定之密碼：** `{sub['pin']}` （請牢記，後續修改或下架需使用）")
        
        detail_df = pd.DataFrame(sub["records"]).rename(columns={
            "month": "月份", "current_shift": "持有的原始班", "wanted_shift": "希望換成", "notes": "備註"
        })
        st.table(detail_df)
        
        if st.button("繼續新增下一筆", type="primary"):
            st.session_state.last_submission = None
            st.session_state.num_shifts = 1
            st.rerun()

    else:
        col_n, col_e = st.columns(2)
        with col_n:
            name = st.text_input("姓名 *", placeholder="例如：郭風詞")
        with col_e:
            emp_id = st.text_input("員工編號 *（當作帳號管理使用）", placeholder="例如：110038")

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
            
            note = st.text_input(f"備註說明（選填，例如：不接受特殊班；1.4月互換）", key=f"note_{i}")
            shift_inputs.append((m, curr, want, note))

            if i < st.session_state.num_shifts - 1:
                st.divider()

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
        pin = st.text_input("設定管理密碼（不限長度，供後續編輯/下架使用）*", type="password")

        if st.button("確認送出刊登", type="primary", use_container_width=True):
            clean_name = name.strip()
            clean_emp = emp_id.strip()
            clean_pin = pin.strip()

            if not clean_name or not clean_emp or not clean_pin:
                st.error("請完整填寫姓名、員工編號及密碼！")
            elif any(c == w for m, c, w, n in shift_inputs):
                st.warning("有項目的持有班與想要換成班別相同，請修正！")
            else:
                input_combos = [(m, c, w) for m, c, w, n in shift_inputs]
                if len(input_combos) != len(set(input_combos)):
                    st.error("您在本次填寫的內容中有完全重複的月份與班別組合，請檢查移除！")
                else:
                    duplicate_found = False
                    dup_msg = ""
                    for m, c, w, _ in shift_inputs:
                        existing = df[
                            (df["emp_id"] == clean_emp) &
                            (df["month"] == m) &
                            (df["current_shift"] == c) &
                            (df["wanted_shift"] == w) &
                            (df["status"] == "刊登中")
                        ]
                        if not existing.empty:
                            duplicate_found = True
                            dup_msg = f"您已在系統中刊登過【{m}：{c} 換 {w}】且尚未下架，無法重複登記！"
                            break

                    if duplicate_found:
                        st.error(dup_msg)
                    else:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M")
                        new_rows = []
                        detail_log = []
                        next_id = int(df["req_id"].astype(int).max() + 1) if not df.empty and df["req_id"].dropna().any() else 1
                        
                        for m, c, w, n in shift_inputs:
                            row_data = {
                                "req_id": str(next_id),
                                "emp_id": clean_emp,
                                "name": clean_name,
                                "month": m,
                                "current_shift": c,
                                "wanted_shift": w,
                                "notes": n.strip(),
                                "pin": clean_pin,
                                "status": "刊登中",
                                "created_at": now
                            }
                            new_rows.append(row_data)
                            detail_log.append({
                                "month": m, "current_shift": c, "wanted_shift": w, "notes": n.strip()
                            })
                            next_id += 1

                        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                        save_data(df)

                        st.session_state.last_submission = {
                            "name": clean_name,
                            "emp_id": clean_emp,
                            "pin": clean_pin,
                            "records": detail_log
                        }
                        st.rerun()

# ----------------- 3. 個人管理 -----------------
with tabs[2]:
    st.subheader("管理我的刊登項目")

    with st.form("user_login"):
        input_emp = st.text_input("輸入員工編號")
        input_pin = st.text_input("輸入您設定的管理密碼", type="password")
        login_btn = st.form_submit_button("查詢我的刊登項目")

    if input_emp and input_pin:
        clean_user_emp = input_emp.strip()
        clean_user_pin = str(input_pin).strip()
        user_records = df[(df["emp_id"] == clean_user_emp) & (df["pin"] == clean_user_pin) & (df["status"] == "刊登中")]

        if not user_records.empty:
            st.write(f"Hello, **{user_records.iloc[0]['name']}**！以下是你目前正在刊登的需求：")

            for idx, row in user_records.iterrows():
                with st.expander(f"📌 {row['month']}：原【{row['current_shift']}】欲換【{row['wanted_shift']}】", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_curr = st.selectbox("修改持有班別", ["A班", "E班", "N班"],
                                                index=["A班", "E班", "N班"].index(row["current_shift"]), key=f"u_c_{idx}")
                        new_want = st.selectbox("修改想要班別", ["A班", "E班", "N班"],
                                                index=["A班", "E班", "N班"].index(row["wanted_shift"]), key=f"u_w_{idx}")
                    with c2:
                        current_note = row["notes"] if pd.notna(row["notes"]) else ""
                        new_note = st.text_input("修改備註說明", value=current_note, key=f"u_n_{idx}")
                        action = st.radio("動作", ["儲存變更", "下架此項目"], key=f"u_a_{idx}")

                    if st.button("確認執行", key=f"btn_{idx}"):
                        if action == "下架此項目":
                            df.at[idx, "status"] = "已下架"
                            st.success(f"{row['month']} 需求已下架！")
                        else:
                            df.at[idx, "current_shift"] = new_curr
                            df.at[idx, "wanted_shift"] = new_want
                            df.at[idx, "notes"] = new_note.strip()
                            st.success(f"{row['month']} 需求已更新！")
                        save_data(df)
                        st.rerun()
        else:
            st.error("查無刊登中的項目，或員工編號/密碼輸入錯誤。")

# ----------------- 4. 管理者後台 -----------------
with tabs[3]:
    st.subheader("🛡️ 系統管理者專案後台")
    admin_auth = st.text_input("請輸入管理員密碼", type="password")

    if admin_auth == ADMIN_PIN:
        st.success("管理者驗證成功")

        column_labels = {
            "req_id": "系統編號",
            "emp_id": "員工編號",
            "name": "同仁姓名",
            "month": "月份",
            "current_shift": "持有班別",
            "wanted_shift": "想要班別",
            "notes": "備註內容",
            "pin": "同仁密碼",
            "status": "刊登狀態",
            "created_at": "登記時間"
        }

        edited_df = st.data_editor(
            df.rename(columns=column_labels),
            column_config={
                "刊登狀態": st.column_config.SelectboxColumn("狀態", options=["刊登中", "已下架", "已換出"], required=True),
                "月份": st.column_config.SelectboxColumn("月份", options=[f"{i}月" for i in range(1, 13)], required=True),
                "持有班別": st.column_config.SelectboxColumn("持有班", options=["A班", "E班", "N班"], required=True),
                "想要班別": st.column_config.SelectboxColumn("想要班", options=["A班", "E班", "N班"], required=True),
            },
            disabled=["系統編號", "登記時間"],
            num_rows="dynamic",
            use_container_width=True
        )

        if st.button("儲存後台全部異動", type="primary"):
            reverse_labels = {v: k for k, v in column_labels.items()}
            save_data(edited_df.rename(columns=reverse_labels))
            st.success("HF Dataset 已同步更新儲存！")
            st.rerun()
    elif admin_auth:
        st.error("管理員密碼錯誤！")
