"""
Streamlit application for generating attractive messages for dating app users.

This module provides the main application interface using separated components.
"""

import streamlit as st

from config import Config
from message_generator import MessageGenerator
from profile_scraper import HealmateProfileScraper
from ui_components import MessageGenUI


def main():
    """Main application function."""
    # Validate configuration
    if not Config.validate():
        st.error("設定エラー：OpenAI API キーが設定されていません。")
        st.stop()

    # Initialize UI
    ui = MessageGenUI()
    ui.render_header()

    # Get user inputs
    target_url, interest_txt, execute_button = ui.render_input_form()

    if execute_button:
        ui.show_divider()

        # Validate input
        if not target_url:
            ui.show_error("ＵＲＬを入力してから「実行」ボタンを押してください。")
            st.stop()

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
                ui.show_result(generated_message)

            except Exception as e:
                ui.show_error(f"エラーが発生しました：{str(e)}")
                print(f"Error: {e}")  # For debugging


if __name__ == "__main__":
    main()
