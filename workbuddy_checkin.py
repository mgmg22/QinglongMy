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
基础对话（chat_once）：
    每次签到一起触发一条最基础的真实对话（固定模型 deepseek-v4.1-flash，
    POST /v2/chat/completions，SSE 流式）。请求会额外携带产品标识头：
        X-Product / X-IDE-Name / X-IDE-Type / X-IDE-Version / X-Product-Version / X-Domain
    不带这套头时，服务端不把该请求归属到客户端，控制台「积分消耗明细」的
    「使用端」列会显示「-」（认不出来）；带上后即显示 WorkBuddy。
==============================================================================
成长中心（派猫旅行 / 开盲盒）：
    每次运行都会在签到后顺带执行成长中心可 API 化部分（派猫旅行往返、开盲盒），
    不会自动完成成长计划任务本体，也不会去领任务奖励。无独立子命令，固定一起跑：
        python workbuddy_checkin.py            # 签到 + 基础对话 + 成长中心
    若成长中心接口需要按产品路由，可设置环境变量 WB_DOMAIN（取自本机登录态
    auth.domain，如 www.workbuddy.cn）；留空通常亦可命中默认产品。
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
# 用户资源包余额接口（与客户端『总剩余积分』同口径）。
# 注意：该接口走无 /v2 前缀的新网关，且必须带 IDE 标识头，否则返回 10085 请求不合法。
RESOURCE_SUMMARY_PATH = "/billing/meter/get-user-resource-summary"
RESOURCE_HEADERS = {
    "X-Product": "WorkBuddy",
    "X-IDE-Name": "WorkBuddy",
    "User-Agent": "WorkBuddy/5.3.8",
}

# ---------------------------------------------------------------------------
# 成长中心（派猫旅行 + 开盲盒）——仅做可 API 化的部分，不自动完成成长计划任务
# 接口基准：{API_BASE}/v2/activity/growth
# 端点参考已验证实现：gitee.com/SJAY/workbuddy-trae-auto-signin（copilot.tencent.com + Bearer）
# ---------------------------------------------------------------------------
GROWTH_BASE = "/v2/activity/growth"
TRAVEL_STATUS = GROWTH_BASE + "/buddy/travel/status"
TRAVEL_CONFIG = GROWTH_BASE + "/buddy/travel/config"
TRAVEL_DEPART = GROWTH_BASE + "/buddy/travel/depart"
TRAVEL_CLAIM = GROWTH_BASE + "/buddy/travel/claim"
LOTTERY_CHANCES = GROWTH_BASE + "/lottery/chances"
LOTTERY_DRAW = GROWTH_BASE + "/lottery/draw"

# ---------------------------------------------------------------------------
# 基础对话：每次签到触发一次最基础真实对话（不读取/不修改任何成长计划任务）
# 端点与签到同域名同鉴权；模型固定 deepseek-v4.1-flash；必须 stream:true（SSE）
# 仅用于发起一次真实对话，与成长计划任务本体无关
# ---------------------------------------------------------------------------
CHAT_PATH = "/v2/chat/completions"
CHAT_MODEL = "deepseek-v4.1-flash"
# 客户端版本：与登录态 auth 客户端版本保持一致，用于标识控制台「使用端」列
CHAT_CLIENT_VERSION = "5.3.8"
ENERGY = GROWTH_BASE + "/energy"
# 开盲盒每次固定消耗的能量值（官方规则：每攒够 10 点能量可开启一次盲盒）
BLINDBOX_ENERGY_COST = 10


def _unwrap(body):
    """剥掉 data 信封：{code, data:{...}} -> {...}；非信封原样返回。"""
    if isinstance(body, dict):
        d = body.get("data")
        if isinstance(d, dict):
            return d
    return body


def _ok(sc, sb):
    """HTTP 2xx 且业务 code 非错误（缺失/0 视为成功）。"""
    if not (200 <= sc < 300):
        return False
    if isinstance(sb, dict) and sb.get("code") not in (None, 0):
        return False
    return True

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


