import asyncio
import base64
import email
import imaplib
import json
import poplib
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.policy import default
from typing import Any
from urllib.parse import quote

import aiohttp


def _message_summary(message: email.message.Message, message_id: str) -> dict[str, Any]:
    body = ""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                try:
                    body = part.get_content()
                except Exception:
                    body = ""
                break
    else:
        try:
            body = message.get_content()
        except Exception:
            body = ""
    return {
        "id": message_id,
        "subject": str(message.get("Subject", "")),
        "from": str(message.get("From", "")),
        "to": str(message.get("To", "")),
        "date": str(message.get("Date", "")),
        "body_preview": str(body)[:4000],
    }


async def _oauth_token(connection: dict[str, Any], secrets: dict[str, str]) -> str:
    provider = connection["provider"]
    config = connection.get("public_config") or {}
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        if provider == "microsoft365":
            url = f"https://login.microsoftonline.com/{quote(str(config['tenant_id']))}/oauth2/v2.0/token"
            data = {
                "client_id": config["client_id"],
                "client_secret": secrets.get("client_secret", ""),
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }
        else:
            url = "https://oauth2.googleapis.com/token"
            data = {
                "client_id": config["client_id"],
                "client_secret": secrets.get("client_secret", ""),
                "refresh_token": secrets.get("refresh_token", ""),
                "grant_type": "refresh_token",
            }
        async with session.post(url, data=data) as response:
            payload = await response.json(content_type=None)
            if response.status >= 400 or not payload.get("access_token"):
                raise ValueError(f"OAuth token request failed ({response.status}): {payload}")
            return str(payload["access_token"])


async def list_messages(connection: dict[str, Any], secrets: dict[str, str], *, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 50))
    provider = connection["provider"]
    if provider == "microsoft365":
        token = await _oauth_token(connection, secrets)
        mailbox = quote(connection["email_address"])
        params = {"$top": str(limit), "$select": "id,subject,from,toRecipients,receivedDateTime,bodyPreview,isRead"}
        if query:
            params["$search"] = f'"{query[:200]}"'
        headers = {"Authorization": f"Bearer {token}", "ConsistencyLevel": "eventual"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages", params=params, headers=headers) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"Microsoft Graph mail request failed ({response.status}): {payload}")
        return [
            {
                "id": item.get("id"),
                "subject": item.get("subject"),
                "from": ((item.get("from") or {}).get("emailAddress") or {}).get("address"),
                "to": [((v.get("emailAddress") or {}).get("address")) for v in item.get("toRecipients") or []],
                "date": item.get("receivedDateTime"),
                "is_read": item.get("isRead"),
                "body_preview": item.get("bodyPreview"),
            }
            for item in payload.get("value", [])
        ]
    if provider == "gmail":
        token = await _oauth_token(connection, secrets)
        mailbox = quote(connection["email_address"])
        headers = {"Authorization": f"Bearer {token}"}
        params = {"maxResults": str(limit)}
        if query:
            params["q"] = query[:500]
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.get(f"https://gmail.googleapis.com/gmail/v1/users/{mailbox}/messages", params=params, headers=headers) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"Gmail list request failed ({response.status}): {payload}")
            results = []
            for item in payload.get("messages", [])[:limit]:
                async with session.get(
                    f"https://gmail.googleapis.com/gmail/v1/users/{mailbox}/messages/{quote(item['id'])}",
                    params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Date"]},
                    headers=headers,
                ) as detail_response:
                    detail = await detail_response.json(content_type=None)
                    if detail_response.status >= 400:
                        continue
                metadata = {h.get("name", "").lower(): h.get("value") for h in (detail.get("payload") or {}).get("headers", [])}
                results.append({"id": item["id"], "thread_id": detail.get("threadId"), "subject": metadata.get("subject"), "from": metadata.get("from"), "to": metadata.get("to"), "date": metadata.get("date"), "body_preview": detail.get("snippet")})
            return results
    return await asyncio.to_thread(_generic_list_messages, connection, secrets, query, limit)


def _generic_list_messages(connection: dict[str, Any], secrets: dict[str, str], query: str, limit: int) -> list[dict[str, Any]]:
    config = connection.get("public_config") or {}
    username = str(config.get("username") or connection["email_address"])
    password = secrets.get("password", "")
    protocol = config.get("receive_protocol", "imap")
    if protocol == "imap":
        cls = imaplib.IMAP4_SSL if config.get("receive_security") == "ssl" else imaplib.IMAP4
        client = cls(str(config["receive_host"]), int(config["receive_port"]), timeout=30)
        try:
            if config.get("receive_security") == "starttls":
                client.starttls(ssl_context=ssl.create_default_context())
            client.login(username, password)
            client.select("INBOX", readonly=True)
            criterion = f'TEXT "{query.replace(chr(34), "")[:200]}"' if query else "ALL"
            status, data = client.search(None, criterion)
            if status != "OK":
                raise ValueError("IMAP search failed")
            ids = data[0].split()[-limit:][::-1]
            results = []
            for item_id in ids:
                status, raw = client.fetch(item_id, "(RFC822)")
                if status == "OK" and raw and isinstance(raw[0], tuple):
                    results.append(_message_summary(email.message_from_bytes(raw[0][1], policy=default), item_id.decode()))
            return results
        finally:
            try:
                client.logout()
            except Exception:
                pass
    cls = poplib.POP3_SSL if config.get("receive_security") == "ssl" else poplib.POP3
    client = cls(str(config["receive_host"]), int(config["receive_port"]), timeout=30)
    try:
        if config.get("receive_security") == "starttls":
            client.stls(context=ssl.create_default_context())
        client.user(username)
        client.pass_(password)
        count = len(client.list()[1])
        results = []
        for index in range(count, max(0, count - min(limit * 3, 100)), -1):
            raw = b"\r\n".join(client.retr(index)[1])
            parsed = email.message_from_bytes(raw, policy=default)
            summary = _message_summary(parsed, str(index))
            if not query or query.lower() in json.dumps(summary).lower():
                results.append(summary)
            if len(results) >= limit:
                break
        return results
    finally:
        client.quit()


