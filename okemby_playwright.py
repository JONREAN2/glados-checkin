import os
import requests
import json

BASE = "https://www.okemby.com"

TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
ACCOUNTS = os.getenv("OKEMBY_ACCOUNT")  # 多账号格式: user1#pass1&user2#pass2

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "okemby-api-checkin-bot"
}

def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠ 未配置 TG 通知")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg}, timeout=20)
    except Exception as e:
        print("⚠ TG 发送失败:", e)

def login(user, password):
    url = f"{BASE}/api/auth/login"
    payload = {
        "userName": user,
        "password": password,
        "verificationToken": None
    }
    try:
        r = requests.post(url, headers=HEADERS, json=payload, timeout=20)
        data = r.json()
        if r.status_code == 200 and "token" in data:
            return data["token"]
        else:
            return None, data.get("message", "未知错误")
    except Exception as e:
        return None, str(e)

def checkin(token):
    url = f"{BASE}/api/checkin"
    headers = HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.post(url, headers=headers, timeout=20)
        data = r.json()
        if r.status_code == 200 and data.get("success"):
            return True, data
        else:
            return False, data.get("message", "签到失败")
    except Exception as e:
        return False, str(e)

def main():
    if not ACCOUNTS:
        print("❌ 未配置 OKEMBY_ACCOUNT")
        return

    accounts = ACCOUNTS.split("&")
    final_msg = "📢 OKEmby API 自动签到结果\n"

    for acc in accounts:
        try:
            user, password = acc.split("#")
        except:
            final_msg += f"⚠ 账号格式错误: {acc}\n"
            continue

        final_msg += f"\n====== {user} ======\n"

        token, err = login(user, password), None
        if isinstance(token, tuple):
            token, err = token
        if not token:
            final_msg += f"❌ 登录失败: {err}\n"
            continue

        success, res = checkin(token)
        if success:
            amount = res.get("amount", 0)
            final_msg += f"✅ 签到成功，获得 {amount} RCoin\n"
        else:
            final_msg += f"❌ 签到失败: {res}\n"

    print(final_msg)
    send_tg(final_msg)

if __name__ == "__main__":
    main()