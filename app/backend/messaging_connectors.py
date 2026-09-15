from typing import Any
from urllib.parse import urlparse

import aiohttp


async def _request(method: str, url: str, *, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        async with session.request(method, url, headers=headers, json=payload) as response:
            value = await response.json(content_type=None) if response.content_length != 0 else {}
            if response.status >= 400:
                raise ValueError(f"Messaging provider returned HTTP {response.status}: {value}")
            return value if isinstance(value, dict) else {"result": value}


async def send_messaging_message(connection: dict[str, Any], secrets: dict[str, str], *, target: str, text: str) -> dict[str, Any]:
    provider = connection["provider"]
    if provider == "line":
        result = await _request("POST", "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {secrets['channel_access_token']}"},
            payload={"to": target, "messages": [{"type": "text", "text": text[:5000]}]})
        return {"sent": True, "provider": provider, "result": result}
    if provider == "slack":
        result = await _request("POST", "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {secrets['bot_token']}"}, payload={"channel": target, "text": text})
        if result.get("ok") is not True:
            raise ValueError(f"Slack rejected the message: {result.get('error', result)}")
        return {"sent": True, "provider": provider, "channel": result.get("channel"), "timestamp": result.get("ts")}
    webhook_url = secrets["webhook_url"]
    parsed = urlparse(webhook_url)
    if parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com", "canary.discord.com", "ptb.discord.com"}:
        raise ValueError("Discord webhook URL must use an official discord.com host")
    await _request("POST", webhook_url + ("&" if "?" in webhook_url else "?") + "wait=true", payload={"content": text[:2000]})
    return {"sent": True, "provider": provider}


async def test_messaging_connection(connection: dict[str, Any], secrets: dict[str, str]) -> dict[str, Any]:
    provider = connection["provider"]
    if provider == "line":
        value = await _request("GET", "https://api.line.me/v2/bot/info", headers={"Authorization": f"Bearer {secrets['channel_access_token']}"})
        return {"ok": True, "message": f"Connected to LINE bot {value.get('displayName', '')}".strip()}
    if provider == "slack":
        value = await _request("POST", "https://slack.com/api/auth.test", headers={"Authorization": f"Bearer {secrets['bot_token']}"})
        if value.get("ok") is not True: raise ValueError(f"Slack authentication failed: {value.get('error', value)}")
        return {"ok": True, "message": f"Connected to Slack workspace {value.get('team', '')}".strip()}
    parsed = urlparse(secrets["webhook_url"])
    if parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com", "canary.discord.com", "ptb.discord.com"}:
        raise ValueError("Discord webhook URL must use an official discord.com host")
    value = await _request("GET", secrets["webhook_url"])
    return {"ok": True, "message": f"Connected to Discord webhook {value.get('name', '')}".strip()}
