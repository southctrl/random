import asyncio
import base64
import json
import os
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "Anti-GC"
CATEGORY_DESC = "Auto-leave GC traps & alerts"

COMMANDS_INFO = {
    "antigctrap":       ("antigctrap <on/off>",    "Toggle anti-GC trap"),
    "agctblock":        ("agctblock <on/off>",      "Auto-block GC creator on leave"),
    "agctmsg":          ("agctmsg <message>",       "Set message sent before leaving"),
    "agctname":         ("agctname <n>",         "Set GC rename before leaving"),
    "agcticon":         ("agcticon <url>",          "Set GC icon before leaving"),
    "agctwebhook":      ("agctwebhook <url>",       "Set webhook for alerts"),
    "agctwl":           ("agctwl <user>",           "Whitelist a user"),
    "agctunwl":         ("agctunwl <user>",         "Unwhitelist a user"),
    "agctwllist":       ("agctwllist",              "List whitelisted users"),
}

_WL_FILE = "agct_whitelist.json"

_state = {
    "enabled":      False,
    "block":        False,
    "silent":       True,
    "leave_msg":    "loser",
    "gc_name":      "u cant trap a god",
    "gc_icon_url":  None,
    "webhook_url":  None,
}
_whitelist: set = set()


def _load_wl():
    global _whitelist
    if os.path.exists(_WL_FILE):
        try:
            with open(_WL_FILE) as f:
                _whitelist = set(json.load(f))
        except Exception:
            # FIX: don't use bare except - it swallows CancelledError
            _whitelist = set()

def _save_wl():
    with open(_WL_FILE, "w") as f:
        json.dump(list(_whitelist), f)

_load_wl()


async def _get_gc_owner(http, spoofer, channel_id: str) -> str | None:
    headers = spoofer.get_headers(skip_context_props=True)
    resp = await http.get(f"https://discord.com/api/v9/channels/{channel_id}", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        return str(data.get("owner_id") or "")
    return None


async def _block_user(http, spoofer, user_id: str):
    r = spoofer.block_user(user_id)
    await http.put(r["url"], json=r["json"], headers=r["headers"])
    print(f"[AGCT] Blocked {user_id}")


async def _rename_gc(http, spoofer, channel_id: str, name: str):
    headers = spoofer.get_headers(skip_context_props=True)
    await http.patch(
        f"https://discord.com/api/v9/channels/{channel_id}",
        json={"name": name},
        headers=headers,
    )

async def _set_gc_icon(http, spoofer, channel_id: str, icon_url: str):
    headers_dl = {"User-Agent": spoofer.profile.user_agent}
    r = await http.get(icon_url, headers=headers_dl)
    if r.status_code != 200:
        return
    image_bytes = r.content
    mime = "image/gif" if image_bytes[:6] in (b"GIF87a", b"GIF89a") else "image/png"
    b64 = base64.b64encode(image_bytes).decode()
    headers = spoofer.get_headers(skip_context_props=True)
    await http.patch(
        f"https://discord.com/api/v9/channels/{channel_id}",
        json={"icon": f"data:{mime};base64,{b64}"},
        headers=headers,
    )

async def _send_msg(http, spoofer, channel_id: str, content: str):
    r = spoofer.send_message(channel_id, content, guild_id="@me")
    await http.post(r["url"], json=r["json"], headers=r["headers"])

async def _leave_gc(http, spoofer, channel_id: str, silent: bool):
    headers = spoofer.get_headers(skip_context_props=True)
    for _ in range(3):
        resp = await http.delete(
            f"https://discord.com/api/v9/channels/{channel_id}",
            params={"silent": "true" if silent else "false"},
            headers=headers,
        )
        if resp.status_code == 200:
            print(f"[AGCT] Left GC {channel_id}")
            return True
        elif resp.status_code == 429:
            wait = float(resp.headers.get("retry-after", 1))
            await asyncio.sleep(wait)
        else:
            await asyncio.sleep(1)
    return False

async def _notify_webhook(http, webhook_url: str, channel_id: str, owner_id: str, members: list):
    if not webhook_url:
        return
    member_names = ", ".join(str(m) for m in members) or "None"
    embed = {
        "title": "Anti-GCTrap Alert",
        "description": (
            f"**Owner ID:** `{owner_id}`\n"
            f"**Channel ID:** `{channel_id}`\n"
            f"**Members:** `{member_names}`"
        ),
        "color": 0xFF0000,
    }
    try:
        await http.post(webhook_url, json={"embeds": [embed]})
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"[AGCT] Webhook failed: {e}")


