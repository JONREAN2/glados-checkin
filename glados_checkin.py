import os
import random
import time
import requests
import datetime
from typing import Tuple, Optional

class GLaDOSChecker:
    API_BASE = "https://glados.rocks/api/user"
    CHECKIN_URL = f"{API_BASE}/checkin"
    STATUS_URL = f"{API_BASE}/status"
    
    def __init__(self):
        self._validate_env()
        self.email = os.environ["GLADOS_EMAIL"]
        self.cookie = os.environ["GLADOS_COOKIE"]
        self.email = os.environ["GLADOS_EMAIL2"]
        self.cookie = os.environ["GLADOS_COOKIE2"]
        self.bot_token = os.environ["TG_BOT_TOKEN"]
        self.chat_id = os.environ["TG_CHAT_ID"]
        
    def _validate_env(self):
        required = {"GLADOS_EMAIL", "GLADOS_COOKIE","GLADOS_EMAIL2", "GLADOS_COOKIE2","TG_BOT_TOKEN", "TG_CHAT_ID"}
        missing = required - set(os.environ)
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")

    @staticmethod
    def _current_time() -> str:
        return (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")

    def _gen_headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Cookie": self.cookie,
            "User-Agent": random.choice([
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
            ]),
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://glados.rocks"
        }

    def _parse_response(self, response: requests.Response) -> dict:
        try:
            return response.json()
        except ValueError:
            return {"message": f"Invalid JSON: {response.text[:50]}"}

    def check_status(self) -> Tuple[bool, str]:
        try:
            resp = requests.get(
                self.STATUS_URL,
                headers=self._gen_headers(),
                timeout=15
            )
            resp.raise_for_status()
            data = self._parse_response(resp)
            days = float(data.get("data", {}).get("leftDays", 0))
            return True, f"剩余天数: {days:.1f} 🗓️"
        except Exception as e:
            return False, f"状态查询失败: {str(e)} ❌"

    def perform_checkin(self) -> Tuple[bool, str]:
        try:
            resp = requests.post(
                self.CHECKIN_URL,
                headers=self._gen_headers(),
                json={"token": "glados.one"},
                timeout=15
            )
            resp.raise_for_status()
            data = self._parse_response(resp)
            return self._handle_checkin_result(data.get("message", ""))
        except Exception as e:
            return False, f"签到失败: {str(e)} ❌"

    def _handle_checkin_result(self, msg: str) -> Tuple[bool, str]:
        if "Please Try Tomorrow" in msg:
            return False, "请明天再试 ⏳"
        if "Got" in msg:
            points = msg.split("Got ")[1].split(" ")[0]
            return True, f"获得 {points} 积分 🎉"
        return False, f"未知响应: {msg} ❓"

    def send_notification(self, status: str, checkin_result: str):
        message = (
            f"🕒 北京时间: {self._current_time()}\n"
            f"📧 账户: {self.email}\n\n"
            f"🔔 签到结果: {checkin_result}\n"
            f"📊 账户状态: {status}\n\n"
            "✅ 任务执行完成"
        )
        
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                },
                timeout=10
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"⚠️ 通知发送失败: {str(e)}")

    def execute(self):
        print(f"🔍 开始处理账户: {self.email}")
        time.sleep(random.uniform(1, 3))
        
        success, checkin_result = self.perform_checkin()
        _, status_result = self.check_status()
        
        self.send_notification(status_result, checkin_result)
        print("🏁 流程执行完毕")

if __name__ == "__main__":
    checker = GLaDOSChecker()
    checker.execute()
