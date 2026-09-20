# Paper Radar

可個人化的 Python CLI：從 arXiv 取得最新論文，使用 TypeSafe AI 的 Noul 問題取得 P(True)，直接作為相關性分數，輸出每日 Markdown / JSON 排行。

## 安裝與執行

需要 Python 3.11+ 與 [uv](https://docs.astral.sh/uv/getting-started/installation/)。PowerShell：

```powershell
cd "C:\Users\choon\Documents\Codex\2026-09-20\ban\outputs\paper-radar"
uv sync
```

交付已包含範例內容的 `config/config.json`。若從 Git 取得專案，先執行：

```powershell
Copy-Item config/config.example.json config/config.json
```

修改研究設定，再執行：

```powershell
uv run paper-radar --config config/config.json --check-config
$env:TYPESAFE_API_KEY = "填入你的 TypeSafe API key"
uv run paper-radar --config config/config.json
```

亦支援：

```powershell
uv run python main.py --config config/config.json
```

第一次 `uv sync` 會建立虛擬環境與 `uv.lock`；請保留並提交鎖定檔，之後可使用 `uv sync --locked`。依使用者要求，本次未安裝依賴，未產生鎖定檔。

API key 只讀取環境變數，不自動讀取 `.env`。SDK 可透過 `TYPESAFE_DEFAULT_MODEL` 選擇模型。研究設定和論文標題、摘要、分類會送至 TypeSafe。

## 設定

預設範例是 Computer Vision / Generative Models。所有領域描述都位於 JSON，Python 不寫死特定研究方向。

| 設定 | 用途 |
|---|---|
| `profile` | 報告名稱與描述 |
| `research.summary` | 主要研究方向 |
| `research.interests` | 核心主題 |
| `research.related_topics` | 延伸主題 |
| `research.negative_topics` | 排除主題 |
| `research.evaluation_guidance` | 判斷準則 |
| `sources.arxiv.categories` | 預設 cs.CV、cs.LG、cs.AI、cs.GR |
| `sources.arxiv.max_results` | 每次取最新 N 篇，預設 300 |
| `evaluation.relevance_threshold` | 相關性門檻，預設 0.5，包含等號 |
| `evaluation.high_priority_threshold` | 高優先門檻，預設 0.8 |
| `evaluation.dimensions` | 多維度問題開關及自訂問題 |
| `output.include_irrelevant` | 是否列出未達門檻的論文 |
| `output.max_papers_in_report` | 最多列出篇數，預設 50 |
| `output.markdown / json` | 輸出格式，至少開啟一種 |

報告預設由高分至低分，也支援 `output.sort_order = "ascending"`。arXiv 的 `sort_by` 支援 `submitted_date`、`last_updated_date`、`relevance`；`sort_order` 支援 `ascending`、`descending`。

啟用 dimensions 時，overall 和維度問題合併為每篇一次請求。維度名稱 `relevant` 保留給 overall 問題。數值超出範圍、欄位拼錯、空摘要設定、空分類、門檻順序錯誤均會被拒絕。

### 路徑與研究設定切換

`storage` 相對路徑以設定檔所在目錄為基準；若設定檔放在名為 `config` 的目錄，則以其上一層為基準。標準配置因此保持 `config/`、`data/`、`daily/` 平行排列，不受 shell 工作目錄影響。亦支援絕對路徑。

修改 `profile`、`research` 或 `evaluation` 後，請指定另一組儲存路徑，例如：

```json
{
  "seen_file": "data/robotics/seen.json",
  "database_file": "data/robotics/papers.jsonl",
  "daily_output_dir": "daily/robotics"
}
```

也可以封存整組舊資料後重新開始。程式會拒絕以不同研究設定沿用相同資料庫，避免錯誤跳過論文。只調整 `output` 不需要重新評分。

## 輸出與可靠性

- 產生 `daily/YYYY-MM-DD.md` 和 `daily/YYYY-MM-DD.json`。
- `data/seen.json` 記錄成功處理 ID，`data/papers.jsonl` 保存全部成功結果，包含低分論文。
- arXiv v1、v2 視為同一篇，亦支援舊式 arXiv ID。
- 不限制過去 24 小時；每次將最新 N 篇與已處理資料比對。若長時間未執行且累積超過 N 篇，仍可能漏掉較早論文，可提高 N 補抓。
- 空摘要、API 失敗、缺失答案或非法機率不會加入 seen；其他論文繼續處理。
- TypeSafe 使用 SDK 內建重試：首次請求後最多 3 次，初始退避 1 秒、上限 4 秒；SDK 可加入 jitter 或遵循 Retry-After。HTTP timeout 為 30 秒，retry budget 為 60 秒。
- arXiv 採套件內建分頁、最多 3 次重試，請求間隔 3 秒。
- 每篇成功評分先保存 JSONL，報告完成才更新 seen；中途退出後，下次會從資料庫恢復，避免重複評分已保存的論文。
- 同日重跑會保留並合併當日結果，沒有新論文時不會清空既有報告。
- 每次從資料庫重建各日期報告，可恢復中斷的報告寫入；日期採本機執行日期。
- 報告統計涵蓋當日全部成功結果，列出篇數另受篩選及上限影響。該次失敗篇數在 CLI 日誌與退出碼中顯示。
- JSONL 每行包含論文欄位、`date` 與 `profile_key`。MVP 使用原子重寫新增資料，避免半行損壞；日後資料大量累積可改為 SQLite。
- seen、資料庫與報告採暫存檔加原子替換，檔案鎖防止共用儲存路徑的程序同時寫入。鎖檔保留是正常行為，程序結束後會釋放 OS lock。
- 資料損壞或 seen 含有資料庫不存在的 ID 時，程式停止並保留原檔；請還原備份或封存整組資料後重建。
- 關閉 arXiv 來源時不抓新論文，仍可重建既有報告。

## 測試

依使用者要求，本次只做 Python 語法檢查，沒有執行 pytest、安裝依賴或呼叫真實 API。

```powershell
uv sync
uv run pytest -q
```

測試涵蓋設定驗證、ID 正規化、metadata、機率邊界、多維度問題、SDK 重試設定、seen / JSONL、報告排序與篩選，以及單篇失敗、寫入失敗、跨日恢復和研究設定變更。資料來源與評分請求均使用測試替身，測試不會連線呼叫 arXiv / TypeSafe。

自行小量實測時，可先將 `max_results` 設為 3，依需求關閉 dimensions，再設定 key 執行。確認報告與重跑去重後，再提高篇數。

| 退出碼 | 意義 |
|---|---|
| 0 | 正常完成或設定檢查成功 |
| 1 | 設定、擷取、儲存等整體錯誤 |
| 2 | 已產生報告，但有論文評分失敗，可重跑 |
| 130 | 使用者中斷 |

## 專案結構

```text
paper-radar/
├── README.md
├── pyproject.toml
├── .gitignore
├── main.py
├── config/
│   ├── config.example.json
│   └── config.json
├── src/paper_radar/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── fetch.py
│   ├── evaluator.py
│   ├── storage.py
│   ├── report.py
│   └── pipeline.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_fetch.py
│   ├── test_evaluator.py
│   ├── test_storage.py
│   ├── test_report.py
│   ├── test_pipeline.py
│   └── test_cli.py
├── data/.gitkeep
└── daily/.gitkeep
```

`uv.lock`、`.venv/` 與實際資料於安裝或執行後建立。個人 config、資料、報告和 `.env` 已列入 `.gitignore`。本版不包含排程、自動 commit 或 push。

## 官方參考

- [TypeSafe Python SDK](https://docs.typesafe.ai/sdk/python)
- [同步 client 參數](https://docs.typesafe.ai/sdk/python/api/clients/sync)
- [RetryPolicy](https://docs.typesafe.ai/sdk/python/api/retries)
- [arxiv 套件文件](https://lukasschwab.me/arxiv.py/arxiv.html)