def setup(handler):
    prefix = handler.prefix

    # FIX: the old _hooked_handle tried to intercept CHANNEL_CREATE by checking
    # message.get("t") on MESSAGE_CREATE payloads - that never matches because
    # gateway.py dispatches CHANNEL_CREATE directly via handler._agct_channel_create.
    # The hook below is a no-op pass-through; CHANNEL_CREATE is handled by the
    # _agct_channel_create path registered at the bottom of setup().
    _orig_handle = handler.handle

    async def _hooked_handle(message: dict):
        await _orig_handle(message)

    async def _handle_gc_create(data: dict):
        if not _state["enabled"]:
            return
        channel_id = str(data.get("id", ""))
        channel_type = data.get("type")
        if channel_type != 3:  # 3 = GROUP_DM
            return

        recipients = data.get("recipients", [])
        member_ids = [str(r.get("id")) for r in recipients]

        await asyncio.sleep(0.5)

        owner_id = str(data.get("owner_id") or "")
        if not owner_id:
            owner_id = await _get_gc_owner(handler.http, handler.spoofer, channel_id) or ""

        my_id = getattr(handler, "_me_id", None)
        if not my_id:
            try:
                me = await handler.http.get(
                    "https://discord.com/api/v10/users/@me",
                    headers=handler.spoofer.get_headers(skip_context_props=True)
                )
                my_id = str(me.json().get("id", ""))
                handler._me_id = my_id
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        if owner_id == my_id:
            return

        if owner_id in _whitelist:
            print(f"[AGCT] Whitelisted owner {owner_id}, skipping")
            return

        print(f"[AGCT] GC trap detected - channel {channel_id}, owner {owner_id}")

        if _state["gc_name"]:
            await _rename_gc(handler.http, handler.spoofer, channel_id, _state["gc_name"])

        if _state["gc_icon_url"]:
            await _set_gc_icon(handler.http, handler.spoofer, channel_id, _state["gc_icon_url"])

        if _state["leave_msg"]:
            await _send_msg(handler.http, handler.spoofer, channel_id, _state["leave_msg"])

        if _state["block"] and owner_id:
            await _block_user(handler.http, handler.spoofer, owner_id)

        await _leave_gc(handler.http, handler.spoofer, channel_id, _state["silent"])

        if _state["webhook_url"]:
            await _notify_webhook(handler.http, _state["webhook_url"], channel_id, owner_id, member_ids)

    handler.handle = _hooked_handle

    # expose for gateway to call on CHANNEL_CREATE events
    handler._agct_channel_create = _handle_gc_create

    @handler.command(name="antigctrap", aliases=["agct"])
    async def antigctrap(ctx, args):
        await ctx.delete()
        if not args:
            state = "ON" if _state["enabled"] else "OFF"
            await ctx.send_timed(ansi.success(f"Anti-GCTrap is **{state}**."), 10)
            return
        s = args[0].lower()
        if s in ("on", "enable"):
            _state["enabled"] = True
            await ctx.send_timed(ansi.success("Anti-GCTrap **enabled**."), 10)
        elif s in ("off", "disable"):
            _state["enabled"] = False
            await ctx.send_timed(ansi.success("Anti-GCTrap **disabled**."), 10)
        else:
            await ctx.send_timed(ansi.error("Specify **on** or **off**."), 10)

    @handler.command(name="agctblock")
    async def agctblock(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agctblock", *COMMANDS_INFO["agctblock"], prefix), 10)
            return
        s = args[0].lower()
        if s in ("on", "enable"):
            _state["block"] = True
            await ctx.send_timed(ansi.success("Auto-block **enabled**."), 10)
        elif s in ("off", "disable"):
            _state["block"] = False
            await ctx.send_timed(ansi.success("Auto-block **disabled**."), 10)
        else:
            await ctx.send_timed(ansi.error("Specify **on** or **off**."), 10)

    @handler.command(name="agctmsg")
    async def agctmsg(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agctmsg", *COMMANDS_INFO["agctmsg"], prefix), 10)
            return
        _state["leave_msg"] = " ".join(args)
        await ctx.send_timed(ansi.success(f"Leave message set."), 10)

    @handler.command(name="agctname")
    async def agctname(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agctname", *COMMANDS_INFO["agctname"], prefix), 10)
            return
        _state["gc_name"] = " ".join(args)
        await ctx.send_timed(ansi.success(f"GC rename set to **{_state['gc_name']}**."), 10)

    @handler.command(name="agcticon")
    async def agcticon(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agcticon", *COMMANDS_INFO["agcticon"], prefix), 10)
            return
        _state["gc_icon_url"] = args[0]
        await ctx.send_timed(ansi.success("GC icon URL set."), 10)

    @handler.command(name="agctwebhook")
    async def agctwebhook(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agctwebhook", *COMMANDS_INFO["agctwebhook"], prefix), 10)
            return
        _state["webhook_url"] = args[0]
        await ctx.send_timed(ansi.success("Webhook URL set."), 10)

    @handler.command(name="agctwl")
    async def agctwl(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agctwl", *COMMANDS_INFO["agctwl"], prefix), 10)
            return
        uid = args[0].strip("<@!>")
        if uid in _whitelist:
            await ctx.send_timed(ansi.error(f"`{uid}` already whitelisted."), 10)
            return
        _whitelist.add(uid)
        _save_wl()
        await ctx.send_timed(ansi.success(f"Whitelisted `{uid}`."), 10)

    @handler.command(name="agctunwl")
    async def agctunwl(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("agctunwl", *COMMANDS_INFO["agctunwl"], prefix), 10)
            return
        uid = args[0].strip("<@!>")
        if uid not in _whitelist:
            await ctx.send_timed(ansi.error(f"`{uid}` is not whitelisted."), 10)
            return
        _whitelist.discard(uid)
        _save_wl()
        await ctx.send_timed(ansi.success(f"Unwhitelisted `{uid}`."), 10)

    @handler.command(name="agctwllist")
    async def agctwllist(ctx, args):
        await ctx.delete()
        if not _whitelist:
            await ctx.send_timed(ansi.error("Whitelist is empty."), 10)
            return
        R = "\u001b[0m"
        lines = [f"{ansi.CYAN}{uid}{R}" for uid in _whitelist]
        await ctx.send_timed(_block("\n".join(lines)), 15)