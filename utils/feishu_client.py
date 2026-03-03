"""
飞书（Lark）API客户端
提供飞书文档的读取、追加，以及消息发送功能

使用前需要在环境变量中设置：
- FEISHU_APP_ID: 飞书应用ID
- FEISHU_APP_SECRET: 飞书应用密钥
"""

import os
import json
import requests
from datetime import datetime


# 飞书API的基础地址
FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书API操作封装类"""

    def __init__(self):
        # 从环境变量读取应用凭证
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        # 用户Open ID，用于自动将新建文档分享给用户
        self.user_open_id = os.environ.get("FEISHU_USER_OPEN_ID", "")

        # 缓存访问令牌（有效期2小时）
        self._access_token = None
        self._token_expires = 0

        # 检查凭证是否配置
        if not self.app_id or not self.app_secret:
            print("⚠️  警告：未找到飞书应用凭证（FEISHU_APP_ID / FEISHU_APP_SECRET）")
            print("     飞书相关功能将不可用，请按README.md步骤配置")

    def is_configured(self) -> bool:
        """检查飞书是否已配置"""
        return bool(self.app_id and self.app_secret)

    # ============================================================
    # 内部方法：获取访问令牌
    # ============================================================

    def _get_access_token(self) -> str:
        """
        获取飞书访问令牌（tenant_access_token）
        令牌有效期2小时，过期后自动刷新
        """
        import time
        # 如果令牌还有效，直接返回
        if self._access_token and time.time() < self._token_expires - 60:
            return self._access_token

        # 请求新的令牌
        try:
            resp = requests.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10
            )
            data = resp.json()

            if data.get("code") != 0:
                raise Exception(f"获取令牌失败：{data.get('msg', '未知错误')}")

            import time as t
            self._access_token = data["tenant_access_token"]
            self._token_expires = t.time() + data.get("expire", 7200)
            return self._access_token

        except Exception as e:
            print(f"❌ 获取飞书令牌失败：{e}")
            return ""

    def _request(self, method: str, path: str, data: dict = None, params: dict = None) -> dict:
        """发送飞书API请求的通用方法"""
        token = self._get_access_token()
        if not token:
            return {"code": -1, "msg": "无法获取访问令牌"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }

        url = f"{FEISHU_BASE_URL}{path}"

        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=15)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, json=data, params=params, timeout=15)
            elif method.upper() == "PATCH":
                resp = requests.patch(url, headers=headers, json=data, params=params, timeout=15)
            else:
                return {"code": -1, "msg": f"不支持的请求方法：{method}"}

            result = resp.json()
            return result

        except Exception as e:
            return {"code": -1, "msg": f"请求失败：{str(e)}"}

    # ============================================================
    # 文档操作
    # ============================================================

    def create_document(self, title: str, folder_token: str = "") -> dict:
        """
        创建一个新的飞书文档

        参数：
        - title: 文档标题
        - folder_token: 存放到哪个文件夹（空则放在根目录）

        返回：{"document_id": "...", "url": "..."} 或 None
        """
        if not self.is_configured():
            print("飞书未配置，跳过创建文档")
            return None

        data = {"title": title}
        if folder_token:
            data["folder_token"] = folder_token

        result = self._request("POST", "/docx/v1/documents", data=data)

        if result.get("code") == 0:
            doc = result.get("data", {}).get("document", {})
            doc_id = doc.get("document_id", "")
            url = f"https://docs.feishu.cn/docx/{doc_id}"
            print(f"✅ 文档创建成功：{title} -> {url}")
            # 自动将文档分享给用户，这样用户可以直接打开链接
            if self.user_open_id:
                self._share_document_with_user(doc_id)
            return {"document_id": doc_id, "url": url}
        else:
            print(f"❌ 创建文档失败：{result.get('msg')}")
            return None

    def _share_document_with_user(self, document_id: str) -> bool:
        """
        自动将文档分享给配置的用户（可编辑权限）
        在 create_document 后自动调用，确保用户能打开链接
        """
        if not self.user_open_id:
            return False
        result = self._request(
            "POST",
            f"/drive/v1/permissions/{document_id}/members",
            data={
                "member_type": "openid",
                "member_id": self.user_open_id,
                "perm": "edit",
                "type": "user"
            },
            params={"type": "docx", "need_notification": "false"}
        )
        if result.get("code") == 0:
            print(f"✅ 文档已自动分享给用户")
            return True
        else:
            print(f"⚠️  文档分享失败（不影响主流程）：{result.get('msg')}")
            return False

    def get_document_content(self, document_id: str) -> str:
        """
        获取飞书文档的纯文字内容

        参数：
        - document_id: 文档ID

        返回：文档的纯文字内容
        """
        if not self.is_configured():
            return ""

        result = self._request("GET", f"/docx/v1/documents/{document_id}/raw_content")

        if result.get("code") == 0:
            return result.get("data", {}).get("content", "")
        else:
            print(f"❌ 读取文档失败（{document_id}）：{result.get('msg')}")
            return ""

    def append_to_document(self, document_id: str, content: str) -> bool:
        """
        向飞书文档末尾追加内容

        参数：
        - document_id: 文档ID
        - content: 要追加的Markdown格式文字

        返回：是否成功
        """
        if not self.is_configured():
            print("飞书未配置，跳过文档更新（内容将打印到控制台）")
            print(f"--- 要追加的内容 ---\n{content}\n---")
            return False

        # 第一步：获取文档的根块ID
        blocks_result = self._request("GET", f"/docx/v1/documents/{document_id}/blocks")
        if blocks_result.get("code") != 0:
            print(f"❌ 获取文档结构失败：{blocks_result.get('msg')}")
            return False

        items = blocks_result.get("data", {}).get("items", [])
        if not items:
            print("❌ 文档没有内容块")
            return False

        # 第一个块是文档根块（page块）
        root_block_id = items[0].get("block_id", "")
        if not root_block_id:
            print("❌ 无法获取根块ID")
            return False

        # 第二步：把Markdown内容转换成飞书文档块格式
        blocks = _markdown_to_blocks(content)

        if not blocks:
            print("⚠️  没有可追加的内容块")
            return False

        # 第三步：追加到文档末尾（index=-1表示追加到末尾）
        result = self._request(
            "POST",
            f"/docx/v1/documents/{document_id}/blocks/{root_block_id}/children",
            data={"children": blocks, "index": -1}
        )

        if result.get("code") == 0:
            print(f"✅ 文档追加成功（{len(blocks)}个内容块）")
            return True
        else:
            print(f"❌ 文档追加失败：{result.get('msg')}")
            return False

    def update_document_title(self, document_id: str, title: str) -> bool:
        """更新文档标题"""
        if not self.is_configured():
            return False

        # 获取文档根块ID
        blocks_result = self._request("GET", f"/docx/v1/documents/{document_id}/blocks")
        if blocks_result.get("code") != 0:
            return False

        items = blocks_result.get("data", {}).get("items", [])
        if not items:
            return False

        root_block_id = items[0].get("block_id", "")

        # 更新根块的标题
        result = self._request(
            "PATCH",
            f"/docx/v1/documents/{document_id}/blocks/{root_block_id}",
            data={
                "update_text_elements": {
                    "elements": [{"text_run": {"content": title}}]
                }
            }
        )
        return result.get("code") == 0

    # ============================================================
    # 消息发送
    # ============================================================

    def send_message_to_user(self, user_open_id: str, message: str) -> bool:
        """
        发送飞书文字消息给指定用户

        参数：
        - user_open_id: 用户的Open ID（在config.json里配置）
        - message: 消息内容（纯文字）

        返回：是否发送成功
        """
        if not self.is_configured():
            print(f"飞书未配置，消息将打印到控制台：\n{message}")
            return False

        if not user_open_id:
            print("⚠️  未配置用户Open ID，无法发送消息")
            return False

        result = self._request(
            "POST",
            "/im/v1/messages",
            data={
                "receive_id": user_open_id,
                "msg_type": "text",
                "content": json.dumps({"text": message})
            },
            params={"receive_id_type": "open_id"}
        )

        if result.get("code") == 0:
            print("✅ 飞书消息发送成功")
            return True
        else:
            print(f"❌ 飞书消息发送失败：{result.get('msg')}")
            return False

    def send_rich_message(self, user_open_id: str, title: str, content: str,
                          doc_url: str = "") -> bool:
        """
        发送飞书富文本消息（带标题和正文）

        参数：
        - user_open_id: 用户Open ID
        - title: 消息标题
        - content: 消息正文
        - doc_url: 相关文档链接（可选）

        返回：是否成功
        """
        if not self.is_configured() or not user_open_id:
            full_message = f"【{title}】\n\n{content}"
            if doc_url:
                full_message += f"\n\n查看详情：{doc_url}"
            print(f"飞书未配置，消息打印如下：\n{full_message}")
            return False

        # 构造富文本内容
        body_content = []

        # 按行处理正文，支持链接
        for line in content.split("\n"):
            if line.strip():
                body_content.append([{"tag": "text", "text": line}])

        # 如果有链接，添加到末尾
        if doc_url:
            body_content.append([])  # 空行
            body_content.append([
                {"tag": "a", "text": "📄 查看完整报告", "href": doc_url}
            ])

        post_content = {
            "zh_cn": {
                "title": title,
                "content": body_content
            }
        }

        result = self._request(
            "POST",
            "/im/v1/messages",
            data={
                "receive_id": user_open_id,
                "msg_type": "post",
                "content": json.dumps(post_content)
            },
            params={"receive_id_type": "open_id"}
        )

        if result.get("code") == 0:
            print("✅ 飞书富文本消息发送成功")
            return True
        else:
            # 降级为普通文字消息
            print(f"富文本发送失败，改用文字消息：{result.get('msg')}")
            plain = f"【{title}】\n\n{content}"
            if doc_url:
                plain += f"\n\n查看详情：{doc_url}"
            return self.send_message_to_user(user_open_id, plain)

    # ============================================================
    # 文件夹操作
    # ============================================================

    def create_folder(self, name: str, parent_token: str = "") -> str:
        """
        创建飞书云盘文件夹

        参数：
        - name: 文件夹名称
        - parent_token: 父文件夹的token（空则在根目录创建）

        返回：新文件夹的token
        """
        if not self.is_configured():
            return ""

        data = {"name": name}
        if parent_token:
            data["folder_token"] = parent_token

        result = self._request("POST", "/drive/v1/files/create_folder", data=data)

        if result.get("code") == 0:
            token = result.get("data", {}).get("token", "")
            print(f"✅ 文件夹创建成功：{name}")
            return token
        else:
            print(f"❌ 文件夹创建失败：{result.get('msg')}")
            return ""


# ============================================================
# 辅助函数：Markdown转飞书文档块
# ============================================================

def _markdown_to_blocks(markdown_text: str) -> list:
    """
    把Markdown格式的文字转换成飞书文档块格式

    支持：
    - # 一级标题
    - ## 二级标题
    - ### 三级标题
    - - 无序列表
    - 普通段落
    - --- 分割线
    - 空行（段落间距）
    """
    blocks = []
    lines = markdown_text.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # 跳过开头的空行
        if not line and not blocks:
            i += 1
            continue

        # 分割线
        if line in ("---", "***", "___"):
            blocks.append({
                "block_type": 22,  # 分割线
                "divider": {}
            })

        # 一级标题
        elif line.startswith("# ") and not line.startswith("## "):
            text = line[2:].strip()
            blocks.append(_make_heading_block(text, level=1))

        # 二级标题
        elif line.startswith("## ") and not line.startswith("### "):
            text = line[3:].strip()
            blocks.append(_make_heading_block(text, level=2))

        # 三级标题
        elif line.startswith("### "):
            text = line[4:].strip()
            blocks.append(_make_heading_block(text, level=3))

        # 无序列表项
        elif line.startswith("- ") or line.startswith("* "):
            text = line[2:].strip()
            blocks.append(_make_bullet_block(text))

        # 有序列表项（如 "1. xxx"）
        elif len(line) > 2 and line[0].isdigit() and line[1] in ".)" and line[2] == " ":
            text = line[3:].strip()
            blocks.append(_make_text_block(f"• {text}"))

        # 加粗文字（简单处理，**bold** 保留标记）
        elif line.strip():
            # 普通段落
            blocks.append(_make_text_block(line.strip()))

        # 空行（段落分隔）
        else:
            # 不添加空白块，飞书文档本身会处理段落间距
            pass

        i += 1

    return blocks


def _make_text_block(text: str) -> dict:
    """创建普通文字块"""
    return {
        "block_type": 2,  # 文字块
        "text": {
            "elements": [{"text_run": {"content": text}}],
            "style": {}
        }
    }


def _make_heading_block(text: str, level: int = 1) -> dict:
    """
    创建标题块
    level: 1=一级标题(block_type=3), 2=二级标题(block_type=4), 3=三级标题(block_type=5)
    """
    # 飞书标题块类型：3=H1, 4=H2, 5=H3
    block_type = 2 + level  # H1=3, H2=4, H3=5

    heading_key = {1: "heading1", 2: "heading2", 3: "heading3"}
    key = heading_key.get(level, "heading2")

    return {
        "block_type": block_type,
        key: {
            "elements": [{"text_run": {"content": text}}],
            "style": {}
        }
    }


def _make_bullet_block(text: str) -> dict:
    """创建无序列表项块"""
    return {
        "block_type": 9,  # 无序列表
        "bullet": {
            "elements": [{"text_run": {"content": text}}],
            "style": {}
        }
    }
