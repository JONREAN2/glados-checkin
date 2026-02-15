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
        # 1. 过 CF
        await page.goto(BASE, timeout=120000)
        await page.wait_for_timeout(random.uniform(3000, 5000))

        # 2. 登录拿 token
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
        await page.wait_for_timeout(random.uniform(1000, 2000))

        # 3. 关键：获取 verificationToken（你抓包里那个超长参数）
        vt = await page.evaluate("""() => {
            return window.localStorage.getItem('verificationToken') || 
                   window.sessionStorage.getItem('verificationToken') || 
                   '';
        }""")

        if not vt:
            # 备用：从页面/接口再取一次
            await page.goto(BASE + "/checkin", timeout=60000)
            await page.wait_for_timeout(random.uniform(2000, 3000))
            vt = await page.evaluate("""() => {
                return window.localStorage.getItem('verificationToken') || '';
            }""")

        # 4. 带 verificationToken 签到（完全复现你抓包的成功请求）
        check = await page.evaluate("""async (d) => {
            const r = await fetch(d.url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: "Bearer " + d.token
                },
                body: JSON.stringify({ verificationToken: d.vt })
            });
            return await r.json();
        }""", {"url": CHECKIN_API, "token": token, "vt": vt})

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

    msg = "📢 OKEmby 自动签到（带verificationToken版）\n"
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
                await asyncio.sleep(random.uniform(15, 30))
            except Exception as e:
                msg += f"\n❌ 账号解析失败：{acc}"

        await browser.close()

    print(msg)
    send_tg(msg)

if __name__ == "__main__":
    asyncio.run(main())