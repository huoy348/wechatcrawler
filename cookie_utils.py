# -*- coding: utf-8 -*-
"""
Cookie Format Conversion Tool
Supports converting various cookie formats exported from browsers to the database storage format {name: value} dictionary
"""
import json
import re


def detect_format(cookie_str):
    """Automatically detect cookie format"""
    text = cookie_str.strip()

    # JSON array format (exported from Chrome DevTools / third-party tools)
    if text.startswith('[') and text.endswith(']'):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return 'json_devtools'
        except json.JSONDecodeError:
            pass

    # JSON object format {name: value, ...}
    if text.startswith('{') and text.endswith('}'):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return 'json_devtools'
        except json.JSONDecodeError:
            pass

    # Netscape HTTP Cookie file format (with tabs, containing fields like domain, path, etc.)
    lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('#') and not l.startswith('//')]
    if len(lines) >= 1 and '\t' in lines[0]:
        parts = lines[0].split('\t')
        # Netscape format usually has 7 columns or at least one column that is not a name/value header
        if len(parts) >= 4:
            return 'netscape'
        # If the first row is a name/value header, it might be a domain export format
        first_word = parts[0].strip().lower()
        if first_word in ('name', 'domain'):
            return 'json_domain'

    # Domain format (copied from Application panel): separated by tabs, first row is header
    if len(lines) >= 1 and '\t' in lines[0]:
        first_line_parts = lines[0].split('\t')
        headers_lower = [h.strip().lower() for h in first_line_parts]
        if 'name' in headers_lower or 'domain' in headers_lower:
            return 'json_domain'

    # Cookie request header string: name=value; name2=value2
    if ';' in text and '=' in text:
        pairs = [p.strip() for p in text.split(';') if p.strip()]
        # Check if most pairs contain =
        eq_count = sum(1 for p in pairs if '=' in p)
        if len(pairs) > 0 and eq_count / len(pairs) > 0.5:
            return 'header_str'

    # Single line name=value format
    if '=' in text and '\n' not in text:
        return 'header_str'

    return 'header_str'  # default


def _json_from_devtools(json_str):
    """Parse JSON cookie arrays copied from Chrome DevTools"""
    cookies = json.loads(json_str)
    if isinstance(cookies, list):
        return cookies
    if isinstance(cookies, dict):
        # {name: value, ...} format
        return [{'name': k, 'value': v} for k, v in cookies.items()]
    raise ValueError("Unrecognized JSON format, expecting array or object")


def _netscape_to_cookies(netscape_str):
    """Convert Netscape HTTP Cookie file format to list[dict]"""
    cookies = []
    for line in netscape_str.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue
        parts = line.split('\t')
        if len(parts) >= 7:
            # Netscape standard format
            cookies.append({
                'domain': parts[0],
                'flag': parts[1],
                'path': parts[2],
                'secure': parts[3] == 'TRUE',
                'expiration': parts[4],
                'name': parts[5],
                'value': parts[6]
            })
        elif len(parts) >= 2:
            # Simplified name\tvalue format
            cookies.append({'name': parts[0], 'value': parts[1]})
    return cookies


def _json_domain_to_cookies(domain_str):
    """Convert domain cookie format copied from Application panel to list[dict]"""
    rows = domain_str.strip().split('\n')
    if not rows:
        return []
    headers = [h.strip() for h in rows[0].split('\t')]
    # Try to identify the index of name and value columns
    name_idx = None
    value_idx = None
    for i, h in enumerate(headers):
        hl = h.lower()
        if hl == 'name':
            name_idx = i
        elif hl == 'value':
            value_idx = i

    cookies = []
    for row in rows[1:]:
        if not row.strip():
            continue
        parts = row.split('\t')
        # Need at least name
        if name_idx is not None and name_idx < len(parts):
            cookie = {'name': parts[name_idx]}
            cookie['value'] = parts[value_idx] if value_idx is not None and value_idx < len(parts) else ''
            # Fill in other fields
            for i, h in enumerate(headers):
                if i == name_idx or i == value_idx:
                    continue
                if i < len(parts):
                    cookie[h] = parts[i]
            cookies.append(cookie)
        elif len(parts) >= 2:
            # No header identified, take by position
            cookies.append({'name': parts[0], 'value': parts[1]})
    return cookies


def _header_str_to_cookies(cookie_str):
    """Parse Cookie request header string: name=value; name2=value2"""
    cookies = []
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if '=' in pair:
            name, value = pair.split('=', 1)
            cookies.append({'name': name.strip(), 'value': value.strip()})
    return cookies


