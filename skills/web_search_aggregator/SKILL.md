---
name: web_search_aggregator
description: 汇总网页结果，对多个网页或搜索结果做去重、来源归纳和结论整理。
metadata: {"echo":{"emoji":"search"}}
---

# Web Search Aggregator

Use this skill when the user asks to search the web, compare pages, summarize search results, or 汇总网页结果.

## Workflow

1. Clarify the topic if the query is too broad.
2. Fetch relevant known URLs with `fetch_web_page`.
3. If the user supplied URLs, fetch those first.
4. If the user supplied a search query but no URLs, use a search-result webpage endpoint through `fetch_web_page` or a read-only `curl` request, then fetch the most relevant pages.
5. Deduplicate repeated claims and separate facts from inference.
6. Prefer primary sources when available.

## Output

Use:

1. Short answer
2. Source-by-source notes
3. Consensus / disagreement
4. Links or source names

Mention when network fetches fail or sources are thin.
