import streamlit as st
from time import sleep
import os
from google import genai
from dotenv import load_dotenv

class PomodoroApp:
    """アプリの画面表示と状態遷移を管理するクラス"""

    def __init__(self):
        self.setup_session_state()

    def setup_session_state(self):
        # ページ管理用の変数をセッションに登録
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
            
        # 【追加】タイマー開始前に画面を綺麗にするためのフラグ
        if "timer_ready" not in st.session_state:
            st.session_state["timer_ready"] = False

    def switch_page(self, page_id):
        # ページを切り替えるメソッド（ここでst.rerun()をまとめることでコードがスッキリします）
        st.session_state["page_control"] = page_id
        st.session_state["timer_ready"] = False # ページ移動時は必ずフラグをリセット
        st.rerun()

    def render_main_page(self):
        """1ページ目（設定画面）の表示"""
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
            </style>
            """,
            unsafe_allow_html=True
        )

        st.sidebar.title("１ページ目")
        
        # switch_page の中に st.rerun() を入れたので、ここはシンプルに書けます
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
                st.success("設定を更新しました！")

        st.markdown("### 現在の設定内容")
        st.markdown(f"**目標:** {st.session_state['goal']}")
        st.markdown(f"**作業時間:** {st.session_state['worktime']} 分")
        st.markdown(f"**休憩時間:** {st.session_state['downtime']} 分")
        st.markdown(f"**セット数:** {st.session_state['sets']} セット")

    def render_second_page(self):
        """2ページ目の表示"""
        st.sidebar.title("２ページ目")
        st.markdown("### ２ページ目（チャット画面）")
        
        if st.sidebar.button("3ページ目へ"): 
            self.switch_page(2)

        if st.sidebar.button("1ページ前に戻る"):
            self.switch_page(0)

        load_dotenv()
        API_KEY = st.secrets.get("GOOGLE_API_KEY", os.getenv("GOOGLE_API_KEY"))
        
        if not API_KEY:
            st.error("Google APIキーが設定されていません。環境変数 GOOGLE_API_KEY を設定してください。")
            st.stop()
            
        client = genai.Client(api_key=API_KEY)
        MODEL_NAME = "gemini-2.5-flash"

        st.title("Gemini Chatbot")

        if "chat_log" not in st.session_state:
            st.session_state.chat_log = []

        for chat in st.session_state.chat_log:
            with st.chat_message(chat["role"]):
                st.markdown(chat["content"])

        user_msg = st.chat_input("ここにメッセージを入力", key="chat_input_page2")

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
                st.rerun()

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
    
    def render_third_page(self):
        """3ページ目の表示"""
        st.sidebar.title("３ページ目")
        if st.sidebar.button("2ページ目（チャット）に戻る"):
            self.switch_page(1)

        st.markdown("### 集中時間（作業中）")
        st.markdown(f"**現在のセット:** {st.session_state['cnt'] + 1} / {st.session_state['sets']} 回目")

        # 【超重要】タイマーの無限ループに入る前に、一度だけ強制的に再描画させる
        # これによりテキストボックスが完全に消滅します
        if not st.session_state["timer_ready"]:
            st.session_state["timer_ready"] = True
            sleep(0.1)  # 画面リセットのためのごくわずかな待機
            st.rerun()

        timer_placeholder = st.empty()
        progress_bar = st.progress(0)

        def work_timer(minutes):
            total_seconds = minutes * 60
            
            for i in range(total_seconds, -1, -1):
                if st.session_state["page_control"] != 2:
                    return False
                
                mins, secs = divmod(i, 60)
                time_format = f"{mins:02d}:{secs:02d}"
                
                timer_placeholder.markdown(
                    f"<h1 style='text-align: center; font-size: 80px; color: text;'>{time_format}</h1>", 
                    unsafe_allow_html=True
                )
                
                if total_seconds > 0:
                    progress_bar.progress(1.0 - (i / total_seconds))
                
                if i > 0:
                    sleep(1)
                    
            return True

        # タイマー完了後、次のページへ
        if work_timer(st.session_state['worktime']):
            self.switch_page(3)

    def render_fourth_page(self):
        """4ページ目の表示"""
        st.sidebar.title("４ページ目")
        st.markdown("### 休憩時間")
        st.markdown(f"**現在のセット:** {st.session_state['cnt'] + 1} / {st.session_state['sets']} 回目")
        
        if st.sidebar.button("中断して戻る"):
            self.switch_page(2)

        # 【超重要】ここでもタイマー前に再描画させて画面をリセット
        if not st.session_state["timer_ready"]:
            st.session_state["timer_ready"] = True
            sleep(0.1)
            st.rerun()

        timer_placeholder = st.empty()
        progress_bar = st.progress(0)

        def downtime_timer(minutes):
            total_seconds = minutes * 60

            for i in range(total_seconds, -1, -1):
                if st.session_state["page_control"] != 3:
                    return False
                mins, secs = divmod(i, 60)
                time_format = f"{mins:02d}:{secs:02d}"

                timer_placeholder.markdown(
                    f"<h1 style='text-align: center; font-size: 80px; color: text;'>{time_format}</h1>", 
                    unsafe_allow_html=True
                )

                if total_seconds > 0:
                    progress_bar.progress(1.0 - (i / total_seconds))
                
                if i > 0:
                    sleep(1)

            return True
        
        if downtime_timer(st.session_state['downtime']):
            st.session_state['cnt'] = st.session_state['cnt'] + 1
            if st.session_state['cnt'] == st.session_state['sets']:
                self.switch_page(4)
            else:
                self.switch_page(2)
    
    def render_fifth_page(self):
        st.sidebar.title("５ページ目")
        st.markdown("### 全てのセット数が完了しました！")
        st.markdown("### お疲れ様でした！")
        
        # 終了後に最初に戻れるボタンを追加
        if st.button("最初に戻る"):
            st.session_state['cnt'] = 0
            self.switch_page(0)

    def run(self):
        """現在の状態に応じて、表示する画面を振り分ける"""
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
