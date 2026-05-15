# -*- coding: utf-8 -*-
"""
WeChat Official Account Articles Crawler Config File 
(Optimized: Lean Config, Cookie Centric)
"""

# ====================== Database Configuration ======================
DB_CONFIG = {
    "host": "your host",
    "port": "your port",
    "user": "root",
    "password": "your password",
    "database": "wechat_crawler",
    "charset": "utf8mb4"
}

# ====================== Chrome Driver Configuration ======================
# "CHROMEDRIVER_MANAGER" Auto-managed by default; a local path can also be manually specified.
EDGE_DRIVER_PATH = "CHROMEDRIVER_MANAGER"
