#!/bin/env python3
# -*- coding: utf-8 -*
"""
cron: 23 0 * * * trae_checkin.py
new Env('TraeWork每日积分签到');

==================== Trae Work 自动签到 ====================

签到点（POST，空 JSON body）：
    状态查询  {host}/trae/api/v2/ug/checkin_credits/status
    领取积分  {host}/trae/api/v2/ug/checkin_credits/claim

鉴权头（对齐逆向仓库 traeClient.ts#postUg 最小集）：
    Content-Type:   application/json
    Authorization:  Cloud-IDE-JWT {token}
    x-device-id:    {数字格式设备id}   # 取自 storage.json 的 iCubeAuthInfo://icube-dc:<numeric> 键

【方式一 · 推荐：环境变量（脚本默认且唯一读取来源）】
在 .env 或运行环境中设置：
    TRAE_TOKEN=<auth_info.token>
    TRAE_DEVICE_ID=<iCubeAuthInfo://icube-dc:<numeric> 键中的数字设备id>
    TRAE_USER_ID=<auth_info.userId>           # 可选，仅用于展示
    # —— 以下为【自动续期】所需材料（一次性引导后持续生效）——
    TRAE_REFRESH_TOKEN=<auth_info.refreshToken>
    TRAE_DEVICE_KEY_PEM=<设备 ECDSA 私钥 PEM>        # ExchangeToken 设备证明签名用
    TRAE_DEVICE_PUB_PEM=<设备 ECDSA 公钥 PEM>
    TRAE_MACHINE_ID=<telemetry.machineId>
脚本【默认只读取上述环境变量】，不再自动读取本机登录态，方便容器 / 跨机 / 青龙部署。
续期后最新凭据写入同目录 .trae_token.json（已加入 .gitignore），是续期后的权威来源。

【自动续期 / 自愈】
Trae 的 access token 仅约 14 天有效。脚本内置 ExchangeToken 续期：用 refreshToken + 设备
ECDSA 私钥（纯标准库签名，无需第三方库）向 {host}/trae/api/v3/oauth/ExchangeToken 换发新
token。触发条件：
  - 无 token 但有续期材料：先续期再签到；
  - token 即将过期（<48h）：先续期；
  - 状态/领取返回鉴权失败：自动续期并重试一次。
材料缺失时退化为原行为并提示先 --export-keys 引导。

【方式二 · 引导 / 刷新：--export-env（仅本机、不进入默认运行链）】
在本机（已登录 Trae 桌面端）执行会解密 storage.json 并打印【全部】变量（含设备私钥）：
    python trae_checkin.py --export-keys          # 或 --export-env（同义）
追加 --save 直接写回 .env 并写入续期缓存：
    python trae_checkin.py --export-keys --save

【仅续期：--renew】
    python trae_checkin.py --renew     # 立即续期并写回缓存 / storage.json

本机登录态文件（仅供参考，不参与默认运行）：
    %APPDATA%\\TRAE SOLO CN\\User\\globalStorage\\storage.json
    键： iCubeAuthInfo://icube.cloudide  （base64 加密信封，AES-128-CBC / SHA512 完整性校验）
    键： iCubeAuthInfo://icube-dc:<numeric>  （设备 ECDSA 密钥对信封）

依赖：pip install requests pycryptodome

声明：仅供学习与个人使用。Trae Work 是字节跳动旗下产品，本脚本与其无任何关联，
使用产生的任何后果（账号风控、封禁等）由使用者自行承担。
============================================================================================
"""

import os
import sys
import re
import json
import base64
import hashlib
import time
import platform
from datetime import datetime, timezone
import sendNotify

import requests
from dotenv import load_dotenv
load_dotenv()

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    from Crypto.PublicKey import ECC
    from Crypto.Signature import DSS
    from Crypto.Hash import SHA256
except ImportError:
    print("缺少依赖 pycryptodome，请执行: pip install pycryptodome")
    sys.exit(1)


def _save_env_values(values: dict):
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

