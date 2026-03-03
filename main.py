"""
AI Agent Team - 主入口
串联Agent 1（动态追踪员） → Agent 2（产品经理） → Agent 3（评审员）的执行流程

运行方式：
  python main.py          # 正常运行完整流水线
  python main.py --dry-run  # 测试模式（不调用LLM，测试飞书连接和状态更新）
  python main.py --agent trend   # 只运行动态追踪员
  python main.py --agent pm      # 只运行产品经理
"""

import argparse
import json
import os
import sys
from datetime import datetime

# 加载环境变量（本地测试时从.env文件读取，GitHub Actions中从Secrets读取）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv不是必须的，GitHub Actions中直接用环境变量

# 导入工具和Agent模块
from utils.feishu_client import FeishuClient
from utils.llm_client import LLMClient
from utils.status_tracker import update_agent_status, log_activity, increment_stat, get_status
import agents.trend_tracker as trend_tracker_agent
import agents.product_manager as product_manager_agent
import agents.product_reviewer as product_reviewer_agent


def run_pipeline(dry_run: bool = False, only_agent: str = None):
    """
    运行完整的Agent流水线

    参数：
    - dry_run: 测试模式，不调用LLM，用于测试飞书连接和GitHub Actions配置
    - only_agent: 只运行某个Agent（"trend"/"pm"/"reviewer"）
    """
    start_time = datetime.now()
    print("\n" + "="*60)
    print("🚀 AI Agent Team 启动")
    print(f"   时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   模式：{'测试模式（dry-run）' if dry_run else '正常运行'}")
    if only_agent:
        print(f"   指定Agent：{only_agent}")
    print("="*60)

    # 初始化客户端（所有Agent共享同一个实例，节省资源）
    feishu = FeishuClient()
    llm = LLMClient()
    config = _load_config()

    # 检查配置状态
    print("\n📋 配置检查：")
    print(f"   飞书：{'✅ 已配置' if feishu.is_configured() else '⚠️  未配置（飞书功能将打印到控制台）'}")
    print(f"   LLM：{'✅ 已配置' if llm.is_configured() else '⚠️  未配置（将使用测试模式）'}")

    # 如果是dry-run模式，用测试流程
    if dry_run:
        return _run_dry_run(feishu, config)

    # 首次运行时自动创建产品方案文件夹（若尚未配置）
    if feishu.is_configured():
        _ensure_ideas_folder(feishu, config)

    # ============================================================
    # 流水线执行
    # ============================================================

    results = {
        "trend": None,
        "pm": None,
        "reviewer": None,
        "pipeline_success": False
    }

    # ----- Agent 1: 动态追踪员 -----
    if only_agent in (None, "trend"):
        try:
            trend_result = trend_tracker_agent.run(
                feishu_client=feishu,
                llm_client=llm,
                config=config
            )
            results["trend"] = trend_result
        except Exception as e:
            print(f"\n❌ 动态追踪员异常：{e}")
            results["trend"] = {"success": False, "summary": str(e), "has_updates": False}

    # 如果只运行追踪员，到这里就结束
    if only_agent == "trend":
        _print_summary(results, start_time)
        return results

    # ----- Agent 2: 产品经理 -----
    if only_agent in (None, "pm"):
        trend_summary = results.get("trend", {}).get("summary", "") if results.get("trend") else ""
        trend_content = results.get("trend", {}).get("content", "") if results.get("trend") else ""

        try:
            pm_result = product_manager_agent.run(
                feishu_client=feishu,
                llm_client=llm,
                config=config,
                trend_summary=trend_summary,
                trend_content=trend_content
            )
            results["pm"] = pm_result
        except Exception as e:
            print(f"\n❌ 产品经理异常：{e}")
            results["pm"] = {"success": False, "summary": str(e), "has_product_idea": False}

    # 如果只运行产品经理，到这里就结束
    if only_agent == "pm":
        _print_summary(results, start_time)
        return results

    # ----- Agent 3: 评审员（仅在有产品创意时运行）-----
    pm_result = results.get("pm", {})
    if pm_result and pm_result.get("has_product_idea") and pm_result.get("product_idea"):
        print("\n🎯 产品经理发现了新的产品机会，启动评审员...")

        try:
            reviewer_result = product_reviewer_agent.run(
                feishu_client=feishu,
                llm_client=llm,
                config=config,
                product_idea=pm_result.get("product_idea", {}),
                idea_doc_url=pm_result.get("idea_doc_url", "")
            )
            results["reviewer"] = reviewer_result
        except Exception as e:
            print(f"\n❌ 评审员异常：{e}")
            results["reviewer"] = {"success": False, "summary": str(e)}
    else:
        print("\nℹ️  本次没有新的产品创意，评审员不需要运行")
        update_agent_status("product_reviewer", "waiting", "等待产品经理生成新创意")

    # ============================================================
    # 完成
    # ============================================================
    results["pipeline_success"] = True
    increment_stat("total_pipeline_runs")
    _print_summary(results, start_time)

    # 推送status.json（GitHub Actions会自动提交这个文件）
    _commit_status_update()

    return results


