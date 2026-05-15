#!/usr/bin/env python3
"""Validate cookies and crawl all accounts (10 per account)"""
import sys
sys.path.insert(0, '.')

from cookie_utils import convert_to_db_format
from crawler import WeChatCrawler

cookie_str = (
    'appmsglist_action_3014484237=card; pgv_pvid=4547614803; '
    '_qimei_uuid42=1a105102a2a10010b8d2557848b26cfba342968085; '
    '_qimei_i_3=63d371d1910e048fc89ead630d8d21b5febaacf7435b0587e0de205b7797766b606631943a89e289a790; '
    '_qimei_h38=19c57cc5b8d2557848b26cfb0200000e31a105; '
    'yybsdk-webId=677a31300000019c07449b994a7d8e9c; '
    '_qimei_q36=; _qimei_i_2=45d16fdfc919; _qimei_q32=; '
    'RK=VZDDDuvgdH; '
    'ptcz=45aab7e8939dff27b69fcdedccb9f5c289f08a36d5c42cfbb26e2c0f3ffd59f2; '
    '_qimei_i_1=6fb228839c0955dc92c4fb6253d071e5f2e9acf51a090184e7d97a582493206c6163629639d8e3dcd3abd0e1; '
    'pac_uid=0_wGysTJTF6i6kX; omgid=0_wGysTJTF6i6kX; '
    'ua_id=jdjHzxNVwS2QMdWZAAAAAIY_Bo8-Qzot_fhbhzPqy6Y=; '
    'wxuin=76748502742110; '
    '_qimei_fingerprint=987c702ffd17c06af8befac930e4dcba; '
    'mm_lang=zh_CN; personAgree_3014484237=true; '
    '_clck=3014484237|1|g60|0; '
    'uuid=bacb3cc4bd50b440b202f028d48449fe; '
    'rand_info=CAESIKRC/nc0MwgdOLvELZrEaP2Rxy9h9oUzBibWXXfRpFy/; '
    'slave_bizuin=3014484237; data_bizuin=3014484237; bizuin=3014484237; '
    'data_ticket=HpaE53XUhBHnDyzqp55aDhMiFGr3iqXEby13ho8SBzAtPwXSOSjaeX5EheBQze1p; '
    'slave_sid=NGFmcGZoWG5mcmlmTzZCSHE5cG5Qc1RSb285TTBxSXV6S0xoM1FURDBzRWJiaWdBRUs5eXBjVExpd1pXRV94VVRvX0hrVFNoUzI3d0J1TjdmZHFGcTBPc2dYb05HYUtjTnltWDBfSEl4M1pvaHJfZmpFN0NzMlV2a3Y2T05WZUlST3JhVmVaM3JOQzdSMVI2; '
    'slave_user=gh_1db1fce2c8d2; '
    'xid=fafc16ccdf3076bafd0866360110d2fa; '
    '_clsk=158sptk|1778635901572|1|1|mp.weixin.qq.com/weheat-agent/payload/record'
)
token = '795541527'

# Initialize crawler (1 page per account = 10 items)
crawler = WeChatCrawler(max_pages=1)

# Inject user-provided browser cookies
ok = crawler.set_user_browser_cookies(cookie_str, token, 'header_str')
if not ok:
    print('❌ Cookie setting failed')
    sys.exit(1)

# First quickly verify if API is available
import requests, random, json
for k, v in crawler._user_cookies.items():
    crawler.session.cookies.set(k, v)

WECHAT_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.52(0x1800342c) NetType/WIFI Language/zh_CN'

# Search first account to verify API
test_url = f'https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&token={token}&query=Renesas&begin=0&count=1&f=json'
headers = {'User-Agent': WECHAT_UA, 'Referer': 'https://mp.weixin.qq.com/', 'X-Requested-With': 'XMLHttpRequest'}
res = crawler.session.get(test_url, headers=headers, timeout=10)
data = res.json()
if data.get('base_resp', {}).get('ret') == 0:
    print(f'✅ API verification successful! Can search for accounts')
    print(f'🚀 Starting to crawl {len(crawler.gzlist)} accounts...')
    crawler.run()
else:
    print(f'❌ API returned error: {data}')
    print('Cookies may still have issues')