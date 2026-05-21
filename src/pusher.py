import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import httpx

logger = logging.getLogger(__name__)


class FeishuPusher:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def push(self, card: dict) -> bool:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    self.webhook_url,
                    headers={"Content-Type": "application/json"},
                    content=json.dumps(card, ensure_ascii=False).encode("utf-8"),
                )
                data = response.json()
                if data.get("code") == 0:
                    logger.info("Feishu push successful")
                    return True
                else:
                    logger.error(f"Feishu push failed: {data}")
                    return False
        except Exception as e:
            logger.error(f"Feishu push error: {e}")
            return False


class DingTalkPusher:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def push(self, markdown_text: str, title: str = "每日跨界灵感早报") -> bool:
        try:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": markdown_text,
                },
            }
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    self.webhook_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                data = response.json()
                if data.get("errcode") == 0:
                    logger.info("DingTalk push successful")
                    return True
                else:
                    logger.error(f"DingTalk push failed: {data}")
                    return False
        except Exception as e:
            logger.error(f"DingTalk push error: {e}")
            return False


class EmailPusher:
    def __init__(self, smtp_host: str, smtp_port: int, sender: str,
                 password: str, recipient: str):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender = sender
        self.password = password
        self.recipient = recipient

    def push(self, markdown_text: str) -> bool:
        try:
            html_content = self._markdown_to_html(markdown_text)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "☕ 每日跨界灵感早报"
            msg["From"] = self.sender
            msg["To"] = self.recipient
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)

            logger.info("Email push successful")
            return True
        except Exception as e:
            logger.error(f"Email push error: {e}")
            return False

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body {{ font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
       max-width: 600px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.8; }}
h1 {{ color: #1a1a2e; font-size: 24px; }}
h2 {{ color: #16213e; font-size: 20px; margin-top: 30px; }}
blockquote {{ border-left: 4px solid #e94560; padding-left: 16px;
             color: #e94560; margin: 16px 0; }}
hr {{ border: none; border-top: 1px solid #eee; margin: 24px 0; }}
</style>
</head>
<body>
{md.replace(chr(10), "<br>")}
</body>
</html>"""