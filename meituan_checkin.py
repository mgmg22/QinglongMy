#!/bin/env python3
# -*- coding: utf-8 -*
"""
# cron: 55 10 * * * meituan_checkin.py
# new Env('美团每日领券');

================== 美团每日自动领券 ==================
发券接口：POST https://media.meituan.com/fulishemini/couponActivity/sendCouponWork
鉴权方式：把用户 Token 放进请求体（无需 Cookie / Session）。

环境变量（推荐，脚本默认且唯一读取来源）：
    MT_TOKEN        用户登录 Token（必填，放进请求体）
    MT_AISCENE      场景标识（可选）
    MT_CLIENT_ID    客户端 id（可选，留空则用内置稳定默认值）

说明：
    - 脚本【默认只读取上述环境变量】；缺失 MT_TOKEN 时 checkin 阶段判为 NO_CREDENTIAL。
    - 兼容 Node 端 run.js 已扫码登录的情况：当 MT_TOKEN 未设置时，脚本回退读取
      本机 pt-passport 缓存（~/.workbuddy/credentials/.../pt_passport_auth.json）
      与插件 config.json 的 aiScene；部署到青龙 / 容器时请直接设置环境变量。
    - 本地每日缓存 meituan_today_cache.json 做每日去重，避免重复打接口。
    - 美团 token 由 Node 端 run.js 扫码登录获得（无自动续期）；获得后填入 MT_TOKEN。
      `--export-env`（配合 --save 可写回 .env）可从本机缓存导出 token。

刷新 token：`python meituan_checkin.py --export-env --save`
            （要求本机已用 Node 端 run.js 扫码登录，写入 pt_passport_auth.json）
=====================================================
"""

import os
import re
import sys
import json
import datetime
import requests
import sendNotify

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# 内置稳定默认 client_id（与 Node run.js 一致）
DEFAULT_CLIENT_ID = "c6f50b5a1e2f4e2bb00a3e2f58df3ced"
COUPON_URL = "https://media.meituan.com/fulishemini/couponActivity/sendCouponWork"
HOME = os.path.expanduser("~")
AUTH_DIR = os.path.join(HOME, ".workbuddy", "credentials", "meituan-living-deals-assistant")
PT_PASSPORT_AUTH = os.path.join(AUTH_DIR, "pt_passport_auth.json")
CONFIG_CANDIDATES = [
    os.path.join(HOME, ".workbuddy", "plugins", "marketplaces", "experts",
                 "plugins", "meituan-living-assistant", "scripts", "config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
]
# 本地每日缓存（与脚本同目录，青龙可读写）
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meituan_today_cache.json")

_TAB_ORDER = ["外卖", "美食团购", "美团闪购", "休闲娱乐", "生活服务", "丽人医疗", "更多福利"]
_TAB_DISPLAY = {"更多福利": "其他"}
_SLOT_PLAN_BASE = [["外卖", 2], ["美食团购", 1], ["美团闪购", 1],
                   ["休闲娱乐", 1], ["生活服务", 1], ["丽人医疗", 1]]


def _clean(v):
    """去除首尾空白与配对引号（对齐其它签到脚本的健壮性处理）。"""
    if not v:
        return ""
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1]
    return v.strip()


def load_ai_scene():
    if os.environ.get("MT_AISCENE"):
        return _clean(os.environ["MT_AISCENE"])
    for p in CONFIG_CANDIDATES:
        if os.path.exists(p):
            try:
                return json.load(open(p, encoding="utf-8")).get("aiScene", "")
            except Exception:
                pass
    return ""


def get_cached_token():
    """优先环境变量 MT_TOKEN；缺失时回退本机 pt-passport 缓存。"""
    if os.environ.get("MT_TOKEN"):
        return _clean(os.environ["MT_TOKEN"])
    if not os.path.exists(PT_PASSPORT_AUTH):
        return None
    try:
        data = json.load(open(PT_PASSPORT_AUTH, encoding="utf-8"))
        cid = _clean(os.environ.get("MT_CLIENT_ID") or DEFAULT_CLIENT_ID)
        return data.get(cid + "@prod", {}).get("token")
    except Exception:
        return None


def fen_to_yuan(fen):
    if not fen:
        return "0"
    yuan = int(fen) / 100
    return str(int(yuan)) if yuan == int(yuan) else ("%.1f" % yuan)


