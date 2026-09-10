#!/bin/env python3
# -*- coding: utf-8 -*
"""
# cron: 33 0 * * * minimax_checkin.py
# new Env('MiniMax Code 每日签到');

==================== MiniMax Code 自动签到 ====================

相关端点（逆向自 MiniMax Code 桌面端 app.asar + 本机 api-*.log 实测）：
    续期登录  {host}/v1/api/user/renewal               (POST, body {}) -> {"data":{"token":"新JWT"}}
    状态查询  {host}/minimax-cloud/api/v1/signin/status (GET)
    领取积分  {host}/minimax-cloud/api/v1/signin/claim  (POST, body {})

【先续期再签到（本次核心优化）】
桌面端每次启动都会调 /v1/api/user/renewal 用旧 token 换新 token（新 token 有效期
顺延 ~40 天）。本脚本把这一步搬进签到流程：**每次运行先续期，再拿新 token 签到**，
并把新 token 写回同目录缓存文件 .minimax_token.json（青龙环境里环境变量改不动，
但脚本目录可写，缓存能让 token 一直保持新鲜，永不续期失败）。

流程：
    env token ──(有效?)──> renewal ──> 新 token ──> 写回缓存/.env ──> status ──> claim
                              │
                              └─ 401/异常 ──> 回落到缓存 token 再试一次 ──> 仍失败则如实上报

【为什么服务器上会 401（本地实测结论）】
    * 正常 token          -> HTTP 200
    * 空 / 截断 / 带引号  -> HTTP 401 且响应体为空（与服务器上报的现象完全一致）
    * x-timestamp 拨快拨慢 24 小时 -> 仍 200（说明**不是**签名/时钟问题）
    * renewal 用非法 token -> HTTP 401 {"statusInfo":{"code":1000021,"msg":"异常用户访问"}}
因此 401 基本只可能是 **token 本身不对**（过期/被截断/粘贴时带引号/串号），
本脚本会在失败信息里直接打印 token 剩余有效期与服务端原始报错，一眼可定位。

【签名机制（逆向 app.asar 结论）】
桌面端在 axios 请求拦截器中对每个请求计算两套签名头：

  (1) x-timestamp : 秒级时间戳 = floor(Date.parse(new Date())/1000)
  (2) x-signature : md5("{x_timestamp}I*7Cf%WZ#S&%1RlZJ&C2{body}")
                      —— GET 时 body 为空串 ""，POST/claim 时 body 为 "{}"
                      —— 已与抓包日志逐字节验证一致 ✅
  (3) yy          : md5( encodeURIComponent(hasSearchParamsPath)
                         + "_" + "{}"
                         + md5(String(time_ms)) + "ooui" )
                      —— hasSearchParamsPath = path + "?" + URLSearchParams(params)
                         params 为设备参数字典（见 DEVICE_PARAMS 顺序），末尾追加 client=desktop
                         time_ms 与 params.unix 取同一毫秒值
                         （该结构已在 app.asar 两处独立源码确认）

鉴权头： token: <本地 JWT>（HS256，存于 minimax-agent-config.json -> tokens.accessToken）
         —— 注意 token 仅出现在 HTTP 头，绝不进入签名用的 URL/yy 计算

【方式一 · 推荐：环境变量（脚本默认读取来源）】
在 .env 或运行环境中设置：
    MINIMAX_TOKEN=<tokens.accessToken>
    MINIMAX_USER_ID=<realUserID>
    MINIMAX_UUID=<设备 uuid，可选，留空则回落脚本内置稳定默认值>
    MINIMAX_DEVICE_ID=<数字设备 id，可选，留空则回落脚本内置稳定默认值>
脚本【默认只读取上述环境变量】，不再自动读取本机登录态，方便容器 / 跨机 / 青龙部署。
环境变量值会自动去除首尾空白与误粘贴的引号（青龙面板最常见的 401 元凶）。

【方式二 · 刷新 token：--export-env（仅本机、不进入默认运行链）】
token 过期时，在本机（已登录 MiniMax Agent 桌面端）执行：
    python minimax_checkin.py --export-env
会读取本机登录态、先续期再打印最新变量；追加 --save 可直接写回 .env：
    python minimax_checkin.py --export-env --save

【方式三 · 只续期：--renew（任意机器，只要当前 token 还有效）】
    python minimax_checkin.py --renew            # 续期并打印
    python minimax_checkin.py --renew --save     # 续期并写回 .env + 缓存
适合"本机 token 还有效、只想把服务器上的 token 换新的"场景。

本机登录态文件（仅供参考，不参与默认运行）：
    %APPDATA%\\MiniMax Agent\\minimax-agent-config.json  （键 tokens.accessToken）

依赖：pip install requests

声明：仅供学习与个人使用。MiniMax Code / MiniMax Agent 是 MiniMax 旗下产品，
本脚本与其无任何关联，使用产生的任何后果（账号风控、封禁等）由使用者自行承担。
============================================================================================
"""

