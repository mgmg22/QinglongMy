#!/bin/env python3
# -*- coding: utf-8 -*
"""
# cron: 9 0 * * * workbuddy_checkin.py
# new Env('WorkBuddy每日积分签到');

==================== 如何获取 WB_ACCESS_TOKEN / WB_USER_ID ====================

脚本签到点 = POST https://copilot.tencent.com/v2/billing/meter/daily-checkin
鉴权需要两个值：accessToken（Bearer） + uid（X-User-Id）。

【方式一 · 推荐：环境变量（脚本默认且唯一读取来源）】
在 .env 或运行环境中设置：
        WB_ACCESS_TOKEN=<auth.accessToken 的值>
        WB_USER_ID=<account.uid 的值>

    脚本【默认只读取上述环境变量】，不再自动读取本机登录态，
    方便容器 / 跨机 / 青龙部署：凭据完全由环境变量决定，行为可预期。

【方式二 · 刷新 token：--export-env（仅本机、不进入默认运行链）】
token 过期时，在本机（已登录 WorkBuddy 桌面端 v5.3.8+）执行：
        python workbuddy_checkin.py --export-env
    会读取本机明文登录态并打印最新变量；追加 --save 可直接写回 .env：
        python workbuddy_checkin.py --export-env --save

本机登录态文件（仅供参考，不参与默认运行）：
    %LOCALAPPDATA%\\CodeBuddyExtension\\Data\\Public\\auth\\workbuddy-desktop.info
    （v5.3.8+ 桌面端写入，纯文本 JSON，无需解密）
    macOS：~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info
    Linux：~/.config/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info
    字段： WB_ACCESS_TOKEN = auth.accessToken ， WB_USER_ID = account.uid

优先级（仅 --export-env 路径）：本机明文登录态 > 其它。
==============================================================================
"""

import os
import re
import sys
import json
import platform
import requests
import sendNotify

# 本地开发时自动加载同目录 .env；已设置的真实环境变量优先，不受影响
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass


def _save_env_values(values: dict):
    """把导出的环境变量写回同目录 .env（仅更新/追加给定 key，保留其它内容）。
    仅 --export-env --save 时调用。返回写入的变量数（0 表示失败）。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    lines = []
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                lines = fh.read().splitlines()
        except Exception:
            lines = []
    updated = set()
    out = []
    for line in lines:
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
        if m and m.group(1) in values:
            out.append(f"{m.group(1)}={values[m.group(1)]}")
            updated.add(m.group(1))
        else:
            out.append(line)
    for k, v in values.items():
        if k not in updated:
            out.append(f"{k}={v}")
    try:
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        return len(values)
    except Exception as e:
        print(f"[warn] 写入 .env 失败: {e}")
        return 0

API_BASE = "https://copilot.tencent.com"
CHECKIN_PATH = "/v2/billing/meter/daily-checkin"
STATUS_PATH = "/v2/billing/meter/checkin-status"

# 本地明文登录态候选路径（v5.3.8+ 桌面端写入）
def _local_info_candidates():
    cands = []
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        app = os.environ.get("APPDATA", "")
        if local:
            cands.append(os.path.join(local, "CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info"))
        if app:
            cands.append(os.path.join(app, "CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info"))
    elif platform.system() == "Darwin":
        home = os.path.expanduser("~")
        cands.append(os.path.join(home, "Library", "Application Support",
                                  "CodeBuddyExtension", "Data", "Public", "auth", "workbuddy-desktop.info"))
    else:
        home = os.path.expanduser("~")
        cands.append(os.path.join(home, ".config", "CodeBuddyExtension", "Data", "Public", "auth",
                                  "workbuddy-desktop.info"))
    return cands


def resolve_credentials():
    """仅读取环境变量，返回凭据 dict。
    缺少 WB_ACCESS_TOKEN / WB_USER_ID 时返回空 token，checkin 阶段判为 NO_CREDENTIAL。
    刷新 token 请用 `python workbuddy_checkin.py --export-env`。"""
    return {
        "token": os.environ.get("WB_ACCESS_TOKEN", "").strip(),
        "uid": os.environ.get("WB_USER_ID", "").strip(),
    }


def read_local_credential():
    """读取本机已登录的 WorkBuddy 桌面端明文登录态（仅 --export-env 使用）。"""
    for f in _local_info_candidates():
        if not os.path.isfile(f):
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                j = json.load(fh)
            token = (j.get("auth") or {}).get("accessToken", "")
            acct = j.get("account") or {}
            auth = j.get("auth") or {}
            uid = str(acct.get("uid", "") or "")
            if token and uid:
                return {"token": token, "uid": uid}
        except Exception as e:
            print(f"[warn] 读取本地登录态失败 {f}: {e}")
    return None


def export_env():
    """--export-env：读取本机登录态并打印/保存环境变量（token 过期时用来刷新）。"""
    c = read_local_credential()
    if not c:
        print("未发现 WorkBuddy 登录态，请先在本机登录 WorkBuddy 桌面端（v5.3.8+）")
        return 1
    values = {
        "WB_ACCESS_TOKEN": c["token"],
        "WB_USER_ID": c["uid"],
    }
    print(f"WB_ACCESS_TOKEN={c['token']}")
    print(f"WB_USER_ID={c['uid']}")
    if "--save" in sys.argv:
        n = _save_env_values(values)
        if n:
            print(f"# 已将上述 {n} 个变量写回 .env")
    return 0


def _call(token, uid, path):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-User-Id": uid,
    }
    try:
        r = requests.post(API_BASE + path, headers=headers, data="{}", timeout=15)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text}
    except Exception as e:
        return 0, {"error": str(e)}


def _num(v):
    """把可能是字符串/数字的剩余值安全地转 float，无法解析记 0。"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _fmt(v):
    """余额取整显示。"""
    return str(int(round(v)))