# ===== 加密信封常量 =====
HEADER = bytes([116, 99, 5, 16, 0, 0])
LEFT_SECRET = bytes([
    82, 9, 106, 213, 48, 54, 165, 56, 191, 64, 163, 158, 129, 243, 215, 251,
    124, 227, 57, 130, 155, 47, 255, 135, 52, 142, 67, 68, 196, 222, 233, 203,
    84, 123, 148, 50, 166, 194, 35, 61, 238, 76, 149, 11, 66, 250, 195, 78,
    8, 46, 161, 102, 40, 217, 36, 178, 118, 91, 162, 73, 109, 139, 209, 37,
])
RIGHT_SECRET = bytes([
    31, 221, 168, 51, 136, 7, 199, 49, 177, 18, 16, 89, 39, 128, 236, 95,
    96, 81, 127, 169, 25, 181, 74, 13, 45, 229, 122, 159, 147, 201, 156, 239,
    160, 224, 59, 77, 174, 42, 245, 176, 200, 235, 187, 60, 131, 83, 153, 97,
    23, 43, 4, 126, 186, 119, 214, 38, 225, 105, 20, 99, 85, 33, 12, 125,
])

STATUS_PATH = "/trae/api/v2/ug/checkin_credits/status"
CLAIM_PATH = "/trae/api/v2/ug/checkin_credits/claim"
ENTITLEMENT_PATH = "/trae/api/v2/pay/user_current_entitlement_list"
HOST = "https://api.trae.cn"
STORAGE_REL = os.path.join("User", "globalStorage", "storage.json")
AUTH_KEY = "iCubeAuthInfo://icube.cloudide"

# ===== 自动续期相关常量 =====
EXCHANGE_PATH = "/trae/api/v3/oauth/ExchangeToken"
CLIENT_ID = "en1oxy7wnw8j9n"
APP_VERSION = os.environ.get("TRAE_APP_VERSION", "1.107.1")
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".trae_token.json")
DEVICE_OS_INFO = "Windows"

# ===== 辅助函数 =====
def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()

# ---- AES 加解密（使用 pad/unpad） ----
def decrypt_trae_auth_info(encoded: str) -> dict:
    envelope = base64.b64decode(encoded)
    if len(envelope) <= 38 or envelope[:6] != HEADER:
        raise ValueError("Invalid TRAE desktop credential envelope")

    random_key = envelope[6:38]
    secret = bytes(a ^ b for a, b in zip(LEFT_SECRET, RIGHT_SECRET))
    derived = _sha512(_sha512(random_key) + secret)
    key, iv = derived[:16], derived[16:32]

    cipher = AES.new(key, AES.MODE_CBC, iv)
    plaintext = unpad(cipher.decrypt(envelope[38:]), 16)

    if len(plaintext) < 64:
        raise ValueError("decrypted payload too short")
    expected_digest, payload = plaintext[:64], plaintext[64:]
    if _sha512(payload) != expected_digest:
        raise ValueError("TRAE desktop credential integrity check failed")
    return json.loads(payload.decode("utf-8"))


def encrypt_trae_auth_info(plaintext: str) -> str:
    random_key = os.urandom(32)
    secret = bytes(a ^ b for a, b in zip(LEFT_SECRET, RIGHT_SECRET))
    derived = _sha512(_sha512(random_key) + secret)
    key, iv = derived[:16], derived[16:32]

    body = plaintext.encode("utf-8")
    payload = _sha512(body) + body
    payload = pad(payload, 16)
    cipher = AES.new(key, AES.MODE_CBC, iv).encrypt(payload)

    envelope = HEADER + random_key + cipher
    return base64.b64encode(envelope).decode("utf-8")

# ---- ECDSA 签名（使用 pycryptodome） ----
_N = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551

def _der_encode_signature(r: int, s: int) -> bytes:
    def _enc(x):
        b = x.to_bytes(32, "big")
        if b[0] & 0x80:
            b = b"\x00" + b
        return b
    rb, sb = _enc(r), _enc(s)
    body = b"\x02" + bytes([len(rb)]) + rb + b"\x02" + bytes([len(sb)]) + sb
    return b"\x30" + bytes([len(body)]) + body

