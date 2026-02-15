import asyncio
import os
import random
import requests
from playwright.async_api import async_playwright

BASE = "https://www.okemby.com"

TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠ 未配置TG通知")
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {
        "chat_id": TG_CHAT_ID,
        "text": msg
    }
    requests.post(url, data=data)

async def run_account(username, password):
    result = f"\n====== {username} ======\n"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("🌐 访问首页 (等待CF)")
            await page.goto(BASE, timeout=60000)
            await page.wait_for_timeout(random.randint(4000,7000))

            print("🔐 登录")
            await page.goto(f"{BASE}/login")
            await page.fill('input[placeholder="用户名"]', username)
            await page.fill('input[placeholder="密码"]', password)
            await page.click("button:has-text('登录')")
            await page.wait_for_timeout(5000)

            print("📊 进入dashboard")
            await page.goto(f"{BASE}/dashboard")
            await page.wait_for_timeout(5000)

            content = await page.content()

            if "已签到" in content:
                print("✅ 今日已签到")
                result += "✅ 今日已签到\n"
            else:
                print("🟡 尝试签到")
                try:
                    await page.click("button:has-text('签到')")
                    await page.wait_for_timeout(3000)
                    result += "✅ 签到成功\n"
                except:
                    result += "⚠ 未找到签到按钮\n"

        except Exception as e:
            result += f"❌ 异常: {str(e)}\n"
            await page.screenshot(path=f"{username}_error.png")
            print("❌ 发生异常，已截图")

        await browser.close()

    return result

async def main():
    accounts = os.getenv("OKEMBY_ACCOUNT")

    if not accounts:
        print("❌ 未设置 OKEMBY_ACCOUNT")
        return

    accounts = accounts.split("&")

    final_msg = "📢 OKEmby 自动签到结果\n"

    for acc in accounts:
        username, password = acc.split("#")
        res = await run_account(username, password)
        final_msg += res

    print(final_msg)
    send_tg(final_msg)

if name == "__main__":
    asyncio.run(main())