# Taiwan PC Component Price Tracker — 台灣電腦零組件價格追蹤

自動爬取台灣 PC 通路商（原價屋、欣亞、Autobuy）即時價格，提供即時儀表板與自動排程更新。

## 快速開始

```bash
# 1. 下載並安裝
git clone <your-repo>
pip install requests

# 2. 編輯產品清單（只需 name + category）
vim products.json

# 3. 爬取所有價格並產生靜態儀表板
python track.py

# 或只測試特定產品：
python track.py --scrape "RTX 5070"

# 驗證比對結果與異常偵測：
python track.py --verify

# 啟動即時伺服器（含自動排程更新）：
python track.py --server
```

## `products.json` 格式

```json
[
  {"name": "NVIDIA RTX 5070", "category": "GPU"},
  {"name": "Intel Core Ultra 5 245K", "category": "CPU"}
]
```

只需填 `name` 和 `category`，其餘欄位（brand、spec、search 關鍵字、base_price）由 scraper 從內建預設值自動補完。分類：`CPU`、`GPU`、`RAM`、`SSD`。

## 自動更新

GitHub Action 每 6 小時執行一次（隨機 ±30 分鐘），每天約更新 4 次。結果自動發佈到 GitHub Pages。

## 涵蓋通路

| 通路 | 狀態 |
|---|---|
| 原價屋 CoolPC | ✓ (100% 比對率) |
| 欣亞 Sinya | ✓ (83%) |
| Autobuy | ✓ (88%) |
| PChome 24h | ✗ (Cloudflare 阻擋，無法爬取) |

## 驗證功能

```bash
python track.py --verify
```

檢查比對率、標記低於建議售價 75% 的價格（舊款 CPU 屬於正常）、偵測單筆歷史異常價格，並顯示各店家的實際產品名稱（`matched_title`）作為正確比對的證明。

## 儀表板功能

- 三欄通路價格（三家店固定顯示）
- 波動卡片 — 各分類依時間的價格波動幅度
- 歷史低價欄位
- 開始追蹤日期欄位
- Cache-busting 重新整理按鈕
- 穩定但偏高（>20% 高於 MSRP）顯示琥珀色「價格偏高」

## 專案結構

```
├── products.json           # 產品清單（使用者編輯）
├── track.py                # 單一進入點
├── price_tracker/
│   ├── scraper.py          # 爬蟲 + 比對邏輯
│   └── database.py         # SQLite 資料庫層
├── scripts/
│   └── generate_static.py  # 產生靜態 JSON + index.html
├── server.py               # 即時 API 伺服器 + 排程器
├── web/templates/
│   └── index.html          # 儀表板樣板
└── docs/                   # GitHub Pages 輸出目錄
```
