# 自動化股票新聞觀察系統設計

這個專案的目標是每天自動收集 YouTube 與財經新聞 RSS，找出重要消息、重複被提到的產業與個股，並輸出一份可追蹤的研究報告。它刻意把結果定義成「研究輔助」而不是直接買賣指令，避免把媒體聲量誤認成投資結論。

## 1. 資料來源層

### YouTube

實作位置：`src/stock_news_bot/collectors/youtube.py`

做法：

- 使用 YouTube Data API v3 的 `search.list`，用 `q` 關鍵字、`channelId`、`publishedAfter`、`publishedBefore`、`order=date` 找近期影片。
- 對每支影片呼叫 `youtube-transcript-api` 抓字幕，優先語言為 `zh-Hant`、`zh-TW`、`zh`、`en`。
- 若字幕不存在，就退回使用影片標題與描述，並在來源 metadata 標記 `has_transcript=false`。

注意：

- YouTube API 有 quota，關鍵字和頻道不要無限制擴張。
- 字幕可能是自動產生，中文金融名詞和股票代號容易聽錯。
- 某些影片沒有字幕或禁止字幕存取，這不是程式錯誤。
- 搜尋結果不是完整市場資料，只是 YouTube 對查詢條件的回傳。
- 在雲端 runner 上大量抓字幕可能遇到 YouTube 對資料中心 IP 的限制，失敗時應降低頻率或改用更穩定的來源策略。

官方文件：

- YouTube Data API `search.list`: https://developers.google.com/youtube/v3/docs/search/list

### 財經新聞 RSS

實作位置：`src/stock_news_bot/collectors/rss.py`

做法：

- 使用 `feedparser` 讀取設定檔中的 RSS/Atom feed。
- 只處理 feed 內的標題、摘要、內容片段、連結與發布時間。
- 以發布時間過濾資料視窗，預設抓最近 24 小時。

注意：

- 優先使用官方 RSS/Atom，不要直接爬整站。
- 沒有 RSS 才考慮網頁爬蟲，而且要先看 robots.txt 與服務條款。
- RSS 摘要通常不是全文，報告中的結論要保留原文連結方便回查。
- 各網站 RSS URL 可能調整，所以 `config/sources.yaml` 先留空，由你填入確認過的官方 feed。

## 2. 文字分析層

實作位置：

- `src/stock_news_bot/analysis/dictionary.py`
- `src/stock_news_bot/analysis/signals.py`
- `src/stock_news_bot/analysis/llm.py`

做法：

- 股票字典：`data/tw_stocks_sample.csv` 維護 `ticker,name,aliases,industry`，例如「台積電」「台積」「2330」「TSMC」會對到同一檔。
- 產業字典：在 `config/sources.yaml` 的 `analysis.industry_terms` 維護產業與關鍵詞。
- 頻率統計：逐篇文章/影片計算股票與產業出現次數，也統計有幾個來源提到。
- 趨勢訊號：和 `data/runtime/daily_entities.csv` 的歷史資料比對，找出連續上榜與聲量放大。
- LLM 摘要：預設關閉。開啟後會把來源摘要、實體統計、訊號候選送到 OpenAI Responses API，產生繁體中文研究摘要。

注意：

- 字典法準確、可控，但吃維護成本；LLM 語意理解較強，但成本與不確定性較高。
- 「統一」「華新」這類公司名很容易和一般詞混淆，alias 要保守。
- 頻率高只代表討論多，不代表可買、會漲或基本面變好。
- LLM 輸出必須附帶風險與待驗證事項，不應輸出保證式結論。

OpenAI 文字產生文件：

- https://developers.openai.com/api/docs/guides/text

## 3. 儲存與彙整層

實作位置：

- `src/stock_news_bot/storage/local_store.py`
- `src/stock_news_bot/storage/sheets.py`

做法：

- 本機預設輸出：
  - `data/history/YYYY-MM-DD.json`
  - `data/runtime/sources/YYYY-MM-DD.jsonl`
  - `data/runtime/daily_entities.csv`
  - `data/runtime/reports/YYYY-MM-DD.md`
- `data/history` 是正式、可版本控制的每日 snapshot；pipeline 也會從這些 snapshot 讀回歷史 `entities`，用來計算連續上榜與聲量放大。
- Google Sheets 可選輸出：
  - `Sources` 工作表：每日來源清單。
  - `Entities` 工作表：每日股票/產業統計。
  - `Reports` 工作表：Markdown 報告全文。

注意：

- Google Sheets 適合輕量資料庫與視覺化，不適合大量全文保存。
- `data/history` 會包含來源文字與報告全文，長期執行後 repo 會變大；若未來資料量增加，可改成只保存摘要與實體統計，全文改放外部儲存。
- 若使用 service account，要把試算表分享給 service account 的 `client_email`。
- API key、service account JSON、OpenAI key 都不要提交到 git。

Google Sheets API 文件：

- https://developers.google.com/workspace/sheets/api/guides/concepts
- gspread service account: https://docs.gspread.org/en/latest/oauth2.html

## 4. 排程層

實作位置：`.github/workflows/daily-report.yml`

做法：

- GitHub Actions 每個交易日台北時間晚上執行。
- 安裝 Python 套件後執行：
  - `python -m stock_news_bot --config config/sources.yaml`
- 密鑰放在 GitHub repository secrets。
- workflow 會把 `data/history` commit/push 回 repo，讓每日 snapshot 成為版本控制資料；也會把 Markdown 報告上傳成 artifact。

注意：

- GitHub Actions 的排程在預設分支最新 commit 上執行。
- 頻率不要設太高，避免 API quota 與不必要成本。
- 排程時間應安排在你想看的資料視窗之後，例如台股收盤後或美股盤前。
- commit snapshot 會使用 `GITHUB_TOKEN`，workflow 需要 `contents: write` 權限。

GitHub Actions schedule 文件：

- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule

## 5. 建議的使用流程

1. 補齊 `config/sources.yaml` 中的 RSS URL、YouTube 關鍵字與頻道 ID。
2. 擴充 `data/tw_stocks_sample.csv`，把你關心的個股與常見別名補齊。
3. 先不開 LLM，跑幾天確認資料收集與字典命中是否合理。
4. 開啟 LLM 摘要，確認摘要有引用來源、列風險、沒有過度給買賣建議。
5. 接上 Google Sheets 和 GitHub Actions，開始累積歷史聲量。
