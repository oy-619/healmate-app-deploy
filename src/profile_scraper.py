"""
Web scraping functionality for Healmate profiles.

This module handles all web scraping operations including login and profile extraction.
"""

from typing import List, Tuple

import requests
from bs4 import BeautifulSoup


class HealmateProfileScraper:
    """Scraper for Healmate dating app profiles."""

    def __init__(self):
        self.session = requests.Session()
        self.login_url = "https://healmate.jp/login"
        self.my_profile_url = (
            "https://my.healmate.jp/detail?" "code=iz3v8aswptmuunp&backpage=profile"
        )
        self.profile_selector = (
            "p.detailNickname, p.detailText, div.detailFlaxBetween, "
            "div.detailNickname, div.detailTitle, div.detailText"
        )

    def login(self, email: str, password: str) -> bool:
        """
        Login to Healmate.

        Args:
            email (str): Login email
            password (str): Login password

        Returns:
            bool: True if login successful, False otherwise
        """
        try:
            # Get login page and extract token
            res = self.session.get(self.login_url)
            soup = BeautifulSoup(res.text, "html.parser")
            token_element = soup.find("input", {"name": "token"})

            if not token_element:
                return False

            token = token_element.get("value")

            # Submit login form
            payload = {"id": email, "pass": password, "token": token}
            login_response = self.session.post(self.login_url, data=payload)

            # Simple check for successful login (you may need to adjust this)
            return login_response.status_code == 200

        except Exception as e:
            print(f"Login failed: {e}")
            return False

    def extract_target_profile(self, target_url: str) -> Tuple[str, str, str]:
        """
        Extract target user's profile information.

        Args:
            target_url (str): URL of the target profile

        Returns:
            Tuple[str, str, str]: (nickname, introduction, full_profile_text)
        """
        try:
            res = self.session.get(target_url)
            soup = BeautifulSoup(res.text, "html.parser")

            # Extract nickname
            nickname_elements = soup.select("p.detailNickname")
            nickname = (
                nickname_elements[0].get_text(strip=True) if nickname_elements else ""
            )

            # Extract self-introduction
            introduction = self._extract_introduction(soup)

            # Extract full profile text
            profile_elements = soup.select(self.profile_selector)
            full_profile = "\n".join(
                [el.get_text(strip=True) for el in profile_elements]
            )

            return nickname, introduction, full_profile

        except Exception as e:
            print(f"Profile extraction failed: {e}")
            return "", "", ""

    def extract_my_profile(self) -> Tuple[str, str]:
        """
        Extract current user's profile information.

        Returns:
            Tuple[str, str]: (nickname, full_profile_text)
        """
        try:
            res = self.session.get(self.my_profile_url)
            soup = BeautifulSoup(res.text, "html.parser")

            # Extract nickname
            nickname_elements = soup.select("p.detailNickname")
            nickname = (
                nickname_elements[0].get_text(strip=True) if nickname_elements else ""
            )

            # Extract full profile text
            profile_elements = soup.select(self.profile_selector)
            full_profile = "\n".join(
                [el.get_text(strip=True) for el in profile_elements]
            )

            return nickname, full_profile

        except Exception as e:
            print(f"My profile extraction failed: {e}")
            return "", ""

    def _extract_introduction(self, soup: BeautifulSoup) -> str:
        """
        Extract self-introduction text from profile.

        Args:
            soup (BeautifulSoup): Parsed HTML content

        Returns:
            str: Introduction text
        """
        titles = soup.select("div.detailTitle")
        for title in titles:
            if title.get_text(strip=True) == "自己紹介":
                # Find next sibling element
                next_elem = title.find_next_sibling()
                while next_elem:
                    if next_elem.name == "p" and "detailText" in next_elem.get(
                        "class", []
                    ):
                        return next_elem.get_text(strip=True)
                    next_elem = next_elem.find_next_sibling()
                break
        return ""
