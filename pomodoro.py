import json
import os
import time
from dotenv import load_dotenv
from google import genai
import streamlit as st
from streamlit_autorefresh import st_autorefresh


@st.cache_resource
def get_gemini_client():
    """APIクライアントの初期化を1回だけにキャッシュする"""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    return None


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
        if "remaining" not in st.session_state:
            st.session_state["remaining"] = 0
        if "target_time" not in st.session_state:
            st.session_state["target_time"] = 0

        if "timer_running_break" not in st.session_state:
            st.session_state["timer_running_break"] = False
        if "remaining_break" not in st.session_state:
            st.session_state["remaining_break"] = 0
        if "target_time_break" not in st.session_state:
            st.session_state["target_time_break"] = 0

    def switch_page(self, page_id):
        st.session_state["page_control"] = page_id
        st.rerun()

    def render_main_page(self):
        # １ページ目 (page_control == 0)
        st.sidebar.title("１ページ目")
        if st.sidebar.button("2ページ目へ"):
            self.switch_page(1)

        st.title("Pomodoro Timer")

        with st.form("setting_form"):
            st.header("タイマー設定")
            goal_input = st.text_input(
                "今回の目標", value=st.session_state["goal"]
            )
            worktime_input = st.number_input(
                "作業時間 (分)", min_value=1, value=st.session_state["worktime"]
            )
            downtime_input = st.number_input(
                "休憩時間 (分)", min_value=1, value=st.session_state["downtime"]
            )
            sets_input = st.number_input(
                "セット数", min_value=1, value=st.session_state["sets"]
            )

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
        # ２ページ目 (page_control == 1)
        st.sidebar.title("２ページ目")

        if st.sidebar.button(
            "3ページ目へ（タイマースタート）", type="primary"
        ):
            for i in range(st.session_state["sets"]):
                goal_text = st.session_state.get(f"user_goal{i}", "")
                st.session_state[f"saved_goal{i}"] = (
                    goal_text if goal_text != "" else "未入力"
                )

            st.session_state.timer_running = True
            st.session_state.remaining = st.session_state["worktime"] * 60
            st.session_state.target_time = (
                time.time() + st.session_state.remaining
            )
            self.switch_page(2)

        if st.sidebar.button("1ページ前に戻る"):
            self.switch_page(0)

        st.sidebar.markdown("---")

        # APIクライアントの取得
        client = get_gemini_client()
        MODEL_NAME = "gemini-2.5-flash"

        if "chat_log" not in st.session_state:
            st.session_state.chat_log = []
        if "last_uploaded_file_id" not in st.session_state:
            st.session_state.last_uploaded_file_id = None

        # --- サイドバー管理 ---
        if client:
            st.sidebar.header("ログの管理")
            uploaded_file = st.sidebar.file_uploader(
                "過去のログ(JSON)を読み込む", type=["json"]
            )
            if (
                uploaded_file is not None
                and uploaded_file.file_id
                != st.session_state.last_uploaded_file_id
            ):
                try:
                    loaded_message = json.load(uploaded_file)
                    st.session_state.chat_log = loaded_message
                    st.sidebar.success("ログを読み込みました")
                    st.session_state.last_uploaded_file_id = (
                        uploaded_file.file_id
                    )
                    st.rerun()
                except json.JSONDecodeError:
                    st.sidebar.error(
                        "JSONの読み込みに失敗しました。正しい形式のファイルを選択してください。"
                    )

            st.sidebar.download_button(
                label="チャットログをダウンロード",
                data=json.dumps(
                    st.session_state.chat_log, ensure_ascii=False, indent=2
                ),
                file_name="chat_log.json",
                mime="application/json",
            )

        # --- メイン画面レイアウト ---
        col1, col2 = st.columns([6, 6])

        with col1:
            st.title("Gemini Chatbot")

            if not client:
                st.error(
                    "Google APIキーが設定されていません。環境変数 GOOGLE_API_KEY を設定してください。"
                )
                st.warning(
                    "APIキーがないためチャット機能は停止していますが、3ページ目のタイマー機能はご利用いただけます。"
                )
            else:
                for chat in st.session_state.chat_log:
                    with st.chat_message(chat["role"]):
                        st.markdown(chat["content"])

                user_msg = st.chat_input("ここにメッセージを入力")

                if user_msg:
                    with st.chat_message("user"):
                        st.markdown(user_msg)
                    st.session_state.chat_log.append(
                        {"role": "user", "content": user_msg}
                    )

                    try:
                        contents = [
                            {
                                "role": msg["role"],
                                "parts": [{"text": msg["content"]}],
                            }
                            for msg in st.session_state.chat_log
                        ]

                        response_stream = (
                            client.models.generate_content_stream(
                                model=MODEL_NAME, contents=contents
                            )
                        )

                        def stream_parser(stream):
                            for chunk in stream:
                                if chunk.text:
                                    yield chunk.text

                        with st.chat_message("model"):
                            assistant_msg = st.write_stream(
                                stream_parser(response_stream)
                            )

                        st.session_state.chat_log.append(
                            {"role": "model", "content": assistant_msg}
                        )

                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")

        with col2:
            if "user_name" not in st.session_state:
                st.session_state["user_name"] = "ゲスト"
            value = st.session_state["sets"]
            st.write("セット数:", value)

            n = int(value) if str(value).isdigit() else 3
            with st.form("setting_form_page2"):
                for i in range(n):
                    st.text_input(f"{i+1}回目の目標:", key=f"user_goal{i}")

                sub = st.form_submit_button("設定を決定")

                if sub:
                    for j in range(n):
                        st.write(
                            f"{j+1}回目の目標: {st.session_state.get(f'user_goal{j}', '未入力')}"
                        )

    def render_third_page(self):
        # ３ページ目 (page_control == 2)
        st.sidebar.title("３ページ目")
        if st.sidebar.button("1ページ前に戻る"):
            st.session_state.timer_running = False
            self.switch_page(1)

        spacer_left, center_col, spacer_right = st.columns([1, 2, 1])

        with center_col:
            st.markdown(
                "<h3 style='text-align: center;'>集中時間（作業中）</h3>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<h3 style='text-align: center;'>目標: {st.session_state['goal']}</h3>",
                unsafe_allow_html=True,
            )

            cnt = st.session_state["cnt"]
            current_goal = st.session_state.get(f"saved_goal{cnt}", "未入力")
            st.markdown(
                f"<p style='text-align: center; font-size: 18px;'><b>{cnt + 1}回目の作業</b>: {current_goal}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='text-align: center; font-size: 18px;'><b>現在のセット:</b> {cnt + 1} / {st.session_state['sets']} 回目</p>",
                unsafe_allow_html=True,
            )

            # タイマー停止中の表示
            if not st.session_state.get("timer_running", False):
                rem = st.session_state.get(
                    "remaining", st.session_state["worktime"] * 60
                )
                st.markdown(
                    f"<div class='main-timer'>{rem // 60:02d}:{rem % 60:02d}</div>",
                    unsafe_allow_html=True,
                )

                if st.button("▶ タイマーをスタート", use_container_width=True):
                    st.session_state.timer_running = True
                    st.session_state.target_time = (
                        time.time() + st.session_state.remaining
                    )
                    st.rerun()

            # タイマー動作中（st_autorefreshにより1秒ごとに再描画）
            else:
                st_autorefresh(interval=1000, key="work_timer_autorefresh")

                if st.button("一時停止", use_container_width=True):
                    st.session_state.timer_running = False
                    st.rerun()

                now = time.time()
                rem = max(0, int(st.session_state.target_time - now))
                st.session_state.remaining = rem

                st.markdown(
                    f"<div class='main-timer'>{rem // 60:02d}:{rem % 60:02d}</div>",
                    unsafe_allow_html=True,
                )

                # 完了判定
                if rem <= 0:
                    st.session_state.timer_running = False
                    st.session_state.timer_running_break = True
                    st.session_state.remaining_break = (
                        st.session_state["downtime"] * 60
                    )
                    st.session_state.target_time_break = (
                        time.time() + st.session_state.remaining_break
                    )
                    self.switch_page(3)

    def render_fourth_page(self):
        # ４ページ目 (page_control == 3)
        st.sidebar.title("４ページ目")

        if st.sidebar.button("中断して戻る"):
            st.session_state.timer_running_break = False
            self.switch_page(1)

        spacer_left, center_col, spacer_right = st.columns([1, 2, 1])

        with center_col:
            st.markdown(
                "<h3 style='text-align: center;'>休憩時間</h3>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='text-align: center; font-size: 18px;'><b>現在のセット:</b> {st.session_state['cnt'] + 1} / {st.session_state['sets']} 回目</p>",
                unsafe_allow_html=True,
            )

            # 休憩タイマー停止中
            if not st.session_state.get("timer_running_break", False):
                rem = st.session_state.get(
                    "remaining_break", st.session_state["downtime"] * 60
                )
                st.markdown(
                    f"<div class='break-timer'>{rem // 60:02d}:{rem % 60:02d}</div>",
                    unsafe_allow_html=True,
                )

                if st.button("▶ 休憩をスタート", use_container_width=True):
                    st.session_state.timer_running_break = True
                    st.session_state.target_time_break = (
                        time.time() + st.session_state.remaining_break
                    )
                    st.rerun()

            # 休憩タイマー動作中
            else:
                st_autorefresh(interval=1000, key="break_timer_autorefresh")

                if st.button("一時停止", use_container_width=True):
                    st.session_state.timer_running_break = False
                    st.rerun()

                now = time.time()
                rem = max(0, int(st.session_state.target_time_break - now))
                st.session_state.remaining_break = rem

                st.markdown(
                    f"<div class='break-timer'>{rem // 60:02d}:{rem % 60:02d}</div>",
                    unsafe_allow_html=True,
                )

                # 完了判定
                if rem <= 0:
                    st.session_state.timer_running_break = False
                    st.session_state["cnt"] += 1

                    if st.session_state["cnt"] >= st.session_state["sets"]:
                        self.switch_page(4)
                    else:
                        st.session_state.remaining = (
                            st.session_state["worktime"] * 60
                        )
                        st.session_state.target_time = (
                            time.time() + st.session_state.remaining
                        )
                        st.session_state.timer_running = True
                        self.switch_page(2)

    def render_fifth_page(self):
        # ５ページ目 (page_control == 4)
        st.sidebar.title("５ページ目")
        st.markdown("### 全てのセット数が完了しました！")
        st.markdown("### お疲れ様でした！")

        if st.button("最初に戻る"):
            st.session_state["cnt"] = 0
            self.switch_page(0)

    def run(self):
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
            .main-timer { font-size: 200px; font-weight: bold; color: #87CEFA; text-align: center; line-height: 1.1; margin-bottom: 20px;}
            .break-timer { font-size: 200px; font-weight: bold; color: #99EE90; text-align: center; line-height: 1.1; margin-bottom: 20px;}
            </style>
            """,
            unsafe_allow_html=True,
        )

        current_page = st.session_state["page_control"]
        main_container = st.empty()

        with main_container.container(key=f"page_container_{current_page}"):
            if current_page == 0:
                self.render_main_page()
            elif current_page == 1:
                self.render_second_page()
            elif current_page == 2:
                self.render_third_page()
            elif current_page == 3:
                self.render_fourth_page()
            elif current_page == 4:
                self.render_fifth_page()


if __name__ == "__main__":
    app = PomodoroApp()
    app.run()