def _get_total_credits(token, uid):
    """读取『总剩余积分』（与 WorkBuddy 客户端展示口径一致）。

    来源是签到状态接口的 total_credits 字段（官方页面『总剩余积分』的直接来源），
    优先 /v2/billing/meter/checkin-activity-status，回退到 STATUS_PATH。
    返回 float 或 None（无数据 / 接口异常）。"""
    for path in ("/v2/billing/meter/checkin-activity-status", STATUS_PATH):
        try:
            sc, sb = _call(token, uid, path)
        except Exception:
            continue
        if isinstance(sb, dict):
            tc = (sb.get("data") or {}).get("total_credits")
            if tc is not None:
                return _num(tc)
    return None


def fetch_balance(token, uid, known_total=None):
    """查询总剩余积分并拼接文案。

    『总剩余积分』取自签到状态接口的 total_credits（与 WorkBuddy 客户端展示口径一致）；
    known_total 由 checkin_once 从已获取的 status 响应直接传入，避免重复请求。
    任何异常 / 无数据返回空串，不影响主流程。"""
    try:
        total = known_total if known_total is not None else _get_total_credits(token, uid)
    except Exception:
        return ""
    if total is None:
        return ""
    return f"- 总剩余积分：{_fmt(total)}"


def checkin_once(cred):
    """执行单次签到，返回 (结果标记, 通知文本)。不做重试：结果如实上报。"""
    cred = cred or {}
    token = cred.get("token", "")
    uid = cred.get("uid", "")

    if not token or not uid:
        return "NO_CREDENTIAL", ("未获取到 WorkBuddy 登录态，请设置环境变量 WB_ACCESS_TOKEN / WB_USER_ID"
                                 "（或运行 python workbuddy_checkin.py --export-env --save 刷新）")

    # 查询状态（仅参考，today_checked_in 不可靠）；同时取总剩余积分供余额展示
    sc, sb = _call(token, uid, STATUS_PATH)
    status_total = None
    if isinstance(sb, dict):
        status_total = (sb.get("data") or {}).get("total_credits")

    # 执行领取（幂等：code=10001 表示今日已签）
    cc, cb = _call(token, uid, CHECKIN_PATH)

    if cc == 0:
        content = f"⚠️ 网络异常，签到请求未发出：{json.dumps(cb, ensure_ascii=False)[:200]}"
        return "NET_ERR", content
    if isinstance(cb, dict):
        code = cb.get("code")
        if code == 0:
            d = cb.get("data", {})
            content = (f"✅ 领取成功\n- 本次积分：{d.get('credit')}\n"
                       f"- 连续签到：第 {d.get('streak_days')} 天")
            bal = fetch_balance(token, uid, known_total=status_total)
            if bal:
                content += f"\n{bal}"
            return "SUCCESS", content
        if code == 10001:
            content = "ℹ️ 今日已签到，无需重复领取"
            bal = fetch_balance(token, uid, known_total=status_total)
            if bal:
                content += f"\n{bal}"
            return "ALREADY_TODAY", content
        if cc in (401, 403):
            return "TOKEN_EXPIRED", f"⚠️ 令牌失效（HTTP {cc}），请打开 WorkBuddy 桌面端刷新登录态后重试"
        return "FAIL", f"⚠️ 签到未成功：HTTP {cc} code={code} msg={cb.get('msg')}"
    return "HTTP_ERR", f"⚠️ 请求异常（HTTP {cc}）：{json.dumps(cb, ensure_ascii=False)[:200]}"


def main():
    if "--export-env" in sys.argv:
        sys.exit(export_env())

    cred = resolve_credentials()
    flag, content = checkin_once(cred)
    print(f"RESULT={flag} | {content}")
    sendNotify.serverJMy("WorkBuddy 每日签到", content)


if __name__ == '__main__':
    main()
