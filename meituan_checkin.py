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
    - 兼容本机已扫码登录的情况：当 MT_TOKEN 未设置时，脚本回退读取
      本机 pt-passport 缓存（~/.workbuddy/credentials/.../pt_passport_auth.json）
      与插件 config.json 的 aiScene；部署到青龙 / 容器时请直接设置环境变量。
    - 本地每日缓存 meituan_today_cache.json 做每日去重，避免重复打接口。
    - 美团 token 由 pt-passport 扫码登录获得（无自动续期）。本脚本内置
      `login` 命令，可用 Python 端直接触发重新扫码（底层仍调用同款 pt-passport 的
      Node 实现，二维码展示/轮询/写 env 均为 Python），无需切回 Node run.js：
        python meituan_checkin.py login            # 交互扫码，打印 MT_TOKEN 等
        python meituan_checkin.py login --save     # 扫码后写回同目录 .env
        python meituan_checkin.py --export-env --login --save
                                                     # 无缓存时先扫码再导出并保存
      登录态统一写入 ~/.workbuddy/credentials/.../pt_passport_auth.json，
      与插件扫码登录共用；也可把 token 直接填进环境变量 MT_TOKEN 部署到青龙。

用法小结：
    python meituan_checkin.py                 # 领券（默认）
    python meituan_checkin.py login [--save] # Python 端重新扫码
    python meituan_checkin.py --export-env [--login] [--save]
