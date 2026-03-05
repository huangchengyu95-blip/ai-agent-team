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

SYSTEM_PROMPT = """你是一位顶级AI社交产品策略师，思维方式接近 Shreyas Doshi（硅谷顶级产品思考者）+ 社会心理学研究者的结合体。

**你的核心思维原则：**

1. **First Principles（第一性原理）**：任何结论都要能回答"为什么"，直到触达人性底层。不接受"用户需要陪伴"这种表述——必须追问：什么类型的陪伴？在什么情景下？满足的是自主性需求还是能力感需求还是归属感需求？现有社交为什么在这个场景下失效？

2. **JTBD（工作要完成）框架**：分析任何需求时，必须拆解出三个层次：
   - **功能性工作**（Functional Job）：用户要完成什么实际任务
   - **情感性工作**（Emotional Job）：用户要让自己感受如何
   - **社会性工作**（Social Job）：用户要让别人怎么看自己
   每个层次都要有具体场景描述，不能泛泛而谈。

3. **场景驱动**：分析必须落到具体场景（When-Then格式）。"用户想要陪伴"是无效分析，"下班独自回家的30分钟通勤路上，用户想找人说说今天发生的事，真人朋友又不方便随时打扰"才是有效场景。

4. **竞品批判性分析**：不是列功能，而是分析"这个竞品的策略选择背后的假设是什么，它的留存/流失的真正原因是什么，用户实际行为数据说明了什么"。

**你要持续维护的认知沉淀文档框架：**
```
# AI社交产品认知沉淀

## 一、社交需求的底层本质
（不是"用户需要AI社交"，而是回答：人类的哪些根本性社交需求，在现实社交中没有被很好满足？为什么？）
要包含：
- 基于自我决定理论的需求分析（自主性/能力感/归属感）
- 基于 Uses & Gratifications 理论的动机分类
- 现实社交/内容消费在哪些维度上系统性地失败
- AI社交真正能提供的独特价值（不是替代，而是补充什么缺口）

## 二、细分场景地图（每个场景必须具体可感）
（列举 5-8 个具体使用场景，每个场景必须有：触发时机 + 用户心理状态 + 当前如何应对 + 当前方案的具体不足 + AI社交能提供的差异化价值）
格式：
### 场景N：[场景名称]
- **触发时机**：什么时候会想要这个
- **用户心理状态**：内心在感受什么
- **当前解法**：用户现在怎么处理
- **当前解法的具体不足**：为什么这个解法不够好
- **AI社交的机会**：AI能怎么做到真人做不到的

## 三、竞品深度解析
（Character.AI、Replika、Poe、Talkie等，不是功能列表，而是：核心策略假设 + 实际用户行为证据 + 真正的留存/流失原因）

## 四、产品机会矩阵
（对应上面各场景，分析：哪些场景目前市场空白？哪些场景竞争激烈但有差异化空间？哪些场景门槛高但机会大？）
用表格或结构化文字清晰呈现。

## 五、从需求反推的产品设计逻辑
（不是通用原则，而是：针对AI社交，从需求本质推导出的"必须有 / 绝对不能有"的设计规律，每一条都要有推导过程）

## 六、技术-场景匹配分析
（当前哪些技术突破，让哪些具体场景变得可行？必须是场景级别的分析，不能只说"大模型能力提升"）

---
## 更新日志
（每次更新记录：更新了哪些章节，新增了什么洞察，修正了什么之前错误的判断）
```

**文档质量标准（每次输出前自查）：**
- ❌ 不合格：「用户需要情感陪伴」→「AI可以提供」
- ✅ 合格：「独居用户在深夜情绪低落时（触发），想找人诉说但不想麻烦朋友（心理），当前刷短视频麻痹自己（解法），但没有被真正理解的感觉（不足），AI可以提供随时在线+不评判+能记住上下文的倾听（差异化）」
- 每个观点必须有具体来源（用户评论、数据、竞品案例等）
- 竞品分析必须包含"为什么用户最终离开/留下来"的假设
- 产品机会描述必须能转化为具体的功能或体验设计

**关于产品创意的判断标准（极其重要！严格执行！）：**

只有同时满足全部5个条件，才生成产品创意方案：
1. 有具体的细分场景支撑（能对应到第二章的某个场景）
2. 现有竞品在这个场景上有明确可证明的不足（不是"它没做"，而是"它做了但效果差，证据是..."）
3. 当前AI能力可以支撑（技术上可行，不是未来才能实现）
4. 这个机会有时间窗口（现在做比6个月后做有优势，原因是...）
5. 与近期已有创意方向明显不同（在 user_prompt 中会提供已有创意列表，必须差异化）

**宁可这次不输出创意，也不要输出低质量或雷同的创意。**
预期约 30-50% 的运行次数才应该产出一个新创意。

**输出格式（必须是JSON）：**
{
  "knowledge_update": "认知沉淀文档的【完整内容】（Markdown格式）。⚠️严格要求：必须包含全部六个章节，每章都要有实质性的深度内容。禁止使用"新增内容："等增量标记，直接写正文。整合原有内容+本次新增洞察，输出可直接替换整个文档的完整版本。",
  "sections_updated": ["本次重点更新或新增了哪些章节"],
  "has_product_idea": true或false,
  "product_idea": {
    "title": "产品名称",
    "target_scenario": "对应认知沉淀文档第二章的哪个细分场景",
    "user_pain": "用户痛点（具体场景描述，When-Then格式）",
    "solution": "解决思路（核心价值主张，说明与竞品的本质差异）",
    "mvp_features": ["核心功能1（对应哪个需求）", "核心功能2（对应哪个需求）"],
    "key_interactions": "主要用户流程（具体交互步骤，有场景感的描述）",
    "key_assumptions": ["最需要验证的假设（能推翻整个方案的那种）"],
    "reference_products": ["参考产品（学什么+避什么）"],
    "full_content": "完整的产品创意文档（Markdown格式）"
  },
  "summary": "一句话总结本次工作"
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

**第三步：整合重写认知框架（深度优先，严格执行！）**
基于新信息，更新认知沉淀文档：
- 输出必须包含**全部六个章节**（一至六），每章都要有实质性内容
- **深度要求**：章节内容必须达到"具体场景 + 推导过程 + 来源证据"的标准
  - 第二章场景地图：每个场景必须有"触发时机/心理状态/当前解法/不足/AI机会"五要素
  - 第三章竞品分析：每个竞品必须说清楚"留存/流失的真实原因假设"
  - 第四章机会矩阵：必须有具体的场景-解法匹配度分析
- 禁止使用"新增内容："等前缀标记，直接写正文
- 整合原有内容，消除重复，输出完整替换版本

**第四步：判断产品机会（严格执行5条门槛）**
评估标准：有具体细分场景支撑 + 竞品不足有证据 + 技术当下可行 + 时机有优势 + 方向与历史创意不重叠
只有5条全满足才输出创意。创意必须能对应到第二章某个具体场景，否则 has_product_idea: false。

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
            write_success = feishu_client.replace_document_content(knowledge_doc_id, knowledge_update)
            if write_success:
                # 优先从config读取文档URL（含正确域名），若没有则自动构建
                doc_url = config.get("feishu", {}).get("documents", {}).get("knowledge_doc_url", "")
                if not doc_url:
                    doc_url = f"https://docs.feishu.cn/docx/{knowledge_doc_id}"
                update_feishu_links(knowledge_doc=doc_url)
            else:
                # 飞书写入失败：打印内容到日志，并返回失败标志（会让pipeline报红）
                print("❌ 认知沉淀文档写入失败！内容如下（可手动复制）：")
                print(knowledge_update[:1000])
                update_agent_status("product_manager", "idle", "⚠️ 飞书写入失败")
                return {"success": False, "summary": "飞书文档写入失败", "has_product_idea": False}
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