def _call(token, uid, path, extra_headers=None, payload=None, method="POST"):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "X-User-Id": uid,
    }
    # 成长中心接口可能按 X-Domain 路由到对应产品（取自本机登录态 auth.domain）。
    # 仅当显式设置 WB_DOMAIN 时附加，不强制；留空通常仍可命中默认产品。
    domain = (os.environ.get("WB_DOMAIN", "") or "").strip()
    if domain:
        headers["X-Domain"] = domain
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps(payload) if payload is not None else "{}"
    try:
        if method and method.upper() == "GET":
            r = requests.get(API_BASE + path, headers=headers, timeout=15)
        else:
            r = requests.post(API_BASE + path, headers=headers, data=body, timeout=15)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text}
    except Exception as e:
        return 0, {"error": str(e)}


def _fmt_credits(v):
    """余额按客户端口径展示：千分位 + 2 位小数（如 1,798.89）。"""
    return f"{v:,.2f}"


def _get_resource_packages(token, uid):
    """查询用户资源包明细（与客户端『总剩余积分』同口径）。

    返回 list[dict]（每条含 CycleRemainCapacity / CycleTotalCapacity 等），
    失败 / 无数据 / 接口异常返回 None。"""
    try:
        sc, sb = _call(token, uid, RESOURCE_SUMMARY_PATH, extra_headers=RESOURCE_HEADERS)
    except Exception:
        return None
    if not isinstance(sb, dict) or sb.get("code") != 0:
        return None
    data = sb.get("data") or {}
    pkgs = data.get("Packages")
    if not isinstance(pkgs, list):
        return None
    return pkgs


def _sum_remaining_credits(pkgs):
    """各资源包 CycleRemainCapacity 的正数之和 = 『总剩余积分』。

    对应客户端 sumSummaryCapacity 的 left（只累加 >0 的剩余）。返回 float 或 None。"""
    if not isinstance(pkgs, list):
        return None
    try:
        total = sum(max(0.0, float(p.get("CycleRemainCapacity", 0) or 0)) for p in pkgs)
    except (TypeError, ValueError):
        return None
    return total


def fetch_balance(token, uid, known_total=None):
    """查询总剩余积分并拼接文案。

    口径以 /billing/meter/get-user-resource-summary 为准——该接口返回的资源包
    CycleRemainCapacity 之和，即客户端『总剩余积分』（含套餐基础 / 平台奖励 / 加量包等全部）。
    旧的 checkin-activity-status 的 total_credits 只是当期签到活动积分（如 1500），
    并非真实余额，不能当作『总剩余积分』。
    查询异常 / 无数据时返回空串，避免展示错误数字（不再回退到活动积分）。
    """
    try:
        pkgs = _get_resource_packages(token, uid)
    except Exception:
        pkgs = None
    if pkgs is not None:
        total = _sum_remaining_credits(pkgs)
        if total is not None:
            return f"- 总剩余积分：{_fmt_credits(total)}"
    return ""


def checkin_once(cred):
    """执行单次签到，返回 (结果标记, 通知文本)。不做重试：结果如实上报。"""
    cred = cred or {}
    token = cred.get("token", "")
    uid = cred.get("uid", "")

    if not token or not uid:
        return "NO_CREDENTIAL", ("未获取到 WorkBuddy 登录态，请设置环境变量 WB_ACCESS_TOKEN / WB_USER_ID"
                                 "（或运行 python workbuddy_checkin.py --export-env --save 刷新）")

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
            bal = fetch_balance(token, uid)
            if bal:
                content += f"\n{bal}"
            return "SUCCESS", content
        if code == 10001:
            content = "ℹ️ 今日已签到，无需重复领取"
            bal = fetch_balance(token, uid)
            if bal:
                content += f"\n{bal}"
            return "ALREADY_TODAY", content
        if cc in (401, 403):
            return "TOKEN_EXPIRED", f"⚠️ 令牌失效（HTTP {cc}），请打开 WorkBuddy 桌面端刷新登录态后重试"
        return "FAIL", f"⚠️ 签到未成功：HTTP {cc} code={code} msg={cb.get('msg')}"
    return "HTTP_ERR", f"⚠️ 请求异常（HTTP {cc}）：{json.dumps(cb, ensure_ascii=False)[:200]}"


