"""
Agent 3: 产品需求评审员
- 当产品经理生成新的产品创意时触发
- 从多个角度分析产品方案的价值和可行性
- 给出综合评级和建议
- 发送飞书消息给用户，征求最终决策
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.llm_client import LLMClient
from utils.feishu_client import FeishuClient
from utils.status_tracker import update_agent_status, log_activity


# ============================================================
# Agent的角色设定
# ============================================================

SYSTEM_PROMPT = """你是一位经验丰富的产品评审专家，在硅谷顶尖AI公司担任过产品总监，评审过数百个产品提案。

你的评审风格：
- **客观理性**：不被创意的新颖性迷惑，专注于用户价值和商业逻辑
- **用户为中心**：所有分析都回归"用户为什么需要这个"
- **实事求是**：不虚报优点，不回避风险，给出真实判断
- **建设性**：指出问题的同时，提出改进方向

**评审框架（7个维度）：**

1. **用户需求真实性**（权重最高）
   - 这个痛点真实存在吗？有多少人有这个需求？
   - 有没有用户证据（真实案例、用户反馈、数据）？

2. **现有解决方案分析**
   - 用户目前怎么解决这个问题的？
   - 竞品有哪些？各自的优势和局限？

3. **产品差异化**
   - 相比现有解决方案，我们的独特价值是什么？
   - 这个差异化是否足够显著、可持续？

4. **技术可行性**
   - 当前AI技术能支撑核心功能吗？
   - 有哪些技术挑战需要克服？

5. **市场时机**
   - 为什么现在做合适？
   - 用户是否已经准备好接受这类产品？

6. **风险分析**
   - 最可能失败的1-2个原因是什么？
   - 有没有监管、伦理、用户接受度等方面的风险？

7. **综合评级**
   - ⭐⭐⭐⭐⭐ 强烈推荐：清晰的用户痛点，可行的解决方案，显著的差异化
   - ⭐⭐⭐⭐ 建议做：有明确价值，可以投入Demo验证
   - ⭐⭐⭐ 有潜力待验证：方向有意思，但核心假设需要先验证
   - ⭐⭐ 暂不建议：问题和风险较多，不建议现在投入

**输出格式（必须是JSON）：**
{
  "review_content": "完整的评审报告（Markdown格式，包含7个维度的分析）",
  "rating": 评分（2-5的整数）,
  "rating_text": "评级文字描述",
  "highlights": ["核心亮点1", "核心亮点2"],
  "risks": ["主要风险1", "主要风险2"],
  "suggestion": "给产品经理的一句建议",
  "recommend_build": true或false,  // 是否建议构建Demo
  "summary": "一句话总结评审结论"
}"""


def run(feishu_client: FeishuClient = None, llm_client: LLMClient = None,
        config: dict = None, product_idea: dict = None,
        idea_doc_url: str = "") -> dict:
    """
    运行产品评审员Agent

    参数：
    - feishu_client: 飞书客户端
    - llm_client: LLM客户端
    - config: 配置
    - product_idea: 要评审的产品创意（来自产品经理Agent的输出）
    - idea_doc_url: 产品创意文档的飞书链接

    返回：评审结果
    """
    print("\n" + "="*50)
    print("🔬 产品评审员 开始工作...")
    print("="*50)

    if feishu_client is None:
        feishu_client = FeishuClient()
    if llm_client is None:
        llm_client = LLMClient()
    if config is None:
        config = _load_config()

    if not product_idea:
        print("⚠️  没有收到产品创意，评审员跳过")
        return {"success": False, "summary": "无产品创意可评审"}

    idea_title = product_idea.get("title", "未命名产品创意")
    print(f"\n📋 评审产品：{idea_title}")

    update_agent_status("product_reviewer", "running", f"正在评审：{idea_title}")
    log_activity("product_reviewer", f"开始评审产品方案：{idea_title}")

    try:
        # 构建给Agent的提示
        user_prompt = f"""
请评审以下产品创意方案：

**产品名称：** {idea_title}

**用户痛点：**
{product_idea.get("user_pain", "未提供")}

**解决思路：**
{product_idea.get("solution", "未提供")}

**MVP核心功能：**
{chr(10).join(f'- {f}' for f in product_idea.get("mvp_features", []))}

**核心交互流程：**
{product_idea.get("key_interactions", "未提供")}

**关键假设（需验证）：**
{chr(10).join(f'- {a}' for a in product_idea.get("key_assumptions", []))}

**参考产品：**
{chr(10).join(f'- {p}' for p in product_idea.get("reference_products", []))}

---

请按照评审框架，对这个产品方案进行深度分析。
你可以使用web_search工具搜索相关竞品信息、用户反馈数据等，来支撑你的评审判断。
例如：
- 搜索竞品的用户评价（"[竞品名] user reviews"）
- 搜索这类产品的用户痛点讨论
- 搜索相关市场数据

