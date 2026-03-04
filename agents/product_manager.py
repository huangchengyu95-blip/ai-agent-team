"""
Agent 2: AI社交产品经理
- 读取最新AI动态追踪结果
- 主动搜索和研究感兴趣的方向（不仅仅依赖Agent 1的信息）
- 不断更新飞书"AI社交认知沉淀"文档（持续拓展认知框架）
- 发现有价值的产品机会时，生成完整的产品创意方案
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.llm_client import LLMClient
from utils.feishu_client import FeishuClient
from utils.status_tracker import update_agent_status, log_activity, increment_stat, update_feishu_links, get_ideas_history
from utils.web_tools import format_rss_sources, fetch_hn_posts


# ============================================================
# 产品经理专用优质信息源（偏向产品策略、用户洞察、技术前沿、投资视角）
# ============================================================

CURATED_RSS_SOURCES = {
    # === AI产品经理必读Newsletter ===
    "Marily's AI Product（Google AI产品总监，产品策略必读）": "https://marily.substack.com/feed",
    "One Useful Thing（Wharton教授，AI对产品/工作影响）": "https://www.oneusefulthing.org/feed",
    "Every（AI时代的产品与商业深度分析）": "https://every.to/feed",
    "Creator Economy by Peter Yang（AI产品经理必读）": "https://creatoreconomy.so/feed",
    "The Algorithmic Bridge（AI与普通用户的桥梁视角）": "https://thealgorithmicbridge.substack.com/feed",

    # === 研究员/工程师深度思考 ===
    "Ahead of AI by Sebastian Raschka（LLM研究深度解读）": "https://magazine.sebastianraschka.com/feed",
    "Lil'Log by Lilian Weng（Anthropic研究员，技术洞察）": "https://lilianweng.github.io/index.xml",
    "karpathy Blog（AI领域最有影响力的工程师博客）": "https://karpathy.github.io/feed.xml",
    "Simon Willison's Weblog（AI工具实践，高产量）": "https://simonwillison.net/atom/everything/",
    "Interconnects（AI研究前沿对产品的影响）": "https://www.interconnects.ai/feed",

    # === 投资/创业视角 ===
    "a16z Future（顶级VC对AI产品趋势的判断）": "https://future.com/feed",
    "Ben's Bites（AI行业产品动态精华）": "https://bensbites.beehiiv.com/feed",

    # === 创业/产品播客（YouTube RSS） ===
    "Lenny's Podcast（顶级产品经理访谈）":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLuMcoKK9mKgHtW_o9h5sGO2vXrffKHwJL",
    "Lightcone Podcast - YC（创业与产品战略）":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLQ-uHSnFig5Ob4XXhgSK26Smb4oRhzFmK",
    "Dwarkesh Podcast（深度访谈AI领袖，战略思考）":
        "https://www.dwarkeshpatel.com/feed",
    "Latent Space Podcast（AI应用层产品机会）":
        "https://www.youtube.com/feeds/videos.xml?playlist_id=PLWEAb1SXhjlfkEF_PxzYHonU_v5LPMI8L",
}

# Hacker News Ask HN — 最能反映用户真实需求的地方
HN_CATEGORIES_PM = [
    "askstories",   # Ask HN：用户提问和讨论，能发现真实需求痛点
    "showstories",  # Show HN：新产品展示，发现竞品和灵感
]


# ============================================================
# Agent的角色设定
# ============================================================

SYSTEM_PROMPT = """你是一位专注于AI社交方向的资深产品经理，在知名AI公司工作多年，有深厚的用户洞察能力和产品设计经验。

你的工作方式：
1. **持续积累认知**：通过大量阅读和思考，不断完善你对AI社交方向的理解框架
2. **主动探索**：不满足于表面信息，会主动搜索深入研究感兴趣的话题
3. **产品敏感度**：时刻关注用户真实需求，在信息中发现产品机会
4. **结构化思考**：把碎片化的信息整合成系统性的认知框架

