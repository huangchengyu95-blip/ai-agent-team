"""
状态追踪工具
- 记录每个Agent的运行状态和进度
- 维护活动日志
- 状态数据存储在status.json文件中
- GitHub Actions会把这个文件推送到仓库，GitHub Pages看板就能显示最新状态
"""

import json
import os
from datetime import datetime


# status.json文件的位置（项目根目录）
STATUS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "status.json")

# 活动日志最多保留多少条（太多了看板会很慢）
MAX_LOG_ENTRIES = 50


def _load_status() -> dict:
    """读取status.json文件"""
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告：status.json文件不存在，将创建新的")
        return _create_empty_status()
    except json.JSONDecodeError:
        print(f"警告：status.json文件格式错误，将重置")
        return _create_empty_status()


def _save_status(status: dict):
    """把状态数据写入status.json文件"""
    status["last_updated"] = datetime.now().isoformat()
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def _create_empty_status() -> dict:
    """创建空的状态数据结构"""
    return {
        "last_updated": "",
        "system_status": "initializing",
        "agents": {
            "trend_tracker": {"name": "AI动态追踪员", "status": "waiting", "last_run": "", "last_result": "", "total_runs": 0},
            "product_manager": {"name": "产品经理", "status": "waiting", "last_run": "", "last_result": "", "total_ideas": 0},
            "product_reviewer": {"name": "产品评审员", "status": "waiting", "last_run": "", "last_result": "", "pending_review": None},
            "engineer": {"name": "工程师", "status": "waiting", "last_run": "", "last_result": "", "demos_built": 0},
        },
        "activity_log": [],
        "feishu_links": {"trend_doc": "", "knowledge_doc": "", "ideas_folder": ""},
        "stats": {"total_pipeline_runs": 0, "total_ideas_generated": 0, "total_demos_built": 0},
    }


def update_agent_status(agent_key: str, status: str, result: str = "", extra: dict = None):
    """
    更新某个Agent的状态

    参数：
    - agent_key: Agent的标识符，如 "trend_tracker", "product_manager" 等
    - status: 状态，可以是 "running"（运行中）、"idle"（空闲）、"waiting"（等待）、"error"（出错）
    - result: 本次运行的结果描述（一句话总结）
    - extra: 额外要保存的字段（如产品方案标题等）
    """
    data = _load_status()

    if agent_key not in data["agents"]:
        data["agents"][agent_key] = {"name": agent_key, "status": "waiting"}

    # 更新Agent状态
    agent = data["agents"][agent_key]
    agent["status"] = status
    if result:
        agent["last_result"] = result
    if status in ["idle", "error"]:
        agent["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        agent["total_runs"] = agent.get("total_runs", 0) + 1

    # 更新额外字段
    if extra:
        agent.update(extra)

    # 更新系统整体状态
    data["system_status"] = "running"

    _save_status(data)


def log_activity(agent_key: str, message: str):
    """
    添加一条活动日志（显示在看板的"最新动态"列表里）

    参数：
    - agent_key: Agent的标识符
    - message: 活动描述
    """
    data = _load_status()

    # 新日志放在最前面
    log_entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "agent": agent_key,
        "message": message
    }

    if "activity_log" not in data:
        data["activity_log"] = []

    data["activity_log"].insert(0, log_entry)

    # 只保留最近N条日志
    data["activity_log"] = data["activity_log"][:MAX_LOG_ENTRIES]

    _save_status(data)


def update_feishu_links(trend_doc: str = None, knowledge_doc: str = None, ideas_folder: str = None):
    """
    更新飞书文档链接（用于看板显示快捷入口）

    参数：
    - trend_doc: AI动态追踪汇总文档链接
    - knowledge_doc: AI社交认知沉淀文档链接
    - ideas_folder: 产品方案文件夹链接
    """
    data = _load_status()

    if "feishu_links" not in data:
        data["feishu_links"] = {}

    if trend_doc:
        data["feishu_links"]["trend_doc"] = trend_doc
    if knowledge_doc:
        data["feishu_links"]["knowledge_doc"] = knowledge_doc
    if ideas_folder:
        data["feishu_links"]["ideas_folder"] = ideas_folder

    _save_status(data)


def increment_stat(stat_key: str):
    """
    增加统计数字（如生成创意数、构建Demo数等）

    参数：
    - stat_key: 统计项的键名，如 "total_ideas_generated"
    """
    data = _load_status()

    if "stats" not in data:
        data["stats"] = {}

    data["stats"][stat_key] = data["stats"].get(stat_key, 0) + 1
    _save_status(data)


def get_status() -> dict:
    """读取并返回当前的完整状态数据"""
    return _load_status()