def ecdsa_sign_pure(private_pem: str, data: bytes) -> str:
    """用设备 EC 私钥对数据做 ECDSA P-256/SHA-256 签名，返回 base64(DER)。"""
    key = ECC.import_key(private_pem)
    signer = DSS.new(key, 'fips-186-3')
    sig = signer.sign(SHA256.new(data))  # DER 编码

    # 解析 DER 提取 r 和 s（格式：0x30 0x44 0x02 len r 0x02 len s）
    # 简单解析：跳过 0x30 和 len，然后 0x02 len_r r 0x02 len_s s
    der = sig
    if der[0] != 0x30:
        raise ValueError("Invalid DER signature")
    idx = 2  # 跳过 0x30 和 length
    if der[1] & 0x80:  # 长格式，但我们的长度固定 <128，所以直接跳过
        idx += 1
    if der[idx] != 0x02:
        raise ValueError("Missing r integer")
    len_r = der[idx + 1]
    r_bytes = der[idx + 2:idx + 2 + len_r]
    idx += 2 + len_r
    if der[idx] != 0x02:
        raise ValueError("Missing s integer")
    len_s = der[idx + 1]
    s_bytes = der[idx + 2:idx + 2 + len_s]
    r = int.from_bytes(r_bytes, "big")
    s = int.from_bytes(s_bytes, "big")

    # 低 s 归一化
    if s > _N // 2:
        s = _N - s

    # 重新 DER 编码
    der_new = _der_encode_signature(r, s)
    return base64.b64encode(der_new).decode("utf-8")

def _normalize_pem(raw: str, key_type="PRIVATE") -> str:
    """把 env 里的 PEM 统一成标准 PEM 文本。支持标准多行或纯 Base64 主体。"""
    s = (raw or "").strip()
    if not s:
        return ""
    if "-----BEGIN" in s:
        return s
    # 若只是纯 Base64 主体（无换行），补全头尾
    if key_type.upper() == "PRIVATE":
        return f"-----BEGIN PRIVATE KEY-----\n{s}\n-----END PRIVATE KEY-----"
    else:
        return f"-----BEGIN PUBLIC KEY-----\n{s}\n-----END PUBLIC KEY-----"

# ---- 续期核心 ----
def build_device_proof(refresh_token: str, private_pem: str) -> dict:
    ts = int(time.time())
    nonce = os.urandom(16).hex()
    canonical = "\n".join(["POST", EXCHANGE_PATH, CLIENT_ID, refresh_token, str(ts), nonce])
    signature = ecdsa_sign_pure(private_pem, canonical.encode("utf-8"))
    return {"Timestamp": ts, "Nonce": nonce, "Signature": signature}

def build_device_info(public_pem: str, device_id: str, machine_id: str) -> dict:
    return {
        "DeviceID": device_id,
        "MachineID": machine_id or "",
        "PlatformCode": "SOLO_PC",
        "DeviceType": "PC",
        "DeviceName": os.environ.get("USERNAME", "user"),
        "DeviceModel": "",
        "ClientVersion": APP_VERSION,
        "DevicePublicKey": public_pem,
        "DeviceBrand": "",
        "DeviceCPU": "",
        "OSInfo": DEVICE_OS_INFO,
        "OSVersion": platform.release(),
    }

def decode_jwt_exp(token: str):
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return 0
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        return float(payload.get("exp") or 0)
    except Exception:
        return 0

def load_cache() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}

