"""
Streamlit application for generating attractive messages for dating app users.

This module provides the main application interface using separated components
with a two-column layout for website display and input form.
"""

import streamlit as st

from config import Config
from message_generator import MessageGenerator
from profile_scraper import HealmateProfileScraper
from ui_components import MessageGenUI

# Configure page to use wide layout and hide menu
st.set_page_config(
    page_title="ヒールメイト メッセージ生成",
    page_icon="💌",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={'Get help': None, 'Report a Bug': None, 'About': None},
)

# Custom CSS to maximize display area
st.markdown(
    """
<style>
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    header {visibility: hidden;}
    
    /* Reduce padding and margins */
    .main .block-container {
        padding-top: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
        max-width: 100%;
    }
    
    /* Make columns take full width */
    .stColumn {
        padding: 0 0.5rem;
    }
    
    /* Adjust text input and text area */
    .stTextInput > div > div > input {
        background-color: #f8f9fa;
    }
    
    .stTextArea > div > div > textarea {
        background-color: #f8f9fa;
        min-height: 120px;
    }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    """Main application function."""
    # Validate configuration
    if not Config.validate():
        st.error("設定エラー：OpenAI API キーが設定されていません。")
        st.stop()

    # Initialize UI
    ui = MessageGenUI()
    ui.render_header()

    # Create two-column layout
    left_col, right_col = ui.render_two_column_layout()

    # Initialize URL state
    if 'current_url' not in st.session_state:
        st.session_state.current_url = None

    # Render input form in right column
    target_url, interest_txt, execute_button = ui.render_input_form_in_column(right_col)

    # Update URL state and render website display in left column
    if target_url and target_url != st.session_state.current_url:
        st.session_state.current_url = target_url

    ui.render_website_display(left_col, st.session_state.current_url)

    if execute_button:
        ui.show_divider()

        # Validate input
        if not target_url:
            with right_col:
                ui.show_error("ＵＲＬを入力してから「実行」ボタンを押してください。")
            st.stop()

        # Show results in right column
        with right_col:
            # Show loading spinner
            with ui.show_loading():
                try:
                    # Initialize components
                    scraper = HealmateProfileScraper()
                    message_gen = MessageGenerator()

                    # Login to Healmate
                    login_success = scraper.login(
                        Config.HEALMATE_EMAIL, Config.HEALMATE_PASSWORD
                    )
                    if not login_success:
                        ui.show_error(
                            "ログインに失敗しました。認証情報を確認してください。"
                        )
                        st.stop()

                    # Extract profiles
                    target_nickname, target_introduction, target_profile = (
                        scraper.extract_target_profile(target_url)
                    )
                    if not target_nickname:
                        ui.show_error(
                            "プロフィール情報の取得に失敗しました。URLを確認してください。"
                        )
                        st.stop()

                    my_nickname, my_profile = scraper.extract_my_profile()
                    if not my_nickname:
                        ui.show_error("自分のプロフィール情報の取得に失敗しました。")
                        st.stop()

                    # Setup RAG system with profiles
                    documents = [target_profile, my_profile]
                    message_gen.setup_rag_system(documents)

                    # Analyze profiles
                    message_gen.analyze_profiles(target_nickname, my_nickname)

                    # Generate message
                    generated_message = message_gen.generate_message(
                        target_nickname, my_nickname, target_introduction, interest_txt
                    )

                    # Display result
                    st.subheader("💌 生成されたメッセージ")
                    ui.show_result(generated_message)

                except Exception as e:
                    ui.show_error(f"エラーが発生しました：{str(e)}")
                    print(f"Error: {e}")  # For debugging


if __name__ == "__main__":
    main()
