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

        # 构建搜索提示（告诉Agent要搜索什么）
        now = datetime.now()
        user_prompt = f"""
当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}

请搜索过去4-8小时内AI社交方向的最新动态。

搜索策略（按优先级）：
1. 搜索 "AI companion app 2025 latest" 、"AI social product news" 等英文关键词
2. 搜索 "Character AI Replika 2025 update user feedback"
3. 搜索 "AI chat application reddit discussion" 了解用户真实反馈
4. 搜索 "Product Hunt AI social" 发现新产品
5. 搜索 "OpenAI ChatGPT social feature" 、"AI relationship app" 等

对每条找到的信息：
- 判断它是否与AI社交产品方向相关
- 判断它是否有产品决策价值
- 只保留重要的信息

最后按要求的JSON格式输出结果。
如果某个搜索结果值得深入阅读，可以用web_fetch工具获取全文。
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
            success = feishu_client.append_to_document(trend_doc_id, content_to_write)
            if success:
                doc_url = f"https://docs.feishu.cn/docx/{trend_doc_id}"
                update_feishu_links(trend_doc=doc_url)
                print(f"✅ 成功追加到飞书文档")
            else:
                print("⚠️  飞书写入失败，内容已打印到控制台")
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