=====================================================
"""

import os
import re
import sys
import json
import time
import subprocess
import datetime
import urllib.request
import requests
import sendNotify

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# 内置稳定默认 client_id（与插件保持一致）
DEFAULT_CLIENT_ID = "c6f50b5a1e2f4e2bb00a3e2f58df3ced"
COUPON_URL = "https://media.meituan.com/fulishemini/couponActivity/sendCouponWork"
HOME = os.path.expanduser("~")
AUTH_DIR = os.path.join(HOME, ".workbuddy", "credentials", "meituan-living-deals-assistant")
PT_PASSPORT_AUTH = os.path.join(AUTH_DIR, "pt_passport_auth.json")
# 插件 scripts 目录（用于定位 pt-passport 的 Node 实现）
SCRIPTS_DIR = os.path.join(HOME, ".workbuddy", "plugins", "marketplaces", "experts",
                           "plugins", "meituan-living-assistant", "scripts")
CONFIG_CANDIDATES = [
    os.path.join(HOME, ".workbuddy", "plugins", "marketplaces", "experts",
                 "plugins", "meituan-living-assistant", "scripts", "config.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
]
# 本地每日缓存（与脚本同目录，青龙可读写）
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meituan_today_cache.json")

# ── Node / pt-passport 发现（用于 Python 端重新扫码登录） ──
# 说明：美团扫码登录的签名/OAuth 逻辑在 pt-passport（Node 实现，已混淆），
# 纯 Python 复刻不可行也不稳；因此「重新扫码」由 Python 编排该 CLI 完成，
# 但二维码展示、轮询、写 env 全部用 Python 实现。
def _find_node():
    if os.environ.get("MT_NODE_BIN"):
        return os.environ["MT_NODE_BIN"]
    for cand in [
        os.path.join(HOME, ".workbuddy", "binaries", "node", "versions", "22.22.2-2", "node.exe"),
        os.path.join(HOME, ".workbuddy", "binaries", "node", "versions", "22.22.2-2", "node"),
    ]:
        if os.path.exists(cand):
            return cand
    return "node"  # 回退 PATH


def _find_pt_passport_js():
    if os.environ.get("MT_PT_PASSPORT_BIN"):
        return os.environ["MT_PT_PASSPORT_BIN"]
    return os.path.join(SCRIPTS_DIR, "node_modules", "@mtuser", "pt-passport", "dist", "index.js")


NODE_BIN = _find_node()
PT_PASSPORT_JS = _find_pt_passport_js()

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


def _run_passport(args, timeout=600):
    """调用 pt-passport CLI，返回 (exit_code, stdout)。
    登录态统一写入 PT_PASSPORT_AUTH_FILE，与插件扫码登录共用。"""
    if not os.path.exists(PT_PASSPORT_JS):
        return (-1, "")
    env = dict(os.environ)
    env["HOME"] = HOME
    env["PT_PASSPORT_AUTH_FILE"] = PT_PASSPORT_AUTH
    env.pop("NODE_OPTIONS", None)
    try:
        p = subprocess.run(
            [NODE_BIN, PT_PASSPORT_JS] + list(args),
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        return (p.returncode, (p.stdout or "").strip())
    except Exception as e:  # noqa
        return (-2, str(e))


def _qr_image_url(url):
    """调用美团服务端接口换取可扫描的二维码图片 URL（对应 run.js qrcode 命令）。"""
    api = "https://click.meituan.com/cps/ai/product/getQrCodeImage"
    body = json.dumps({"originalUrl": url, "clientSource": "coupon-fusion-workbuddy"}).encode("utf-8")
    req = urllib.request.Request(api, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        return data.get("data") if isinstance(data, dict) else None
    except Exception:
        return None


def login_flow(env="prod", max_wait=300):
    """重新扫码登录（Python 端）：get-code -> 展示二维码 -> poll-token 阻塞等待，直到拿到 Token。
    成功后会写入 pt_passport_auth.json（与插件共用同一份登录态），并返回凭据 dict；
    失败（如超时未扫码）返回 None。"""
    cid = _clean(os.environ.get("MT_CLIENT_ID") or DEFAULT_CLIENT_ID)
    env_flag = ["--env", env] if env == "test" else []
    print("▶ 正在生成美团登录二维码 ...")
    code, out = _run_passport(["auth", "get-code", "--client_id", cid] + env_flag)
    token = None
    m = re.search(r"Token:\s*(\S+)", out)
    if m:
        token = m.group(1).strip()
    link = None
    lm = re.search(r"AUTH_LINK:\s*(\S+)", out)
    if lm:
        link = lm.group(1).strip()

    if not token and link:
        print("🔗 请扫码登录（打开链接或扫描下方二维码）：")
        print("   %s" % link)
        qrimg = _qr_image_url(link)
        if qrimg:
            print("   二维码图片：%s" % qrimg)
        try:  # 可选：本地生成 PNG（需 pip install qrcode）
            import qrcode  # type: ignore
            png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meituan_login_qr.png")
            qrcode.make(link).save(png)
            print("   本地二维码已保存：%s" % png)
        except Exception:
            pass
        print("⏳ 等待扫码确认（最多 %d 秒）..." % max_wait)
        # pt-passport 的 poll-token 为阻塞式（内部轮询扫码结果），单次调用即可，
        # 不要反复中断它；超时后再用下方兜底逻辑判断是否需重新 get-code。
        code, out = _run_passport(["auth", "poll-token", "--client_id", cid], timeout=max_wait)
        tm = re.search(r"Token:\s*(\S+)", out or "")
        if tm:
            token = tm.group(1).strip()
        # 兜底：poll 失败（后端竞态：用户已扫码成功但 poll 会话已关闭）时，
        # 再 get-code 确认是否已拿到 token（与 run.js 行为一致）
        if not token and (code != 0 or "❌" in (out or "")):
            fc, fout = _run_passport(["auth", "get-code", "--client_id", cid] + env_flag)
            fm = re.search(r"Token:\s*(\S+)", fout or "")
            if fm:
                token = fm.group(1).strip()

    if not token:
        print("❌ 未能获取登录 Token，请确认已扫码并完成授权；可重试：python meituan_checkin.py login")
        return None
    print("✅ 登录成功，Token 已写入本地缓存（pt_passport_auth.json）。")
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
    """--export-env：读取本机登录态并打印/保存环境变量。
    若本机无登录态且带了 --login，则先触发 Python 端扫码登录再导出。"""
    if "--login" in sys.argv and not read_local_credential():
        print("未发现美团登录态，尝试用 Python 端重新扫码登录 ...")
        login_flow()
    c = read_local_credential()
    if not c:
        print("未发现美团登录态，请先扫码登录：")
        print("  python meituan_checkin.py login            # Python 端交互扫码")
        print("  python meituan_checkin.py login --save     # 扫码后写回同目录 .env")
        print("  python meituan_checkin.py --export-env --login --save  # 无缓存时先扫码再导出")
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
                                 "，或先扫码登录：python meituan_checkin.py login [--save]"
                                 "，再执行 python meituan_checkin.py --export-env --save 刷新")

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
        return "TOKEN_EXPIRED", ("⚠️ 登录已过期，请用 Python 端重新扫码登录并刷新："
                                 "python meituan_checkin.py login --save")

    if c in (509, 50200):
        return "RATE_LIMITED", "⏳ 请求过于频繁（限流），请稍后重试"

    return "FAIL", f"⚠️ 领券未成功：HTTP {code} code={c} msg={resp.get('msg')}"


def main():
    if "login" in sys.argv:
        c = login_flow()
        if not c:
            sys.exit(1)
        vals = {"MT_TOKEN": c["token"], "MT_CLIENT_ID": c["client_id"]}
        if c.get("ai_scene"):
            vals["MT_AISCENE"] = c["ai_scene"]
        for k, v in vals.items():
            print(f"{k}={v}")
        if "--save" in sys.argv:
            if _save_env_values(vals):
                print("# 已将上述变量写回 .env")
        sys.exit(0)

    if "--export-env" in sys.argv:
        sys.exit(export_env())

    cred = resolve_credentials()
    flag, content = checkin_once(cred)
    print(f"RESULT={flag} | {content}")
    sendNotify.serverJMy("美团每日领券", content)


if __name__ == "__main__":
    main()
