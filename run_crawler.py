#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat Official Account Article Crawler - Startup Script

Usage:

  # [Method 1] Provide browser cookies (recommended) - token automatically extracted, validated and then crawl all
  python3 run_crawler.py --cookie-str 'uin=xxx; key=xxx; ...'
  python3 run_crawler.py --cookie-json '[{"name":"uin","value":"xxx"}]'
  python3 run_crawler.py --cookie-domain "$(cat cookies.txt)"

  # [Method 2] Specify account
  python3 run_crawler.py --cookie-str 'uin=xxx; key=xxx' Megermite

  # [Method 3] Auto mode: first check database cookies, prompt user if expired
  python3 run_crawler.py
  python3 run_crawler.py Megermite
"""
import os
import sys
import argparse

# Ensure current directory modules can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(
        description="WeChat Official Account Article Crawler — Automatically extract Token + Validate + Full crawl",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples：
  %(prog)s                                    # Auto mode (check database cookies)
  %(prog)s --cookie-json '[...]'              # Provide cookies, automatically extract token
  %(prog)s --cookie-str 'uin=xxx; key=xxx'    # Provide cookie request header
  %(prog)s --cookie-domain "$(cat c.txt)"     # Provide Application panel cookies
  %(prog)s --cookie-json '[...]' Megermite     # Specify single account to crawl
        """
    )

    # Cookie argument group (choose one of three)
    cookie_group = parser.add_mutually_exclusive_group()
    cookie_group.add_argument('--cookie-json', type=str, default=None,
                              help='Browser cookie JSON format (exported from DevTools)')
    cookie_group.add_argument('--cookie-domain', type=str, default=None,
                              help='Browser cookie domain format (full select copy from Application panel)')
    cookie_group.add_argument('--cookie-str', type=str, default=None,
                              help='Browser cookie request header string format')

    parser.add_argument('--token', type=str, default=None,
                        help='(Optional) Manually specify token, not provided then automatically extract from WeChat platform')

    parser.add_argument('gzh_name', type=str, nargs='?', default=None,
                        help='Specify account name to crawl (optional, default crawls all)')

    args = parser.parse_args()

    # Check dependencies
    try:
        import selenium
        import pymysql
        import requests
        from bs4 import BeautifulSoup
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install selenium beautifulsoup4 pymysql requests webdriver-manager")
        sys.exit(1)

    # Check database connection
    try:
        from db_operations import WeChatDB
        db = WeChatDB()
        db.close()
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        sys.exit(1)

    from crawler import WeChatCrawler

    # ====== Initialize crawler ======
    if args.gzh_name:
        # If account specified, ensure it's in task list
        from db_operations import WeChatDB
        db = WeChatDB()
        db.add_task(args.gzh_name)
        db.close()
        crawler = WeChatCrawler()
        crawler.gzlist = [args.gzh_name]
    else:
        crawler = WeChatCrawler()

    # ====== Handle user-provided browser cookies ======
    has_user_cookies = False
    expect_crawl = True  # Default to need crawling

    if args.cookie_json:
        print("📥 Detected --cookie-json parameter, converting...")
        has_user_cookies = crawler.set_user_browser_cookies(args.cookie_json, args.token, 'json_devtools')

    elif args.cookie_domain:
        print("📥 Detected --cookie-domain parameter, converting...")
        has_user_cookies = crawler.set_user_browser_cookies(args.cookie_domain, args.token, 'json_domain')

    elif args.cookie_str:
        print("📥 Detected --cookie-str parameter, converting...")
        has_user_cookies = crawler.set_user_browser_cookies(args.cookie_str, args.token, 'header_str')

    # ====== Run crawler ======
    if has_user_cookies or (not args.cookie_json and not args.cookie_domain and not args.cookie_str):
        # Has user-provided cookies (will auto-validate) or no cookie arguments (follow database check process)
        crawler.run(skip_validate=not has_user_cookies)
    else:
        # Cookie conversion failed
        print("❌ Browser cookie conversion failed, unable to start crawler")
        sys.exit(1)


if __name__ == "__main__":
    main()