def save_cache(cred: dict):
    try:
        data = {
            "token": cred.get("token", ""),
            "refresh_token": cred.get("refresh_token", ""),
            "device_id": cred.get("device_id", ""),
            "user_id": cred.get("user_id", ""),
            "machine_id": cred.get("machine_id", ""),
            "device_key_pem": cred.get("device_key_pem", ""),
            "device_pub_pem": cred.get("device_pub_pem", ""),
            "expires_ms": cred.get("expires_ms", 0),
            "refresh_expires_ms": cred.get("refresh_expires_ms", 0),
            "updated_at": int(time.time()),
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[warn] 写入续期缓存失败: {e}")

def exchange_token(cred: dict):
    refresh = cred.get("refresh_token", "").strip()
    priv = cred.get("device_key_pem", "").strip()
    pub = cred.get("device_pub_pem", "").strip()
    did = cred.get("device_id", "").strip()
    mid = cred.get("machine_id", "").strip()
    if not (refresh and priv and pub and did):
        return False, None, "缺少 refreshToken / 设备私钥材料（请先运行 python trae_checkin.py --export-keys --save 引导）"
    try:
        proof = build_device_proof(refresh, priv)
    except Exception as e:
        return False, None, f"设备证明生成失败（设备私钥材料可能无效）: {e}"
    body = {
        "ClientID": CLIENT_ID,
        "ClientSecret": "",
        "RefreshToken": refresh,
        "DeviceInfo": build_device_info(pub, did, mid),
        "DeviceProof": proof,
        "IDEVersion": APP_VERSION,
    }
    headers = {"Content-Type": "application/json", "x-cloudide-token": ""}
    try:
        r = requests.post(HOST + EXCHANGE_PATH, headers=headers, data=json.dumps(body),
                          timeout=30, proxies={"http": None, "https": None})
    except Exception as e:
        return False, None, f"续期请求异常: {e}"
    try:
        j = r.json()
    except Exception:
        return False, None, f"续期响应非 JSON（HTTP {r.status_code}）: {r.text[:200]}"
    err = (j.get("ResponseMetadata") or {}).get("Error")
    if err:
        return False, None, f"续期被拒 HTTP {r.status_code} code={err.get('Code')} msg={err.get('Message')}"
    res = j.get("Result") or {}
    token = res.get("Token")
    if not token:
        return False, None, f"续期响应无 Token: {json.dumps(j, ensure_ascii=False)[:200]}"
    return True, {
        "token": token,
        "refresh_token": res.get("RefreshToken") or refresh,
        "expires_ms": float(res.get("TokenExpireAt") or 0),
        "refresh_expires_ms": float(res.get("RefreshExpireAt") or 0),
    }, None

def write_back_storage(new_token: str, new_refresh: str, token_expire_ms: float, refresh_expire_ms: float):
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return
    sp = os.path.join(appdata, "TRAE SOLO CN", STORAGE_REL)
    if not os.path.isfile(sp):
        return
    try:
        with open(sp, "r", encoding="utf-8") as fh:
            st = json.load(fh)
        enc = st.get(AUTH_KEY)
        if not enc:
            return
        auth = decrypt_trae_auth_info(enc)
        auth["token"] = new_token
        if new_refresh:
            auth["refreshToken"] = new_refresh
        if token_expire_ms:
            auth["expiredAt"] = datetime.fromtimestamp(token_expire_ms / 1000, tz=timezone.utc).isoformat()
        if refresh_expire_ms:
            auth["refreshExpiredAt"] = datetime.fromtimestamp(refresh_expire_ms / 1000, tz=timezone.utc).isoformat()
        auth["tokenReleaseAt"] = datetime.now(timezone.utc).isoformat()
        st[AUTH_KEY] = encrypt_trae_auth_info(json.dumps(auth, ensure_ascii=False))
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False)
        print("[trae] 已把续期结果同步写回本机 storage.json（桌面端登录态保持一致）")
    except Exception as e:
        print(f"[warn] 写回 storage.json 失败（不影响本次签到）: {e}")

def self_heal(cred: dict):
    ok, fields, err = exchange_token(cred)
    if not ok:
        return False, f"⚠️ {cred.get('user_id') or '未知用户'} 自动续期失败：{err}"
    cred["token"] = fields["token"]
    cred["refresh_token"] = fields["refresh_token"]
    cred["expires_ms"] = fields["expires_ms"]
    cred["refresh_expires_ms"] = fields["refresh_expires_ms"]
    save_cache(cred)
    write_back_storage(fields["token"], fields["refresh_token"], fields["expires_ms"], fields["refresh_expires_ms"])
    remain = (fields["expires_ms"] - datetime.now(timezone.utc).timestamp() * 1000) / 86400000
    return True, f"已自动续期 token（新有效期约 {remain:.1f} 天）"

def _can_self_heal(cred: dict) -> bool:
    return bool(cred.get("refresh_token") and cred.get("device_key_pem") and cred.get("device_pub_pem"))

def _token_expiring_soon(cred: dict) -> bool:
    exp = cred.get("expires_ms") or (decode_jwt_exp(cred.get("token", "")) * 1000)
    if not exp:
        return False
    remain_h = (exp - datetime.now(timezone.utc).timestamp() * 1000) / 3600000
    return remain_h <= 48

def ensure_valid_token(cred: dict):
    """确保 token 有效且非即将过期；若材料齐全则自动续期。返回 (ok, msg)。"""
    if not cred.get("token"):
        if _can_self_heal(cred):
            return self_heal(cred)
        return False, "未获取到 token 且无续期材料"
    if _can_self_heal(cred) and _token_expiring_soon(cred):
        return self_heal(cred)
    return True, "OK"

