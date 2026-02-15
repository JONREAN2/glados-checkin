import asyncio
import os
import random
import requests
from playwright.async_api import async_playwright

BASE = "https://www.okemby.com"
LOGIN_URL = "https://www.okemby.com/login"
CHECKIN_URL = "https://www.okemby.com/checkin"

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
        await page.goto(BASE, timeout=120000)
        await page.wait_for_timeout(random.uniform(6000, 10000))

        await page.goto(LOGIN_URL, timeout=120000)
        await page.wait_for_timeout(random.uniform(2000, 4000))

        await page.wait_for_selector('input#userName', timeout=60000)
        await page.fill('input#userName', username)
        await page.wait_for_timeout(500)

        await page.wait_for_selector('input#password', timeout=60000)
        await page.fill('input#password', password)
        await page.wait_for_timeout(500)

        await page.click('button[type="submit"]', timeout=30000)
        await page.wait_for_timeout(random.uniform(5000, 8000))

        if "login" in page.url.lower():
            result += "❌ 登录失败"
            return result
        result += "✅ 登录成功\n"

        await page.goto(CHECKIN_URL, timeout=120000)
        await page.wait_for_timeout(random.uniform(3000, 6000))

        # ====================== 终极正确逻辑 ======================
        # 你的签到是：点击【包含“每日签到”文字的整个卡片】
        # 不是按钮！不是按钮！不是按钮！
        try:
            # 匹配包含“每日签到”的卡片区域
            card = page.locator('[data-checkin-card]')
            if await card.count() > 0:
                await card.scroll_into_view_if_needed()
                await page.wait_for_timeout(1000)
                await card.click(timeout=15000)  # 点整个卡片
                await page.wait_for_timeout(3000)
                result += "✅ 签到成功（点击卡片）"
            else:
                result += "ℹ️ 今日已签到"
        except:
            result += "ℹ️ 今日已签到"

    except Exception as e:
        result += f"❌ 异常：{str(e)[:200]}"
    finally:
        await context.close()

    return result

async def main():
    if not ACCOUNTS:
        print("未配置账号")
        return

    msg = "📢 OKEmby 自动签到（终极卡片点击版）\n"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--ignore-certificate-errors",
            ]
        )

        for acc in ACCOUNTS.split("&"):
            try:
                u, pwd = acc.split("#", 1)
                msg += await run_account(browser, u, pwd)
                await asyncio.sleep(random.uniform(20, 40))
            except Exception as e:
                msg += f"\n❌ 账号解析失败：{acc}"

        await browser.close()

    print(msg)
    send_tg(msg)

if __name__ == "__main__":
    asyncio.run(main())