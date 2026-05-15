## wechatcrawler
A Python-based crawler for extracting information from WeChat Official Accounts.



### 📖 Introduction
wechatcrawler is a Python application that automatically collects and parses information from WeChat Official Accounts, including articles, titles, content, publish time, and other public data.
It uses Selenium for page rendering, BeautifulSoup for data parsing, and supports data storage via files or databases.

### 🛠️ Technology Stack & Dependencies
Python == 3.12
selenium == 4.15.0
beautifulsoup4 == 4.12.2
pymysql == 1.1.0
requests == 2.31.0
webdriver-manager == 4.0.1

### ✨ Features
Crawl articles from specified WeChat Official Accounts.
Parse title, content, publish date, URL and other fields.
Support browser automation via Selenium.
Data parsing with BeautifulSoup4.
Support MySQL data storage (via pymysql).
Automatic webdriver management.
Simple and easy to extend.