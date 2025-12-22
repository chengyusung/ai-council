# AI Council - LLM 委員會討論系統

讓多個 AI 模型一起討論主題的工具，基於 Andrej Karpathy 提出的 LLM Council 概念。

## 功能特色

- **五頂思考帽**：每位成員發言時隨機分配思考帽，從不同角度切入討論
  - ⚪ 白帽：事實與數據（冷靜客觀，如科學家）
  - 🔴 紅帽：情感與直覺（直接情緒化，表達好惡）
  - ⚫ 黑帽：批判與風險（尖銳懷疑，如審計師）
  - 🟡 黃帽：樂觀與價值（樂觀鼓勵，如支持者）
  - 🟢 綠帽：創意與替代方案（開放好奇，如創意總監）
- **蘇格拉底反詰法**：成員必須引用前一位觀點並提出挑戰性問題
- **挑釁型主持人**：前期（第 1-2 輪）挑撥製造衝突，後期（第 3 輪起）收斂整合觀點
- **匿名化發言**：使用隨機名字（Alice、Bob...）避免模型名稱偏見
- **網路搜尋**：主持人可在最終總結時搜尋驗證資訊
- **Rate Limit 處理**：自動重試機制，成員失敗時跳過繼續討論

## 安裝

### 前置需求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (Python 套件管理工具)

### 安裝步驟

```bash
# 1. 進入專案目錄
cd ai-council

# 2. 安裝依賴
uv sync

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env 填入你的 API Keys
```

## 取得 API Keys

1. **OpenRouter API Key**
   - 前往 https://openrouter.ai/keys
   - 註冊帳號並建立 API Key
   - OpenRouter 可以用單一 API Key 存取多種 AI 模型
   - **重要**：前往 https://openrouter.ai/settings/privacy 設定隱私政策，否則免費模型可能無法使用

2. **Tavily API Key** (網路搜尋用)
   - 前往 https://tavily.com/
   - 註冊帳號取得 API Key
   - 免費額度：1000 次/月

## 使用方式

```bash
# 啟動伺服器
uv run python main.py

# 指定埠號
uv run python main.py --port 8080

# 建立公開分享連結
uv run python main.py --share
```

啟動後開啟瀏覽器訪問 http://127.0.0.1:7860

## 操作說明

1. **設定討論主題**：在左側輸入要討論的主題
2. **選擇參與者**：選擇要參與討論的 AI 模型（成員間不可重複）
3. **設定人設**（選填）：為主持人或成員設定角色人設
4. **設定輪數**：每位成員會發言 N 輪
5. **開始討論**：點擊「開始討論」按鈕
6. **查看對照表**：側邊欄會顯示名字與模型的對應關係
7. **互動控制**：
   - 點擊「請主持人總結」可提前進入總結
   - 點擊「停止」可中斷討論

## 討論流程

```
1. 主持人開場（挑釁型開場，預示衝突點）
2. 成員依序發言（每人每次戴隨機帽子）
   ├─ 第一位：只能是 ⚪白帽 或 🟢綠帽（不能黑帽，無東西可批判）
   ├─ 發言規則：
   │   ├─ 引用上一位的具體觀點
   │   ├─ 依帽子角色發表觀點
   │   └─ 結尾提出挑戰性問題（蘇格拉底問題）
   └─ 主持人小結（第 1-2 輪挑撥，第 3 輪起收斂）
3. 重複 N 輪
4. 主持人最終總結（可使用網路搜尋驗證）
```

## 專案結構

```
ai-council/
├── main.py              # 程式入口
├── config.py            # 設定管理（模型清單、名字列表）
├── models.py            # 資料模型（Message, SessionConfig 等）
├── council/             # 核心邏輯
│   ├── hats.py          # 五頂思考帽管理（HatManager, HatColor）
│   ├── prompts.py       # Prompt 模板（帽子指令、蘇格拉底問題）
│   ├── moderator.py     # 主持人（挑釁型，前期挑撥後期收斂）
│   ├── member.py        # 討論成員（蘇格拉底式發言）
│   └── session.py       # 會議管理（流程控制、帽子分配）
├── services/            # 服務層
│   ├── openrouter.py    # OpenRouter API（含重試機制）
│   └── search.py        # Tavily 搜尋
└── ui/
    └── app.py           # Gradio UI
```

## 模型設定

### 預設支援模型

編輯 `config.py` 中的 `AVAILABLE_MODELS` 可自訂模型清單：

```python
AVAILABLE_MODELS = [
    # 付費模型
    {"id": "openai/gpt-5.2", "name": "GPT-5.2"},
    {"id": "anthropic/claude-sonnet-4.5", "name": "Claude Sonnet 4.5"},
    {"id": "google/gemini-3-pro-preview", "name": "Gemini 3 Pro"},
    {"id": "google/gemini-3-flash-preview", "name": "Gemini 3 Flash"},
    {"id": "x-ai/grok-4.1-fast", "name": "Grok 4.1 Fast"},
    {"id": "deepseek/deepseek-v3.2", "name": "DeepSeek V3.2"},
    {"id": "moonshotai/kimi-k2-thinking", "name": "Kimi K2 Thinking"},

    # 免費模型（ID 結尾有 :free）
    {"id": "allenai/olmo-3.1-32b-think:free", "name": "Olmo 3.1 32b Think"},
    {"id": "xiaomi/mimo-v2-flash:free", "name": "Mimo V2 Flash"},
    {"id": "mistralai/devstral-2512:free", "name": "Devstral 2512"},
    {"id": "openai/gpt-oss-120b:free", "name": "GPT-OSS 120b"},
    {"id": "z-ai/glm-4.5-air:free", "name": "GLM 4.5 Air"},
    {"id": "moonshotai/kimi-k2:free", "name": "Kimi K2"},
    {"id": "deepseek/deepseek-r1-0528:free", "name": "DeepSeek R1 0528"},
    {"id": "qwen/qwen3-coder:free", "name": "Qwen 3 Coder"},
]
```

### 新增模型

1. 前往 [OpenRouter Models](https://openrouter.ai/models) 查詢模型 ID
2. 在 `AVAILABLE_MODELS` 新增一筆：
   ```python
   {"id": "provider/model-name", "name": "顯示名稱"},
   ```
3. 重啟應用程式

### 其他設定

```python
# 預設設定
DEFAULT_MAX_TOKENS = 500      # 每次發言的 token 上限
DEFAULT_ROUNDS = 3            # 預設討論輪數
DEFAULT_TEMPERATURE = 0.7     # 生成溫度

# 成員隨機名字
RANDOM_NAMES = ["Alice", "Bob", "Carol", "David", "Eve", ...]

# 主持人名字
MODERATOR_NAME = "Max"
```

## 帽子分配機制

| 項目 | 說明 |
|------|------|
| 分配時機 | 每次發言時系統隨機分配 |
| 第一位發言者 | 只能是 ⚪白帽 或 🟢綠帽 |
| 權重機制 | 少用的帽子有更高機率被選中 |
| 主持人 | 不戴帽子，負責流程控制 |

## Rate Limit 處理

免費模型容易遇到 Rate Limit，系統會自動處理：

| 場景 | 重試次數 | 失敗處理 |
|------|---------:|---------|
| 成員發言 | 2 次 | 跳過此成員，繼續討論 |
| 主持人小結 | 5 次 | 必須成功 |
| 主持人開場/總結 | 5 次 | 必須成功 |

重試間隔：指數退避（2s → 4s → 8s → 16s → 32s）

## License

MIT
