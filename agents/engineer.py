"""
Agent 4: 工程师
- 用户批准产品方案后手动触发
- 读取飞书产品方案文档
- 用HTML/CSS/JavaScript构建可交互的Demo原型
- 保存到demos/目录，发飞书通知

使用方式：
  python agents/engineer.py --doc-id <飞书文档ID>
  或在GitHub Actions中通过 build_demo.yml 触发
"""

import json
import os
import sys
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.llm_client import LLMClient
from utils.feishu_client import FeishuClient
from utils.status_tracker import update_agent_status, log_activity, increment_stat


# ============================================================
# Agent的角色设定
# ============================================================

SYSTEM_PROMPT = """你是一位全栈工程师，专注于构建AI产品的交互原型。你有深厚的前端技术功底和出色的产品感。

你的任务：
根据产品设计文档，用HTML/CSS/JavaScript构建一个高质量的可交互Demo原型。

**Demo构建要求（必须遵守）：**

1. **单文件原则**：所有代码放在一个 index.html 文件中（CSS用<style>标签，JS用<script>标签）
   这样用户直接双击文件就能在浏览器中打开，无需任何服务器

2. **移动端优先**：
   - 以375px宽度为基准设计（iPhone尺寸）
   - 使用flexible布局，支持不同屏幕尺寸
   - 触控友好的按钮和交互区域（最小44px）

3. **真实感数据**：
   - 用户头像、名字、聊天内容都要填充真实感强的假数据
   - 时间戳要看起来真实
   - 不要出现"示例内容"、"Lorem ipsum"等占位符

4. **核心流程可交互**：
   - 主要用户路径（Happy Path）要能完整演示
   - 按钮点击要有反馈（状态变化、页面跳转等）
   - AI回复可以用setTimeout模拟延迟，增加真实感

5. **视觉风格**：
   - 现代简洁（参考ChatGPT、Claude、Notion的设计风格）
   - 适当使用渐变、阴影、圆角等视觉效果
   - 配色和谐，避免刺眼的颜色搭配
   - 所有图标用emoji代替，不需要外部图标库

6. **技术约束**：
   - 不使用任何外部依赖（不引入CDN、不请求外部API）
   - 纯原生HTML/CSS/JS，确保离线可用
   - 代码要有中文注释，解释关键部分

**代码组织结构：**
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>[产品名]</title>
    <style>
        /* CSS样式 - 包含：基础重置、颜色变量、布局、组件、动画 */
    </style>
</head>
<body>
    <!-- HTML结构 - 包含所有页面/状态 -->
    <script>
        // JavaScript逻辑 - 包含：状态管理、交互处理、模拟数据
    </script>
</body>
</html>
```

**输出要求：**
直接输出完整的HTML代码，不需要任何解释文字，代码要完整可运行。"""


def run(feishu_client: FeishuClient = None, llm_client: LLMClient = None,
        config: dict = None, doc_id: str = "") -> dict:
    """
    运行工程师Agent构建Demo

    参数：
    - feishu_client: 飞书客户端
    - llm_client: LLM客户端
    - config: 配置
    - doc_id: 飞书产品方案文档ID

    返回：运行结果
    """
    print("\n" + "="*50)
    print("🔧 工程师 开始构建Demo...")
    print("="*50)

    if feishu_client is None:
        feishu_client = FeishuClient()
    if llm_client is None:
        llm_client = LLMClient()
    if config is None:
        config = _load_config()

    if not doc_id:
        print("❌ 错误：需要提供产品方案文档ID（--doc-id参数）")
        return {"success": False, "summary": "未提供文档ID"}

    update_agent_status("engineer", "running", "正在读取产品方案...")
    log_activity("engineer", f"开始构建Demo，读取文档：{doc_id}")

    try:
        # 读取产品方案文档
        print(f"\n📄 读取产品方案文档（ID：{doc_id}）...")
        doc_content = feishu_client.get_document_content(doc_id)

        if not doc_content:
            print("❌ 无法读取文档内容，请检查：")
            print("   1. 文档ID是否正确")
            print("   2. 飞书应用是否有读取权限")
            return {"success": False, "summary": "无法读取产品方案文档"}

        print(f"   文档长度：{len(doc_content)}字")

        # 提取产品名称（从文档第一行）
        product_name = _extract_product_name(doc_content)
        print(f"   产品名称：{product_name}")

        # 构建给Agent的提示
        user_prompt = f"""
请根据以下产品设计文档，构建一个完整的Demo原型：

---
{doc_content[:5000]}
---

产品名称：{product_name}

特别注意：
1. 重点实现文档中描述的"核心交互流程"部分
2. 确保Demo能完整展示产品的核心价值
3. 模拟数据要贴近真实场景
4. 代码注释用中文

直接输出完整的HTML代码。
"""

        print(f"\n💻 正在生成Demo代码（这可能需要2-3分钟）...")
        update_agent_status("engineer", "running", f"正在生成《{product_name}》Demo代码...")

        html_code = llm_client.run_agent(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            use_tools=False,  # 工程师不需要搜索工具，专注写代码
            max_iterations=3   # 通常一次就够
        )

        # 验证生成的HTML
        if not html_code or "<html" not in html_code.lower():
            print("⚠️  生成的代码格式异常，尝试提取HTML部分...")
            html_code = _extract_html(html_code)

        if not html_code:
            print("❌ 未能生成有效的HTML代码")
            return {"success": False, "summary": "未能生成有效Demo代码"}

        # 保存Demo文件
        demo_dir, demo_path = _save_demo(product_name, html_code)
        print(f"\n✅ Demo已保存：{demo_path}")

        # 发飞书通知
        user_open_id = config.get("feishu", {}).get("user", {}).get("open_id", "")
        _send_completion_notification(feishu_client, user_open_id, product_name, demo_path)

        increment_stat("total_demos_built")
        update_agent_status(
            "engineer", "waiting",
            f"完成《{product_name}》Demo构建",
            extra={"demos_built": _get_demos_count(), "last_demo": product_name}
        )
        log_activity("engineer", f"完成Demo构建：《{product_name}》，文件：{demo_path}")

        return {
            "success": True,
            "summary": f"Demo构建完成：{product_name}",
            "demo_path": demo_path,
            "product_name": product_name
        }

    except Exception as e:
        error_msg = f"工程师出错：{str(e)}"
        print(f"\n❌ {error_msg}")
        update_agent_status("engineer", "error", error_msg)
        log_activity("engineer", f"运行出错：{str(e)[:100]}")
        return {"success": False, "summary": error_msg}


