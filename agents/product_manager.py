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
from utils.status_tracker import update_agent_status, log_activity, increment_stat, update_feishu_links


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

**关于产品创意的判断标准（重要！）：**
只有同时满足以下条件，才生成产品创意方案：
- 用户痛点明确且真实存在（有用户证据）
- 现有解决方案不够好（有明显的改进空间）
- 当前AI能力可以支撑（技术上可行）
- 这个机会有一定的时间窗口（现在是好时机）

不要为了生成创意而生成创意。质量比数量重要。

**输出格式（必须是JSON）：**
{
  "knowledge_update": "要追加到认知沉淀文档的新内容（Markdown格式）",
  "sections_updated": ["更新了哪些章节，如：第四章、第六章"],
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

        # 构建给Agent的提示
        now = datetime.now()
        user_prompt = f"""
当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}

**最新AI动态追踪信息（来自动态追踪员）：**
{trend_content if trend_content else "（本次无新的动态追踪内容，请主动搜索）"}

**你当前的认知沉淀文档：**
{current_knowledge[:3000] if current_knowledge else "（文档为空，需要从头建立）"}

---

请按以下步骤工作：

**第一步：消化新动态**
分析上面的动态追踪内容，思考哪些信息对你的认知有更新。

**第二步：主动深入研究**
根据你的判断，对最感兴趣的1-2个话题进行深入搜索研究。
例如：
- 如果看到某个AI社交产品有新进展，搜索它的用户评价和数据
- 如果发现某个用户需求被多次提及，搜索相关研究和案例
- 如果有你一直想了解的话题，主动去搜

**第三步：更新认知框架**
基于新信息和你的思考，决定：
- 认知沉淀文档的哪些部分需要补充或修正？
- 有没有新的维度需要加入框架？
- 写出要追加的新内容（Markdown格式）

**第四步：判断产品机会**
思考：基于最新的信息和你对行业的理解，有没有发现值得深入探索的产品机会？
评估标准：用户痛点真实 + 现有解决不好 + 技术可行 + 时机合适

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

        # 更新认知沉淀文档
        knowledge_update = result.get("knowledge_update", "")
        if knowledge_update and knowledge_doc_id:
            print("\n📝 更新认知沉淀文档...")
            feishu_client.append_to_document(knowledge_doc_id, knowledge_update)
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
