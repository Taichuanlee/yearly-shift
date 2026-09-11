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
CONFIG_FILE = "system_config.csv"
ADMIN_PIN = "117493"

# ----------------- 資料庫與設定讀寫 -----------------
def load_data():
    empty_df = pd.DataFrame(columns=[
        "req_id", "emp_id", "name", "month", "current_shift", "wanted_shift", "notes", "pin", "status", "created_at"
    ])
    if not HF_TOKEN or not HF_REPO_ID:
        if os.path.exists(DATA_FILE):
            df = pd.read_csv(DATA_FILE, dtype=str)
            if "req_id" not in df.columns:
                df["req_id"] = [str(i+1) for i in range(len(df))]
            if "notes" not in df.columns:
                df["notes"] = ""
            return df
        return empty_df

    try:
        file_path = hf_hub_download(
            repo_id=HF_REPO_ID, filename=DATA_FILE, repo_type="dataset", token=HF_TOKEN
        )
        df = pd.read_csv(file_path, dtype=str)
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

def load_config():
    # 讀取全站系統設定（預設為極簡模式、關閉智慧媒合）
    default_cfg = {"app_mode": "極簡模式", "enable_matching": False}
    if not HF_TOKEN or not HF_REPO_ID:
        if os.path.exists(CONFIG_FILE):
            cfg = pd.read_csv(CONFIG_FILE)
            mode = cfg.iloc[0]["app_mode"] if "app_mode" in cfg.columns else "極簡模式"
            matching = bool(cfg.iloc[0]["enable_matching"]) if "enable_matching" in cfg.columns else False
            return mode, matching
        return default_cfg["app_mode"], default_cfg["enable_matching"]

    try:
        cfg_path = hf_hub_download(
            repo_id=HF_REPO_ID, filename=CONFIG_FILE, repo_type="dataset", token=HF_TOKEN
        )
        cfg = pd.read_csv(cfg_path)
        mode = cfg.iloc[0]["app_mode"] if "app_mode" in cfg.columns else "極簡模式"
        matching = bool(cfg.iloc[0]["enable_matching"]) if "enable_matching" in cfg.columns else False
        return mode, matching
    except Exception:
        return default_cfg["app_mode"], default_cfg["enable_matching"]

def save_config(app_mode: str, enable_matching: bool):
    cfg_df = pd.DataFrame([{"app_mode": app_mode, "enable_matching": enable_matching}])
    if not HF_TOKEN or not HF_REPO_ID:
        cfg_df.to_csv(CONFIG_FILE, index=False)
        return
    api = HfApi(token=HF_TOKEN)
    buf = io.StringIO()
    cfg_df.to_csv(buf, index=False)
    api.upload_file(
        path_or_fileobj=buf.getvalue().encode("utf-8"),
        path_in_repo=CONFIG_FILE,
        repo_id=HF_REPO_ID,
        repo_type="dataset",
        commit_message="Update system config"
    )

st.set_page_config(page_title="年度抽班交換看板", layout="wide")

df = load_data()
current_system_mode, enable_matching = load_config()

# ----------------- 側邊欄：管理員身分驗證 -----------------
with st.sidebar:
    st.markdown("### 🏥 急診換班許願池")
    st.caption(f"目前全站運作狀態：**{current_system_mode}**")
    if st.button("🔄 重新整理資料", use_container_width=True):
        st.rerun()

    st.divider()
    with st.expander("🔑 管理者入口"):
        admin_pass = st.text_input("輸入管理密碼", type="password", key="side_admin_pass")
        is_admin = (admin_pass == ADMIN_PIN)

