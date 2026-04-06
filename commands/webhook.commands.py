import httpx as _httpx
import asyncio
import re
import base64
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY      = "Webhook"
CATEGORY_DESC = "Webhook embed output configuration"

COMMANDS_INFO = {
    "webhook":      ("webhook <url|clear>",        "Set a webhook URL for embed output, or clear it"),
    "webhooktest":  ("webhooktest",                "Send a test embed to the configured webhook"),
    "webhookcolor": ("webhookcolor <hex>",         "Change the embed accent color e.g. ff00ff"),
    "webhookimg":   ("webhookimg <url|clear>",     "Set a thumbnail image on all embeds"),
    "webhookname":  ("webhookname <name>",         "Set the webhook username shown on posts"),
    "webhookdelay": ("webhookdelay <seconds>",     "Set how long forwarded msgs stay (0 = forever)"),
    "webhookinfo":  ("webhookinfo",                "Show current webhook config"),
    "webhookstop":  ("webhookstop",                 "Disable webhook mode, back to ansi"),
}

_ANSI_RE     = re.compile(r"\x1b\[[0-9;]*m")
_EMBED_COLOR = 0x9B59B6
_CTX_PROPS   = base64.b64encode(b'{"location":"forwarding"}').decode()
_DEFAULT_IMG = "https://i.pinimg.com/736x/ed/11/6e/ed116e818eef98d3b034444eabbbd835.jpg"


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _to_embed(content: str, color: int, img: str) -> dict:
    clean = _strip_ansi(content)
    embed = {"color": color, "description": clean[:4096]}
    if img:
        embed["image"] = {"url": img}
    return embed


async def _forward(ctx, embed: dict, wh_guild_id: str, wh_name: str, delete_after: float = None):
    wh_url   = ctx._wh_url
    wh_parts = wh_url.rstrip("/").split("/")
    wh_id    = wh_parts[-2]
    wh_token = wh_parts[-1]

    # 1. POST to webhook
    try:
        async with _httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                wh_url,
                json={"embeds": [embed], "username": wh_name},
                params={"wait": "true"},
            )
        data       = resp.json() if resp.status_code == 200 else {}
        wh_msg_id  = data.get("id")
        wh_chan_id = data.get("channel_id")
    except Exception as e:
        print(f"[WEBHOOK] Post error: {e}")
        return

    if not wh_msg_id or not wh_chan_id:
        print(f"[WEBHOOK] Bad webhook response: {data}")
        return

    # 2. Forward to command channel
    fwd_msg_id = None
    try:
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id or '@me'}/{ctx.channel_id}",
            skip_context_props=True,
        )
        headers["x-context-properties"] = _CTX_PROPS

        payload = {
            "content": "",
            "tts": False,
            "flags": 0,
            "mobile_network_type": "unknown",
            "message_reference": {
                "type": 1,
                "guild_id": wh_guild_id,
                "channel_id": wh_chan_id,
                "message_id": wh_msg_id,
            },
        }

        fwd = await ctx.http.post(
            f"{ctx.api_base}/channels/{ctx.channel_id}/messages",
            json=payload,
            headers=headers,
        )
        print(f"[WEBHOOK] Forward {fwd.status_code}")
        fwd_data   = fwd.json() if fwd.status_code == 200 else {}
        fwd_msg_id = fwd_data.get("id")
    except Exception as e:
        print(f"[WEBHOOK] Forward error: {e}")

    # 3. Delete webhook source message immediately
    async def _del_wh():
        await asyncio.sleep(1)
        try:
            async with _httpx.AsyncClient(timeout=8) as c:
                await c.delete(f"https://discord.com/api/v10/webhooks/{wh_id}/{wh_token}/messages/{wh_msg_id}")
        except Exception:
            pass

    asyncio.create_task(_del_wh())

    # 4. Delete forwarded message after delay
    if fwd_msg_id and delete_after and delete_after > 0:
        async def _del_fwd():
            await asyncio.sleep(delete_after)
            try:
                r = ctx.spoofer.delete_message(
                    ctx.channel_id, fwd_msg_id,
                    guild_id=ctx.guild_id or "@me",
                )
                await ctx.http.delete(r["url"], headers=r["headers"])
            except Exception:
                pass
        asyncio.create_task(_del_fwd())


def _patch_ctx(ctx, cfg: dict):
    ctx._wh_url = cfg["url"]

    async def send(content: str) -> dict:
        await _forward(ctx, _to_embed(content, cfg["color"], cfg["img"]), cfg["guild_id"], cfg["name"], cfg["delay"])
        return {}

    async def send_timed(content: str, seconds: float) -> dict:
        delay = cfg["delay"] if cfg["delay"] and cfg["delay"] > 0 else seconds
        await _forward(ctx, _to_embed(content, cfg["color"], cfg["img"]), cfg["guild_id"], cfg["name"], delay)
        return {}

    ctx.send       = send
    ctx.send_timed = send_timed


