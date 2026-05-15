# -*- coding: utf-8 -*-
"""
WeChat Official Account Article Crawler - Core Module
Enhanced version: Supports users providing browser cookies → format conversion → automatic save to database → crawling
Process:
  1. First determine if user has provided browser cookies
  2. If not provided, check if database cookies have expired
  3. If expired, remind user to obtain browser cookies
  4. Convert browser cookies to database JSON format
  5. Finally crawl WeChat official account articles and statistics
"""
import time
import random
import re
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from config import EDGE_DRIVER_PATH
from db_operations import WeChatDB
from datetime import datetime

# Mobile WeChat UA
WECHAT_MOBILE_UA = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.52(0x1800342c) NetType/WIFI Language/zh_CN",
    "Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36 MMWEBID/1234 MicroMessenger/8.0.53.2560(0x28003538) Process/toolsmp WeChat/unknown NetType/WIFI Language/zh_CN",
]


class WeChatCrawler:
    def __init__(self, max_pages=5):
        self.db = WeChatDB()
        self.gzlist = self.db.get_crawl_tasks()
        if not self.gzlist:
            print("📌 No crawling tasks in database, default added: Megermite")
            self.db.add_task("Megermite")
            self.gzlist = ["Megermite"]
        self.session = requests.Session()
        self.max_pages = max_pages  # Maximum number of pages to get for each account (10 per page)
        self._user_cookies = None  # Cookies provided by user from browser
        self._user_token = None    # Token provided by user

    # ====================== New: User Provides Browser Cookies ======================

    def set_user_browser_cookies(self, browser_cookies_text, token=None, format_type='auto'):
        """
        Set cookies provided by user from browser.
        Automatically detect format and convert to database format, save to database for crawling.

        [Improved] token parameter is now optional, automatically extracted from WeChat platform if missing.

        Parameters:
            browser_cookies_text: str — Raw cookie text exported from browser
            token: str or None — Optional. Token obtained from WeChat platform URL,
                                 not provided then automatically extracted
            format_type: str — 'auto' | 'json_devtools' | 'netscape' | 'json_domain' | 'header_str'

        Returns:
            bool — Whether successful
        """
        from cookie_utils import convert_to_db_format, auto_extract_token

        try:
            print("🔄 Converting browser cookies to database format...")
            cookies_dict = convert_to_db_format(browser_cookies_text, format_type)
        except Exception as e:
            print(f"❌ Cookie conversion failed: {e}")
            print("💡 Please check if cookie format is correct, or retry with --cookie-json / --cookie-domain / --cookie-str parameter")
            return False

        if not cookies_dict:
            print("❌ Converted cookies are empty, please check input content")
            return False

        # Sync to requests session
        for k, v in cookies_dict.items():
            self.session.cookies.set(k, v)

        # ====== Automatic Token Extraction (if not provided) ======
        if not token:
            print("🔑 No token provided, attempting automatic extraction...")
            token = self.auto_extract_token()
            if not token:
                print("❌ Token automatic extraction failed")
                print("💡 Can manually provide --token parameter to retry")
                return False

        # Save to database
        self.db.save_cookie(cookies_dict, token)

        # Memory cache
        self._user_cookies = cookies_dict
        self._user_token = token

        print(f"✅ Browser cookies converted successfully and saved to database ({len(cookies_dict)} fields)")
        print(f"   Token: {token[:15]}...")
        return True

    # ====================== Automatic Token Extraction ======================

    def auto_extract_token(self):
        """Utilize loaded cookies in session to automatically extract token from WeChat platform."""
        from cookie_utils import auto_extract_token as _auto_extract
        return _auto_extract(self.session)

    # ====================== Quick API Availability Verification ======================

    def quick_validate(self, test_keyword="Renesas"):
        """
        Quickly verify if Cookie+Token is available.
        Test if API returns normal data by searching for an official account keyword.

        Parameters:
            test_keyword: str — Test keyword for search (default "Renesas")

        Returns:
            bool — Return True if verification passes
        """
        import random

        if not self._user_token:
            print("❌ Unable to verify: Missing token")
            return False

        headers = {
            "User-Agent": random.choice(WECHAT_MOBILE_UA),
            "Referer": "https://mp.weixin.qq.com/",
            "X-Requested-With": "XMLHttpRequest",
        }

        try:
            search_url = (
                f"https://mp.weixin.qq.com/cgi-bin/searchbiz"
                f"?action=search_biz&token={self._user_token}"
                f"&query={test_keyword}&begin=0&count=1&f=json"
            )
            res = self.session.get(search_url, headers=headers, timeout=10)
            data = res.json()

            ret_code = data.get("base_resp", {}).get("ret")
            if ret_code == 0:
                total = data.get("total", 0)
                print(f"✅ API verification passed! Found {total} related accounts")
                return True

            print(f"❌ API verification failed (ret={ret_code}): {data}")
            return False

        except Exception as e:
            print(f"❌ API verification exception: {e}")
            return False

    # ====================== Core: Login and Get Cookie (Retain Original Scan Method) ======================
    def weChat_login(self):
        """
        [Backup Plan] Open WeChat platform login page, wait for user to scan QR code to login
        Only used when user has not provided browser cookies and browser environment is available
        """
        print("🔐 Preparing to open WeChat platform login page...")

        # Configure browser options
        options = Options()
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--start-maximized")
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'user-agent={random.choice(WECHAT_MOBILE_UA)}')

        # Prioritize system installed chromedriver, fallback to cache/auto-download
        import glob, os
        chromedriver_path = None

        # 1. First try chromedriver in system path
        system_paths = [
            '/usr/bin/chromedriver',
            '/usr/local/bin/chromedriver',
            '/snap/bin/chromedriver',
        ]
        for path in system_paths:
            if os.path.exists(path):
                chromedriver_path = path
                print(f"✅ Found system ChromeDriver: {path}")
                break

        # 2. If system path doesn't have it, try cached latest version
        if not chromedriver_path:
            cached = glob.glob('/root/.cache/selenium/chromedriver/linux64/*/chromedriver')
            if cached:
                cached.sort(key=lambda p: os.path.basename(os.path.dirname(p)), reverse=True)
                chromedriver_path = cached[0]
                print(f"✅ Using cached ChromeDriver: {chromedriver_path}")

        # 3. If no cache either, auto download latest matching version
        if not chromedriver_path:
            print("📥 Downloading matching version of ChromeDriver...")
            from webdriver_manager.chrome import ChromeDriverManager
            chromedriver_path = ChromeDriverManager().install()

        driver = webdriver.Chrome(service=Service(chromedriver_path), options=options)

        try:
            # Open login page
            driver.get("https://mp.weixin.qq.com/")
            print("✅ Login page opened, please scan QR code to login...")

            # Wait for user to scan QR code and login (max 120 seconds)
            WebDriverWait(driver, 120).until(
                lambda d: 'token=' in d.current_url
            )

            # Get token
            current_url = driver.current_url
            token_match = re.search(r'token=(\d+)', current_url)
            token = token_match.group(1) if token_match else None

            if not token:
                print("❌ Failed to get token")
                return None, None

            print(f"✅ Login successful, Token: {token[:10]}...")

            # Get cookies and sync to session
            cookies = {}
            for c in driver.get_cookies():
                cookies[c['name']] = c['value']
                self.session.cookies.set(c['name'], c['value'])

            # Save to database
            self.db.save_cookie(cookies, token)

            return cookies, token

        except Exception as e:
            print(f"❌ Login failed: {e}")
            return None, None
        finally:
            driver.quit()

    # ====================== Check Cookie Validity ======================
    def check_cookie_valid(self, cookies, token=None):
        """Verify if cookie is valid"""
        actual_token = token or cookies.get('token')
        if not actual_token:
            return False
        try:
            url = f"https://mp.weixin.qq.com/cgi-bin/home?token={actual_token}"
            headers = {"User-Agent": random.choice(WECHAT_MOBILE_UA)}
            res = self.session.get(url, cookies=cookies, headers=headers, allow_redirects=False, timeout=10)
            return res.status_code == 200
        except:
            return False

    # ====================== Get Valid Cookie (New Process) ======================
    def get_valid_cookies_and_token(self):
        """
        Get valid cookies: New process

        Process:
          1. User has provided browser cookies via set_user_browser_cookies()? → Use directly
          2. Valid cookies in database? → Use
          3. Cookie expired or doesn't exist → Prompt user to get browser cookie, return None, None
        """
        # ====== Step 1: User has already provided browser cookies ======
        if self._user_cookies and self._user_token:
            print("✅ Using user-provided browser cookies")
            return self._user_cookies, self._user_token

        # ====== Step 2: Check if database has cookies ======
        if not self.db.has_cookie():
            print("📭 No cookies in database")
            self._print_cookie_reminder()
            return None, None

        # ====== Step 3: Get from database and verify ======
        cookies, token = self.db.get_latest_valid_cookie()
        if not cookies or not token:
            print("📭 Cookie data in database is incomplete")
            self._print_cookie_reminder()
            return None, None

        if self.check_cookie_valid(cookies, token):
            # Cookie valid, sync to session
            for k, v in cookies.items():
                self.session.cookies.set(k, v)
            print("✅ Using cached cookies from database (valid)")
            return cookies, token

        # ====== Step 4: Cookie has expired ======
        print("🔄 Cookie in database has expired")
        self._print_cookie_reminder()
        return None, None

    def _print_cookie_reminder(self):
        """Print guide for obtaining browser cookies"""
        from cookie_utils import print_cookie_help
        print("\n" + "=" * 60)
        print("🔔 Cookie unavailable — Please provide browser cookies")
        print("=" * 60)
        print(print_cookie_help())
        print("\n💡 Ways to provide (token will be automatically extracted, no manual provision needed):")
        print("   1) python3 run_crawler.py --cookie-json '[...]'")
        print("   2) python3 run_crawler.py --cookie-domain \"$(cat cookies.txt)\"")
        print("   3) python3 run_crawler.py --cookie-str 'name=value;...'")
        print("=" * 60)

    # ====================== Parse Article URL Parameters ======================
    def parse_article_url_params(self, article_url):
        """Parse biz, mid, idx, sn parameters from article URL"""
        article_url = article_url.replace('amp;', '')
        params = {}
        for key, pattern in [('biz', r'__biz=([^&]+)'), ('mid', r'mid=(\d+)'),
                             ('idx', r'idx=(\d+)'), ('sn', r'sn=([a-f0-9]+)')]:
            match = re.search(pattern, article_url)
            if match:
                params[key] = match.group(1)
        return params

    def extract_params_from_html(self, article_html):
        """Directly extract JS variables like biz, mid, idx, sn from article HTML"""
        params = {}
        for var_name in ['biz', 'mid', 'idx', 'sn']:
            # Match patterns like: var biz = 'xxx'; or var biz = "xxx";
            pattern = rf"var\s+{var_name}\s*=\s*[\"']([^\"']*)"
            match = re.search(pattern, article_html)
            if match:
                params[var_name] = match.group(1)
        return params

    # ====================== Get Article Basic Information ======================
    def get_article_base_info(self, article_url, login_cookies):
        """Get article raw HTML, extract comment_id and req_id"""
        headers = {
            "User-Agent": random.choice(WECHAT_MOBILE_UA),
            "Referer": "https://mp.weixin.qq.com/",
        }
        try:
            resp = self.session.get(article_url, cookies=login_cookies, headers=headers, timeout=25)
            resp.encoding = "utf-8"
            return resp.text
        except Exception as e:
            print(f"❌ Failed to get article info: {e}")
            return ""

    # ====================== Get Article Statistics ======================
    def get_article_stats(self, article_url, login_cookies, token):
        """Get article read count, like count, viewed count, share count"""
        url_params = self.parse_article_url_params(article_url)
        # Need at least biz, mid, idx; if sn is missing try to extract from page
        if not all(k in url_params for k in ['biz', 'mid', 'idx']):
            print(f"⚠️ Article URL missing critical parameters, trying to extract from HTML: {article_url[:80]}")
            # First get HTML, extract parameters from it
            article_html = self.get_article_base_info(article_url, login_cookies)
            if article_html:
                html_params = self.extract_params_from_html(article_html)
                for k in ['biz', 'mid', 'idx', 'sn']:
                    if k not in url_params and k in html_params:
                        url_params[k] = html_params[k]
                        print(f"    [INFO] Extracted {k} = {html_params[k][:20]} from HTML")
            if not all(k in url_params for k in ['biz', 'mid', 'idx']):
                print(f"❌ Still missing critical parameters (biz/mid/idx), skipping stats: {article_url[:80]}")
                return 0, 0, 0, 0

        if not url_params.get('sn'):
            print(f"⚠️ Article URL missing sn parameter: {article_url[:80]}")

        # Extract comment_id and req_id
        article_html = self.get_article_base_info(article_url, login_cookies)
        if not article_html:
            return 0, 0, 0, 0

        comment_id = re.search(r"var comment_id = '(.*?)';", article_html)
        comment_id = comment_id.group(1) if comment_id else ""

        req_id = ""
        if 'var req_id = ' in article_html:
            req_id_match = re.search(r"var req_id = '(.*?)';", article_html)
            req_id = req_id_match.group(1) if req_id_match else ""

        # Build request
        detail_url = (
            f"https://mp.weixin.qq.com/mp/getappmsgext?f=json&fasttmplajax=1"
            f"&uin={login_cookies.get('uin', '')}&key={login_cookies.get('key', '')}"
            f"&pass_ticket={login_cookies.get('pass_ticket', '')}&__biz={url_params['biz']}"
        )

        data = {
            'r': '0.' + ''.join([str(random.randint(0, 9)) for _ in range(16)]),
            'sn': url_params.get('sn', ''), 'mid': url_params['mid'], 'idx': url_params['idx'],
            'req_id': req_id, 'comment_id': comment_id, '__biz': url_params['biz'],
            'pass_ticket': login_cookies.get('pass_ticket', ''),
        }

        try:
            res = self.session.post(detail_url, data=data, cookies=login_cookies,
                                   headers={"User-Agent": random.choice(WECHAT_MOBILE_UA),
                                          "Referer": article_url}, timeout=15)
            res_json = json.loads(res.text)
            stats = res_json.get('appmsgstat', {})
            return (stats.get('read_num', 0), stats.get('like_num', 0) or stats.get('old_like_num', 0),
                    stats.get('show_read', 0), stats.get('share_num', 0))
        except Exception as e:
            print(f"❌ Failed to get stats: {e}")
            return 0, 0, 0, 0

    # ====================== Get Article Content ======================
    def get_article_content(self, article_url, login_cookies):
        """Extract article main content"""
        headers = {
            "User-Agent": random.choice(WECHAT_MOBILE_UA),
            "Referer": "https://mp.weixin.qq.com/",
        }
        try:
            resp = self.session.get(article_url, cookies=login_cookies, headers=headers, timeout=25)
            resp.encoding = "utf-8"
            soup = BeautifulSoup(resp.text, "html.parser")
            content_div = soup.find("div", class_="rich_media_content")
            if content_div:
                for tag in ["script", "style", "iframe", "img"]:
                    for x in content_div.find_all(tag):
                        x.decompose()
                return re.sub(r"\s+", " ", content_div.get_text().strip())
            return ""
        except Exception as e:
            print(f"❌ Failed to get content: {e}")
            return ""

    # ====================== Get Comments ======================
    def get_comments(self, article_url, login_cookies, token):
        """Get article comments"""
        url_params = self.parse_article_url_params(article_url)
        # Need at least mid, idx; if missing try to extract from HTML
        if not all(k in url_params for k in ['mid', 'idx']):
            article_html = self.get_article_base_info(article_url, login_cookies)
            if article_html:
                html_params = self.extract_params_from_html(article_html)
                for k in ['biz', 'mid', 'idx', 'sn']:
                    if k not in url_params and k in html_params:
                        url_params[k] = html_params[k]
            if not all(k in url_params for k in ['mid', 'idx']):
                return []

        try:
            url = "https://mp.weixin.qq.com/mp/appmsg_comment"
            params = {"action": "getcomment", "token": token, "limit": 100, **url_params}
            resp = self.session.get(url, params=params, cookies=login_cookies,
                                   headers={"User-Agent": random.choice(WECHAT_MOBILE_UA),
                                          "Referer": article_url}, timeout=10)
            data = resp.json()
            return data.get("published_comment", []) + data.get("top_comment", [])
        except Exception as e:
            print(f"❌ Failed to get comments: {e}")
            return []

    # ====================== Crawl Single Account ======================
    def get_content(self, query):
        """Crawl articles from specified account (supports pagination)"""
        cookies, token = self.get_valid_cookies_and_token()
        if not token:
            print("❌ Unable to get valid cookies and token, crawling aborted")
            return

        headers = {
            "User-Agent": random.choice(WECHAT_MOBILE_UA),
            "Referer": "https://mp.weixin.qq.com/",
            "X-Requested-With": "XMLHttpRequest"
        }

        # Prioritize getting fakeid and account_id from database cache to avoid searching every time
        account_info = self.db.get_account_info(query)
        if account_info:
            fakeid = account_info['fakeid']
            account_id = account_info['id']
            print(f"✅ Found account from cache: {query} (fakeid: {fakeid[:20]}...)")
        else:
            # Cache miss, search for account
            try:
                search_url = "https://mp.weixin.qq.com/cgi-bin/searchbiz"
                params = {"action": "search_biz", "token": token, "query": query, "begin": 0, "count": 5, "f": "json"}
                res = self.session.get(search_url, cookies=cookies, headers=headers, params=params).json()
                fakeid = res["list"][0]["fakeid"]
                account_id = self.db.save_account(query, fakeid)
                print(f"✅ Search found account: {query}")
            except Exception as e:
                print(f"❌ Account {query} not found: {e}")
                return

        # Paginate to get article list
        all_publish_list = []
        begin = 0
        page_size = 10
        max_pages = self.max_pages  # Max pages to get

        for page_num in range(max_pages):
            try:
                appmsg_url = "https://mp.weixin.qq.com/cgi-bin/appmsgpublish"
                data_params = {"sub": "list", "begin": begin, "count": page_size, "fakeid": fakeid,
                              "token": token, "sub_action": "list_ex", "f": "json"}
                data = self.session.get(appmsg_url, cookies=cookies, headers=headers, params=data_params).json()

                if data.get("base_resp", {}).get("ret") != 0:
                    print("❌ Login has expired, please provide browser cookies again")
                    self._print_cookie_reminder()
                    break

                publish_list = json.loads(data.get("publish_page", "{}")).get("publish_list", [])

                if not publish_list:
                    break  # No more articles

                all_publish_list.extend(publish_list)
                print(f"  📄 Page {page_num + 1}: Got {len(publish_list)}, cumulative {len(all_publish_list)}")

                # If returned less than page_size items, it's the last page
                if len(publish_list) < page_size:
                    break

                begin += page_size
                time.sleep(random.uniform(2, 4))  # Page flip interval

            except Exception as e:
                print(f"❌ Failed to get article list page {page_num + 1}: {e}")
                break

        print(f"📦 Total got {len(all_publish_list)} articles")

        # Process articles one by one
        processed_links = set()  # Deduplicate
        for item in all_publish_list:
            appmsgex = json.loads(item["publish_info"]).get("appmsgex", [])[:1]
            for art in appmsgex:
                title = art.get("title", "")
                link = art.get("link", "").replace('amp;', '')
                if not link:
                    continue

                # Duplicate check
                if link in processed_links:
                    continue
                processed_links.add(link)

                # Check if already exists
                existing = self.db.article_exists(link)
                if existing:
                    article_id = existing
                    print(f"\n⏭️ Already exists: {title}")
                    # Only update statistics (don't redownload content)
                    read_num, like_num, show_read, share_num = self.get_article_stats(link, cookies, token)
                    if read_num > 0 or like_num > 0:  # Only update if got valid data
                        self.db.save_article_stats(article_id, read_num, like_num, share_num, show_read)
                        print(f"   📊 [Updated] Reads:{read_num} Likes:{like_num} Views:{show_read} Shares:{share_num}")
                    continue

                print(f"\n📝 Crawling: {title}")

                # Get content, stats, comments
                content = self.get_article_content(link, cookies)
                read_num, like_num, show_read, share_num = self.get_article_stats(link, cookies, token)
                comments = self.get_comments(link, cookies, token)

                print(f"   📊 Reads:{read_num} Likes:{like_num} Views:{show_read} Shares:{share_num} Comments:{len(comments)}")

                # Save to database
                article_id = self.db.save_article(account_id, title, art.get("create_time", 0), link, content)
                self.db.save_article_stats(article_id, read_num, like_num, share_num, show_read)

                for c in comments:
                    nick = c.get("nick_name", "")
                    c_content = c.get("content", "")
                    ctime = datetime.fromtimestamp(c.get("createtime", 0))
                    self.db.save_comment(article_id, nick, c_content, ctime, 0)

            time.sleep(random.uniform(1, 3))  # Random delay to prevent blocking

    # ====================== Main Run ======================
    def run(self, skip_validate=False):
        """
        Run crawler.

        When new cookies provided via set_user_browser_cookies():
          → Automatically execute quick_validate() simple validation
          → After validation, crawl all accounts

        Parameters:
            skip_validate: bool — If True, skip API validation (for scenarios where database already has cookies)
        """
        try:
            # ====== User provided new cookies: validate first ======
            if self._user_cookies and not skip_validate:
                print(f"\n🔍 Verifying cookie and token availability...")
                if not self.quick_validate():
                    print("❌ API validation failed, cookies may have expired")
                    self._print_cookie_reminder()
                    return

            # ====== Load crawling tasks ======
            if not self.gzlist:
                self.gzlist = self.db.get_crawl_tasks()
            if not self.gzlist:
                print("📌 No crawling tasks in database, default added: Megermite")
                self.db.add_task("Megermite")
                self.gzlist = ["Megermite"]

            print(f"\n🚀 Starting to crawl {len(self.gzlist)} accounts: {self.gzlist}")
            for gzh in self.gzlist:
                print(f"\n{'='*50}")
                print(f"📌 Starting to crawl: {gzh}")
                print('='*50)
                self.get_content(gzh)
            print("\n🎉 All crawling completed!")
        except Exception as e:
            print(f"❌ Crawler error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.db.close()
            self.session.close()


if __name__ == "__main__":
    WeChatCrawler().run()