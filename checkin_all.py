#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 8 0 * * * checkin_all.py
new Env('每日Token签到汇总');

==================== 聚合签到（单次定时，一次推送）====================

把多个独立签到脚本聚合到【一次定时任务】里依次执行，最后把各脚本结果
合并成一条消息，只推送一次（避免每个脚本各自推送刷屏）。

当前聚合（执行顺序即列表顺序）：
    - WorkBuddy 每日签到    (workbuddy_checkin.py)
    - Trae Work 每日签到    (trae_checkin.py)
    - MiniMax Code 每日签到 (minimax_checkin.py)

设计要点：
    - 子脚本均已提供 checkin_once(cred) -> (flag, content)，本脚本直接调用并
      收集结果，不触发子脚本自身的推送（最终合并推送由本脚本统一发出）。
    - 子脚本在【导入阶段】失败（如依赖缺失会 sys.exit）时，仅跳过该脚本并在
      汇总中标注，不中断其余脚本。
    - 任一脚本运行异常均被捕获，结果如实汇总。

批量刷新（写回）token：在本机已登录三个桌面端的前提下，用一条命令即可把
    本机最新登录态写回 .env（等价逐个执行各脚本的 --export-env --save）：
        python checkin_all.py --export-env          # 仅打印各脚本从本机读出的变量
        python checkin_all.py --export-env --save   # 一次性写回 .env（推荐刷新时加 --save）
    任一脚本在本机未登录 / 依赖缺失 / 无 export_env 时会跳过并提示，不中断其余脚本。

在青龙/定时平台只需建【一个】任务指向本脚本即可，原 3 个独立签到任务的
定时可停用或删除。

依赖：pip install requests pycryptodome python-dotenv
==============================================================================
"""

import os
import sys
import importlib
import traceback
from datetime import datetime
import sendNotify

# 本地开发时自动加载同目录 .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass



# 聚合的脚本清单：(显示名, 模块文件名(不含 .py), 推送标题)
# 顺序即执行顺序：WorkBuddy -> Trae Work -> MiniMax Code
TASKS = [
    ("WorkBuddy", "workbuddy_checkin", "WorkBuddy 每日签到"),
    ("Trae Work", "trae_checkin", "Trae Work 每日签到"),
    ("MiniMax Code", "minimax_checkin", "MiniMax Code 每日签到"),
]

# 结果标记 -> 汇总行前缀图标
FLAG_ICON = {
    "SUCCESS": "✅",
    "ALREADY_TODAY": "ℹ️",
    "NET_ERR": "⚠️",
    "HTTP_ERR": "⚠️",
    "FAIL": "⚠️",
    "TOKEN_EXPIRED": "⚠️",
    "AUTH_EXPIRED": "⚠️",
    "RATE_LIMITED": "⏳",
    "NO_CREDENTIAL": "⚠️",
    "IMPORT_FAIL": "⚠️",
    "ERROR": "⚠️",
}


def _import_module(mod_name):
    """导入子模块；失败时返回 (None, 错误信息)。
    捕获 BaseException 以兼容子模块在 import 阶段 sys.exit / 依赖缺失等情况。"""
    try:
        return importlib.import_module(mod_name), None
    except BaseException as e:  # 含 SystemExit（如 trae 缺 pycryptodome 时 sys.exit(1)）
        return None, f"{type(e).__name__}: {e}"


def run_one(display_name, mod_name):
    """运行单个签到，返回 (display_name, flag, content)。异常被捕获并标注。"""
    mod, err = _import_module(mod_name)
    if mod is None:
        hint = "（trae_checkin 依赖 pycryptodome，请先安装：pip install pycryptodome）" \
            if mod_name == "trae_checkin" else ""
        return display_name, "IMPORT_FAIL", f"⚠️ 模块导入失败，已跳过：{err}{hint}"
    try:
        cred = mod.resolve_credentials()
        flag, content = mod.checkin_once(cred)
        return display_name, flag, content
    except BaseException as e:
        return display_name, "ERROR", \
            f"⚠️ 执行异常：{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}"


def build_summary(results):
    now = datetime.now().strftime("%m-%d")
    # 输出 Markdown：标题 + 每行加粗任务名，便于 server酱 按段渲染换行
    lines = [f"## {now} Token签到汇总", ""]
    ok = 0
    for name, flag, content in results:
        icon = FLAG_ICON.get(flag, "•")
        first_line = str(content).splitlines()[0] if str(content).strip() else "(空)"
        lines.append(f"{icon} **{name}**：{first_line}")
        if flag in ("SUCCESS", "ALREADY_TODAY"):
            ok += 1
    lines.append("")
    lines.append(f"**共 {len(results)} 项，成功/已签 {ok} 项**")
    return "\n".join(lines), ok, len(results)


def export_all():
    """批量刷新（写回）token：依次调用各子脚本的 export_env()，从本机登录态读取
    最新凭据；若带 --save 则一次性写回 .env。任一脚本失败仅跳过并提示。"""
    saving = "--save" in sys.argv
    print("== 批量刷新 token ==（从本机登录态读取最新凭据）")
    if not saving:
        print("提示：未带 --save，仅打印变量；加 --save 才会写回 .env")
    print("要求本机已登录：WorkBuddy 桌面端 / Trae 桌面端 / MiniMax Agent 桌面端\n")
    ok = 0
    for display_name, mod_name, _title in TASKS:
        mod, err = _import_module(mod_name)
        if mod is None:
            print(f"[跳过] {display_name}：模块导入失败（{err}）\n")
            continue
        if not hasattr(mod, "export_env"):
            print(f"[跳过] {display_name}：无 export_env 方法\n")
            continue
        print(f"--- {display_name} ---")
        try:
            rc = mod.export_env() or 0
        except BaseException as e:
            print(f"[异常] {display_name}：{type(e).__name__}: {e}\n")
            rc = 1
        if rc == 0:
            ok += 1
        print()
    print(f"完成：{ok}/{len(TASKS)} 个脚本成功刷新本地登录态"
          + ("（已写回 .env）" if saving else "（未写回，仅预览）"))


def main():
    if "--export-env" in sys.argv:
        export_all()
        return

    results = []
    for display_name, mod_name, _title in TASKS:
        name, flag, content = run_one(display_name, mod_name)
        results.append((name, flag, content))
        # 实时打印（仅首行，便于日志查看；完整内容见下方汇总）
        print(f"\n[{name}] RESULT={flag} | {str(content).splitlines()[0]}")

    summary, ok, total = build_summary(results)
    print("\n" + "=" * 50)
    print(summary)
    print("=" * 50)

    title = f"每日Token签到汇总✅{ok}/{total}"
    try:
        sendNotify.serverJMy(title, summary)
    except Exception as e:
        print(f"[warn] 合并推送失败: {e}")


if __name__ == "__main__":
    main()