def _extract_product_name(doc_content: str) -> str:
    """从文档内容中提取产品名称"""
    # 尝试从第一个 # 标题中提取
    lines = doc_content.strip().split("\n")
    for line in lines[:5]:
        line = line.strip()
        if line.startswith("#"):
            name = line.lstrip("#").strip()
            # 去掉常见前缀
            for prefix in ["【产品创意】", "产品创意：", "产品方案："]:
                if name.startswith(prefix):
                    name = name[len(prefix):]
            return name[:30]  # 最多30个字

    return f"AI产品Demo_{datetime.now().strftime('%Y%m%d')}"


def _extract_html(text: str) -> str:
    """从文本中提取HTML代码"""
    if not text:
        return ""

    # 查找 ```html ... ``` 格式
    import re
    html_match = re.search(r'```(?:html)?\s*(<!DOCTYPE.*?</html>)\s*```', text, re.DOTALL | re.IGNORECASE)
    if html_match:
        return html_match.group(1)

    # 查找 <!DOCTYPE 到 </html>
    start = text.lower().find("<!doctype")
    if start == -1:
        start = text.lower().find("<html")
    end = text.lower().rfind("</html>")

    if start != -1 and end != -1:
        return text[start:end+7]

    return ""


def _save_demo(product_name: str, html_code: str) -> tuple:
    """
    保存Demo文件到demos目录

    返回：(目录路径, 文件路径)
    """
    # 清理产品名称，用作目录名
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in product_name)
    safe_name = safe_name.strip("_")[:30]

    # 添加时间戳避免重复
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    dir_name = f"{safe_name}_{timestamp}"

    # 创建目录
    demos_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demos")
    demo_dir = os.path.join(demos_root, dir_name)
    os.makedirs(demo_dir, exist_ok=True)

    # 保存HTML文件
    demo_path = os.path.join(demo_dir, "index.html")
    with open(demo_path, "w", encoding="utf-8") as f:
        f.write(html_code)

    # 保存产品名称信息文件
    info_path = os.path.join(demo_dir, "info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump({
            "product_name": product_name,
            "created_at": datetime.now().isoformat(),
            "file": "index.html"
        }, f, ensure_ascii=False, indent=2)

    return demo_dir, demo_path


def _get_demos_count() -> int:
    """统计已构建的Demo数量"""
    demos_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "demos")
    if not os.path.exists(demos_root):
        return 0
    return len([d for d in os.listdir(demos_root)
                if os.path.isdir(os.path.join(demos_root, d))])


def _send_completion_notification(feishu_client, user_open_id, product_name, demo_path):
    """发送Demo完成的飞书通知"""
    message = (
        f"✅ Demo构建完成！\n\n"
        f"产品名称：{product_name}\n"
        f"文件位置：{demo_path}\n\n"
        f"使用方法：\n"
        f"用文件管理器找到上述路径，双击 index.html 即可在浏览器中打开Demo\n\n"
        f"如果是在GitHub Actions中运行，请到仓库的 demos/ 目录下载文件。"
    )
    feishu_client.send_message_to_user(user_open_id, message)


def _load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ============================================================
# 命令行入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI工程师Agent - 构建产品Demo原型")
    parser.add_argument("--doc-id", required=True, help="飞书产品方案文档ID")
    args = parser.parse_args()

    result = run(doc_id=args.doc_id)
    print(f"\n运行结果：{result.get('summary')}")
    if result.get("demo_path"):
        print(f"Demo文件：{result.get('demo_path')}")