def setup(handler):
    _wh = {
        "url":        None,
        "channel_id": None,
        "guild_id":   None,
        "color":      _EMBED_COLOR,
        "img":        _DEFAULT_IMG,
        "name":       "nevermore",
        "delay":      10.0,
    }

    original_handle = handler.handle

    async def patched_handle(message: dict):
        author  = message.get("author", {})
        content = message.get("content", "")
        if not content.startswith(handler.prefix) or author.get("bot"):
            return await original_handle(message)

        me_id = getattr(handler, "_me_id", None)
        if me_id and author.get("id") != me_id:
            return await original_handle(message)

        parts    = content[len(handler.prefix):].split()
        cmd_name = parts[0].lower() if parts else ""

        _wh_cmds = {"webhook", "webhooktest", "webhookcolor", "webhookimg", "webhookname", "webhookdelay", "webhookinfo"}
        if cmd_name in _wh_cmds:
            return await original_handle(message)

        if _wh["url"]:
            import time, traceback
            from core.tools import Context as Ctx
            ctx = Ctx(message, handler.http, handler.token, handler.api_base, handler.spoofer, handler)
            _patch_ctx(ctx, _wh)

            args = parts[1:]
            if cmd_name not in handler.commands:
                return

            try:
                start   = time.perf_counter()
                await handler.commands[cmd_name](ctx, args)
                elapsed = (time.perf_counter() - start) * 1000
                print(f"[CMD] {cmd_name} | {elapsed:.1f}ms (webhook)")
            except Exception:
                traceback.print_exc()

            try:
                r = handler.spoofer.delete_message(
                    message.get("channel_id"),
                    message.get("id"),
                    guild_id=message.get("guild_id") or "@me",
                )
                await handler.http.delete(r["url"], headers=r["headers"])
            except Exception:
                pass
        else:
            await original_handle(message)

    handler.handle = patched_handle

    @handler.command(name="webhook")
    async def webhook_cmd(ctx, args):
        await ctx.delete()
        if not args:
            status = f"Current webhook: `{_wh['url']}`" if _wh["url"] else "No webhook set."
            await ctx.send_timed(ansi.success(status), 8)
            return

        if args[0].lower() == "clear":
            _wh["url"] = _wh["channel_id"] = _wh["guild_id"] = None
            await ctx.send_timed(ansi.success("Webhook cleared."), 8)
            return

        url = args[0]
        if "discord.com/api/webhooks/" not in url and "discordapp.com/api/webhooks/" not in url:
            await ctx.send_timed(ansi.error("Invalid Discord webhook URL."), 8)
            return

        try:
            async with _httpx.AsyncClient(timeout=8) as client:
                wr = await client.get(url)
            wdata             = wr.json()
            _wh["channel_id"] = wdata.get("channel_id")
            _wh["guild_id"]   = wdata.get("guild_id")
            print(f"[WEBHOOK] Set guild={_wh['guild_id']} channel={_wh['channel_id']}")
        except Exception as e:
            print(f"[WEBHOOK] Info fetch error: {e}")

        _wh["url"] = url
        await ctx.send_timed(ansi.success("Webhook set."), 8)

    @handler.command(name="webhookcolor")
    async def webhookcolor_cmd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("webhookcolor", *COMMANDS_INFO["webhookcolor"], handler.prefix), 8)
            return
        try:
            _wh["color"] = int(args[0].lstrip("#"), 16)
            await ctx.send_timed(ansi.success(f"Embed color set to #{args[0].lstrip('#')}."), 8)
        except ValueError:
            await ctx.send_timed(ansi.error("Invalid hex color."), 8)

    @handler.command(name="webhookimg")
    async def webhookimg_cmd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("webhookimg", *COMMANDS_INFO["webhookimg"], handler.prefix), 8)
            return
        if args[0].lower() == "clear":
            _wh["img"] = None
            await ctx.send_timed(ansi.success("Thumbnail image cleared."), 8)
            return
        _wh["img"] = args[0]
        await ctx.send_timed(ansi.success("Thumbnail image set."), 8)

    @handler.command(name="webhookname")
    async def webhookname_cmd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("webhookname", *COMMANDS_INFO["webhookname"], handler.prefix), 8)
            return
        _wh["name"] = " ".join(args)
        await ctx.send_timed(ansi.success(f"Webhook name set to {_wh['name']}."), 8)

    @handler.command(name="webhookdelay")
    async def webhookdelay_cmd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("webhookdelay", *COMMANDS_INFO["webhookdelay"], handler.prefix), 8)
            return
        try:
            _wh["delay"] = float(args[0])
            label = f"{_wh['delay']}s" if _wh["delay"] > 0 else "never"
            await ctx.send_timed(ansi.success(f"Forwarded messages will delete after {label}."), 8)
        except ValueError:
            await ctx.send_timed(ansi.error("Invalid number."), 8)

    @handler.command(name="webhookinfo")
    async def webhookinfo_cmd(ctx, args):
        await ctx.delete()
        lines = [
            f"URL     : {_wh['url'] or 'not set'}",
            f"Guild   : {_wh['guild_id'] or 'unknown'}",
            f"Color   : #{hex(_wh['color'])[2:].zfill(6)}",
            f"Image   : {_wh['img'] or 'none'}",
            f"Name    : {_wh['name']}",
            f"Delay   : {_wh['delay']}s",
        ]
        await ctx.send_timed(ansi.success("\n".join(lines)), 12)

    @handler.command(name="webhooktest")
    async def webhooktest_cmd(ctx, args):
        await ctx.delete()
        if not _wh["url"]:
            await ctx.send_timed(ansi.error("No webhook set. Use `.webhook <url>` first."), 8)
            return
        embed = _to_embed("Webhook is working correctly.", _wh["color"], _wh["img"])
        embed["title"] = "nevermore"
        await _forward(ctx, embed, _wh["guild_id"], _wh["name"], _wh["delay"])

    @handler.command(name="webhookstop")
    async def webhookstop_cmd(ctx, args):
        await ctx.delete()
        _wh["url"] = _wh["channel_id"] = _wh["guild_id"] = None
        await ctx.send_timed(ansi.success("Webhook disabled. Back to normal ansi messages."), 8)
