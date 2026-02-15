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
        print("⚠ 未配置 TG 通知")
        return

    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {
        "chat_id": TG_CHAT_ID,
        "text": msg
    }

    try:
        requests.post(url, data=data, timeout=20)
    except Exception as e:
        print("TG 发送失败:", e)


async def run_account(username, password):
    result = f"\n====== {username} ======\n"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("🌐 访问首页 (等待CF验证)")
            await page.goto(BASE, timeout=60000)
            await page.wait_for_timeout(random.randint(4000, 7000))

            print("🔐 打开登录页")
            await page.goto(f"{BASE}/login")

            # 等待用户名输入框出现（关键）
            await page.wait_for_selector('input[name="userName"]', timeout=60000)

            print("✍ 填写账号密码")
            await page.fill('input[name="userName"]', username)
            await page.fill('input[name="password"]', password)

            print("🚀 点击登录")
            try:
                await page.click('button[type="submit"]')
            except:
                await page.locator("button").filter(has_text="登录").click()

            await page.wait_for_timeout(random.randint(4000, 6000))

            print("📊 进入 dashboard")
            await page.goto(f"{BASE}/dashboard")
            await page.wait_for_timeout(random.randint(4000, 6000))

            content = await page.content()

            if "已签到" in content:
                print("✅ 今日已签到")
                result += "✅ 今日已签到\n"
            else:
                print("🟡 尝试签到")
                try:
                    await page.locator("button").filter(has_text="签到").click()
                    await page.wait_for_timeout(3000)
                    print("✅ 签到成功")
                    result += "✅ 签到成功\n"
                except:
                    print("⚠ 未找到签到按钮")
                    result += "⚠ 未找到签到按钮\n"

        except Exception as e:
            print("❌ 异常:", e)
            result += f"❌ 异常: {e}\n"
            await page.screenshot(path=f"{username}_error.png")
            print(f"📸 已保存截图 {username}_error.png")

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
        try:
            username, password = acc.split("#")
        except:
            print("⚠ 账号格式错误:", acc)
            continue

        res = await run_account(username, password)
        final_msg += res

    print(final_msg)
    send_tg(final_msg)


if __name__ == "__main__":
    asyncio.run(main())