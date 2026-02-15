import asyncio
import os
import random
import requests
from playwright.async_api import async_playwright

BASE = "https://www.okemby.com"
LOGIN_API = f"{BASE}/api/auth/login"
STATUS_API = f"{BASE}/api/checkin/status"
CHECKIN_API = f"{BASE}/api/checkin"

ACCOUNTS = os.getenv("OKEMBY_ACCOUNT")
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")


# =============================
# TG 推送（不用 JS，最稳）
# =============================
def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠ 未配置 TG")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT_ID,
                "text": msg
            },
            timeout=20
        )
    except Exception as e:
        print("TG 发送失败:", e)


# =============================
# 单账号执行
# =============================
async def run_account(browser, username, password):
    result = f"\n====== {username} ======\n"

    context = await browser.new_context()
    page = await context.new_page()

    try:
        # 1️⃣ 访问首页，过 CF
        await page.goto(BASE, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(random.randint(6000, 10000))

        # 2️⃣ 浏览器内登录
        login = await page.evaluate(
            """async ({login_url, username, password}) => {
                const r = await fetch(login_url, {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        userName: username,
                        password: password,
                        verificationToken: null
                    })
                });
                return await r.json();
            }""",
            {
                "login_url": LOGIN_API,
                "username": username,
                "password": password
            }
        )

        token = login.get("token")
        if not token:
            return result + "❌ 登录失败\n"

        result += "✅ 登录成功\n"

        # 3️⃣ 查询签到状态
        status = await page.evaluate(
            """async ({status_url, token}) => {
                const r = await fetch(status_url, {
                    headers: {
                        "Authorization": "Bearer " + token
                    }
                });
                return await r.json();
            }""",
            {
                "status_url": STATUS_API,
                "token": token
            }
        )

        if status.get("hasCheckedInToday"):
            result += f"ℹ 今日已签到 {status.get('amount')} RCoin\n"
            await context.close()
            return result

        # 4️⃣ 执行签到
        checkin = await page.evaluate(
            """async ({checkin_url, token}) => {
                const r = await fetch(checkin_url, {
                    method: "POST",
                    headers: {
                        "Authorization": "Bearer " + token
                    }
                });
                return await r.json();
            }""",
            {
                "checkin_url": CHECKIN_API,
                "token": token
            }
        )

        if checkin.get("success"):
            result += f"✅ 签到成功 {checkin.get('amount')} RCoin\n"
        else:
            result += f"❌ 签到失败: {checkin}\n"

    except Exception as e:
        result += f"❌ 异常: {e}\n"
        await page.screenshot(path=f"{username}_error.png")

    await context.close()
    return result


# =============================
# 主程序
# =============================
async def main():
    if not ACCOUNTS:
        print("❌ 未配置 OKEMBY_ACCOUNT")
        return

    final_msg = "📢 OKEmby 自动签到结果\n"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        accounts = ACCOUNTS.split("&")

        for i, acc in enumerate(accounts):
            username, password = acc.split("#")

            # 多账号延迟，降低风控
            if i > 0:
                delay = random.randint(20, 60)
                print(f"⏳ 等待 {delay} 秒避免风控...")
                await asyncio.sleep(delay)

            res = await run_account(browser, username, password)
            final_msg += res

        await browser.close()

    print(final_msg)
    send_tg(final_msg)


if __name__ == "__main__":
    asyncio.run(main())