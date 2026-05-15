#!/usr/bin/env python3
"""Debug: Test live crawler's extraction methods directly."""
import sys
import json
import re
sys.path.insert(0, '.')

from crawler import WeChatCrawler
import requests

crawler = WeChatCrawler()

# Get valid cookies and token
cookies, token = crawler.get_valid_cookies_and_token()
print(f"Token: {token}")
print(f"Cookie keys: {list(cookies.keys())}")

# Test URL (shortened)
article_url = "https://mp.weixin.qq.com/s/h4Jr3mqoDjoOaL_6107slw"

# Step 1: Parse URL params
url_params = crawler.parse_article_url_params(article_url)
print(f"\nURL params: {url_params}")

# Step 2: Check if fallback needed
needs_fallback = not all(k in url_params for k in ['biz', 'mid', 'idx'])
print(f"Needs HTML fallback: {needs_fallback}")

# Step 3: Fetch HTML using get_article_base_info
html = crawler.get_article_base_info(article_url, cookies)
print(f"HTML length: {len(html) if html else 'None'}")

# Check if HTML is valid
if html:
    # Check for var biz in HTML
    biz_match = re.search(r"var\s+biz\s*=\s*'([^']*)'", html)
    print(f"var biz in HTML: {biz_match.group(1) if biz_match else 'NOT FOUND'}")
    
    mid_match = re.search(r"var\s+mid\s*=\s*'([^']*)'", html)
    print(f"var mid in HTML: {mid_match.group(1) if mid_match else 'NOT FOUND'}")
    
    idx_match = re.search(r"var\s+idx\s*=\s*'([^']*)'", html)
    print(f"var idx in HTML: {idx_match.group(1) if idx_match else 'NOT FOUND'}")
    
    sn_match = re.search(r"var\s+sn\s*=\s*'([^']*)'", html)
    print(f"var sn in HTML: {sn_match.group(1) if sn_match else 'NOT FOUND'}")
    
    # Try the crawler's extraction method
    print(f"\n--- Crawler extract_params_from_html ---")
    extracted = crawler.extract_params_from_html(html)
    print(f"Extracted params: {extracted}")
    
    # Show a snippet around var biz
    biz_pos = html.find("var biz")
    if biz_pos >= 0:
        print(f"\nSnippet around 'var biz' (pos={biz_pos}):")
        print(repr(html[biz_pos: biz_pos + 100]))
    else:
        print(f"\n'var biz' NOT found in HTML")
        # Check if HTML has any script tags
        script_count = html.count("<script")
        print(f"Script tags: {script_count}")
        # Check encoding
        print(f"HTML first 500 chars: {html[:500]}")
        print(f"HTML first 500 repr: {repr(html[:500])}")
else:
    print("No HTML returned!")