def format_ts_ms(ts_ms):
    if not ts_ms:
        return "-"
    try:
        d = datetime.datetime.fromtimestamp(int(ts_ms) / 1000)
        return d.strftime("%Y-%m-%d")
    except Exception:
        return str(ts_ms)


def format_coupon(c):
    price_limit = c.get("priceLimit")
    coupon_value = c.get("couponValue") or 0
    discount_info = ""
    if price_limit and price_limit > 0:
        discount_info = "满%s元减%s元" % (fen_to_yuan(price_limit), fen_to_yuan(coupon_value))
    start, end = c.get("couponStartTime"), c.get("couponEndTime")
    valid_period = (format_ts_ms(start) + " 至 " + format_ts_ms(end)) if (start and end) else ""
    return {
        "name": c.get("couponName", ""),
        "discount_info": discount_info,
        "valid_period": valid_period,
        "priceLimit": price_limit,
        "couponValue": coupon_value,
        "tabName": c.get("tabName", ""),
    }


def build_count_str(coupons):
    tab_count = {}
    for c in coupons:
        t = c.get("tabName", "")
        tab_count[t] = tab_count.get(t, 0) + 1
    unknown = [t for t in tab_count if t not in _TAB_ORDER]
    order = _TAB_ORDER[:6] + unknown + _TAB_ORDER[6:]
    parts = []
    for t in order:
        if not tab_count.get(t):
            continue
        name = _TAB_DISPLAY.get(t, t)
        parts.append("%s优惠券%d张" % (name, tab_count[t]))
    return "、".join(parts)


def build_display_coupons(coupons):
    def sort_key(c):
        pl = c.get("priceLimit")
        if not pl:
            return [0, 0]
        return [1, -(c.get("couponValue", 0) / pl)]

    groups = {}
    for c in coupons:
        groups.setdefault(c.get("tabName", ""), []).append(c)
    for t in groups:
        groups[t].sort(key=sort_key)

    unknown = [t for t in groups if t not in _TAB_ORDER]
    slot_plan = _SLOT_PLAN_BASE + [[t, 1] for t in unknown] + [["更多福利", 1]]

    used = {}
    slots = []
    for tab, quota in slot_plan:
        if len(slots) >= 8:
            break
        grp = groups.get(tab, [])
        taken = 0
        for c in grp:
            if taken >= quota or len(slots) >= 8:
                break
            slots.append(c)
            used[tab] = used.get(tab, 0) + 1
            taken += 1

    fallback = ["外卖", "美食团购", "美团闪购", "休闲娱乐", "生活服务", "丽人医疗"] + unknown + ["更多福利"]
    while len(slots) < 8:
        filled = False
        for t in fallback:
            remaining = groups.get(t, [])[used.get(t, 0):]
            if remaining:
                slots.append(remaining[0])
                used[t] = used.get(t, 0) + 1
                filled = True
                break
        if not filled:
            break
    return slots


def build_display_result(coupons):
    return {"count_str": build_count_str(coupons),
            "display_coupons": build_display_coupons(coupons)}


def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")


def load_today_cache():
    try:
        if not os.path.exists(CACHE_PATH):
            return None
        cache = json.load(open(CACHE_PATH, encoding="utf-8"))
        if cache.get("date") == today_str():
            return cache.get("data")
    except Exception:
        return None
    return None


def save_today_cache(data):
    try:
        os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
        json.dump({"date": today_str(), "data": data},
                  open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def resolve_credentials():
    """仅读取环境变量，返回凭据 dict。缺失 MT_TOKEN 时返回空 token。"""
    return {
        "token": _clean(os.environ.get("MT_TOKEN", "")),
        "ai_scene": _clean(os.environ.get("MT_AISCENE", "")),
        "client_id": _clean(os.environ.get("MT_CLIENT_ID", "")) or DEFAULT_CLIENT_ID,
    }


def read_local_credential():
    """从本机 pt-passport 缓存读取 token + client_id（仅 --export-env 使用）。"""
    token = get_cached_token()
    if not token:
        return None
    cid = _clean(os.environ.get("MT_CLIENT_ID") or DEFAULT_CLIENT_ID)
    return {"token": token, "client_id": cid, "ai_scene": load_ai_scene()}


def _save_env_values(values):
    """把导出的环境变量写回同目录 .env（仅更新/追加给定 key，保留其它内容）。"""
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


def export_env():
    """--export-env：读取本机登录态并打印/保存环境变量。"""
    c = read_local_credential()
    if not c:
        print("未发现美团登录态，请先在本机用 Node 端 run.js 扫码登录（写入 pt_passport_auth.json）")
        return 1
    values = {
        "MT_TOKEN": c["token"],
        "MT_CLIENT_ID": c["client_id"],
    }
    if c.get("ai_scene"):
        values["MT_AISCENE"] = c["ai_scene"]
    for k, v in values.items():
        print(f"{k}={v}")
    if "--save" in sys.argv:
        n = _save_env_values(values)
        if n:
            print(f"# 已将上述 {n} 个变量写回 .env")
    return 0


def _call(token, ai_scene, client_id):
    """POST 发券接口，返回 (http_code, json_or_raw)。"""
    body = json.dumps({"token": token, "aiScene": ai_scene, "version": 2}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    }
    try:
        r = requests.post(COUPON_URL, data=body, headers=headers, timeout=15)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text}
    except Exception as e:
        return 0, {"error": str(e)}


