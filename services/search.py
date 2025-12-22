"""Tavily 搜尋服務封裝"""

from tavily import TavilyClient

import config


class SearchService:
    """網路搜尋服務"""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or config.TAVILY_API_KEY
        self._client = None

    @property
    def client(self) -> TavilyClient:
        """延遲初始化 Tavily 客戶端"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("TAVILY_API_KEY 未設定")
            self._client = TavilyClient(api_key=self.api_key)
        return self._client

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
    ) -> dict:
        """
        執行網路搜尋

        Args:
            query: 搜尋關鍵字
            max_results: 最大結果數量
            search_depth: 搜尋深度 ("basic" 或 "advanced")
            include_answer: 是否包含 AI 生成的摘要答案

        Returns:
            dict with keys:
                - answer: AI 生成的摘要（如果 include_answer=True）
                - results: 搜尋結果列表，每個結果包含 title, url, content
        """
        try:
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=include_answer,
            )

            results = []
            for item in response.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                })

            return {
                "answer": response.get("answer", ""),
                "results": results,
            }

        except Exception as e:
            return {
                "error": str(e),
                "answer": "",
                "results": [],
            }

    def format_results_for_ai(self, search_results: dict) -> str:
        """
        將搜尋結果格式化為 AI 可讀的文字

        Args:
            search_results: search() 方法的回傳值

        Returns:
            格式化的搜尋結果字串
        """
        if "error" in search_results:
            return f"搜尋失敗: {search_results['error']}"

        lines = ["### 搜尋結果\n"]

        if search_results.get("answer"):
            lines.append(f"**摘要**: {search_results['answer']}\n")

        lines.append("**來源**:")
        for i, result in enumerate(search_results["results"], 1):
            lines.append(f"\n{i}. **{result['title']}**")
            lines.append(f"   - 網址: {result['url']}")
            lines.append(f"   - 內容: {result['content'][:200]}...")

        return "\n".join(lines)

    def format_sources(self, search_results: dict) -> str:
        """
        只取得來源連結列表

        Args:
            search_results: search() 方法的回傳值

        Returns:
            格式化的來源連結
        """
        if "error" in search_results or not search_results.get("results"):
            return ""

        sources = []
        for result in search_results["results"]:
            sources.append(f"- [{result['title']}]({result['url']})")

        return "\n".join(sources)