**你要维护的认知沉淀文档框架：**
```
# AI社交产品认知沉淀

## 一、AI社交的本质与趋势
（AI社交是什么，正在向什么方向发展）

## 二、核心用户需求分析
（用户为什么需要AI社交，不同类型用户的诉求）

## 三、现有产品格局
（主要竞品分析，各自的优势和局限）

## 四、未被满足的需求（机会所在）
（用户有哪些痛点还没被很好地解决）

## 五、产品设计原则
（做好AI社交产品需要遵循什么原则）

## 六、技术-产品结合点
（哪些AI技术突破创造了新的产品机会）

---
## 更新日志
（每次更新后追加，记录有什么新洞察）
```

**关于产品创意的判断标准（极其重要！严格执行！）：**

只有同时满足全部5个条件，才生成产品创意方案：
1. 用户痛点明确且真实存在（必须有用户讨论/数据等具体证据，不能凭感觉）
2. 现有解决方案不够好（必须说清楚竞品具体在哪里差）
3. 当前AI能力可以支撑（技术上可行，不是未来才能实现）
4. 这个机会有时间窗口（现在做比6个月后做有优势）
5. 与近期已有创意方向明显不同（在 user_prompt 中会提供已有创意列表，必须差异化）

**宁可这次不输出创意，也不要输出低质量或雷同的创意。**
预期约 30-50% 的运行次数才应该产出一个新创意。如果没有真正新颖且满足条件的机会，直接输出 has_product_idea: false。

**输出格式（必须是JSON）：**
{
  "knowledge_update": "认知沉淀文档的【完整内容】（Markdown格式）。⚠️严格要求：必须包含六个完整章节（一至六），每章都要有实质性内容，不能省略或跳过任何章节。将原有内容与本次新增洞察融合后输出完整版，可直接替换整个文档。禁止使用"新增内容："等增量标记，直接写正文。如果某章本次没有新内容，保留原有内容即可。",
  "sections_updated": ["本次更新了哪些章节，如：第四章、第六章"],
  "has_product_idea": true或false,
  "product_idea": {
    "title": "产品名称或方向",
    "user_pain": "用户痛点描述（具体）",
    "solution": "解决思路（核心价值主张）",
    "mvp_features": ["核心功能1", "核心功能2", "核心功能3"],
    "key_interactions": "主要用户流程和交互说明（类似原型图的文字描述）",
    "key_assumptions": ["最需要验证的假设1", "最需要验证的假设2"],
    "reference_products": ["参考产品1", "参考产品2"],
    "full_content": "完整的产品创意文档（Markdown格式，包含以上所有内容的详细版本）"
  },
  "summary": "一句话总结本次工作内容"
}"""


def _get_recent_ideas() -> list:
    """
    从 status.json 读取所有历史产品创意标题，用于创意去重。
    数据来自 ideas_history 列表（永久保存，不被50条日志限制截断）。
    """
    history = get_ideas_history()
    return [item.get("title", "") for item in history if item.get("title")]


def run(feishu_client: FeishuClient = None, llm_client: LLMClient = None,
        config: dict = None, trend_summary: str = "", trend_content: str = "") -> dict:
    """
    运行产品经理Agent

    参数：
    - feishu_client: 飞书客户端
    - llm_client: LLM客户端
    - config: 配置
    - trend_summary: 本次动态追踪的摘要（来自Agent 1）
    - trend_content: 本次动态追踪的详细内容（来自Agent 1）

    返回：运行结果，包含是否有产品创意
    """
    print("\n" + "="*50)
    print("💡 产品经理 开始工作...")
    print("="*50)

    if feishu_client is None:
        feishu_client = FeishuClient()
    if llm_client is None:
        llm_client = LLMClient()
    if config is None:
        config = _load_config()

    update_agent_status("product_manager", "running", "正在研究AI社交方向，更新认知沉淀...")
    log_activity("product_manager", "开始研究AI社交方向，更新认知沉淀")

    try:
        # 读取当前的认知沉淀文档
        knowledge_doc_id = config.get("feishu", {}).get("documents", {}).get("knowledge_doc_id", "")
        current_knowledge = ""
        if knowledge_doc_id:
            print("\n📚 读取现有认知沉淀文档...")
            current_knowledge = feishu_client.get_document_content(knowledge_doc_id)
            if current_knowledge:
                print(f"   读取成功，文档长度：{len(current_knowledge)}字")
            else:
                print("   文档为空或读取失败，将从头开始建立认知")

        # 预先读取所有信息源（不消耗LLM工具调用次数）
        now = datetime.now()

        print("\n📡 读取产品策略RSS信息源...")
        rss_content = format_rss_sources(CURATED_RSS_SOURCES, max_items_per_source=3)

        print("📡 读取 Hacker News Ask/Show HN...")
        hn_content = "\n".join([fetch_hn_posts(cat, max_items=8) for cat in HN_CATEGORIES_PM])

        print("   信息源读取完成")

        # 读取历史产品创意列表，用于去重（从永久保存的 ideas_history 读取）
        recent_ideas = _get_recent_ideas()
        recent_ideas_text = "\n".join(f"- {idea}" for idea in recent_ideas) if recent_ideas else "（暂无历史创意）"

        # 构建给Agent的提示
        user_prompt = f"""
