"""
Agent 1: AI社交动态追踪员
- 每隔4小时搜索AI社交方向的最新动态
- 筛选有产品决策价值的重要信息
- 追加到飞书"AI动态追踪汇总"文档（同一个文档，按时间追加）
- 更新系统状态看板
"""

import json
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径（让import能找到utils包）
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.llm_client import LLMClient
from utils.feishu_client import FeishuClient
from utils.status_tracker import update_agent_status, log_activity, update_feishu_links
from utils.web_tools import format_rss_sources, fetch_hn_posts, fetch_reddit_posts


# ============================================================
# 优质信息源（RSS订阅，无需任何API Key）
# ============================================================

CURATED_RSS_SOURCES = {
    # === 头部AI公司官方博客 ===
    "OpenAI官方博客（产品发布与研究公告）": "https://openai.com/news/rss.xml",
    "Hugging Face博客（开源AI模型与工具）": "https://huggingface.co/blog/feed.xml",
    "Google官方博客（Google AI产品公告）": "https://blog.google/rss/",

    # === AI行业Newsletter ===
    "Ben's Bites（AI行业每日新闻精华）": "https://bensbites.beehiiv.com/feed",
    "AINews by smol.ai（AI研究与工程动态）": "https://buttondown.com/ainews/rss",
    "TheSequence（AI技术与产业深度分析）": "https://thesequence.substack.com/feed",
    "The Algorithmic Bridge（AI与社会的深度思考）": "https://thealgorithmicbridge.substack.com/feed",
    "Interconnects（AI研究前沿，Nathan Lambert）": "https://www.interconnects.ai/feed",
    "Epoch AI（AI能力进展追踪）": "https://epochai.substack.com/feed",
    "Every（AI产品与商业深度分析）": "https://every.to/feed",

    # === 研究员/工程师博客 ===
    "Simon Willison's Weblog（AI工具与应用实践）": "https://simonwillison.net/atom/everything/",

    # === 产品发现 ===
    "Product Hunt（每日新上线AI产品）": "https://www.producthunt.com/feed",

    # === AI播客（YouTube RSS） ===
    "The AI Daily Brief（AI每日要闻播客）":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLRYSuzHGhXPmKnOpd-f588cNNmTe2S9FP",
    "Latent Space Podcast（AI工程师/创业者视角）":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLWEAb1SXhjlfkEF_PxzYHonU_v5LPMI8L",
    "Training Data - Anthropic官方播客":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLOhHNjZItNnMm5tdW61JpnyxeYH5NDDx8",
    "No Priors Podcast（投资人视角的AI趋势）":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLmYVYFmFwGm3txxUduawn7i53C5rDjjd7",
    "Dwarkesh Podcast（深度访谈AI领袖）":
        "https://www.dwarkeshpatel.com/feed",
}

# Hacker News 关注的板块（技术社区真实讨论）
HN_CATEGORIES = [
    "topstories",   # 综合热门
    "showstories",  # Show HN：新工具/项目展示，最容易发现AI创业新项目
]

# Reddit 关注的AI社交相关版块（用户真实反馈第一手来源）
REDDIT_SUBREDDITS = [
    "artificial",       # AI综合讨论
    "ChatGPT",          # ChatGPT用户真实反馈
    "singularity",      # AI未来趋势讨论
    "MachineLearning",  # 研究者社区
]


# ============================================================
# Agent的角色设定（System Prompt）
# ============================================================