# ==============================================================================
# 判斷一：若輸入管理員密碼，直接進入管理員後台控制室
# ==============================================================================
if is_admin:
    st.title("🛡️ 系統管理者控制台")
    st.success("身分驗證通過：管理員權限已啟動")

    # 修改點 2：管理者手動切換全站模式
    st.markdown("### ⚙️ 全站模式與功能切換")
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        new_mode = st.radio(
            "設定全站同仁看到的介面：",
            ["極簡模式", "完整模式"],
            index=0 if current_system_mode == "極簡模式" else 1
        )
    with c_m2:
        new_enable_matching = st.toggle("開啟完整版「智慧媒合專區」", value=enable_matching)

    if (new_mode != current_system_mode) or (new_enable_matching != enable_matching):
        if st.button("💾 儲存並套用全站設定", type="primary"):
            save_config(new_mode, new_enable_matching)
            st.success(f"已成功將全站模式變更為【{new_mode}】！")
            st.rerun()

    st.divider()
    st.markdown("### 📋 全站資料即時維護")
    column_labels = {
        "req_id": "系統編號", "emp_id": "員工編號", "name": "同仁姓名",
        "month": "月份", "current_shift": "持有班別", "wanted_shift": "想要班別",
        "notes": "備註內容", "pin": "同仁密碼", "status": "刊登狀態", "created_at": "登記時間"
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

    if st.button("儲存資料庫全部修改", type="primary"):
        reverse_labels = {v: k for k, v in column_labels.items()}
        save_data(edited_df.rename(columns=reverse_labels))
        st.success("HF Dataset 已同步更新儲存！")
        st.rerun()

# ==============================================================================
# 判斷二：一般同仁畫面 —— 模式 A：🐣 極簡模式（由管理者控制）
# ==============================================================================
elif current_system_mode == "極簡模式":
    st.title("⚡ 快速換班許願池")
    st.caption("簡單 3 步驟：填姓名 ➔ 選月份班別 ➔ 送出。有合適的直接找同事私訊！")

    # 1. 登記區塊
    with st.expander("➕ 我要刊登換班需求（點此展開填寫）", expanded=True):
        with st.form("simple_form", clear_on_submit=True):
            s_name = st.text_input("你的姓名或暱稱 *", placeholder="例如：風詞 / 閔叔")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                s_month = st.selectbox("月份 *", [f"{i}月" for i in range(1, 13)])
            with c2:
                s_curr = st.selectbox("我手上的原始班 *", ["A班", "E班", "N班"])
            with c3:
                s_want = st.selectbox("我想要換成的班 *", ["A班", "E班", "N班"])
            
            s_note = st.text_input("備註（選填）", placeholder="例如：某月某月互換、夜班優先、私訊我")
            
            s_submit = st.form_submit_button("🚀 一鍵送出刊登", type="primary", use_container_width=True)
            if s_submit:
                if not s_name.strip():
                    st.error("請輸入姓名或暱稱！")
                elif s_curr == s_want:
                    st.warning("持有班別與想要換的班別不能一樣喔！")
                else:
                    valid_ids = pd.to_numeric(df["req_id"], errors='coerce').dropna()
                    next_id = str(int(valid_ids.max() + 1)) if not valid_ids.empty else "1"
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    
                    new_entry = pd.DataFrame([{
                        "req_id": next_id,
                        "emp_id": "無",
                        "name": s_name.strip(),
                        "month": s_month,
                        "current_shift": s_curr,
                        "wanted_shift": s_want,
                        "notes": s_note.strip(),
                        "pin": "0000",
                        "status": "刊登中",
                        "created_at": now
                    }])
                    df = pd.concat([df, new_entry], ignore_index=True)
                    save_data(df)
                    st.success("🎉 刊登成功！已同步至下方看板。")
                    st.rerun()

    st.divider()

    # 2. 修改點 1：極簡模式看板，改為「先選月份與班別」再秀資料
    st.subheader("📋 查詢現有換班需求")
    
    active_simple = df[df["status"].astype(str).str.strip() == "刊登中"].copy() if "status" in df.columns else df.copy()
    for col in ["month", "current_shift", "wanted_shift"]:
        if col in active_simple.columns:
            active_simple[col] = active_simple[col].astype(str).str.strip()

    f_col1, f_col2 = st.columns(2)
    with f_col1:
        q_month = st.selectbox("📅 選擇欲查詢月份 *", ["-- 請選擇月份 --"] + [f"{i}月" for i in range(1, 13)], index=0)
    with f_col2:
        q_shift = st.selectbox("🎯 我想換到的班別（對方的持有班）", ["不限班別", "A班", "E班", "N班"], index=0)

    # 核心條件：沒選月份時不秀卡片，保持乾淨
    if q_month == "-- 請選擇月份 --":
        st.info("💡 請先在上方選擇「欲查詢的月份」，系統將會顯示該月份的換班清單。")
    else:
        filtered_simple = active_simple[active_simple["month"] == q_month]
        if q_shift != "不限班別":
            filtered_simple = filtered_simple[filtered_simple["current_shift"] == q_shift]

        if not filtered_simple.empty:
            st.caption(f"共找到 {len(filtered_simple)} 筆符合條件的需求：")
            for idx, row in filtered_simple.iterrows():
                title_text = f"📌 {row['month']}：{row['current_shift']} ➔ 換 {row['wanted_shift']}（{row['name']}）"
                with st.expander(title_text, expanded=True):
                    ca, cb = st.columns([3, 1])
                    with ca:
                        st.markdown(f"- **同仁：** {row['name']}")
                        st.markdown(f"- **持有班別：** `{row['current_shift']}` ➔ **想換：** `{row['wanted_shift']}`")
                        st.markdown(f"- **備註說明：** {row['notes'] if pd.notna(row['notes']) and str(row['notes']).strip() else '無特定備註'}")
                        st.caption(f"刊登時間：{row['created_at']}")
                    with cb:
                        with st.popover("✅ 標記已換出", use_container_width=True):
                            st.caption(f"即將下架 **{row['name']}** 的 {row['month']} 換班需求。")
                            if st.button("⚠️ 確認已換好並下架", key=f"confirm_del_{row['req_id']}", type="primary", use_container_width=True):
                                r_idx = df[df["req_id"] == row["req_id"]].index
                                df.loc[r_idx, "status"] = "已換出"
                                save_data(df)
                                st.success("已更新為【已換出】！")
                                st.rerun()
        else:
            st.warning(f"目前【{q_month}】沒有符合條件的換班需求。")

# ==============================================================================
# 判斷三：一般同仁畫面 —— 模式 B：🛡️ 完整模式（由管理者控制）
# ==============================================================================
else:
    st.title("🔄 換班許願看板（完整版）")

    if "num_shifts" not in st.session_state:
        st.session_state.num_shifts = 1
    if "last_submission" not in st.session_state:
        st.session_state.last_submission = None

    tabs = st.tabs(["➕ 刊登換班需求", "🔍 即時換班看板", "⚙️ 我的刊登管理"])

    # 1. 完整刊登
    with tabs[0]:
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
                name = st.text_input("姓名 *", placeholder="例如：王小明")
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
                note = st.text_input(f"備註說明（選填）", key=f"note_{i}")
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
                                (df["emp_id"].astype(str).str.strip() == clean_emp) &
                                (df["month"].astype(str).str.strip() == m) &
                                (df["current_shift"].astype(str).str.strip() == c) &
                                (df["wanted_shift"].astype(str).str.strip() == w) &
                                (df["status"].astype(str).str.strip() == "刊登中")
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
                            valid_ids = pd.to_numeric(df["req_id"], errors='coerce').dropna()
                            next_id = int(valid_ids.max() + 1) if not valid_ids.empty else 1

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
                                "name": clean_name, "emp_id": clean_emp, "pin": clean_pin, "records": detail_log
                            }
                            st.rerun()

    # 2. 完整看板
    with tabs[1]:
        col_t, col_r = st.columns([5, 1])
        with col_t:
            st.subheader("即時換班需求")
        with col_r:
            if st.button("🔄 重新整理", use_container_width=True):
                st.rerun()

        active_df = df[df["status"].astype(str).str.strip() == "刊登中"].copy() if "status" in df.columns else df.copy()
        for col in ["month", "current_shift", "wanted_shift"]:
            if col in active_df.columns:
                active_df[col] = active_df[col].astype(str).str.strip()

        if enable_matching:
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

            match_count_text = f"🔥 系統智慧媒合成功 ({len(matches)} 組可互換)" if matches else "🔥 系統智慧媒合專區"
            with st.expander(match_count_text, expanded=False):
                if matches:
                    st.caption("以下配對組合雙向需求完全吻合，確認私下講好後，可直接在此輸入任一人密碼完成一鍵下架。")
                    for idx, (user_a, user_b) in enumerate(matches):
                        st.markdown(f"#### 🎯 配對 #{idx + 1}：【{user_a['month']}】")
                        c1, c2 = st.columns(2)
                        with c1:
                            st.info(f"👤 **{user_a['name']}**\n\n- 持有：`{user_a['current_shift']}`\n- 想換：`{user_a['wanted_shift']}`\n- 備註：{user_a['notes'] if str(user_a['notes']).strip() else '無'}")
                        with c2:
                            st.success(f"👤 **{user_b['name']}**\n\n- 持有：`{user_b['current_shift']}`\n- 想換：`{user_b['wanted_shift']}`\n- 備註：{user_b['notes'] if str(user_b['notes']).strip() else '無'}")
                        with st.popover("🤝 我們講好了，確認換班（下架此組需求）", use_container_width=True):
                            st.write(f"即將同步將 **{user_a['name']}** 與 **{user_b['name']}** 的 {user_a['month']} 需求標記為「已換出」。")
                            auth_pin = st.text_input("輸入任一方刊登密碼以核銷：", type="password", key=f"auth_pin_{idx}")
                            if st.button("確認核銷並下架", key=f"confirm_match_{idx}", type="primary"):
                                if auth_pin.strip() in [str(user_a["pin"]).strip(), str(user_b["pin"]).strip()]:
                                    idx_a = df[df["req_id"] == user_a["req_id"]].index
                                    idx_b = df[df["req_id"] == user_b["req_id"]].index
                                    df.loc[idx_a, "status"] = "已換出"
                                    df.loc[idx_b, "status"] = "已換出"
                                    save_data(df)
                                    st.success("🎉 換班完成！已同步標記為【已換出】！")
                                    st.rerun()
                                else:
                                    st.error("密碼不符合任一方設定之密碼！")
                        st.divider()
                else:
                    st.info("目前尚無雙向完全吻合的需求組合。")

        col1, col2 = st.columns(2)
        with col1:
            search_month = st.selectbox("📅 選擇欲查詢月份 *", ["-- 請選擇月份 --"] + [f"{i}月" for i in range(1, 13)], index=0)
        with col2:
            search_shift = st.selectbox("🎯 我想換到的班別（對方的持有班）", ["不限班別", "A班", "E班", "N班"], index=0)

        selected_target_shifts = st.multiselect(
            "📌 對方希望換成的班別（可複選，空白代表不限）：",
            options=["A班", "E班", "N班"],
            default=[]
        )
        st.divider()

        if search_month == "-- 請選擇月份 --":
            st.info("💡 請在上方先選擇「欲查詢的月份」，系統將會顯示符合的需求清單。")
        else:
            filtered_df = active_df[active_df["month"] == search_month]
            if search_shift != "不限班別":
                filtered_df = filtered_df[filtered_df["current_shift"] == search_shift]
            if selected_target_shifts:
                filtered_df = filtered_df[filtered_df["wanted_shift"].isin(selected_target_shifts)]

            if not filtered_df.empty:
                st.caption(f"共找到 {len(filtered_df)} 筆符合條件的需求：")
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
                st.warning(f"目前【{search_month}】沒有符合您篩選條件的換班需求。")

    # 3. 個人管理
    with tabs[2]:
        st.subheader("管理我的刊登項目")
        with st.form("user_login"):
            input_emp = st.text_input("輸入員工編號")
            input_pin = st.text_input("輸入您設定的管理密碼", type="password")
            login_btn = st.form_submit_button("查詢我的刊登項目")

        if input_emp and input_pin:
            clean_user_emp = input_emp.strip()
            clean_user_pin = str(input_pin).strip()
            user_records = df[(df["emp_id"].astype(str).str.strip() == clean_user_emp) & 
                              (df["pin"].astype(str).str.strip() == clean_user_pin) & 
                              (df["status"].astype(str).str.strip() == "刊登中")]

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
