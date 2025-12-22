"""OpenRouter API 封裝模組"""

import asyncio
from typing import AsyncIterator
from openai import AsyncOpenAI, RateLimitError, APIStatusError

import config

# 重試設定
REQUEST_DELAY = 1.5  # 每次請求後的延遲（秒）
BASE_RETRY_DELAY = 2  # 重試基礎延遲（秒）
DEFAULT_MAX_RETRIES = 2  # 預設最大重試次數


class OpenRouterClient:
    """OpenRouter API 客戶端，支援 streaming"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.OPENROUTER_API_KEY
        self.client = AsyncOpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=self.api_key,
        )

    async def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
        temperature: float = config.DEFAULT_TEMPERATURE,
        tools: list[dict] | None = None,
        stream: bool = True,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> AsyncIterator[str] | dict:
        """
        發送聊天請求（帶重試機制）

        Args:
            model: 模型 ID (e.g., "openai/gpt-4o")
            messages: 對話訊息列表
            max_tokens: 最大輸出 token 數
            temperature: 溫度參數
            tools: 工具定義（用於 function calling）
            stream: 是否使用 streaming
            max_retries: 最大重試次數

        Returns:
            如果 stream=True，回傳 AsyncIterator[str]
            如果 stream=False，回傳完整回應 dict
        """
        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if stream:
            return self._stream_chat(max_retries=max_retries, **kwargs)
        else:
            return await self._chat_with_retry(max_retries=max_retries, **kwargs)

    async def _chat_with_retry(self, max_retries: int, **kwargs) -> dict:
        """非 streaming 請求（帶重試）"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                # 成功後加入延遲
                await asyncio.sleep(REQUEST_DELAY)
                return self._parse_response(response)
            except (RateLimitError, APIStatusError) as e:
                last_error = e
                if attempt < max_retries:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_error

    async def _stream_chat(self, max_retries: int = DEFAULT_MAX_RETRIES, **kwargs) -> AsyncIterator[str]:
        """Streaming 聊天（帶重試）"""
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                stream = await self.client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                # 成功完成後加入延遲
                await asyncio.sleep(REQUEST_DELAY)
                return
            except (RateLimitError, APIStatusError) as e:
                last_error = e
                if attempt < max_retries:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)
                else:
                    raise

        if last_error:
            raise last_error

    def _parse_response(self, response) -> dict:
        """解析非 streaming 回應"""
        choice = response.choices[0]
        result = {
            "content": choice.message.content or "",
            "tool_calls": None,
            "finish_reason": choice.finish_reason,
        }

        if choice.message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
                for tc in choice.message.tool_calls
            ]

        return result

    async def chat_with_tools(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = config.DEFAULT_MAX_TOKENS,
        temperature: float = config.DEFAULT_TEMPERATURE,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> dict:
        """
        發送帶有工具的聊天請求（不使用 streaming，以便處理 tool calls）

        Returns:
            dict with keys: content, tool_calls, finish_reason
        """
        return await self.chat(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools,
            stream=False,
            max_retries=max_retries,
        )


# 搜尋工具定義
SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "搜尋網路獲取最新資訊。請在需要查證事實、獲取即時資料、或驗證其他人的說法時使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜尋關鍵字，請使用精確且相關的關鍵字",
                }
            },
            "required": ["query"],
        },
    },
}