# ---- 签到 API 调用 ----
def parse_time_ms(value) -> float:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s.isdigit():
        return float(s)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp() * 1000
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s).timestamp() * 1000
    except ValueError:
        return 0

def extract_dc_device_id(storage: dict) -> str:
    cands = []
    for k in storage.keys():
        if k.startswith("iCubeAuthInfo://icube-dc:"):
            did = k.split(":", 3)[-1]
            cands.append(did)
    numeric = [d for d in cands if d.isdigit()]
    if numeric:
        return numeric[0]
    if cands:
        return cands[0]
    return ""

def read_local_credential():
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        return None
    storage_path = os.path.join(appdata, "TRAE SOLO CN", STORAGE_REL)
    if not os.path.isfile(storage_path):
        return None
    try:
        with open(storage_path, "r", encoding="utf-8") as fh:
            storage = json.load(fh)
        encrypted = storage.get(AUTH_KEY)
        if not encrypted:
            return None
        auth = decrypt_trae_auth_info(encrypted)
        token = (auth.get("token") or "").strip()
        if not token:
            return None
        device_id = extract_dc_device_id(storage) or (storage.get("telemetry.devDeviceId") or "").strip()
        device_key_pem = device_pub_pem = ""
        if device_id:
            dev_enc = storage.get(f"iCubeAuthInfo://icube-dc:{device_id}")
            if dev_enc:
                try:
                    dev = decrypt_trae_auth_info(dev_enc)
                    device_key_pem = (dev.get("privateKeyPEM") or "").strip()
                    device_pub_pem = (dev.get("publicKeyPEM") or dev.get("publicKeyPEM") or "").strip()
                except Exception as e:
                    print(f"[warn] 解密设备密钥失败: {e}")
        return {
            "token": token,
            "device_id": device_id,
            "user_id": str(auth.get("userId") or ""),
            "expires_ms": parse_time_ms(auth.get("expiredAt")),
            "refresh_token": (auth.get("refreshToken") or "").strip(),
            "device_key_pem": device_key_pem,
            "device_pub_pem": device_pub_pem,
            "machine_id": (storage.get("telemetry.machineId") or "").strip(),
        }
    except Exception as e:
        print(f"[warn] 解析 {storage_path} 失败: {e}")
        return None

def resolve_credentials():
    cred = {
        "token": os.environ.get("TRAE_TOKEN", "").strip(),
        "device_id": os.environ.get("TRAE_DEVICE_ID", "").strip(),
        "user_id": os.environ.get("TRAE_USER_ID", "").strip(),
        "refresh_token": os.environ.get("TRAE_REFRESH_TOKEN", "").strip(),
        "device_key_pem": _normalize_pem(os.environ.get("TRAE_DEVICE_KEY_PEM", ""), "PRIVATE"),
        "device_pub_pem": _normalize_pem(os.environ.get("TRAE_DEVICE_PUB_PEM", ""), "PUBLIC"),
        "machine_id": os.environ.get("TRAE_MACHINE_ID", "").strip(),
        "expires_ms": 0,
        "refresh_expires_ms": 0,
    }
    cache = load_cache()
    if cache:
        for k in ("token", "device_id", "user_id", "refresh_token",
                  "device_key_pem", "device_pub_pem", "machine_id",
                  "expires_ms", "refresh_expires_ms"):
            if cache.get(k):
                cred[k] = cache[k]
    return cred

# ---- 精简后的错误判断 ----
def is_auth_failure(http_status: int, data) -> bool:
    if http_status in (401, 403):
        return True
    if isinstance(data, dict):
        code = data.get("code")
        if isinstance(code, (int, float)) and code in (401, 403, 1001):
            return True
    return False

def is_rate_limited(http_status: int, data) -> bool:
    # 仅凭状态码判断，429 或 5xx 视为限频/临时故障
    if http_status in (429, 500, 502, 503, 504):
        return True
    return False