SYSTEM_PROMPT = """你是一位专业的AI社交产品方向动态追踪员，工作在一个顶尖的AI产品研究团队中。

你的任务：
搜索并整理AI社交方向最近几个小时的重要动态，筛选出对产品经理有决策价值的信息。

**关注的方向：**
1. AI社交/伴侣/聊天应用的新产品、功能更新（Character.AI、Replika、Poe、Companion Apps等）
2. 头部AI公司（OpenAI、Anthropic、Google、Meta、ByteDance）在社交AI方向的动作
3. 用户对现有AI社交产品的真实反馈、痛点讨论（Reddit、Twitter等）
4. AI社交领域的融资、并购、重大战略变化
5. 新出现的AI社交创业项目（Product Hunt等）
6. 关键意见领袖（AI builder、VC、产品经理）对AI社交的最新思考

**筛选原则（重要！）：**
- 只保留"值得产品经理关注"的信息，过滤掉纯技术细节和无关新闻
- 优先级：用户真实反馈 > 重要产品发布 > 行业思考观点 > 融资动态
- 每条信息要说清楚：是什么、来自哪里、为什么重要

**输出格式（必须是JSON）：**
请严格按以下JSON格式输出，不要有其他内容：
{
  "has_updates": true或false,  // 是否有值得记录的新动态
  "content": "### 追踪时间标题\\n\\n完整的Markdown格式内容...",  // 要写入飞书的内容
  "summary": "一句话总结（用于看板显示）",  // 如：发现5条重要AI社交新动态
  "highlights": ["最重要的1-2条信息（用于飞书消息通知）"]  // 最值得注意的
}

如果没有新的值得记录的动态，has_updates设为false，content可以为空字符串。"""


