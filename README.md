# Stock News Sentinel

每天自動收集 YouTube 與財經新聞 RSS，統計被重複提到的台股產業與個股，並輸出 Markdown/Google Sheets 報告。這是研究輔助工具，不是自動下單或個人化投資顧問。

## 快速開始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
python -m stock_news_bot --config config/sources.yaml --dry-run
```

如果是 cloud task 或 Linux runner，可直接用 repo 內的 setup：

```bash
bash .codex/setup.sh
bash .codex/run-checks.sh
```

需要的環境變數可參考 `.env.example`：

- `YOUTUBE_API_KEY`: YouTube Data API v3 key。
- `OPENAI_API_KEY`: 選用，開啟 LLM 摘要時才需要。
- `OPENAI_MODEL`: 選用，預設 `gpt-5.5`，可依你的帳號可用模型調整。
- `GOOGLE_APPLICATION_CREDENTIALS`: 選用，本機執行時的 Google service account JSON 路徑。
- `GOOGLE_SHEET_ID`: 選用，Google Sheet ID。

CLI 會自動讀取專案根目錄的 `.env`。

## 設定重點

- `config/sources.yaml`: RSS、YouTube 查詢、產業詞、儲存與 LLM 設定。
- `data/tw_stocks_sample.csv`: 股票代號、公司名、別名與產業對照表。
- `.github/workflows/daily-report.yml`: GitHub Actions 每日排程。

專案目前已內建多個台灣財經與科技產業 RSS，包括 Anue 鉅亨網、經濟日報、MoneyDJ 理財網、自由時報財經頻道、TechNews、中央社產經證券、中央社科技新聞與商業周刊。`工商時報` 與 `Yahoo奇摩股市` 仍保留空白 URL，等你補上確認過的官方 feed。YouTube 頻道請填 channel ID；若只想用關鍵字搜尋，保留 `queries` 即可。

## 執行

產生並儲存報告：

```bash
python -m stock_news_bot --config config/sources.yaml
```

指定日期會使用該日的日曆視窗：

```bash
python -m stock_news_bot --config config/sources.yaml --date 2026-06-23
```

## Cloud Task / CI

- `.codex/setup.sh`：建立 `.venv`、顯示 Python 版本、安裝 `.[dev]`
- `.codex/run-checks.sh`：執行 `python --version`、`pytest`、主程式 smoke run
- `.github/workflows/verify-python.yml`：在 GitHub Actions 上驗證 Python 3.11、依賴、測試與主程式
- `.github/workflows/daily-report.yml`：每日任務也會先做相同的 Python 驗證與測試，再產出報告

輸出位置：

- `data/history/YYYY-MM-DD.json`
- `data/runtime/sources/YYYY-MM-DD.jsonl`
- `data/runtime/daily_entities.csv`
- `data/runtime/reports/YYYY-MM-DD.md`

`data/history/YYYY-MM-DD.json` 會保存當日來源、實體統計、聲量訊號、LLM 摘要與報告全文。GitHub Actions 跑完後會把這個資料夾 commit/push 回 repo，之後做 Streamlit 儀表板或回測時可以直接讀取完整時間序列。

## LLM 摘要

預設關閉。要啟用時：

1. 設定 `OPENAI_API_KEY`。
2. 在 `config/sources.yaml` 將 `llm.enabled` 改成 `true`。
3. 視需要調整 `OPENAI_MODEL`。

LLM prompt 已要求輸出研究觀察、風險與待驗證事項，避免直接給個人化買賣建議。

## Google Sheets

要輸出到 Sheets 時：

1. 建立 Google Cloud service account。
2. 下載 JSON key，設定 `GOOGLE_APPLICATION_CREDENTIALS`。
3. 把 Google Sheet 分享給 JSON 裡的 `client_email`。
4. 設定 `GOOGLE_SHEET_ID`。
5. 將 `storage.sheets.enabled` 改成 `true`。

在 GitHub Actions 上，請把 service account JSON 全文放進 `GOOGLE_SERVICE_ACCOUNT_JSON` secret，workflow 會在 runner 暫存路徑建立憑證檔。

## 模組說明

更完整的架構、注意事項與 API 文件連結在 `docs/architecture.md`。
