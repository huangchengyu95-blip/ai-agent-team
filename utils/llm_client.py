"""
LLM客户端（支持 OpenRouter 和 火山引擎）
- 优先使用 OpenRouter（设置 OPENROUTER_API_KEY 即可启用）
- 备用：火山引擎豆包模型（VOLCENGINE_API_KEY）
- 两者都是 OpenAI 兼容格式，工具调用方式相同

环境变量配置（GitHub Secrets）：
  OpenRouter（推荐）：
    OPENROUTER_API_KEY  = sk-or-v1-...
    OPENROUTER_MODEL_ID = anthropic/claude-sonnet-4-5（或其他模型）
  火山引擎（备用）：
    VOLCENGINE_API_KEY  = ...
    VOLCENGINE_MODEL_ID = doubao-pro-32k-240828
"""

import os
import json

# 尝试导入openai库
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("警告：openai库未安装，LLM功能不可用（pip install openai）")


# 工具定义：告诉模型可以用哪些工具
AVAILABLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "在网上搜索最新信息。当你需要了解最新动态、新闻、产品信息时使用这个工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，尽量具体，可以包含时间限定词如'2024 2025 latest'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "获取指定网页的内容。当搜索结果中有某个值得深入阅读的链接时，用这个工具获取全文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要获取内容的网页URL"
                    }
                },
                "required": ["url"]
            }
        }
    }
]