def run(feishu_client: FeishuClient = None, llm_client: LLMClient = None,
        config: dict = None) -> dict:
    """
    运行AI动态追踪员

    参数：
    - feishu_client: 飞书客户端（None时自动创建）
    - llm_client: LLM客户端（None时自动创建）
    - config: 配置字典（None时从config.json读取）

    返回：运行结果字典 {"success": bool, "summary": str, "has_idea": bool}
    """
    print("\n" + "="*50)
    print("🔍 AI动态追踪员 开始工作...")
    print("="*50)

    # 初始化客户端
    if feishu_client is None:
        feishu_client = FeishuClient()
    if llm_client is None:
        llm_client = LLMClient()
    if config is None:
        config = _load_config()

    # 更新状态：正在运行
    update_agent_status("trend_tracker", "running", "正在搜索AI社交最新动态...")
    log_activity("trend_tracker", "开始搜索AI社交方向最新动态")

    try:
        # 获取飞书文档ID
        trend_doc_id = config.get("feishu", {}).get("documents", {}).get("trend_doc_id", "")

        # 读取飞书文档中已有的动态内容（末尾3000字），用于去重
        recent_trend_content = ""
        if trend_doc_id:
            print("\n📖 读取已有动态文档（用于去重）...")
            existing = feishu_client.get_document_content(trend_doc_id)
            if existing:
                recent_trend_content = existing[-3000:]  # 只取末尾，避免上下文过长
                print(f"   已读取最近内容（{len(recent_trend_content)}字）")

        # 预先读取所有信息源（直接拉取，不消耗LLM工具调用次数）
        now = datetime.now()

        print("\n📡 读取RSS信息源...")
        rss_content = format_rss_sources(CURATED_RSS_SOURCES, max_items_per_source=3)

        print("📡 读取Hacker News...")
        hn_content = "\n".join([fetch_hn_posts(cat, max_items=8) for cat in HN_CATEGORIES])

        print("📡 读取Reddit...")
        reddit_content = fetch_reddit_posts(REDDIT_SUBREDDITS, max_items_per_sub=5)

        print("   全部信息源读取完成")

        # 构建给Agent的提示，包含已抓取的信息源内容
        user_prompt = f"""
当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}

==============================
【RSS信息源（Newsletter + 官方博客 + 播客）】
==============================
{rss_content}

==============================
【Hacker News 技术社区讨论】
==============================
{hn_content}

==============================
【Reddit 用户真实讨论】
==============================
{reddit_content}

==============================
【飞书文档中已记录的最近动态（请严格去重！）】
==============================
{recent_trend_content if recent_trend_content else "（暂无历史记录）"}

⚠️ 去重说明：上方"已记录的最近动态"是我们文档里最近保存的内容。
如果某条信息（产品发布、研究报告、用户讨论等）在上面已经出现过，请跳过，不要再次记录。
只记录那些在历史记录里完全没有提到的新内容。

==============================
【你的工作任务】
==============================

上面已自动抓取了三类信息源：RSS博客/Newsletter、Hacker News技术社区、Reddit用户讨论。
请重点分析其中与AI社交方向相关的内容。

此外，请用 web_search 工具补充搜索以下方向（优先搜索上面没有覆盖到的内容）：
1. "AI companion app 2025" 、"AI social product news" — 最新AI社交产品动态
2. "Character AI Replika 2025 update" — 头部AI社交产品的最新动态
3. 对上面任何引发兴趣的话题，用 web_fetch 深入阅读原文

请综合以上全部内容，筛选出对AI社交产品经理有价值的**新**信息（排除已记录的内容），按JSON格式输出。
"""

        # 运行Agent
        print("\n📡 正在搜索最新动态...")
        response = llm_client.run_agent(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            use_tools=True,
            max_iterations=20  # 追踪员需要多次搜索
        )

        # 解析Agent的回应
        result = _parse_agent_response(response)

        if not result.get("has_updates"):
            print("ℹ️  本次没有发现值得记录的新动态")
            update_agent_status("trend_tracker", "idle", "本次未发现重要新动态")
            log_activity("trend_tracker", f"搜索完成，暂无重要新动态")
            return {"success": True, "summary": "无新动态", "has_updates": False}

        # 把内容写入飞书文档
        content_to_write = result.get("content", "")
        summary = result.get("summary", "发现新动态")

        if content_to_write and trend_doc_id:
            print(f"\n📝 正在写入飞书文档...")
            write_success = feishu_client.append_to_document(trend_doc_id, content_to_write)
            if write_success:
                # 优先从config读取文档URL（含正确域名），若没有则自动构建
                doc_url = config.get("feishu", {}).get("documents", {}).get("trend_doc_url", "")
                if not doc_url:
                    doc_url = f"https://docs.feishu.cn/docx/{trend_doc_id}"
                update_feishu_links(trend_doc=doc_url)
                print(f"✅ 成功追加到飞书文档")
            else:
                # 飞书写入失败：打印内容到日志，并返回失败标志（会让pipeline报红）
                print("❌ 飞书文档写入失败！内容如下（可手动复制）：")
                print(content_to_write[:1000])
                update_agent_status("trend_tracker", "idle", f"⚠️ 飞书写入失败：{summary}")
                return {"success": False, "summary": f"飞书写入失败：{summary}", "has_updates": True}
        elif content_to_write:
            print("\n📋 飞书文档ID未配置，动态内容：")
            print(content_to_write[:500] + "..." if len(content_to_write) > 500 else content_to_write)
        else:
            print("⚠️  没有生成内容")

        # 更新状态
        update_agent_status("trend_tracker", "idle", summary)
        log_activity("trend_tracker", summary)

        print(f"\n✅ 动态追踪完成：{summary}")

        return {
            "success": True,
            "summary": summary,
            "has_updates": True,
            "content": content_to_write,
            "highlights": result.get("highlights", [])
        }

    except Exception as e:
        error_msg = f"动态追踪员出错：{str(e)}"
        print(f"\n❌ {error_msg}")
        update_agent_status("trend_tracker", "error", error_msg)
        log_activity("trend_tracker", f"运行出错：{str(e)[:100]}")
        return {"success": False, "summary": error_msg, "has_updates": False}


def _parse_agent_response(response: str) -> dict:
    """
    解析Agent的回应，提取JSON格式的结果

    有时模型会在JSON前后加上一些说明文字，需要提取出JSON部分
    """
    if not response:
        return {"has_updates": False, "content": "", "summary": "无响应"}

    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON部分（在```json和```之间，或者{和}之间）
    import re

    # 查找 ```json ... ``` 格式
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # 查找第一个{到最后一个}
    start = response.find('{')
    end = response.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(response[start:end+1])
        except json.JSONDecodeError:
            pass

    # 如果无法解析JSON，把整个回应作为内容保存
    print("⚠️  无法解析JSON格式，将原始回应作为内容保存")
    now = datetime.now()
    return {
        "has_updates": bool(response.strip()),
        "content": f"## {now.strftime('%Y-%m-%d %H:%M')}\n\n{response}",
        "summary": "动态追踪完成（格式解析异常）"
    }


def _load_config() -> dict:
    """读取config.json配置文件"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  读取config.json失败：{e}")
        return {}


# ============================================================
# 直接运行此文件时的入口
# ============================================================

if __name__ == "__main__":
    print("单独测试：AI动态追踪员")
    result = run()
    print(f"\n运行结果：{result.get('summary')}")
