"""
网络搜索和网页抓取工具
- web_search: 用DuckDuckGo搜索最新信息（免费，无需API Key）
- web_fetch: 抓取指定网页的文字内容
- fetch_rss_feed: 读取RSS/Atom订阅源（支持Newsletter和YouTube播客）
- format_rss_sources: 批量读取多个RSS源，格式化成文本
- fetch_hn_posts: 读取Hacker News热门帖子（官方免费API，无需Key）
- fetch_reddit_posts: 读取Reddit子版块最新帖子（公开JSON，无需Key）
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
                timelimit='d'  # 只搜索最近24小时，每4小时运行一次，确保信息不重复
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


def fetch_rss_feed(url: str, max_items: int = 5) -> list:
    """
    读取RSS或Atom格式的订阅源，返回最新文章列表
    支持：Newsletter RSS、YouTube播客RSS（无需任何API Key）

    参数：
    - url: RSS feed地址
    - max_items: 最多返回几条

    返回：文章列表，每条包含 title/link/date/summary
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; RSS Reader)",
            "Accept": "application/rss+xml, application/xml, application/atom+xml, text/xml",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()

        # 用BeautifulSoup解析XML，优先用lxml-xml，失败则回退到内置xml解析
        try:
            soup = BeautifulSoup(resp.content, "lxml-xml")
        except Exception:
            soup = BeautifulSoup(resp.content, "xml")

        # RSS格式用<item>标签，Atom格式（YouTube等）用<entry>标签
        entries = soup.find_all("item") or soup.find_all("entry")

        items = []
        for entry in entries[:max_items]:
            # 提取标题
            title_tag = entry.find("title")
            title = title_tag.get_text(strip=True) if title_tag else "无标题"

            # 提取链接（Atom用href属性，RSS用文本内容）
            link_tag = entry.find("link")
            if link_tag:
                link = link_tag.get("href") or link_tag.get_text(strip=True)
            else:
                link = ""

            # 提取发布时间
            date_tag = (entry.find("pubDate") or entry.find("published")
                        or entry.find("updated"))
            date = date_tag.get_text(strip=True)[:16] if date_tag else ""

            # 提取摘要（RSS是description，Atom是summary/content，内容可能含HTML）
            summary_tag = (entry.find("description") or entry.find("summary")
                           or entry.find("content"))
            summary = ""
            if summary_tag:
                raw = summary_tag.get_text(strip=True)
                # 如果摘要里含HTML标签，再用BS解析一次剥掉
                if "<" in raw:
                    raw = BeautifulSoup(raw, "html.parser").get_text()
                summary = raw[:250].strip()

            items.append({
                "title": title,
                "link": link,
                "date": date,
                "summary": summary,
            })

        return items

    except Exception:
        # RSS读取失败不影响主流程，静默返回空列表
        return []


def format_rss_sources(sources_dict: dict, max_items_per_source: int = 4) -> str:
    """
    批量读取多个RSS信息源，格式化成给LLM阅读的文本

    参数：
    - sources_dict: {"源名称": "RSS URL", ...}
    - max_items_per_source: 每个源最多取几条

    返回：格式化文本，供写入LLM的user_prompt
    """
    all_sections = []
    success_count = 0

    for source_name, url in sources_dict.items():
        items = fetch_rss_feed(url, max_items=max_items_per_source)
        if not items:
            continue

        success_count += 1
        section_lines = [f"\n**{source_name}**"]
        for item in items:
            line = f"• {item['title']}"
            if item["date"]:
                line += f"（{item['date'][:10]}）"
            if item["summary"]:
                line += f"\n  {item['summary']}"
            if item["link"]:
                line += f"\n  {item['link']}"
            section_lines.append(line)

        all_sections.append("\n".join(section_lines))

    if not all_sections:
        return "（信息源读取失败，请通过搜索获取信息）"

    header = f"以下是从 {success_count} 个优质信息源自动抓取的最新内容：\n"
    return header + "\n".join(all_sections)


def fetch_hn_posts(category: str = "topstories", max_items: int = 10) -> str:
    """
    读取Hacker News热门帖子（使用HN官方免费API，无需任何Key）

    参数：
    - category: 帖子类型
        "topstories" = 热门帖子（综合热度排名）
        "newstories" = 最新帖子
        "askstories"  = Ask HN（技术社区的用户提问讨论，高质量）
        "showstories" = Show HN（开发者分享的新项目/工具）
    - max_items: 最多返回几条

    返回：格式化的帖子文本
    """
    try:
        # 第一步：获取帖子ID列表
        list_url = f"https://hacker-news.firebaseio.com/v0/{category}.json"
        resp = requests.get(list_url, timeout=10)
        resp.raise_for_status()
        story_ids = resp.json()[:max_items * 2]  # 多取一些，避免部分失败

        # 第二步：逐条获取帖子详情
        items = []
        for story_id in story_ids:
            if len(items) >= max_items:
                break
            try:
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                item_resp = requests.get(item_url, timeout=5)
                item = item_resp.json()
                # 只保留有标题的帖子（过滤掉评论等）
                if item and item.get("title") and item.get("type") == "story":
                    items.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "score": item.get("score", 0),
                        "comments": item.get("descendants", 0),
                        "by": item.get("by", ""),
                    })
            except Exception:
                continue

        if not items:
            return "（Hacker News 暂时无法读取）"

        # 格式化输出
        category_names = {
            "topstories": "热门帖子",
            "newstories": "最新帖子",
            "askstories": "Ask HN（技术社区问答）",
            "showstories": "Show HN（新项目展示）",
        }
        label = category_names.get(category, category)
        lines = [f"\n**Hacker News · {label}**"]
        for item in items:
            lines.append(
                f"• {item['title']}\n"
                f"  👍{item['score']} 💬{item['comments']}  {item['url']}"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"（Hacker News 读取失败：{str(e)}）"


def fetch_reddit_posts(subreddits: list, max_items_per_sub: int = 5) -> str:
    """
    读取Reddit子版块的热门帖子（使用Reddit公开JSON，无需任何API Key）

    参数：
    - subreddits: 子版块列表，如 ["artificial", "ChatGPT", "MachineLearning"]
    - max_items_per_sub: 每个版块最多取几条

    返回：格式化的帖子文本
    """
    # 模拟浏览器，避免被Reddit拒绝
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AggregatorBot/1.0)",
        "Accept": "application/json",
    }

    all_sections = []

    for sub in subreddits:
        try:
            # Reddit公开JSON接口，hot=热门，new=最新
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={max_items_per_sub}"
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            if not posts:
                continue

            lines = [f"\n**Reddit · r/{sub}**"]
            for post in posts[:max_items_per_sub]:
                pd = post.get("data", {})
                title = pd.get("title", "无标题")
                score = pd.get("score", 0)
                num_comments = pd.get("num_comments", 0)
                permalink = f"https://reddit.com{pd.get('permalink', '')}"
                selftext = pd.get("selftext", "")[:150].strip()

                line = f"• {title}\n  👍{score} 💬{num_comments}  {permalink}"
                if selftext:
                    line += f"\n  {selftext}..."
                lines.append(line)

            all_sections.append("\n".join(lines))

        except Exception:
            # 单个版块失败不影响其他版块
            continue

    if not all_sections:
        return "（Reddit 暂时无法读取）"

    return "\n".join(all_sections)