当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}

==============================
【来自动态追踪员的最新动态】
==============================
{trend_content if trend_content else "（本次无新的动态追踪内容）"}

==============================
【来自优质信息源的最新内容】
（Newsletter + 研究员博客 + 投资人思考 + 产品播客）
==============================
{rss_content}

==============================
【Hacker News 技术社区真实声音】
（Ask HN用户提问 + Show HN新产品展示）
==============================
{hn_content}

==============================
【你当前的认知沉淀文档（最新8000字）】
==============================
{current_knowledge[-8000:] if current_knowledge else "（文档为空，需要从头建立）"}

==============================
【近期已生成的产品创意列表（去重必看！）】
==============================
{recent_ideas_text}

⚠️ 重要提示：如果你想生成的新创意与上面列表中的方向高度重叠（如同样是"低延迟语音AI陪伴"一类），
请放弃，输出 has_product_idea: false。必须探索真正不同的产品方向。

---

请按以下步骤工作：

**第一步：消化信息**
综合分析上面的全部内容，找出与AI社交方向最相关的洞察。
重点关注：HN Ask里用户在问什么需求？HN Show里有什么新AI社交产品？研究员/投资人在关注什么趋势？

**第二步：主动深入研究**
对感兴趣的话题，用 web_search 和 web_fetch 工具深入研究：
- 播客/博客标题看起来有价值？用web_fetch读原文
- 某个AI社交产品有新进展？搜用户真实评价
- HN或Newsletter里提到某个趋势？搜更多佐证材料

**第三步：整合重写认知框架（严格执行！）**
基于新信息，对认知沉淀文档进行整合重写：
- 输出必须包含**全部六个章节**（一、二、三、四、五、六），每章都要有实质性文字
- 将新洞察融入已有内容的对应章节，无新内容的章节直接保留原文
- 禁止使用"新增内容："、"新增："等前缀标记，直接写正文内容
- 消除重复描述，保持语句流畅
- 最终输出是完整的可替换整个文档的内容，不是只写变化的部分

**第四步：判断产品机会（严格执行5条门槛）**
评估标准：痛点有用户证据 + 竞品具体差在哪 + 技术当下可行 + 时机有优势 + 方向与历史创意不重叠
只有5条全满足才输出创意，否则 has_product_idea: false。