import os
import sys
import json
import time
import hashlib
import re
import base64
import urllib.parse
from datetime import datetime, timezone
import sendNotify

import requests

# 内置零依赖 VLESS 代理（仅标准库，不依赖 xray/clash 等外部客户端）。
# 提供 VlessProxy（订阅/单链接 -> 本地 HTTP 代理）与 fetch_subscription。
from vless_proxy import VlessProxy, fetch_subscription

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 本地开发时自动加载同目录 .env；已设置的环境变量优先，不受影响。
# python-dotenv 为本项目依赖（见 requirements.txt），统一用官方库加载，不做自定义兜底。
from dotenv import load_dotenv

load_dotenv()


def _save_env_values(values: dict):
    """把导出的环境变量写回同目录 .env（仅更新/追加给定 key，保留其它内容）。
    仅 --export-env --save（本机开发者显式刷新 .env）时调用；自动续期不写 .env。
    返回写入的变量数（0 表示失败）。"""
    env_path = os.path.join(BASE_DIR, ".env")
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


# ===== 端点常量 =====
HOST = "https://agent.minimax.io"
RENEW_PATH = "/v1/api/user/renewal"  # 续期登录：旧 token 换新 token
STATUS_PATH = "/minimax-cloud/api/v1/signin/status"
CLAIM_PATH = "/minimax-cloud/api/v1/signin/claim"

# 续期得到的新 token 缓存（脚本同目录）。青龙改不动环境变量，但脚本目录可写，
# 靠这个缓存让 token 每次运行都滚动续期。
CACHE_FILE = os.path.join(BASE_DIR, ".minimax_token.json")

# 默认本机登录态配置文件（Windows，位于 %APPDATA%\MiniMax Agent\minimax-agent-config.json）
DEFAULT_CONFIG_REL = os.path.join("MiniMax Agent", "minimax-agent-config.json")

# 设备参数顺序严格对齐桌面端 mC() 构建顺序（影响 yy 签名）
DEVICE_PARAM_ORDER = [
    "device_platform", "biz_id", "app_id", "version_code", "unix",
    "timezone_offset", "is_desktop", "desktop_version", "sys_language",
    "lang", "uuid", "device_id", "os_name", "browser_name", "device_memory",
    "cpu_core_num", "browser_language", "browser_platform", "user_id",
    "op_ticket", "screen_width", "screen_height",
]


# ===== 签名工具 =====

def _md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def encode_uri_component(s: str) -> str:
    """忠实复刻 JavaScript 的 encodeURIComponent：
    仅放行 A-Z a-z 0-9 以及 - _ . ! ~ * ' ( )，其余按 %XX（大写）编码。"""
    return re.sub(
        r'([^A-Za-z0-9\-_.!~*\'()])',
        lambda m: '%%%02X' % ord(m.group(1)),
        s,
    )