def convert_to_db_format(browser_cookies, format_type='auto'):
    """
    Convert browser cookies to database storage dictionary format {name: value, ...}

    Parameters:
        browser_cookies: str — Raw text of cookies exported from browser
        format_type: str — Format type: 'auto' | 'json_devtools' | 'netscape' | 'json_domain' | 'header_str'

    Returns:
        dict — {cookie_name: cookie_value, ...}

    Supported browser cookie sources:
        - Chrome DevTools → Application → Cookies → Export JSON
        - Chrome DevTools → Application → Cookies → Select all and copy (domain format)
        - Netscape format exported by extensions like Cookie-Editor
        - Cookie request header copied from Network panel
    """
    if not browser_cookies or not browser_cookies.strip():
        raise ValueError("Cookie content is empty, please check input")

    if format_type == 'auto':
        format_type = detect_format(browser_cookies)
        print(f"🔍 Detected cookie format: {format_type}")

    # Parse to cookies list
    if format_type == 'json_devtools':
        items = _json_from_devtools(browser_cookies)
    elif format_type == 'netscape':
        items = _netscape_to_cookies(browser_cookies)
    elif format_type == 'json_domain':
        items = _json_domain_to_cookies(browser_cookies)
    elif format_type == 'header_str':
        items = _header_str_to_cookies(browser_cookies)
    else:
        raise ValueError(f"Unsupported cookie format: {format_type}")

    # Convert to {name: value} dictionary
    result = {}
    for c in items:
        if isinstance(c, dict) and 'name' in c and 'value' in c:
            result[c['name']] = c['value']

    if not result:
        raise ValueError("Cookie is empty after conversion, please check if the input content is correct")

    return result


def auto_extract_token(session, user_agent=None):
    """
    Automatically extract token from WeChat Public Platform using a requests.Session with loaded cookies.

    Process:
      1. Access https://mp.weixin.qq.com/ (allowing redirects)
      2. Extract token=xxx parameter from the final URL
      3. If not in URL, try searching for token in page content

    Parameters:
        session: requests.Session — Session with cookies injected via session.cookies.set()
        user_agent: str — Custom UA, defaults to mobile WeChat UA

    Returns:
        str — Extracted token, returns None if failed
    """
    import re
    import random

    if user_agent is None:
        user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
            "MicroMessenger/8.0.52(0x1800342c) NetType/WIFI Language/zh_CN"
        )

    headers = {
        "User-Agent": user_agent,
        "Referer": "https://mp.weixin.qq.com/",
    }

    print("🔍 Accessing WeChat Public Platform to automatically extract Token...")

    try:
        resp = session.get(
            "https://mp.weixin.qq.com/",
            headers=headers,
            allow_redirects=True,
            timeout=15,
        )

        final_url = resp.url
        print(f"  Final URL: {final_url}")

        # Method 1: Extract token from URL
        token_match = re.search(r'token=(\d+)', final_url)
        if token_match:
            token = token_match.group(1)
            print(f"✅ Automatically extracted Token from URL: {token}")
            return token

        # Method 2: Search for token in page content
        t = re.search(r'token["\']?\s*[:=]\s*["\']?(\d+)', resp.text[:20000])
        if t:
            token = t.group(1)
            print(f"✅ Extracted Token from page content: {token}")
            return token

        # Method 3: Try matching from certain field in cookie (in some cases token is in cookie URL)
        print("❌ Failed to extract Token from URL or page content")
        print(f"  HTTP status code: {resp.status_code}")
        return None

    except Exception as e:
        print(f"❌ Failed to access WeChat Public Platform: {e}")
        return None


def print_cookie_help():
    """Return instructions for obtaining browser cookies"""
    return """
📋 How to obtain browser Cookie (choose any of the following):

━━━ Method 1: Chrome DevTools → Select All Copy (Recommended) ━━━
  1. Open https://mp.weixin.qq.com/ in Chrome and scan QR code to log in
  2. Press F12 to open developer tools
  3. Switch to "Application" tab
  4. Expand "Cookies" on the left → Select "https://mp.weixin.qq.com"
  5. In the right cookie list: Click on row 1 → Scroll to bottom → Hold Shift and click on the last row (select all)
  6. Press Ctrl+C (Mac: Cmd+C) to copy
  7. Pass the content as --cookie-domain parameter

━━━ Method 2: Chrome DevTools → Export JSON ━━━
  1. Open https://mp.weixin.qq.com/ and log in
  2. F12 → "Application" → "Cookies" → "https://mp.weixin.qq.com"
  3. Install "EditThisCookie" or "Cookie-Editor" extension
  4. Export cookies in JSON format using the extension
  5. Pass the JSON content as --cookie-json parameter

━━━ Method 3: Copy Cookie Request Header from Network Panel ━━━
  1. In a logged-in browser, open any public account article page or management backend
  2. F12 → "Network" tab
  3. Refresh the page, click on any request (e.g., home?t=home/index)
  4. Find the "Cookie:" field in "Request Headers"
  5. Select and copy the Cookie value (from first item to last item)
  6. Pass as --cookie-str parameter

━━━ Token Acquisition (Required) ━━━
  After logging in to https://mp.weixin.qq.com/, check the browser address bar:
  The number after token= in the URL is the token
  For example: https://mp.weixin.qq.com/cgi-bin/home?t=home/index&token=123456789&lang=zh_CN
  Copy 123456789 as the --token parameter

━━━ Usage Example ━━━
  python3 run_crawler.py --cookie-domain "$(cat cookie.txt)" --token 123456789
  python3 run_crawler.py --cookie-json '[...]' --token 123456789
  python3 run_crawler.py --cookie-str 'name=value; name2=value2' --token 123456789
"""