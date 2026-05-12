import json
import urllib.parse
import urllib.request

from pydantic import BaseModel, Field

from app.core.config import settings
from app.skills.base import CancelToken, OnProgress, Skill, SkillError, SkillProgress


class WebSearchParams(BaseModel):
    user_id: str = ""
    query: str = Field(min_length=1, max_length=500)
    num: int = Field(default=5, ge=1, le=10)


class WebSearchAggregatorSkill(Skill):
    name = "web_search_aggregator"
    description = "搜索网页并汇总结果，返回标题、摘要和链接"
    parameters = WebSearchParams
    example_triggers = ["搜一下", "帮我查", "找找关于", "搜索", "查一下", "帮我搜", "查资料", "网上找找"]

    async def execute(
        self,
        params: dict,
        on_progress: OnProgress,
        timeout: float,
        cancel_token: CancelToken,
    ) -> str:
        del timeout
        try:
            parsed = WebSearchParams.model_validate(params)
        except Exception as exc:
            raise SkillError("INVALID_PARAMS", str(exc), "搜索参数不太对。") from exc

        if not settings.google_search_api_key or not settings.google_search_cx:
            raise SkillError("API_KEY_MISSING", "Google Search API not configured", "搜索功能还没配置好，需要先设置 Google Search API Key。")

        await on_progress(SkillProgress(skill_name=self.name, message=f"搜索: {parsed.query}...", percent=0.4))
        if cancel_token.is_set():
            raise SkillError("CANCELLED", "Skill cancelled", "搜索已取消。")

        query_params = urllib.parse.urlencode(
            {
                "key": settings.google_search_api_key,
                "cx": settings.google_search_cx,
                "q": parsed.query,
                "num": parsed.num,
            }
        )
        request = urllib.request.Request(
            f"https://www.googleapis.com/customsearch/v1?{query_params}",
            headers={"User-Agent": "ShinobuChat/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise SkillError("NETWORK_ERROR", str(exc), "网络好像不太稳定，稍后再搜？") from exc

        await on_progress(SkillProgress(skill_name=self.name, message="整理搜索结果...", percent=0.85))
        items = data.get("items", [])
        if not items:
            return f"没有找到关于「{parsed.query}」的结果。"

        lines = [f"# 搜索结果：{parsed.query}"]
        for index, item in enumerate(items, 1):
            title = item.get("title", "无标题")
            snippet = item.get("snippet", "无摘要")
            link = item.get("link", "")
            lines.append(f"\n## {index}. {title}\n{snippet}\n{link}")
        return "\n".join(lines)