def build_device_params(user_id: str, uuid_str: str, device_id: str) -> dict:
    """构建设备参数字典（严格保持 DEVICE_PARAM_ORDER 顺序）。"""
    now_ms = int(round(datetime.now(timezone.utc).timestamp() * 1000))
    values = {
        "device_platform": "web",
        "biz_id": "3",
        "app_id": "3001",
        "version_code": "22201",
        "unix": str(now_ms),
        "timezone_offset": "28800",
        "is_desktop": "1",
        "desktop_version": "",
        "sys_language": "en",
        "lang": "en",
        "uuid": uuid_str,
        "device_id": device_id,
        "os_name": "Windows",
        "browser_name": "Chrome",
        "device_memory": "16",
        "cpu_core_num": "4",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "user_id": str(user_id),
        "op_ticket": "undefined",
        "screen_width": "1536",
        "screen_height": "864",
    }
    return {k: values[k] for k in DEVICE_PARAM_ORDER}


def _sign_request(path: str, token: str, params: dict, method: str, body: dict):
    """对单个请求计算签名所需的 query 串、请求头与 body 串。返回 (url_query, headers, body_str)。"""
    now_ms = int(round(datetime.now(timezone.utc).timestamp() * 1000))
    now_sec = now_ms // 1000

    # 设备参数里 unix 必须与 now_ms 完全一致（yy 内部 md5 也用同一毫秒值）
    params = dict(params)
    params["unix"] = str(now_ms)
    params["client"] = "desktop"  # 拦截器末尾追加 client=desktop

    query = urllib.parse.urlencode(params)  # 与 requests 发送时的序列化一致
    has_search_params_path = f"{path}?{query}"

    # body 串：GET 为 ""，POST 为 JSON 串
    body_str = "" if method.lower() == "get" else json.dumps(body or {}, ensure_ascii=False)

    # x-signature = md5("{now_sec}I*7Cf%WZ#S&%1RlZJ&C2{body_str}")
    x_signature = _md5_hex(f"{now_sec}I*7Cf%WZ#S&%1RlZJ&C2{body_str}")

    # yy = md5( encodeURIComponent(hasSearchParamsPath) + "_" + "{}" + md5(str(now_ms)) + "ooui" )
    inner = _md5_hex(str(now_ms))
    yy = _md5_hex(encode_uri_component(has_search_params_path) + "_" + "{}" + inner + "ooui")

    headers = {
        "token": token,
        "yy": yy,
        "x-timestamp": str(now_sec),
        "x-signature": x_signature,
        "origin": "https://agent.minimax.io",
        "referer": "https://agent.minimax.io/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) MiniMaxAgent/desktop Chrome/124.0 Safari/537.36",
    }
    if method.lower() != "get":
        headers["content-type"] = "application/json"
    return params, headers, body_str


# ===== JWT 本地解析（用于判断 token 是否过期、给出可读诊断） =====

def _b64url_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def decode_token(token: str):
    """本地解析 JWT（不校验签名，只读 exp / user.id）。
    返回 (exp_ts, user_id)；非 JWT 或解析失败返回 (0, "")。"""
    try:
        parts = str(token or "").split(".")
        if len(parts) != 3:
            return 0, ""
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
        exp = int(payload.get("exp") or 0)
        uid = str(((payload.get("user") or {}).get("id")) or "")
        return exp, uid
    except Exception:
        return 0, ""


def token_exp_text(token: str) -> str:
    """把 token 有效期翻译成人话，供失败诊断使用。"""
    exp, _ = decode_token(token)
    if not exp:
        return "token 不是合法 JWT（疑似被截断 / 粘贴时带引号 / 复制不全）"
    delta = exp - time.time()
    if delta > 0:
        return f"token 剩余 {delta / 86400:.1f} 天有效"
    return f"token 已于 {-delta / 86400:.1f} 天前过期，必须重新 --export-env"