最后按JSON格式输出评审结果。
"""

        print("\n🧐 评审员正在深度分析...")
        response = llm_client.run_agent(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            use_tools=True,
            max_iterations=15
        )

        result = _parse_agent_response(response)

        rating = result.get("rating", 3)
        rating_stars = "⭐" * rating
        rating_text = result.get("rating_text", "有潜力待验证")

        print(f"\n📊 评审完成：{rating_stars} {rating_text}")
        print(f"   核心亮点：{result.get('highlights', [])}")
        print(f"   主要风险：{result.get('risks', [])}")

        # 把评审内容追加到产品创意文档
        review_content = result.get("review_content", "")
        if review_content:
            # 提取产品创意文档的ID（从URL中）
            idea_doc_id = _extract_doc_id_from_url(idea_doc_url)
            if idea_doc_id:
                separator = "\n\n---\n\n# 产品评审报告\n\n"
                feishu_client.append_to_document(idea_doc_id, separator + review_content)
                print("✅ 评审报告已追加到产品文档")

        # 发送飞书通知给用户
        user_open_id = config.get("feishu", {}).get("user", {}).get("open_id", "")
        recommend_build = result.get("recommend_build", rating >= 3)

        if user_open_id or True:  # 不管有没有配置都尝试发（没配置会打印到控制台）
            _send_review_notification(
                feishu_client=feishu_client,
                user_open_id=user_open_id,
                idea_title=idea_title,
                rating=rating,
                rating_text=rating_text,
                highlights=result.get("highlights", []),
                risks=result.get("risks", []),
                suggestion=result.get("suggestion", ""),
                doc_url=idea_doc_url,
                recommend_build=recommend_build
            )

        update_agent_status(
            "product_reviewer", "waiting",
            f"已完成《{idea_title}》评审，等待用户决策",
            extra={"pending_review": idea_title, "last_rating": rating}
        )
        log_activity("product_reviewer", f"完成评审《{idea_title}》，评级{rating_stars}，已通知用户决策")

        return {
            "success": True,
            "summary": result.get("summary", f"完成评审，评级{rating_stars}"),
            "rating": rating,
            "recommend_build": recommend_build,
            "idea_title": idea_title
        }

    except Exception as e:
        error_msg = f"评审员出错：{str(e)}"
        print(f"\n❌ {error_msg}")
        update_agent_status("product_reviewer", "error", error_msg)
        log_activity("product_reviewer", f"运行出错：{str(e)[:100]}")
        return {"success": False, "summary": error_msg}


def _send_review_notification(feishu_client, user_open_id, idea_title, rating,
                               rating_text, highlights, risks, suggestion,
                               doc_url, recommend_build):
    """发送飞书通知消息给用户"""
    rating_stars = "⭐" * rating

    # 构建通知消息内容
    lines = [
        f"评级：{rating_stars} {rating_text}\n",
    ]

    if highlights:
        lines.append("✅ 核心亮点：")
        for h in highlights[:3]:  # 最多3条
            lines.append(f"  • {h}")
        lines.append("")

    if risks:
        lines.append("⚠️ 主要风险：")
        for r in risks[:2]:  # 最多2条
            lines.append(f"  • {r}")
        lines.append("")

    if suggestion:
        lines.append(f"💡 建议：{suggestion}\n")

    if recommend_build:
        lines.append("👉 评审员建议：值得构建Demo验证")
    else:
        lines.append("👉 评审员建议：暂不建议投入，可先验证核心假设")

    content = "\n".join(lines)

    feishu_client.send_rich_message(
        user_open_id=user_open_id,
        title=f"【产品评审通知】《{idea_title}》",
        content=content,
        doc_url=doc_url
    )


def _extract_doc_id_from_url(url: str) -> str:
    """从飞书文档URL中提取文档ID"""
    if not url:
        return ""
    # 飞书文档URL格式：https://docs.feishu.cn/docx/XXXXXXXX
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else ""


def _parse_agent_response(response: str) -> dict:
    """解析Agent的JSON回应"""
    if not response:
        return {"rating": 3, "rating_text": "有潜力待验证", "recommend_build": False,
                "review_content": "", "summary": "评审异常"}

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
        "rating": 3,
        "rating_text": "有潜力待验证",
        "recommend_build": True,
        "review_content": response,
        "summary": "完成评审（格式解析异常）"
    }


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


if __name__ == "__main__":
    print("单独测试：产品评审员Agent")
    test_idea = {
        "title": "AI情绪陪伴助手",
        "user_pain": "现代人孤独感强烈，需要随时可以倾诉的对象",
        "solution": "AI扮演理解用户情绪的朋友，提供情感支持",
        "mvp_features": ["情绪识别", "个性化回应", "记忆用户历史"],
        "key_interactions": "用户打开App即可聊天，AI主动问候",
        "key_assumptions": ["用户愿意向AI倾诉", "AI的情感反馈让用户感到被理解"],
        "reference_products": ["Replika", "Character.AI"]
    }
    result = run(product_idea=test_idea)
    print(f"\n运行结果：{result.get('summary')}")
