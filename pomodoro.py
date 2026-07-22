import streamlit as st
import time
import os
import json
import cv2
import numpy as np
from google import genai
from dotenv import load_dotenv

class PomodoroApp:
    """アプリの画面表示と状態遷移を管理するクラス"""

    def __init__(self):
        st.set_page_config(layout="wide", page_title="Pomodoro Timer")
        self.setup_session_state()

    def setup_session_state(self):
        if "page_control" not in st.session_state:
            st.session_state["page_control"] = 0
        if "cnt" not in st.session_state:
            st.session_state["cnt"] = 0
        if "goal" not in st.session_state:
            st.session_state["goal"] = "未設定"
        if "worktime" not in st.session_state:
            st.session_state["worktime"] = 25
        if "sets" not in st.session_state:
            st.session_state["sets"] = 4
        if "downtime" not in st.session_state:
            st.session_state["downtime"] = 5
            
        if "timer_running" not in st.session_state:
            st.session_state["timer_running"] = False
        if "prompt_break" not in st.session_state:
            st.session_state["prompt_break"] = False
        if "remaining" not in st.session_state:
            st.session_state["remaining"] = 0
        if "timer_running_break" not in st.session_state:
            st.session_state["timer_running_break"] = False
        if "remaining_break" not in st.session_state:
            st.session_state["remaining_break"] = 0
        if "last_seen" not in st.session_state:
            st.session_state["last_seen"] = time.time()

    def switch_page(self, page_id):
        st.session_state["page_control"] = page_id
        st.rerun()

    def render_main_page(self):
        st.title("Pomodoro Timer")
        
        st.markdown(
            """
            <style>
            input[type="number"]::-webkit-outer-spin-button,
            input[type="number"]::-webkit-inner-spin-button {
                -webkit-appearance: none;
                margin: 0;
            }
            input[type="number"] {
                -moz-appearance: textfield;
            }
            .main-timer { font-size: 80px; font-weight: bold; color: #87CEFA; text-align: center; }
            .break-timer { font-size: 80px; font-weight: bold; color: #99EE90; text-align: center; }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.sidebar.title("１ページ目")
        if st.sidebar.button("2ページ目へ"):
            self.switch_page(1)
        
        with st.form("setting_form"):
            st.header('タイマー設定')
            goal_input = st.text_input("今回の目標", value=st.session_state["goal"])
            worktime_input = st.number_input("作業時間 (分)", min_value=1, value=st.session_state["worktime"])
            downtime_input = st.number_input("休憩時間 (分)", min_value=1, value=st.session_state["downtime"])
            sets_input = st.number_input("セット数", min_value=1, value=st.session_state["sets"])
            
            submitted = st.form_submit_button("設定を決定")
            
            if submitted:
                st.session_state["goal"] = goal_input
                st.session_state["worktime"] = worktime_input
                st.session_state["downtime"] = downtime_input
                st.session_state["sets"] = sets_input
                st.session_state["remaining"] = worktime_input * 60
                st.session_state["remaining_break"] = downtime_input * 60
                st.success("設定を更新しました！")

        st.markdown("### 現在の設定内容")
        st.markdown(f"**目標:** {st.session_state['goal']}")
        st.markdown(f"**作業時間:** {st.session_state['worktime']} 分")
        st.markdown(f"**休憩時間:** {st.session_state['downtime']} 分")
        st.markdown(f"**セット数:** {st.session_state['sets']} セット")

    def render_second_page(self):
        st.sidebar.title("２ページ目")
        
        if st.sidebar.button("3ページ目へ（タイマースタート）", type="primary"):
            # 【修正点1】ページを切り替える前に、目標のデータを「saved_goal」にコピーして退避させる
            for i in range(st.session_state["sets"]):
                goal_text = st.session_state.get(f"user_goal{i}", "")
                # 空白のままボタンが押された場合は「未入力」とする
                st.session_state[f"saved_goal{i}"] = goal_text if goal_text != "" else "未入力"

            st.session_state.timer_running = True
            st.session_state.remaining = st.session_state['worktime'] * 60
            st.session_state.last_seen = time.time()
            self.switch_page(2)

        if st.sidebar.button("1ページ前に戻る"):
            self.switch_page(0)
            
        st.sidebar.markdown("---")
        
        col1, col2 = st.columns([6,6])
        with col1:
            load_dotenv()
            API_KEY = os.getenv("GOOGLE_API_KEY")
        
            st.title("Gemini Chatbot")
            
            if not API_KEY:
                st.error("Google APIキーが設定されていません。環境変数 GOOGLE_API_KEY を設定してください。")
                st.warning("APIキーがないためチャット機能は停止していますが、3ページ目のタイマー機能はご利用いただけます。")
            else:
                client = genai.Client(api_key=API_KEY)
                MODEL_NAME = "gemini-2.5-flash"
            
                if "chat_log" not in st.session_state:
                    st.session_state.chat_log = []
                if "message" not in st.session_state:
                    st.session_state.message = []
                if "last_uploaded_file_id" not in st.session_state:
                    st.session_state.last_uploaded_file_id = None 
                    
                with st.sidebar:
                    st.header("ログの管理")
                    uploaded_file = st.file_uploader("過去のログ(JSON)を読み込む", type=["json"])
                    if (uploaded_file is not None and uploaded_file.file_id != st.session_state.last_uploaded_file_id):
                        try:
                            loaded_message = json.load(uploaded_file)
                            st.session_state.chat_log = loaded_message
                            st.success("ログを読み込みました")
                            st.session_state.last_uploaded_file_id = uploaded_file.file_id
                            st.rerun()
                        except json.JSONDecodeError:
                            st.error("JSONの読み込みに失敗しました。正しい形式のファイルを選択してください。")
            
                    json_data = json.dumps(st.session_state.chat_log, ensure_ascii=False, indent=2)
        
                    st.download_button(
                        label="チャットログをダウンロード",
                        data=json_data,
                        file_name="chat_log.json",
                        mime="application/json",
                    )

                for chat in st.session_state.chat_log:
                    with st.chat_message(chat["role"]):
                        st.markdown(chat["content"])

                user_msg = st.chat_input("ここにメッセージを入力")

                if user_msg:
                    with st.chat_message("user"):
                        st.markdown(user_msg)
                    st.session_state.chat_log.append({
                        "role": "user",
                        "content": user_msg
                    })

                    try:
                        contents = []
                        for msg in st.session_state.chat_log:
                            contents.append({
                                "role": msg["role"],
                                "parts": [{"text": msg["content"]}]
                            })

                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=contents
                        )
                        assistant_msg = response.text

                        with st.chat_message("model"):
                            st.markdown(assistant_msg)

                        st.session_state.chat_log.append({
                            "role": "model",
                            "content": assistant_msg
                        })

                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
    
        with col2:
            if "user_name" not in st.session_state:
                st.session_state["user_name"] = "ゲスト"
            value = st.session_state["sets"]
            st.write("セット数:", value)

            n = int(value) if str(value).isdigit() else 3
            with st.form("setting form"):
                for i in range(n):
                    st.text_input(f"{i+1}回目の目標:", key=f"user_goal{i}")
                
                sub = st.form_submit_button("設定を決定")

                if sub:
                    for j in range(n):
                        # ここは同じページ内なのでそのまま参照可能
                        st.write(f"{j+1}回目の目標: {st.session_state.get(f'user_goal{j}', '未入力')}")
    
    def render_third_page(self):
        st.sidebar.title("３ページ目")
        if st.sidebar.button("1ページ前に戻る"):
            st.session_state.timer_running = False
            self.switch_page(1)

        st.markdown("### 集中時間（作業中）")
        st.markdown(f"### 目標 {st.session_state['goal']}")
        
        cnt = st.session_state['cnt']
        # 【修正点2】リセットされてしまう「user_goal」ではなく、退避させた「saved_goal」から読み込む
        current_goal = st.session_state.get(f'saved_goal{cnt}', '未入力')
        st.markdown(f"**{cnt + 1}回目の作業**: {current_goal}")
        st.markdown(f"**現在のセット:** {cnt + 1} / {st.session_state['sets']} 回目")

        if st.session_state.get('prompt_break', False):
            st.warning("集中が切れているようです。休憩しますか？")
                
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                if st.button("休憩する（自動スタート）", type="primary", use_container_width=True):
                    st.session_state.prompt_break = False
                    st.session_state.timer_running = False
                    st.session_state.timer_running_break = True 
                    st.session_state.remaining_break = st.session_state['downtime'] * 60
                    self.switch_page(3) 
            with col_b2:
                if st.button("タイマーを再開し作業を継続する", use_container_width=True):
                    st.session_state.prompt_break = False
                    st.session_state.timer_running = True
                    st.session_state.last_seen = time.time()
                    st.rerun()
            return

        if not st.session_state.get('timer_running', False):
            if 'remaining' not in st.session_state or st.session_state.remaining <= 0:
                st.session_state.remaining = st.session_state['worktime'] * 60

            timer_placeholder = st.empty()
            rem = st.session_state.remaining
            timer_placeholder.markdown(
                f"<div class='main-timer'>{rem // 60:02d}:{rem % 60:02d}</div>", 
                unsafe_allow_html=True
            )

            if st.button("▶ タイマーをスタート"):
                st.session_state.timer_running = True
                st.session_state.last_seen = time.time()
                st.rerun()
        else:
            col_cam, col_empty = st.columns([1, 2])
            with col_cam:
                cam_placeholder = st.empty()
            timer_placeholder = st.empty()

            if st.button("一時停止"):
                st.session_state.timer_running = False
                st.rerun()

            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            cap = cv2.VideoCapture(0)
            last_timer_update = time.time()

            while st.session_state.remaining > 0 and st.session_state.timer_running:
                ret, frame = cap.read()
                if ret:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                    if len(faces) > 0:
                        st.session_state.last_seen = time.time()
                        for (x, y, w, h) in faces:
                            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 43, 43), 2)
                    
                    if time.time() - st.session_state.last_seen > 120:
                        st.session_state.timer_running = False
                        st.session_state.prompt_break = True
                        cap.release()
                        st.rerun()

                    cam_placeholder.image(frame, channels="BGR", width=300)

                current_time = time.time()
                elapsed = current_time - last_timer_update
                
                if elapsed >= 1.0:
                    deduct = int(elapsed)
                    st.session_state.remaining -= deduct
                    last_timer_update += deduct
                    
                    rem = max(0, st.session_state.remaining)
                    timer_placeholder.markdown(
                        f"<div class='main-timer'>{rem // 60:02d}:{rem % 60:02d}</div>",
                        unsafe_allow_html=True
                    )
                time.sleep(0.01)

            if cap.isOpened():
                cap.release()

            if st.session_state.remaining <= 0 and not st.session_state.get('prompt_break', False):
                st.session_state.timer_running = False
                st.session_state.timer_running_break = True
                st.session_state.remaining_break = st.session_state['downtime'] * 60
                self.switch_page(3)

    def render_fourth_page(self):
        st.sidebar.title("４ページ目")
        st.markdown("### 休憩時間")
        st.markdown(f"**現在のセット:** {st.session_state['cnt'] + 1} / {st.session_state['sets']} 回目")

        if st.sidebar.button("中断して戻る"):
            st.session_state.timer_running_break = False
            self.switch_page(1)

        if not st.session_state.get('timer_running_break', False):
            if 'remaining_break' not in st.session_state or st.session_state.remaining_break <= 0:
                st.session_state.remaining_break = st.session_state['downtime'] * 60

            timer_placeholder = st.empty()
            rem = st.session_state.remaining_break
            timer_placeholder.markdown(
                f"<div class='main-timer'>{rem // 60:02d}:{rem % 60:02d}</div>", 
                unsafe_allow_html=True
            )

            if st.button("▶ 休憩をスタート"):
                st.session_state.timer_running_break = True
                st.rerun()
        else:
            timer_placeholder = st.empty()

            if st.button("一時停止"):
                st.session_state.timer_running_break = False
                st.rerun()

            last_timer_update = time.time()

            while st.session_state.remaining_break > 0 and st.session_state.timer_running_break:
                current_time = time.time()
                elapsed = current_time - last_timer_update
                
                if elapsed >= 1.0:
                    deduct = int(elapsed)
                    st.session_state.remaining_break -= deduct
                    last_timer_update += deduct
                    
                    rem = max(0, st.session_state.remaining_break)
                    timer_placeholder.markdown(
                        f"<div class='break-timer'>{rem // 60:02d}:{rem % 60:02d}</div>",
                        unsafe_allow_html=True
                    )
                time.sleep(0.01)

            if st.session_state.remaining_break <= 0:
                st.session_state.timer_running_break = False
                st.session_state['cnt'] += 1
                
                if st.session_state['cnt'] >= st.session_state['sets']:
                    self.switch_page(4)
                else:
                    st.session_state.remaining = st.session_state['worktime'] * 60
                    st.session_state.timer_running = True
                    st.session_state.last_seen = time.time()
                    self.switch_page(2) 
    
    def render_fifth_page(self):
        st.sidebar.title("５ページ目")
        st.markdown("### 全てのセット数が完了しました！")
        st.markdown("### お疲れ様でした！")
        
        if st.button("最初に戻る"):
            st.session_state['cnt'] = 0
            self.switch_page(0)

    def run(self):
        with st.container():
            if st.session_state["page_control"] == 0:
                self.render_main_page()
            elif st.session_state["page_control"] == 1:
                self.render_second_page()
            elif st.session_state["page_control"] == 2:
                self.render_third_page()
            elif st.session_state["page_control"] == 3:
                self.render_fourth_page()
            elif st.session_state["page_control"] == 4:
                self.render_fifth_page()

if __name__ == "__main__":
    app = PomodoroApp()
    app.run()
