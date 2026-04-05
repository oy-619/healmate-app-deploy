"""
UI components for the Healmate message generation app.

This module contains all Streamlit UI components and layout definitions.
"""

import streamlit as st
import streamlit.components.v1 as components


class MessageGenUI:
    """UI components for message generation app."""

    @staticmethod
    def render_header():
        """Render the application header."""
        st.markdown("## 💌 いいね付きメッセージ自動生成アプリ")
        st.markdown("---")

    @staticmethod
    def render_two_column_layout():
        """
        Create two-column layout for website display and input form.

        Returns:
            tuple: (left_column, right_column) - Streamlit column objects
        """
        # Create two columns with equal width
        left_col, right_col = st.columns([1, 1])
        return left_col, right_col

    @staticmethod
    def render_website_display(column, url: str = None, session_cookies: dict = None):
        """
        Render website display in the specified column.

        Args:
            column: Streamlit column object
            url (str, optional): URL to display (if None, shows Healmate homepage)
            session_cookies (dict, optional): Session cookies for authentication
        """
        with column:
            st.subheader("🌐 ヒールメイト")

            # Determine which URL to display
            display_url = url if url else "https://healmate.jp/"
            url_title = f"プロフィール: {url}" if url else "公式ホームページ"

            # Warning about iframe login limitations
            st.warning(
                "⚠️ **ログイン制限について**\n"
                "セキュリティポリシーにより、iframe内でのログインはできません。\n"
                "下のボタンから新しいタブでヒールメイトにアクセスしてください。"
            )

            # Button to open in new tab using st.link_button
            st.link_button(
                f"🔗 {url_title}を新しいタブで開く",
                url=display_url,
                use_container_width=True,
                type="primary",
            )

            # Try to display the website in iframe
            try:
                # Add sandbox attributes to improve security and functionality
                iframe_html = f"""
                <div style="position: relative;">
                    <iframe 
                        src="{display_url}" 
                        width="100%" 
                        height="calc(100vh - 300px)" 
                        frameborder="0"
                        sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-top-navigation"
                        referrerpolicy="no-referrer-when-downgrade"
                        style="border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-height: 600px;">
                    </iframe>
                    <div style="
                        position: absolute;
                        top: 10px;
                        right: 10px;
                        background: rgba(255,255,255,0.9);
                        padding: 5px 10px;
                        border-radius: 5px;
                        font-size: 12px;
                        color: #666;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.2);
                    ">
                        📺 プレビュー表示
                    </div>
                </div>
                """
                components.html(iframe_html, height=650, scrolling=True)

                # Show current URL info and instructions
                st.caption(f"📍 表示中: {url_title}")
                st.info(
                    "💡 **使用方法**: プロフィール閲覧はこちらで可能です。ログインが必要な操作は「新しいタブで開く」をご利用ください。"
                )

            except Exception as e:
                st.error(f"サイト表示エラー: {str(e)}")
                st.info("セキュリティ制限により、iframe表示できません。")

                # Fallback: Show clickable link
                st.markdown(f"**{url_title}:** [{display_url}]({display_url})")

                # Show fallback message with better instructions
                fallback_html = f"""
                <div style="
                    height: 400px;
                    border: 2px solid #f39c12; 
                    border-radius: 8px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background-color: #fef9e7;
                    color: #b7950b;
                    font-size: 16px;
                    text-align: center;
                    line-height: 1.5;
                ">
                    <div>
                        <div style="font-size: 48px; margin-bottom: 20px;">🔒</div>
                        <div><strong>iframe表示制限</strong></div>
                        <div style="margin-top: 10px; font-size: 14px;">
                            上記の「新しいタブで開く」ボタンまたは<br>
                            下記リンクをクリックしてご利用ください
                        </div>
                    </div>
                </div>
                """
                components.html(fallback_html, height=420, scrolling=False)

    @staticmethod
    def render_input_form_in_column(column):
        """
        Render the input form in the specified column.

        Args:
            column: Streamlit column object

        Returns:
            tuple: (target_url, interest_txt, execute_button)
        """
        with column:
            st.subheader("📝 メッセージ生成設定")

            # URL input section with clipboard functionality
            st.markdown("**女性のプロフィールＵＲＬ**")

            # Create columns for URL input and clipboard button
            url_col1, url_col2 = st.columns([3, 1])

            with url_col1:
                target_url = st.text_input(
                    label="女性のプロフィールＵＲＬを入力してください。",
                    placeholder="https://healmate.jp/profile/...",
                    label_visibility="collapsed",
                )

            with url_col2:
                if st.button(
                    "📋\nURL\n貼付",
                    key="paste_url_btn",
                    help="クリップボードからURLを貼り付け",
                ):
                    # Use streamlit experimental user info to handle clipboard
                    st.info(
                        "📋 **クリップボード機能**\n\n"
                        "**自動貼り付け手順:**\n"
                        "1. 新しいタブでプロフィールページを開く\n"
                        "2. アドレスバーのURLを全選択してコピー (Ctrl+C)\n"
                        "3. この入力欄をクリックしてペースト (Ctrl+V)\n\n"
                        "または下記の手動入力欄をご利用ください ↓"
                    )

                # Manual URL input as fallback
                manual_url = st.text_input(
                    "手動でURLを入力/貼り付け:",
                    key="manual_url_input",
                    placeholder="Ctrl+V でURLを貼り付け",
                    label_visibility="visible",
                )

                if manual_url and manual_url != target_url:
                    if st.button("✅ このURLを使用", key="use_manual_url"):
                        st.session_state.target_url_override = manual_url
                        st.success("✅ URLが更新されました！")

            # Override target_url if manual input is used
            if (
                'target_url_override' in st.session_state
                and st.session_state.target_url_override
            ):
                target_url = st.session_state.target_url_override
                st.success(
                    f"🎯 **使用中のURL:** {target_url[:60]}{'...' if len(target_url) > 60 else ''}"
                )
                if st.button("🗑️ URL をクリア", key="clear_url"):
                    st.session_state.target_url_override = None
                    st.rerun()

            interest_txt = st.text_area(
                label="深堀したい内容を入力してください。",
                placeholder="例: 趣味について、価値観について、ライフスタイルについて等",
                height=120,
            )

            # Add some styling to the button
            execute_button = st.button(
                "🚀 メッセージ生成実行", type="primary", use_container_width=True
            )

            return target_url, interest_txt, execute_button

    @staticmethod
    def render_input_form():
        """
        Render the input form (legacy method for backward compatibility).

        Returns:
            tuple: (target_url, interest_txt, execute_button)
        """
        target_url = st.text_input(
            label="女性のプロフィールＵＲＬを入力してください。",
            placeholder="https://healmate.jp/profile/...",
        )
        interest_txt = st.text_area(
            label="深堀したい内容を入力してください。",
            placeholder="例: 趣味について、価値観について、ライフスタイルについて等",
        )
        execute_button = st.button("実行")

        return target_url, interest_txt, execute_button

    @staticmethod
    def show_error(message: str):
        """
        Show error message.

        Args:
            message (str): Error message to display
        """
        st.error(message)

    @staticmethod
    def show_divider():
        """Show a divider."""
        st.divider()

    @staticmethod
    def show_result(result: str):
        """
        Show the generated message result.

        Args:
            result (str): Generated message to display
        """
        st.write(result)

    @staticmethod
    def show_loading():
        """Show loading spinner."""
        return st.spinner("メッセージを生成中...")