def buddy_travel(token, uid):
    """派猫旅行状态机：arrived→领奖；idle→派出发；traveling→跳过。
    返回 (人话汇报, 数据) 元组。动作由服务端状态驱动，天然幂等，重复运行不会重复领/派。"""
    sc, sb = _call(token, uid, TRAVEL_STATUS, method="GET")
    if not _ok(sc, sb):
        return f"查询旅行状态失败（HTTP {sc}）", None
    data = _unwrap(sb)
    state = data.get("state")
    parts = []

    if state == "arrived":
        record_id = data.get("record_id")
        cc, cb = _call(token, uid, TRAVEL_CLAIM, payload={"record_id": record_id})
        if _ok(cc, cb):
            reward = _unwrap(cb).get("reward_credit")
            parts.append(f"领旅行礼物 +{reward} 积分" if reward is not None else "领旅行礼物成功")
        else:
            parts.append(f"领旅行礼物失败（HTTP {cc}）")
        state = "idle"  # 领完回到 idle，下方再派一程

    if state == "idle":
        # 服务端标记今日派猫额度已用完时，depart 会返回 400 daily limit reached，属正常幂等态
        if data.get("daily_limit_reached"):
            parts.append("今日派猫额度已用完")
        else:
            cc, cb = _call(token, uid, TRAVEL_CONFIG, method="GET")
            locs = _unwrap(cb).get("locations") if _ok(cc, cb) else None
            if isinstance(locs, list) and locs:
                loc = locs[0]
                dc, db = _call(token, uid, TRAVEL_DEPART, payload={"location_id": loc.get("id")})
                if _ok(dc, db):
                    loc_name = (_unwrap(db).get("location") or {}).get("name", "?")
                    parts.append(f"派 Buddy 去{loc_name}")
                else:
                    parts.append(f"派 Buddy 失败（HTTP {dc}）")
            else:
                parts.append("无可用旅行地点")
    elif state == "traveling":
        loc_name = (data.get("location") or {}).get("name", "?")
        parts.append(f"Buddy 旅行中（{loc_name}）")

    return ("；".join(parts) if parts else "旅行无变动"), data


def open_blindbox(token, uid):
    """开盲盒：查询可抽次数（lottery/chances），能量足够（>=10）则抽一次。
    盲盒每次消耗 10 点能量，属于成长中心可 API 化部分，与『完成成长计划任务』无关。
    返回 (人话汇报, 剩余机会) 元组。能量不足或机会为 0 时不抽，避免无谓报错。"""
    sc, sb = _call(token, uid, LOTTERY_CHANCES, method="GET")
    if not _ok(sc, sb):
        return f"查询盲盒机会失败（HTTP {sc}）", None
    chances = _unwrap(sb).get("balance")
    if not isinstance(chances, int) or chances <= 0:
        return "暂无可开盲盒机会", chances
    # 开盲盒每次固定消耗 10 点能量；能量不足时接口返回 400 invalid request，属前端约束
    es, eb = _call(token, uid, ENERGY, method="GET")
    energy = _unwrap(eb).get("balance") if _ok(es, eb) else None
    if isinstance(energy, int) and energy < BLINDBOX_ENERGY_COST:
        return f"能量不足（当前{energy}/{BLINDBOX_ENERGY_COST}）", chances
    dc, db = _call(token, uid, LOTTERY_DRAW, payload={})
    if _ok(dc, db):
        prize = _unwrap(db).get("prize_name") or _unwrap(db).get("prize") or "未知奖励"
        return f"开盲盒获得：{prize}", max(0, chances - 1)
    return f"开盲盒失败（HTTP {dc}，能量{energy}）", chances