def checkin_once(cred):
    """执行单次领券，返回 (结果标记, 通知文本)。结果如实上报，不做重试。"""
    cred = cred or {}

    # 优先环境变量；缺失时回退本机 pt-passport 缓存
    token = cred.get("token", "") or get_cached_token() or ""
    ai_scene = cred.get("ai_scene", "") or load_ai_scene() or ""
    client_id = cred.get("client_id", "") or DEFAULT_CLIENT_ID

    if not token:
        return "NO_CREDENTIAL", ("未获取到美团登录 Token，请设置环境变量 MT_TOKEN"
                                 "（或先在本机用 Node 端 run.js 扫码登录后执行 "
                                 "python meituan_checkin.py --export-env --save 刷新）")

    # 本地每日缓存命中 -> 视为今日已领
    cached = load_today_cache()
    if cached:
        cc = cached.get("coupon_count", 0)
        cs = cached.get("count_str", "")
        content = (f"ℹ️ 今天已领取过美团优惠券\n- 共 {cc} 张（{cs}）\n"
                   f"- 活动：{cached.get('activity_name', '')}")
        return "ALREADY_TODAY", content

    code, resp = _call(token, ai_scene, client_id)

    if code == 0:
        content = f"⚠️ 网络异常，领券请求未发出：{json.dumps(resp, ensure_ascii=False)[:200]}"
        return "NET_ERR", content

    if not isinstance(resp, dict):
        return "HTTP_ERR", f"⚠️ 请求异常（HTTP {code}）：{str(resp)[:200]}"

    c = resp.get("code")
    data = resp.get("data") or {}

    if c == 200:
        coupon_list = data.get("couponList") or []
        formatted = [format_coupon(x) for x in coupon_list]
        display = build_display_result(formatted)
        result = {
            "coupon_count": len(formatted),
            "coupons": formatted,
            "count_str": display["count_str"],
            "display_coupons": display["display_coupons"],
            "activity_name": data.get("activityName", ""),
            "activity_link": data.get("activityLink", ""),
        }
        save_today_cache(result)
        lines = [f"✅ 美团领券成功，共 {len(formatted)} 张"]
        if display["count_str"]:
            lines.append(f"- 分类：{display['count_str']}")
        for c0 in display["display_coupons"][:8]:
            extra = f"（{c0['discount_info']}）" if c0["discount_info"] else ""
            lines.append(f"- {c0['tabName']}：{c0['name']}{extra}")
        if data.get("activityName"):
            lines.append(f"- 活动：{data.get('activityName')}")
        return "SUCCESS", "\n".join(lines)

    if c == 1014:
        return "ALREADY_TODAY", "ℹ️ 您今天已经领取过美团的优惠券，每天只能领取一次，明天再来哦～"

    if c in (401,):
        return "TOKEN_EXPIRED", "⚠️ 登录已过期，请重新扫码登录后更新环境变量 MT_TOKEN"

    if c in (509, 50200):
        return "RATE_LIMITED", "⏳ 请求过于频繁（限流），请稍后重试"

    return "FAIL", f"⚠️ 领券未成功：HTTP {code} code={c} msg={resp.get('msg')}"


def main():
    if "--export-env" in sys.argv:
        sys.exit(export_env())

    cred = resolve_credentials()
    flag, content = checkin_once(cred)
    print(f"RESULT={flag} | {content}")
    sendNotify.serverJMy("美团每日领券", content)


if __name__ == "__main__":
    main()
