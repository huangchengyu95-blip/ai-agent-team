"""
网络搜索和网页抓取工具
- web_search: 用DuckDuckGo搜索最新信息（免费，无需API Key）
- web_fetch: 抓取指定网页的文字内容
"""

import requests
from bs4 import BeautifulSoup

# 尝试导入DuckDuckGo搜索库
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("警告：duckduckgo-search库未安装，搜索功能不可用")


def web_search(query: str, max_results: int = 8) -> str:
    """
    用DuckDuckGo搜索网络，返回格式化的搜索结果文字

    参数：
    - query: 搜索关键词
    - max_results: 最多返回几条结果

    返回：格式化的搜索结果字符串
    """
    if not DDGS_AVAILABLE:
        return "搜索功能不可用：请先安装duckduckgo-search库（pip install duckduckgo-search）"

    try:
        with DDGS() as ddgs:
            # timelimit: 'd'=最近一天, 'w'=最近一周, 'm'=最近一个月
            results = list(ddgs.text(
                query,
                max_results=max_results,
                timelimit='w'  # 只搜索最近一周的内容，保证信息新鲜
            ))

        if not results:
            return f"没有找到关于「{query}」的最新结果"

        # 格式化搜索结果
        formatted = [f"搜索关键词：{query}\n搜索结果：\n"]
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', '无标题')}**\n"
                f"   来源：{r.get('href', '未知')}\n"
                f"   摘要：{r.get('body', '无摘要')}\n"
            )

        return "\n".join(formatted)

    except Exception as e:
        return f"搜索出错（关键词：{query}）：{str(e)}"


def web_fetch(url: str, max_length: int = 4000) -> str:
    """
    抓取指定网页的主要文字内容

    参数：
    - url: 要抓取的网页地址
    - max_length: 最多返回多少个字符

    返回：网页主要文字内容
    """
    try:
        # 模拟浏览器访问，避免被网站拒绝
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()  # 如果状态码不是200，抛出异常

        # 解析HTML，提取文字
        soup = BeautifulSoup(response.text, "html.parser")

        # 删除不需要的标签（导航栏、脚注、广告等）
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "advertisement", "iframe"]):
            tag.decompose()

        # 提取标题
        title = soup.title.string if soup.title else "未知标题"

        # 提取正文
        text = soup.get_text(separator="\n", strip=True)

        # 清理多余空行
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = "\n".join(lines)

        # 返回结果（限制长度）
        result = f"网页标题：{title}\n网页地址：{url}\n\n内容摘要：\n{clean_text[:max_length]}"
        if len(clean_text) > max_length:
            result += f"\n...[内容已截断，原文约{len(clean_text)}个字符]"

        return result

    except requests.exceptions.Timeout:
        return f"访问超时：{url}"
    except requests.exceptions.HTTPError as e:
        return f"网页访问错误（{e.response.status_code}）：{url}"
    except Exception as e:
        return f"抓取网页失败（{url}）：{str(e)}"