def run_growth(token, uid):
    """成长中心编排：派猫旅行 + 开盲盒。不含任务领奖（避免自动刷满成长计划）。"""
    if not token or not uid:
        return "未配置 WB_ACCESS_TOKEN / WB_USER_ID，跳过成长中心"
    parts = []
    t, _ = buddy_travel(token, uid)
    if t:
        parts.append(t)
    b, _ = open_blindbox(token, uid)
    if b:
        parts.append("盲盒：" + b)
    return "；".join(parts) if parts else "成长中心无可执行项"


def _parse_sse_content(raw):
    """从 SSE 原始响应中拼接所有 delta.content（遇 [DONE] 即止）。"""
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if isinstance(obj, dict):
            choices = obj.get("choices") or []
            if choices:
                c = (choices[0].get("delta") or {}).get("content")
                if c:
                    out.append(c)
    return "".join(out)


def chat_once(token, uid, prompt=None):
    """发起一次最基础的真实对话（固定模型 deepseek-v4.1-flash，SSE 流式）。
    目的仅为发起一句话真实对话，不读取/不修改任何成长计划任务。
    默认发送「你好」，回执固定为「已发起对话」（不含模型回复内容）。
    返回 (状态汇报, 回复文本)。"""
    if prompt is None or not str(prompt).strip():
        prompt = "你好"
    prompt = str(prompt).strip()
    # 请求体只含标准 OpenAI 字段；控制台「使用端」列由下列产品标识头决定，
    # 缺失时该列显示「-」，带上后显示 WorkBuddy（详见顶部说明）。
    body = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Authorization": f"Bearer {token}",
        "X-User-Id": uid,
        "X-Product": "WorkBuddy",
        "X-IDE-Name": "WorkBuddy",
        "X-IDE-Type": "WorkBuddy",
        "X-IDE-Version": CHAT_CLIENT_VERSION,
        "X-Product-Version": CHAT_CLIENT_VERSION,
        "X-Domain": "www.workbuddy.cn",
        "User-Agent": f"WorkBuddyIDE/{CHAT_CLIENT_VERSION} WorkBuddy/{CHAT_CLIENT_VERSION}",
    }
    try:
        r = requests.post(API_BASE + CHAT_PATH, headers=headers,
                          data=json.dumps(body), stream=True, timeout=60)
        if r.status_code != 200:
            return f"对话请求失败（HTTP {r.status_code}）：{r.text[:120]}", None
        text = _parse_sse_content(r.content.decode("utf-8", "replace"))
        if not text:
            return "对话已发送，但未解析到回复内容", None
        return "已发起对话", text
    except Exception as e:
        return f"对话请求异常：{str(e)[:160]}", None


def run_full(cred):
    """完整运行：每日签到 + 基础真实对话 + 成长中心（派猫旅行 / 开盲盒）。
    返回 (flag, content)，content 为三部分合并文本。供单独运行与 checkin_all
    聚合脚本共用，确保无论哪种入口都执行同样的全量流程（含派猫/盲盒/对话）。
    对话与成长中心仅在凭据齐全时执行；任一部分失败不影响其余部分如实汇总。"""
    cred = cred or {}
    token, uid = cred.get("token", ""), cred.get("uid", "")
    flag, content = checkin_once(cred)
    if token and uid:
        ch, _ = chat_once(token, uid)
        content = content + "\n" + ch
        gr = run_growth(token, uid)
        content = content + "\n" + gr
    return flag, content


def main():
    if "--export-env" in sys.argv:
        sys.exit(export_env())

    cred = resolve_credentials()
    flag, content = run_full(cred)
    print(f"RESULT={flag} | {content}")
    sendNotify.serverJMy("WorkBuddy 每日签到", content)


if __name__ == '__main__':
    main()