def api_succeeded(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    code = data.get("code")
    if isinstance(code, (int, float)) and code in (0, 200):
        return True
    if isinstance(code, str) and code.strip() in ("0", "200"):
        return True
    if data.get("success") is True:
        return True
    return str(data.get("status", "")).lower() == "success"

def build_checkin_headers(token: str, device_id: str) -> dict:
    return {
        "content-type": "application/json",
        "authorization": token if str(token).startswith("Cloud-IDE-JWT ")
        else f"Cloud-IDE-JWT {token}",
        "x-device-id": device_id or "",
    }

def api_call(host, token, device_id, path, body=None, timeout=30):
    headers = build_checkin_headers(token, device_id)
    url = f"{host}{path}"
    req_body = json.dumps(body or {})

    try:
        req = requests.Request("POST", url, headers=headers, data=req_body)
        prepared = req.prepare()
        session = requests.Session()
        session.trust_env = False  # 禁用代理，强制直连
        r = session.send(prepared, timeout=timeout)

        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:300]}

        if r.status_code != 200:
            print(f"[trae] {path} -> HTTP {r.status_code} {r.text[:200]}")
        return r.status_code, data
    except Exception as e:
        print(f"[trae] {path} 请求异常: {e}")
        return 0, {"error": str(e)}

def query_points(host, token, device_id):
    sc, sb = api_call(host, token, device_id, ENTITLEMENT_PATH,
                      body={"require_usage": True}, timeout=15)
    try:
        packs = (((sb or {}).get("data") or {}).get("user_entitlement_pack_list")) or []
        total = 0
        found = False
        for p in packs:
            limit = ((((p.get("entitlement_base_info") or {}).get("quota")) or {})
                     .get("credits_limit")) or 0
            used = (((p.get("usage") or {}).get("credits_amount"))) or 0
            if limit > 0:
                found = True
                total += max(limit - used, 0)
        if found:
            return total
    except Exception:
        pass
    return None

def checkin_once(cred: dict):
    """执行单次签到，返回 (结果标记, 通知文本)。"""
    cred = cred or {}
    # 确保 token 有效（无 token 或即将过期则自动续期）
    ok, msg = ensure_valid_token(cred)
    if not ok:
        return "NO_CREDENTIAL", f"⚠️ {msg}"

    token = cred["token"]
    device_id = cred.get("device_id", "")
    host = HOST

    # 1) 状态查询
    sc, sb = api_call(host, token, device_id, STATUS_PATH)
    if isinstance(sb, dict) and sb.get("checked_in"):
        pts = query_points(host, token, device_id)
        extra = f"\n- 总可用积分：{pts:,.2f}" if pts is not None else ""
        return "ALREADY_TODAY", f"ℹ️ 今日已签到{extra}"

    if is_auth_failure(sc, sb):
        if _can_self_heal(cred):
            ok, msg = self_heal(cred)
            if ok:
                token = cred["token"]
                print(f"[trae] {msg}")
            else:
                return "AUTH_EXPIRED", f"⚠️ 鉴权失败（HTTP {sc}）且自动续期失败：{msg}"
            sc, sb = api_call(host, token, device_id, STATUS_PATH)
            if isinstance(sb, dict) and sb.get("checked_in"):
                pts = query_points(host, token, device_id)
                extra = f"\n- 总可用积分：{pts:,.2f}" if pts is not None else ""
                return "ALREADY_TODAY", f"ℹ️ 今日已签到{extra}（已自动续期）"
            if is_auth_failure(sc, sb):
                return "AUTH_EXPIRED", f"⚠️ 续期后再次鉴权失败（HTTP {sc}），请检查设备证明材料是否完整"
        else:
            msg = (sb or {}).get("message") or (sb or {}).get("msg") or "未知错误"
            return "AUTH_EXPIRED", f"⚠️ 鉴权失败（HTTP {sc}）：{msg}，请打开 Trae 桌面端刷新登录态，或运行 python trae_checkin.py --export-keys --save 引导自动续期"

    if not api_succeeded(sb):
        msg = (sb or {}).get("message") or (sb or {}).get("msg") or json.dumps(sb, ensure_ascii=False)[:120]
        if is_rate_limited(sc, sb):
            return "RATE_LIMITED", f"⏳ 服务端限频/临时故障：{msg}，建议错峰或稍后重试"
        return "STATUS_ERR", f"⚠️ 状态查询异常：HTTP {sc} {msg}"

    # 2) 领取
    cc, cb = api_call(host, token, device_id, CLAIM_PATH)
    if is_auth_failure(cc, cb):
        if _can_self_heal(cred):
            ok, msg = self_heal(cred)
            if ok:
                token = cred["token"]
                print(f"[trae] {msg}")
            else:
                return "AUTH_EXPIRED", f"⚠️ 领取时鉴权失败（HTTP {cc}）且自动续期失败：{msg}"
            cc, cb = api_call(host, token, device_id, CLAIM_PATH)
        else:
            msg = (cb or {}).get("message") or (cb or {}).get("msg") or "未知错误"
            return "AUTH_EXPIRED", f"⚠️ 领取时鉴权失败（HTTP {cc}）：{msg}，请打开 Trae 桌面端刷新登录态"

    if api_succeeded(cb):
        points = ((cb.get("data") or {}).get("points")) or cb.get("points")
        message = cb.get("message") or cb.get("msg") or ""
        pts = query_points(host, token, device_id)
        extra = f"\n- 总可用积分：{pts:,.2f}" if pts is not None else ""
        text = "签到成功" if message == "success" else message
        gain = f"本次 +{points} 积分" if points else text
        return "SUCCESS", f"✅ {gain}{extra}"

    msg = (cb or {}).get("message") or (cb or {}).get("msg") or json.dumps(cb, ensure_ascii=False)[:150]
    if is_rate_limited(cc, cb):
        return "RATE_LIMITED", f"⏳ 服务端限频/临时故障：{msg}，建议错峰或稍后重试"
    return "FAIL", f"⚠️ 签到未成功：HTTP {cc} {msg}"