async def send_message(connection: dict[str, Any], secrets: dict[str, str], *, to: list[str], cc: list[str], bcc: list[str], subject: str, body: str, is_html: bool = False) -> dict[str, Any]:
    provider = connection["provider"]
    if provider == "microsoft365":
        token = await _oauth_token(connection, secrets)
        mailbox = quote(connection["email_address"])
        def recipients(values: list[str]) -> list[dict[str, dict[str, str]]]:
            return [{"emailAddress": {"address": value}} for value in values]

        payload = {"message": {"subject": subject, "body": {"contentType": "HTML" if is_html else "Text", "content": body}, "toRecipients": recipients(to), "ccRecipients": recipients(cc), "bccRecipients": recipients(bcc)}, "saveToSentItems": True}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(f"https://graph.microsoft.com/v1.0/users/{mailbox}/sendMail", json=payload, headers=headers) as response:
                text = await response.text()
                if response.status >= 400:
                    raise ValueError(f"Microsoft Graph send failed ({response.status}): {text[:1000]}")
        return {"accepted": True, "provider": provider, "status": 202}
    message = EmailMessage()
    message["From"] = connection["email_address"]
    message["To"] = ", ".join(to)
    if cc:
        message["Cc"] = ", ".join(cc)
    if provider == "gmail" and bcc:
        message["Bcc"] = ", ".join(bcc)
    message["Subject"] = subject
    if is_html:
        message.set_content("This message contains HTML content.")
        message.add_alternative(body, subtype="html")
    else:
        message.set_content(body)
    if provider == "gmail":
        token = await _oauth_token(connection, secrets)
        mailbox = quote(connection["email_address"])
        payload = {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(f"https://gmail.googleapis.com/gmail/v1/users/{mailbox}/messages/send", json=payload, headers=headers) as response:
                result = await response.json(content_type=None)
                if response.status >= 400:
                    raise ValueError(f"Gmail send failed ({response.status}): {result}")
        return {"accepted": True, "provider": provider, "message_id": result.get("id")}
    await asyncio.to_thread(_smtp_send, connection, secrets, message, to + cc + bcc)
    return {"accepted": True, "provider": provider}


def _smtp_client(connection: dict[str, Any], secrets: dict[str, str]) -> smtplib.SMTP:
    config = connection.get("public_config") or {}
    host = str(config["smtp_host"])
    port = int(config["smtp_port"])
    cls = smtplib.SMTP_SSL if config.get("smtp_security") == "ssl" else smtplib.SMTP
    stage = "connect"
    try:
        client = cls(host, port, timeout=15)
        stage = "EHLO"
        client.ehlo()
        if config.get("smtp_security") == "starttls":
            stage = "STARTTLS"
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        stage = "authentication"
        client.login(str(config.get("username") or connection["email_address"]), secrets.get("password", ""))
        return client
    except (TimeoutError, socket.timeout) as exc:
        if "client" in locals():
            client.close()
        raise ValueError(f"SMTP {stage} timed out for {host}:{port}; check host, port, security mode, firewall and container egress") from exc
    except (OSError, smtplib.SMTPException) as exc:
        if "client" in locals():
            client.close()
        raise ValueError(f"SMTP {stage} failed for {host}:{port}: {exc}") from exc


def _smtp_send(connection: dict[str, Any], secrets: dict[str, str], message: EmailMessage, recipients: list[str]) -> None:
    client = _smtp_client(connection, secrets)
    try:
        client.send_message(message, to_addrs=recipients)
    except (TimeoutError, socket.timeout) as exc:
        raise ValueError("SMTP send timed out after authentication; check relay/firewall policy") from exc
    except (OSError, smtplib.SMTPException) as exc:
        raise ValueError(f"SMTP send was rejected: {exc}") from exc
    finally:
        # Do not wait for QUIT: the message may already be accepted and a slow
        # QUIT response must not turn a successful send into an apparent retry.
        client.close()


def _smtp_test(connection: dict[str, Any], secrets: dict[str, str]) -> None:
    client = _smtp_client(connection, secrets)
    client.close()


async def test_mail_connection(connection: dict[str, Any], secrets: dict[str, str]) -> dict[str, Any]:
    messages = await list_messages(connection, secrets, limit=1)
    if connection["provider"] == "generic":
        await asyncio.to_thread(_smtp_test, connection, secrets)
        return {
            "ok": True,
            "message": f"Incoming mail and SMTP authentication succeeded; read test returned {len(messages)} message(s)",
        }
    return {"ok": True, "message": f"Connected to {connection['provider']} mailbox; read test returned {len(messages)} message(s)"}