def _run_dry_run(feishu: FeishuClient, config: dict) -> dict:
    """
    测试模式：验证系统基础设施是否正常工作
    不调用LLM，专注测试：飞书连接、状态更新、文件读写
    """
    print("\n🧪 测试模式启动（不调用LLM）\n")

    tests_passed = 0
    tests_failed = 0

    # 测试1：状态更新
    print("测试1：状态文件读写...")
    try:
        update_agent_status("trend_tracker", "idle", "干运行测试成功")
        log_activity("trend_tracker", "干运行测试 - 状态更新正常")
        print("   ✅ 状态文件读写正常")
        tests_passed += 1
    except Exception as e:
        print(f"   ❌ 状态文件读写失败：{e}")
        tests_failed += 1

    # 测试2：飞书连接
    print("\n测试2：飞书API连接...")
    if feishu.is_configured():
        try:
            token = feishu._get_access_token()
            if token:
                print("   ✅ 飞书API连接正常，令牌获取成功")
                tests_passed += 1
            else:
                print("   ❌ 飞书API令牌获取失败，请检查 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
                tests_failed += 1
        except Exception as e:
            print(f"   ❌ 飞书连接测试失败：{e}")
            tests_failed += 1
    else:
        print("   ⚠️  飞书未配置（FEISHU_APP_ID / FEISHU_APP_SECRET 未设置），跳过测试")

    # 测试3：飞书消息发送
    print("\n测试3：飞书消息发送...")
    user_open_id = config.get("feishu", {}).get("user", {}).get("open_id", "")
    if feishu.is_configured() and user_open_id:
        try:
            success = feishu.send_message_to_user(
                user_open_id,
                "🧪 AI Agent Team 测试消息\n\n系统基础设施测试中，收到此消息说明飞书消息发送正常！"
            )
            if success:
                print("   ✅ 飞书消息发送成功，请检查你的飞书是否收到测试消息")
                tests_passed += 1
            else:
                print("   ❌ 飞书消息发送失败，请检查 FEISHU_USER_OPEN_ID 配置")
                tests_failed += 1
        except Exception as e:
            print(f"   ❌ 飞书消息测试失败：{e}")
            tests_failed += 1
    else:
        print("   ⚠️  飞书未完全配置（缺少 FEISHU_USER_OPEN_ID），跳过消息测试")

    # 测试4：飞书文档读写
    print("\n测试4：飞书文档读写...")
    trend_doc_id = config.get("feishu", {}).get("documents", {}).get("trend_doc_id", "")
    if feishu.is_configured() and trend_doc_id:
        try:
            test_content = f"\n## 🧪 干运行测试 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n这是系统测试时自动写入的内容，可以删除。\n"
            success = feishu.append_to_document(trend_doc_id, test_content)
            if success:
                print("   ✅ 飞书文档写入成功")
                tests_passed += 1
            else:
                print("   ❌ 飞书文档写入失败，请检查文档ID和应用权限")
                tests_failed += 1
        except Exception as e:
            print(f"   ❌ 飞书文档测试失败：{e}")
            tests_failed += 1
    else:
        print("   ⚠️  未配置飞书文档ID（config.json中trend_doc_id为空），跳过文档测试")

    # 汇总测试结果
    print(f"\n{'='*40}")
    print(f"测试结果：{tests_passed}个通过，{tests_failed}个失败")
    if tests_failed == 0:
        print("🎉 所有测试通过！基础设施正常工作")
        print("   下一步：配置火山引擎API Key，完成LLM功能测试")
    else:
        print("⚠️  部分测试失败，请根据上面的提示检查配置")
    print(f"{'='*40}")

    return {"dry_run": True, "passed": tests_passed, "failed": tests_failed}


def _print_summary(results: dict, start_time: datetime):
    """打印流水线运行摘要"""
    elapsed = (datetime.now() - start_time).total_seconds()
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "="*60)
    print("📊 本次运行摘要")
    print(f"   总耗时：{minutes}分{seconds}秒")
    print(f"   完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if results.get("trend"):
        status = "✅" if results["trend"].get("success") else "❌"
        print(f"   {status} 动态追踪员：{results['trend'].get('summary', '无摘要')}")

    if results.get("pm"):
        status = "✅" if results["pm"].get("success") else "❌"
        has_idea = "（发现产品机会！）" if results["pm"].get("has_product_idea") else ""
        print(f"   {status} 产品经理：{results['pm'].get('summary', '无摘要')}{has_idea}")

    if results.get("reviewer"):
        status = "✅" if results["reviewer"].get("success") else "❌"
        print(f"   {status} 评审员：{results['reviewer'].get('summary', '无摘要')}")

    print("="*60)


def _ensure_ideas_folder(feishu: FeishuClient, config: dict):
    """
    确保产品方案文件夹已创建并配置。
    若 config.json 中的 ideas_folder_token 为空，则自动创建飞书文件夹，
    并将 token 保存回 config.json（下次运行时直接使用）。
    """
    from utils.status_tracker import update_feishu_links

    folder_token = config.get("feishu", {}).get("documents", {}).get("ideas_folder_token", "")
    if folder_token:
        return  # 已配置，无需重复创建

    print("\n📁 产品方案文件夹尚未创建，正在自动创建...")
    token = feishu.create_folder("产品方案")
    if not token:
        print("   ⚠️  文件夹创建失败，将把产品方案文档存放在云盘根目录")
        return

    print(f"   ✅ 产品方案文件夹创建成功，token={token}")

    # 把 token 写回 config.json，供后续运行使用
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        raw["feishu"]["documents"]["ideas_folder_token"] = token
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
        config["feishu"]["documents"]["ideas_folder_token"] = token
        print("   ✅ 已将文件夹 token 保存到 config.json")
    except Exception as e:
        print(f"   ⚠️  保存 config.json 失败：{e}")

    # 更新看板中的文件夹链接（飞书文件夹 URL 格式）
    doc_domain = config.get("feishu", {}).get("feishu_doc_domain", "docs.feishu.cn")
    folder_url = f"https://{doc_domain}/drive/folder/{token}"
    update_feishu_links(ideas_folder=folder_url)
    print(f"   ✅ 看板文件夹链接已更新：{folder_url}")


def _commit_status_update():
    """
    在GitHub Actions中，自动提交status.json到仓库
    这样GitHub Pages就能显示最新状态
    """
    # 只在GitHub Actions环境中执行
    if not os.environ.get("GITHUB_ACTIONS"):
        return

    try:
        import subprocess
        subprocess.run(["git", "config", "user.email", "agent@ai-team.bot"], check=True)
        subprocess.run(["git", "config", "user.name", "AI Agent Team"], check=True)
        # 同时提交 status.json 和 config.json（创建新文件夹时 config.json 也会更新）
        subprocess.run(["git", "add", "status.json", "config.json"], check=True)
        # 检查是否有变化再提交
        result = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if result.returncode != 0:  # 有变化
            subprocess.run(["git", "commit", "-m", f"chore: update agent status [{datetime.now().strftime('%Y-%m-%d %H:%M')}]"], check=True)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
            subprocess.run(["git", "push"], check=True)
            print("✅ 状态已推送到GitHub Pages")
    except Exception as e:
        print(f"⚠️  状态推送失败（不影响主流程）：{e}")


def _load_config() -> dict:
    """读取config.json配置文件"""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️  读取config.json失败：{e}")
        return {}


# ============================================================
# 命令行入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="AI Agent Team - 产品经理助手系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python main.py                # 运行完整流水线
  python main.py --dry-run      # 测试模式，验证飞书配置是否正确
  python main.py --agent trend  # 只运行动态追踪员
  python main.py --agent pm     # 只运行产品经理
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="测试模式：不调用LLM，只测试飞书连接和系统配置"
    )
    parser.add_argument(
        "--agent",
        choices=["trend", "pm", "reviewer"],
        default=None,
        help="只运行指定的Agent（默认运行完整流水线）"
    )

    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run, only_agent=args.agent)
