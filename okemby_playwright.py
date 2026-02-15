import asyncio
import os
import random
import requests
from playwright.async_api import async_playwright

BASE = "https://www.okemby.com"
LOGIN_URL = f"{BASE}/login"
CHECKIN_URL = f"{BASE}/checkin"

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
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
    )

    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    """)

    page = await context.new_page()
    try:
        # 1. 进主页过 CF 验证
        await page.goto(BASE, timeout=120000)
        await page.wait_for_timeout(random.uniform(3, 6))
        await page.wait_for_selector("body", timeout=60000)
        await page.wait_for_timeout(random.uniform(2, 4))

        # 2. 去登录页
        await page.goto(LOGIN_URL, timeout=60000)
        await page.wait_for_timeout(random.uniform(2, 4))

        # 3. 模拟人工输入登录（关键！）
        await page.fill('input[name="userName"]', username, delay=random.randint(120, 200))
        await page.fill('input[name="password"]', password, delay=random.randint(100, 180))
        await page.wait_for_timeout(random.uniform(1, 2))
        await page.click('button[type="submit"]', delay=random.randint(300, 600))
        await page.wait_for_timeout(random.uniform(3, 5))

        # 判断是否登录成功
        if "login" in page.url:
            result += "❌ 登录失败（账号或密码错误）\n"
            return result

        result += "✅ 登录成功\n"

        # 4. 进入签到页
        await page.goto(CHECKIN_URL, timeout=60000)
        await page.wait_for_timeout(random.uniform(2, 4))

        # 5. 点击签到按钮
        checkin_btn = page.locator('button:has-text("每日签到")')
        if await checkin_btn.count() > 0:
            await checkin_btn.click(delay=random.randint(400, 700))
            await page.wait_for_timeout(random.uniform(2, 3))
            result += "✅ 签到成功"
        else:
            result += "ℹ️ 今日已签到"

    except Exception as e:
        result += f"❌ 异常：{str(e)[:120]}"
    finally:
        await context.close()
    return result

async def main():
    if not ACCOUNTS:
        print("未配置账号")
        return

    msg = "📢 OKEmby 自动签到（过CF修复版）\n"
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--start-maximized",
            ]
        )

        for acc in ACCOUNTS.split("&"):
            try:
                u, p = acc.split("#", 1)
                msg += await run_account(browser, u, p)
                await asyncio.sleep(random.uniform(20, 40))
            except Exception as e:
                msg += f"\n❌ 账号解析失败：{acc}"

        await browser.close()

    print(msg)
    send_tg(msg)

if __name__ == "__main__":
    asyncio.run(main())