class LLMClient:
    """LLM客户端（OpenRouter 优先，火山引擎备用）"""

    def __init__(self):
        # 优先检测 OpenRouter
        openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
        volcengine_key = os.environ.get("VOLCENGINE_API_KEY", "")

        if openrouter_key:
            self.provider = "openrouter"
            self.api_key = openrouter_key
            self.model_id = os.environ.get(
                "OPENROUTER_MODEL_ID",
                "anthropic/claude-sonnet-4-5"  # 默认模型，可在 GitHub Secrets 里覆盖
            )
            self.base_url = "https://openrouter.ai/api/v1"
            self.extra_headers = {
                "X-Title": "AI Agent Team"  # OpenRouter 推荐带上来源说明
            }
            print(f"✅ LLM：使用 OpenRouter（模型：{self.model_id}）")
        elif volcengine_key:
            self.provider = "volcengine"
            self.api_key = volcengine_key
            self.model_id = os.environ.get("VOLCENGINE_MODEL_ID", "doubao-pro-32k-240828")
            self.base_url = "https://ark.cn-beijing.volces.com/api/v3"
            self.extra_headers = {}
            print(f"✅ LLM：使用 火山引擎（模型：{self.model_id}）")
        else:
            self.provider = "none"
            self.api_key = ""
            self.model_id = ""
            self.base_url = ""
            self.extra_headers = {}
            print("⚠️  警告：未找到 LLM API Key")
            print("     请在 GitHub Secrets 中配置 OPENROUTER_API_KEY 或 VOLCENGINE_API_KEY")

        self._client = None
        if self.api_key:
            self._init_client()

    def is_configured(self) -> bool:
        """检查LLM是否已配置"""
        return bool(self.api_key and OPENAI_AVAILABLE)

    def _init_client(self):
        """初始化OpenAI兼容客户端"""
        if not OPENAI_AVAILABLE:
            return
        try:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self.extra_headers
            )
        except Exception as e:
            print(f"❌ LLM客户端初始化失败：{e}")

    def run_agent(self, system_prompt: str, user_prompt: str,
                  use_tools: bool = True, max_iterations: int = 15) -> str:
        """
        运行一个AI Agent，支持工具调用循环

        工作原理：
        1. 把任务发给大模型
        2. 如果模型要使用工具（搜索/抓取），执行工具并把结果返回给模型
        3. 重复步骤2，直到模型给出最终答案

        参数：
        - system_prompt: 系统提示词（Agent的角色和任务说明）
        - user_prompt: 用户输入（本次任务的具体要求）
        - use_tools: 是否启用网络搜索等工具
        - max_iterations: 最多执行多少轮（防止无限循环）

        返回：Agent的最终回答
        """
        if not self.is_configured():
            return self._mock_response(system_prompt, user_prompt)

        # 构建对话历史
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # 决定是否提供工具
        tools = AVAILABLE_TOOLS if use_tools else None

        print(f"\n🤖 开始运行Agent（最多{max_iterations}轮工具调用）...")

        for iteration in range(max_iterations):
            try:
                # 调用LLM
                kwargs = {
                    "model": self.model_id,
                    "messages": messages,
                    "max_tokens": 4096,
                    "temperature": 0.7,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                response = self._client.chat.completions.create(**kwargs)
                message = response.choices[0].message

                # 检查是否有工具调用
                if message.tool_calls:
                    print(f"   第{iteration + 1}轮：模型调用了{len(message.tool_calls)}个工具")

                    # 把模型的回应加入对话历史
                    messages.append(message)

                    # 执行每个工具调用
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)

                        print(f"   执行工具 [{tool_name}]: {list(tool_args.values())[0][:60]}...")
                        tool_result = _execute_tool(tool_name, tool_args)

                        # 把工具结果加入对话历史
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        })

                else:
                    # 没有工具调用，说明模型已经有了最终答案
                    final_answer = message.content or ""
                    print(f"✅ Agent完成（共{iteration + 1}轮）")
                    return final_answer

            except Exception as e:
                print(f"❌ LLM调用出错（第{iteration + 1}轮）：{e}")
                return f"运行出错：{str(e)}"

        print(f"⚠️  达到最大轮数（{max_iterations}），返回最后的回答")
        # 返回最后一条非工具消息
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                return msg.get("content", "")
            elif hasattr(msg, "content") and msg.content:
                return msg.content
        return "Agent未能完成任务"

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        当LLM未配置时，返回模拟回应
        用于测试系统的其他部分（飞书、状态追踪等）是否正常工作
        """
        # 根据system_prompt判断是哪个Agent
        if "动态追踪" in system_prompt or "trend" in system_prompt.lower():
            return json.dumps({
                "has_updates": True,
                "content": f"## {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n**[测试模式]** LLM暂未配置，这是模拟的动态追踪结果\n\n- [OpenAI] 测试：发现AI社交产品新趋势\n- [Product Hunt] 测试：新AI伴侣应用上线\n- [Reddit] 测试：用户讨论AI社交产品体验\n",
                "summary": "[测试模式] 模拟发现3条AI社交新动态"
            }, ensure_ascii=False)

        elif "产品经理" in system_prompt or "product manager" in system_prompt.lower():
            return json.dumps({
                "knowledge_update": "## 新洞察（测试模式）\n\n这是LLM未配置时的模拟认知更新内容\n",
                "has_product_idea": False,
                "summary": "[测试模式] 模拟完成认知沉淀更新，暂无产品创意"
            }, ensure_ascii=False)

        else:
            return json.dumps({
                "status": "test_mode",
                "message": "LLM未配置，这是测试模式的模拟输出",
                "summary": "[测试模式] 模拟完成任务"
            }, ensure_ascii=False)


def _execute_tool(tool_name: str, tool_args: dict) -> str:
    """
    执行工具调用

    参数：
    - tool_name: 工具名称（"web_search" 或 "web_fetch"）
    - tool_args: 工具参数

    返回：工具执行结果的字符串
    """
    try:
        if tool_name == "web_search":
            from utils.web_tools import web_search
            return web_search(tool_args.get("query", ""))

        elif tool_name == "web_fetch":
            from utils.web_tools import web_fetch
            return web_fetch(tool_args.get("url", ""))

        else:
            return f"未知工具：{tool_name}"

    except Exception as e:
        return f"工具执行出错（{tool_name}）：{str(e)}"