# ---- 命令行功能 ----
def export_env():
    c = read_local_credential()
    if not c:
        print("未发现 Trae 登录态，请先在本机登录 Trae 桌面端")
        return 1
    values = {
        "TRAE_TOKEN": c["token"],
        "TRAE_DEVICE_ID": c["device_id"],
        "TRAE_USER_ID": c["user_id"],
        "TRAE_REFRESH_TOKEN": c["refresh_token"],
        "TRAE_DEVICE_KEY_PEM": base64.b64encode((c["device_key_pem"] or "").encode()).decode(),
        "TRAE_DEVICE_PUB_PEM": base64.b64encode((c["device_pub_pem"] or "").encode()).decode(),
        "TRAE_MACHINE_ID": c["machine_id"],
    }
    for k, v in values.items():
        print(f"{k}={v}")
    if c["expires_ms"]:
        exp = datetime.fromtimestamp(c["expires_ms"] / 1000, tz=timezone.utc)
        print(f"# token 过期时间(UTC): {exp:%Y-%m-%d %H:%M}")
    print("# 说明：TRAE_DEVICE_KEY_PEM 为设备 ECDSA 私钥，请勿外泄；它使脚本可在无 Trae 桌面端的")
    print("#       服务器上用 refreshToken 自动续期，无需每天手动刷新。")
    if "--save" in sys.argv:
        n = _save_env_values(values)
        if n:
            print(f"# 已将上述 {n} 个变量写回 .env")
        save_cache({
            "token": c["token"],
            "refresh_token": c["refresh_token"],
            "device_id": c["device_id"],
            "user_id": c["user_id"],
            "machine_id": c["machine_id"],
            "device_key_pem": c["device_key_pem"],
            "device_pub_pem": c["device_pub_pem"],
            "expires_ms": c["expires_ms"],
        })
        print(f"# 已写入续期缓存 {os.path.basename(CACHE_FILE)}")
    return 0

def renew_cmd():
    cred = resolve_credentials()
    if not _can_self_heal(cred):
        c = read_local_credential()
        if c:
            cred.update({k: c[k] for k in ("token", "device_id", "user_id", "expires_ms",
                                           "refresh_token", "device_key_pem",
                                           "device_pub_pem", "machine_id") if c.get(k)})
    if not _can_self_heal(cred):
        print("缺少自动续期材料（refreshToken / 设备私钥）。请先在本机登录 Trae 桌面端后运行：")
        print("  python trae_checkin.py --export-keys --save")
        return 1
    ok, msg = self_heal(cred)
    print(msg)
    return 0 if ok else 1

def main():
    if "--export-env" in sys.argv or "--export-keys" in sys.argv:
        sys.exit(export_env())
    if "--renew" in sys.argv:
        sys.exit(renew_cmd())

    title = "Trae Work 每日签到"
    cred = resolve_credentials()
    flag, content = checkin_once(cred)

    print(f"RESULT={flag} | {content}")

    try:
        sendNotify.serverJMy(title, content)
    except Exception as e:
        print(f"[warn] 通知发送失败: {e}")


if __name__ == "__main__":
    main()
