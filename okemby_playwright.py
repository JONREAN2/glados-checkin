import asyncio
import os
import random
import requests
from playwright.async_api import async_playwright

BASE = "https://www.okemby.com"
LOGIN_API = f"{BASE}/api/auth/login"
CHECKIN_API = f"{BASE}/api/checkin"

ACCOUNTS = os.getenv("OKEMBY_ACCOUNT")
TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      json={"chat_id": TG_CHAT_ID, "text": msg}, timeout=20)
    except:
        pass

async def run_account(browser, username, password):
    result = f"\n====== {username} ======\n"
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        viewport={"width": 390, "height": 844},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """)

    page = await context.new_page()

    try:
        # 1. 进 TG 小程序页面拿 CF + 验证环境
        await page.goto("https://www.okemby.com/telegram-miniapp", timeout=120000)
        await page.wait_for_timeout(random.uniform(5000, 8000))

        # 2. 登录
        login_res = await page.evaluate("""async (d) => {
            const r = await fetch(d.url, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ userName: d.user, password: d.pwd, verificationToken: null })
            });
            return await r.json();
        }""", {"url": LOGIN_API, "user": username, "pwd": password})

        token = login_res.get("token")
        if not token:
            result += "❌ 登录失败\n"
            return result

        result += "✅ 登录成功\n"
        await page.wait_for_timeout(random.uniform(2000, 3000))

        # 3. 关键：从页面直接获取最新 verificationToken
        vt = await page.evaluate("""() => {
            try {
                return window.verificationToken || 
                       window.localStorage.getItem('verificationToken') ||
                       document.body.getAttribute('data-verification-token') ||
                       '';
            } catch(e) { return ''; }
        }""")

        if not vt:
            result += "⚠️ 未获取到验证令牌，重试…\n"
            await page.goto("https://www.okemby.com/checkin", timeout=60000)
            await page.wait_for_timeout(3000)
            vt = await page.evaluate("""() => window.localStorage.getItem('verificationToken') || ''""")

        # 4. 完全按你抓包成功的格式去签到
        check = await page.evaluate("""async (d) => {
            const r = await fetch(d.url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + d.token,
                    "Referer": "https://www.okemby.com/telegram-miniapp",
                    "Origin": "https://www.okemby.com",
                    "Sec-Fetch-Site": "same-origin",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Dest": "empty"
                },
                body: JSON.stringify({ verificationToken: d.vt })
            });
            return await r.json();
        }""", {
            "url": CHECKIN_API,
            "token": token,
            "vt": vt
        })

        if check.get("success"):
            result += f"✅ 签到成功：{check.get('amount')} RCoin"
        else:
            result += f"❌ 签到失败：{check}"

    except Exception as e:
        result += f"❌ 异常：{str(e)[:200]}"
    finally:
        await context.close()

    return result

async def main():
    if not ACCOUNTS:
        print("未配置账号")
        return

    msg = "📢 OKEmby 自动签到（telegram-miniapp 过CF版）\n"
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        for acc in ACCOUNTS.split("&"):
            try:
                u, p = acc.split("#", 1)
                msg += await run_account(browser, u, p)
                await asyncio.sleep(random.uniform(20, 30))
            except Exception as e:
                msg += f"\n❌ 账号解析失败：{acc}"

        await browser.close()

    print(msg)
    send_tg(msg)

if __name__ == "__main__":
    asyncio.run(main())