按JSON格式输出结果。
"""

        print("\n🧠 产品经理正在思考和研究...")
        response = llm_client.run_agent(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            use_tools=True,
            max_iterations=25  # 产品经理需要大量研究
        )

        # 解析结果
        result = _parse_agent_response(response)

        # 更新认知沉淀文档（整合重写，替换全文而非追加）
        knowledge_update = result.get("knowledge_update", "")
        if knowledge_update and knowledge_doc_id:
            print("\n📝 更新认知沉淀文档（整合重写）...")
            feishu_client.replace_document_content(knowledge_doc_id, knowledge_update)
            # 优先从config读取文档URL（含正确域名），若没有则自动构建
            doc_url = config.get("feishu", {}).get("documents", {}).get("knowledge_doc_url", "")
            if not doc_url:
                doc_url = f"https://docs.feishu.cn/docx/{knowledge_doc_id}"
            update_feishu_links(knowledge_doc=doc_url)
        elif knowledge_update:
            print("\n📋 认知沉淀文档ID未配置，更新内容：")
            print(knowledge_update[:500])

        # 处理产品创意
        has_idea = result.get("has_product_idea", False)
        product_idea = result.get("product_idea", {})
        idea_doc_url = ""

        if has_idea and product_idea:
            print(f"\n🎯 发现产品机会：{product_idea.get('title', '未命名')}")

            # 创建产品创意飞书文档
            ideas_folder = config.get("feishu", {}).get("documents", {}).get("ideas_folder_token", "")
            idea_title = f"【产品创意】{product_idea.get('title', now.strftime('%Y%m%d'))}"

            idea_content = product_idea.get("full_content", _format_idea(product_idea))

            idea_doc = feishu_client.create_document(idea_title, folder_token=ideas_folder)
            if idea_doc:
                idea_doc_id = idea_doc.get("document_id", "")
                feishu_client.append_to_document(idea_doc_id, idea_content)
                idea_doc_url = idea_doc.get("url", "")
                print(f"   产品创意文档已创建：{idea_doc_url}")

            increment_stat("total_ideas_generated")
            update_agent_status("product_manager", "idle",
                                f"发现产品机会：{product_idea.get('title')}",
                                extra={"pending_ideas": 1, "latest_idea_title": product_idea.get("title")})
        else:
            print("\nℹ️  本次未发现值得深入的产品机会")
            update_agent_status("product_manager", "idle", result.get("summary", "完成认知沉淀更新"))

        summary = result.get("summary", "完成认知更新")
        log_activity("product_manager", summary)

        print(f"\n✅ 产品经理工作完成：{summary}")

        return {
            "success": True,
            "summary": summary,
            "has_product_idea": has_idea,
            "product_idea": product_idea,
            "idea_doc_url": idea_doc_url
        }

    except Exception as e:
        error_msg = f"产品经理出错：{str(e)}"
        print(f"\n❌ {error_msg}")
        update_agent_status("product_manager", "error", error_msg)
        log_activity("product_manager", f"运行出错：{str(e)[:100]}")
        return {"success": False, "summary": error_msg, "has_product_idea": False}


def _format_idea(product_idea: dict) -> str:
    """把产品创意字典格式化成Markdown文档"""
    now = datetime.now()
    title = product_idea.get("title", "未命名产品创意")

    sections = [
        f"# {title}\n",
        f"> 生成时间：{now.strftime('%Y年%m月%d日 %H:%M')}\n",
        "---\n",
        "## 用户痛点\n",
        product_idea.get("user_pain", ""),
        "\n## 解决思路\n",
        product_idea.get("solution", ""),
        "\n## MVP核心功能\n",
    ]

    for feat in product_idea.get("mvp_features", []):
        sections.append(f"- {feat}")

    sections.extend([
        "\n## 核心交互流程\n",
        product_idea.get("key_interactions", ""),
        "\n## 关键假设（需要验证）\n",
    ])

    for assumption in product_idea.get("key_assumptions", []):
        sections.append(f"- {assumption}")

    ref_products = product_idea.get("reference_products", [])
    if ref_products:
        sections.extend(["\n## 参考产品\n"])
        for p in ref_products:
            sections.append(f"- {p}")

    sections.extend([
        "\n---\n",
        "## 评审状态\n",
        "- [ ] 待评审\n",
        "- [ ] 用户批准\n",
        "- [ ] Demo开发中\n",
        "- [ ] Demo完成\n",
    ])

    return "\n".join(sections)


def _parse_agent_response(response: str) -> dict:
    """解析Agent的JSON回应"""
    if not response:
        return {"has_product_idea": False, "knowledge_update": "", "summary": "无响应"}

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass

    start = response.find('{')
    end = response.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(response[start:end+1])
        except:
            pass

    return {
        "has_product_idea": False,
        "knowledge_update": f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} 更新\n\n{response[:1000]}",
        "summary": "完成认知更新（格式解析异常）"
    }


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


if __name__ == "__main__":
    print("单独测试：产品经理Agent")
    result = run()
    print(f"\n运行结果：{result.get('summary')}")
    if result.get("has_product_idea"):
        print(f"产品创意：{result.get('product_idea', {}).get('title', '未命名')}")
