import asyncio
import os
import random
import requests
from playwright.async_api import async_playwright

BASE = "https://www.okemby.com"

TG_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
ACCOUNTS = os.getenv("OKEMBY_ACCOUNT")  # 多账号格式: user1#pass1&user2#pass2

def send_tg(msg):
    if not TG_TOKEN or not TG_CHAT_ID:
        print("⚠ 未配置 TG 通知")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      data={"chat_id": TG_CHAT_ID, "text": msg},
                      timeout=20)
    except Exception as e:
        print("⚠ TG 发送失败:", e)

async def run_account(username, password):
    result = f"\n====== {username} ======\n"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1️⃣ 打开首页，触发 CF
            print("🌐 打开首页")
            await page.goto(BASE, timeout=60000)
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(random.randint(5000,8000))

            # 2️⃣ 点击首页登录按钮（模拟用户）
            print("🔐 点击登录按钮")
            await page.locator("a").filter(has_text="登录").click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(random.randint(3000,5000))

            # 3️⃣ 等待密码输入框出现
            await page.wait_for_selector("input[type='password']", timeout=60000)

            # 4️⃣ 填写账号密码登录
            await page.fill("input[type='text']", username)
            await page.fill("input[type='password']", password)
            await page.locator("button").filter(has_text="登录").click()

            # 等待登录完成
            await page.wait_for_timeout(random.randint(4000,6000))

            # 5️⃣ 使用浏览器 fetch API 调签到（自动通过人机验证）
            print("🚀 直接调用浏览器内 fetch 签到接口")
            retries = 3
            for i in range(retries):
                try:
                    result_json = await page.evaluate("""
                    async () => {
                        const res = await fetch('/api/checkin', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'}
                        });
                        return await res.json();
                    }
                    """)
                    if result_json.get("success"):
                        amount = result_json.get("amount", 0)
                        result += f"✅ 签到成功，获得 {amount} RCoin\n"
                        print(result_json)
                        break
                    else:
                        result += f"⚠ 第{i+1}次签到失败: {result_json.get('message')}\n"
                except Exception as e:
                    result += f"⚠ 第{i+1}次签到异常: {e}\n"

        except Exception as e:
            print("❌ 异常:", e)
            result += f"❌ 异常: {e}\n"
            await page.screenshot(path=f"{username}_error.png")
            print(f"📸 已保存截图 {username}_error.png")

        await browser.close()
    return result

async def main():
    if not ACCOUNTS:
        print("❌ 未配置 OKEMBY_ACCOUNT")
        return

    accounts = ACCOUNTS.split("&")
    final_msg = "📢 OKEmby 自动签到结果\n"

    for acc in accounts:
        try:
            username, password = acc.split("#")
        except:
            final_msg += f"⚠ 账号格式错误: {acc}\n"
            continue

        res = await run_account(username, password)
        final_msg += res

    print(final_msg)
    send_tg(final_msg)

if __name__ == "__main__":
    asyncio.run(main())