def clean_env_value(raw: str) -> str:
    """清洗环境变量：去首尾空白、去误粘贴的成对引号、去零宽/BOM 字符。"""
    if raw is None:
        return ""
    s = str(raw).strip().strip("\ufeff").strip()
    while len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        s = s[1:-1].strip()
    return s


# ===== token 缓存（青龙环境自愈的关键，始终启用） =====

def load_token_cache() -> str:
    try:
        if not os.path.isfile(CACHE_FILE):
            return ""
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return clean_env_value(data.get("token") or "")
    except Exception as e:
        print(f"[warn] 读取 token 缓存失败: {e}")
        return ""


def save_token_cache(token: str, source: str = "renewal") -> bool:
    if not token:
        return False
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump({"token": token, "source": source,
                       "updated_at": int(time.time())}, fh)
        return True
    except Exception as e:
        print(f"[warn] 写入 token 缓存失败: {e}")
        return False


def persist_token(token: str, source: str = "renewal") -> list:
    """续期成功后落盘：仅写缓存文件（青龙靠它自愈）。返回写入位置列表。"""
    saved = []
    if save_token_cache(token, source):
        saved.append("缓存")
    return saved


# ===== 凭据解析 =====

def read_local_credential():
    """读取本机 MiniMax Agent 登录态（tokens.accessToken）。"""
    cfg_path = os.path.join(os.environ.get("APPDATA", ""), DEFAULT_CONFIG_REL)
    if not cfg_path or not os.path.isfile(cfg_path):
        return None
    try:
        with open(cfg_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        token = ((data.get("tokens") or {}).get("accessToken") or "").strip()
        if not token:
            return None
        user = data.get("user") or {}
        return {
            "token": token,
            "user_id": str(user.get("realUserID") or user.get("userID") or "").strip(),
            "user_name": (user.get("userName") or "").strip(),
            "mail": (user.get("userMail") or "").strip(),
        }
    except Exception as e:
        print(f"[warn] 解析 {cfg_path} 失败: {e}")
        return None


# 稳定的默认设备身份：仅在未设置对应环境变量时回落使用，避免每次随机导致设备指纹漂移。
# 如需更换，可在 .env / 运行环境中设置 MINIMAX_UUID 与 MINIMAX_DEVICE_ID 覆盖。
_DEFAULT_UUID = "3548c8fa-9ac2-4a28-8f6b-71ecd88bc048"
_DEFAULT_DEVICE_ID = "1790426211"


def load_persistent_device():
    """返回稳定的 uuid 与数字 device_id。
    优先取环境变量 MINIMAX_UUID / MINIMAX_DEVICE_ID（便于跨机/容器部署）；
    未设置时回落到脚本内写死的稳定常量。不再读写任何缓存文件。"""
    uid = clean_env_value(os.environ.get("MINIMAX_UUID", ""))
    did = clean_env_value(os.environ.get("MINIMAX_DEVICE_ID", ""))
    if uid and did:
        return uid, did
    return (uid or _DEFAULT_UUID), (did or _DEFAULT_DEVICE_ID)


def _token_alive(token: str) -> bool:
    """token 非空且（若是 JWT）未过期。"""
    if not token:
        return False
    exp, _ = decode_token(token)
    if exp == 0:
        return True  # 非 JWT，交给服务端判断
    return exp - time.time() > 60


def resolve_credentials():
    """读取环境变量（并按需回落到续期缓存），返回凭据 dict。
    - env token 有效  -> 直接用（先 env 后缓存的顺序在 checkin 里兜底重试）
    - env token 缺失/已过期 -> 用缓存里上次续期成功的 token
    - 都没有          -> 原样返回，由 checkin 阶段报 NO_CREDENTIAL / AUTH_EXPIRED"""
    env_token = clean_env_value(os.environ.get("MINIMAX_TOKEN", ""))
    cache_token = load_token_cache()
    token = env_token
    source = "env"
    if not _token_alive(env_token) and _token_alive(cache_token):
        token, source = cache_token, "cache"
    return {
        "token": token,
        "env_token": env_token,
        "cache_token": cache_token,
        "source": source,
        "user_id": clean_env_value(os.environ.get("MINIMAX_USER_ID", "")),
        "user_name": "",
        "mail": "",
    }


def _candidate_tokens(cred: dict):
    """生成待尝试的 token 列表 [(token, 来源标签)]，已过期的排后面、去重。"""
    env_t = clean_env_value(cred.get("env_token") or cred.get("token") or "")
    cache_t = clean_env_value(cred.get("cache_token") or "")
    ordered = []
    if _token_alive(env_t):
        ordered.append((env_t, "环境变量"))
    if cache_t and cache_t != env_t and _token_alive(cache_t):
        ordered.append((cache_t, "缓存"))
    for t, tag in ((env_t, "环境变量"), (cache_t, "缓存")):
        if t and t not in [x[0] for x in ordered]:
            ordered.append((t, tag))
    return ordered


# ===== 业务解析 =====

AUTH_FAIL_KEYWORDS = ("unauthorized", "token", "expired", "not login",
                      "not logged", "登录", "鉴权", "invalid", "异常用户")
RATE_LIMIT_KEYWORDS = ("频繁", "frequent", "too many", "太多", "稍后再试",
                       "繁忙", "busy", "limit")


def api_succeeded(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    # MiniMax 约定：base_resp.status_code == 0 表示业务成功
    br = data.get("base_resp") or {}
    if isinstance(br, dict) and br.get("status_code") == 0:
        return True
    code = data.get("code")
    if isinstance(code, (int, float)) and code in (0, 200):
        return True
    if isinstance(code, str) and code.strip() in ("0", "200"):
        return True
    if data.get("success") is True:
        return True
    return str(data.get("status", "")).lower() == "success"


def server_message(data) -> str:
    """从各种响应结构里抠出服务端给的文案，便于如实上报。"""
    if not isinstance(data, dict):
        return ""
    si = data.get("statusInfo") or {}
    if isinstance(si, dict) and si.get("message"):
        return str(si["message"])
    br = data.get("base_resp") or {}
    if isinstance(br, dict) and br.get("status_msg") and br.get("status_code") not in (0, None):
        return f"{br.get('status_msg')}(code={br.get('status_code')})"
    return str(data.get("message") or data.get("msg") or "")


def is_auth_failure(http_status: int, data) -> bool:
    if http_status in (401, 403):
        return True
    if not isinstance(data, dict):
        return False
    try:
        code = int(str(data.get("code")))
        if code in (401, 403):
            return True
    except (TypeError, ValueError):
        pass
    si = data.get("statusInfo") or {}
    if isinstance(si, dict):
        try:
            if int(str(si.get("code"))) in (1000021, 1000022, 1000023):
                return True
        except (TypeError, ValueError):
            pass
    msg = str(data.get("message") or data.get("msg") or "").lower()
    if any(k in msg for k in RATE_LIMIT_KEYWORDS):
        return False
    return any(k.lower() in msg for k in AUTH_FAIL_KEYWORDS)


def is_rate_limited(http_status: int, data) -> bool:
    if http_status in (429, 500, 502, 503, 504):
        return True
    if not isinstance(data, dict):
        return False
    msg = str(data.get("message") or data.get("msg") or "")
    return any(k in msg for k in RATE_LIMIT_KEYWORDS)


# ===== 经代理出网（绕过透明 TLS 拦截网关）=====
# 当服务器出口被网关全阻断时，经 VLESS 订阅由内置零依赖代理（vless_proxy.py，纯标准库，
# 不依赖任何外部客户端、不下载二进制）拉起本地 HTTP 代理干净出网；签到前拉起，
# checkin_once 结束（finally）时自动关闭。订阅地址由 MINIMAX_SUB 指定。
# 订阅地址示例：https://rom.msdmcp.top/sub?token=54fb6f9b95583ec8ad17bad7493a276f
_PROXIES = None  # requests 代理 dict，start_proxy_from_env() 设置
_PROXY_INSTANCE = None  # 内置 VlessProxy 实例，stop_proxy() 时关闭


def start_proxy_from_env():
    """读 MINIMAX_SUB（VLESS 订阅地址）拉起内置零依赖代理。返回是否启用。"""
    global _PROXIES, _PROXY_INSTANCE
    if _PROXIES is not None:
        return True
    sub = clean_env_value(os.environ.get("MINIMAX_SUB", ""))
    if not sub:
        return False
    try:
        links = fetch_subscription(sub)
    except Exception as e:
        print(f"[miniMax] 抓取订阅失败：{e}")
        return False
    if not links:
        return False
    try:
        inst = VlessProxy(links, local_port=10808, verify=True)
        url = inst.start()
        _PROXIES = {"http": url, "https": url}
        _PROXY_INSTANCE = inst
        print(f"[miniMax] 已用内置零依赖代理拉起本地代理：{url}（{len(links)} 节点）")
        return True
    except Exception as e:
        print(f"[miniMax] 拉起内置代理失败：{e}")
        return False


def stop_proxy():
    """关闭内置零依赖代理（若启用了），并清空代理状态以便下次重新拉起。"""
    global _PROXIES, _PROXY_INSTANCE
    if _PROXY_INSTANCE is not None:
        try:
            _PROXY_INSTANCE.stop()
        except Exception:
            pass
        _PROXY_INSTANCE = None
    _PROXIES = None


def _do_request(connect_base, token, params, path, method, body, timeout, proxies=None):
    """单次请求：计算签名 -> 发送 -> 返回 (status_code, json_or_raw)。"""
    signed_params, headers, body_str = _sign_request(path, token, params, method, body)
    url = f"{connect_base}{path}"
    req = requests.Request(method.upper(), url, params=signed_params,
                           headers=headers, data=body_str or None)
    prepared = req.prepare()
    try:
        session = requests.Session()
        # proxies=None 时回落到模块全局 _PROXIES（若已配置代理）；否则直连
        if proxies is None:
            proxies = _PROXIES or None
        r = session.send(prepared, timeout=timeout, proxies=proxies)
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"raw": r.text[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def api_call(host, token, params, path, method="GET", body=None, timeout=30):
    """带签名的请求。若已配置 MINIMAX_SUB 订阅代理，请求走本地代理直连域名。"""
    proxies = _PROXIES or None
    sc, sb = _do_request(host, token, params, path, method, body, timeout, proxies)
    return sc, sb


def renew_token(token: str, params: dict):
    """续期登录：用旧 token 换新 token。返回 (新token, http状态码, 服务端文案)。
    失败时新 token 为空串。"""
    code, data = api_call(HOST, token, params, RENEW_PATH, method="POST", body={})
    if isinstance(data, dict):
        new_token = ((data.get("data") or {}).get("token") or "").strip()
        if new_token:
            return new_token, code, ""
    return "", code, server_message(data) or (str((data or {}).get("error")) if isinstance(data, dict) else "")


def _diag(token: str, http_status: int, data) -> str:
    """把失败原因拼成一句人话，供通知文本直接展示。"""
    bits = []
    if http_status:
        bits.append(f"HTTP {http_status}")
    else:
        bits.append("网络异常（无响应）")
    msg = server_message(data) or str((data or {}).get("error") or "")
    if msg:
        bits.append(msg)
    bits.append(token_exp_text(token))
    return "；".join(bits)


def _try_checkin(user_id: str, token: str, source: str):
    """用指定 token 走一遍「续期 -> 状态 -> 领取」。返回 (flag, content)。"""
    uid, did = load_persistent_device()
    base_params = build_device_params(user_id, uid, did)

    # 1) 先续期（等价于重新登录一次，新 token 有效期顺延 ~40 天）
    renewed = ""
    new_token, rcode, rmsg = renew_token(token, base_params)
    if new_token:
        renewed = new_token
        token = new_token
        where = persist_token(new_token, "renewal")
        print(f"[miniMax] 续期成功（来源 {source}），已写回：{'/'.join(where) or '仅内存'}")
    elif rcode:
        print(f"[miniMax] 续期失败：HTTP {rcode} {rmsg}（沿用原 token 继续尝试）")

    # 2) 状态查询（GET）
    sc, sb = api_call(HOST, token, base_params, STATUS_PATH, method="GET")
    if is_auth_failure(sc, sb):
        return "AUTH_EXPIRED", f"⚠️ 鉴权失败：{_diag(token, sc, sb)}｜token 来源：{source}"
    if not api_succeeded(sb):
        msg = server_message(sb) or json.dumps(sb, ensure_ascii=False)[:150]
        return "STATUS_ERR", f"⚠️ 状态查询异常：HTTP {sc} {msg}"

    # 解析今日签到状态：days[] 中 is_today=true 的那天，status==3 表示已领取
    days = (((sb or {}).get("data") or {}).get("days")) or []
    today = next((d for d in days if d.get("is_today")), None)
    today_done = bool(today and today.get("status") == 3)
    if today_done:
        extra = "（已自动续期 token）" if renewed else ""
        return "ALREADY_TODAY", f"ℹ️ 今日已签到（第 {today.get('day_no')} 天）{extra}"

    # 3) 领取（POST，body {}）
    cc, cb = api_call(HOST, token, base_params, CLAIM_PATH, method="POST", body={})
    if is_auth_failure(cc, cb):
        return "AUTH_EXPIRED", f"⚠️ 鉴权失败：{_diag(token, cc, cb)}｜token 来源：{source}"
    if is_rate_limited(cc, cb):
        msg = server_message(cb) or json.dumps(cb, ensure_ascii=False)[:120]
        return "RATE_LIMITED", f"⏳ 服务端限频：{msg}，建议错峰或稍后重试"
    if not api_succeeded(cb):
        msg = server_message(cb) or json.dumps(cb, ensure_ascii=False)[:150]
        return "FAIL", f"⚠️ 领取未成功：HTTP {cc} {msg}"

    # 解析领取结果：claim_result 1=新领取成功，2=今日已领取
    cdata = (cb or {}).get("data") or {}
    claim_result = cdata.get("claim_result")
    points = cdata.get("points")
    extra = "（已自动续期 token，下次仍可用）" if renewed else ""
    if claim_result == 2:
        return "ALREADY_TODAY", f"ℹ️ 今日已签到（claim_result=2）{extra}"
    if claim_result == 1 or points is not None:
        gain = f"本次 +{points} 积分" if points else "签到成功"
        return "SUCCESS", f"✅ {gain}（第 {cdata.get('day_no')} 天）{extra}"
    return "SUCCESS", f"✅ 领取成功{extra}"


def checkin_once(cred: dict):
    """执行签到，返回 (结果标记, 通知文本)。

    策略：先续期（相当于先登录）再签到；若某个 token 鉴权失败，自动换另一个
    候选 token（环境变量 / 上次续期缓存）重试，全部失败才如实上报。
    """
    cred = cred or {}
    user_id = clean_env_value(cred.get("user_id", ""))

    candidates = _candidate_tokens(cred)
    if not candidates:
        return "NO_CREDENTIAL", ("未获取到 MiniMax 登录态，请设置环境变量 MINIMAX_TOKEN / MINIMAX_USER_ID"
                                 "（或运行 python minimax_checkin.py --export-env --save 刷新）")

    # 已配置出网代理时，本次所有请求走本地代理；结束（finally）时自动关闭
    start_proxy_from_env()
    try:
        last = ("NO_CREDENTIAL", "未获取到 MiniMax 登录态")
        for token, source in candidates:
            try:
                flag, content = _try_checkin(user_id, token, source)
            except Exception as e:  # 单个候选异常不中断其余尝试
                flag, content = "ERROR", f"⚠️ 执行异常（token 来源：{source}）：{type(e).__name__}: {e}"
                print(f"[miniMax] {content}")
            if flag in ("SUCCESS", "ALREADY_TODAY", "RATE_LIMITED"):
                return flag, content
            last = (flag, content)
            print(f"[miniMax] token 来源 {source} 失败：RESULT={flag} | {content}")

        # 全部候选都失败：补一条可操作提示
        flag, content = last
        if flag == "AUTH_EXPIRED":
            content += "｜处理：①本机 python minimax_checkin.py --export-env --save 重新导出；" \
                       "②把新的 MINIMAX_TOKEN 填回青龙（注意别带引号）；" \
                       "③若确认 token 无误仍 401，多为服务器出口 IP 被风控"
        return flag, content
    finally:
        stop_proxy()


def export_env():
    """--export-env：从本机登录态读取并打印环境变量（token 过期时用来刷新）。
    读取后会先走一次续期，导出的是**最新** token；追加 --save 可直接写回 .env。"""
    c = read_local_credential()
    if not c:
        print("未发现 MiniMax 登录态，请先在本机登录 MiniMax Agent 桌面端")
        return 1
    uid, did = load_persistent_device()
    params = build_device_params(c["user_id"], uid, did)

    token = c["token"]
    new_token, rcode, rmsg = renew_token(token, params)
    if new_token:
        token = new_token
        print(f"# 已续期：token 有效期顺延（{token_exp_text(token)}）")
    elif rcode:
        print(f"# 续期未成功（HTTP {rcode} {rmsg}），导出本机现有 token")

    values = {
        "MINIMAX_TOKEN": token,
        "MINIMAX_USER_ID": c["user_id"],
        "MINIMAX_UUID": uid,
        "MINIMAX_DEVICE_ID": did,
    }
    for k, v in values.items():
        print(f"{k}={v}")
    if c.get("user_name") or c.get("mail"):
        print(f"# 用户: {c.get('user_name')} <{c.get('mail')}>")
    if "--save" in sys.argv:
        n = _save_env_values(values)
        if n:
            print(f"# 已将上述 {n} 个变量写回 .env")
        save_token_cache(token, "export-env")
    return 0


def run_renew():
    """--renew：只续期 token（要求当前 token 仍有效），并写回缓存/.env。"""
    cred = resolve_credentials()
    token = clean_env_value(cred.get("token") or "")
    if not token:
        print("未找到可用 token：请先设置 MINIMAX_TOKEN，或在本机执行 --export-env --save")
        return 1
    uid, did = load_persistent_device()
    params = build_device_params(cred.get("user_id", ""), uid, did)

    print(f"# 当前 {token_exp_text(token)}")
    new_token, rcode, rmsg = renew_token(token, params)
    if not new_token:
        print(f"续期失败：HTTP {rcode} {rmsg}｜{token_exp_text(token)}")
        return 1
    where = persist_token(new_token, "renew")
    print(new_token)
    print(f"# 续期成功：{token_exp_text(new_token)}；已写回 {'/'.join(where) or '仅内存'}")
    return 0


def main():
    # python minimax_checkin.py --export-env [--save]  仅导出环境变量后退出
    if "--export-env" in sys.argv:
        sys.exit(export_env())
    # python minimax_checkin.py --renew [--save]       仅续期 token 后退出
    if "--renew" in sys.argv:
        sys.exit(run_renew())

    title = "MiniMax Code 每日签到"
    cred = resolve_credentials()
    if not cred:
        flag, content = "NO_CREDENTIAL", "未获取到 MiniMax 登录态，请登录 MiniMax Agent 桌面端后重试"
    else:
        flag, content = checkin_once(cred)

    print(f"RESULT={flag} | {content}")

    try:
        sendNotify.serverJMy(title, content)
    except Exception as e:
        print(f"[warn] 通知发送失败: {e}")


if __name__ == "__main__":
    main()
