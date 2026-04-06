import asyncio
import base64
import random
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY      = "Group Chat Extra"
CATEGORY_DESC = "GC icon, members, bulk leave & invites"

COMMANDS_INFO = {
    "gcicon":      ("gcicon",                        "Get the current GC's icon URL"),
    "setgcicon":   ("setgcicon <url>",               "Set the GC icon from a URL"),
    "gcadd":       ("gcadd <username>",              "Add a friend to this GC by username"),
    "gcremove":    ("gcremove <username>",            "Remove a user from this GC by username"),
    "gcremoveall": ("gcremoveall",                   "Remove all members from this GC"),
    "massgcleave": ("massgcleave",                   "Leave all private group chats"),
    "friendlink":  ("friendlink [days] [max_uses]",  "Generate a friend invite link"),
}


def setup(handler):
    prefix = handler.prefix

    def _is_gc(ctx):
        return ctx.guild_id is None and ctx.channel_id is not None

    async def _fetch_channel(ctx, channel_id):
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/@me/{channel_id}",
            skip_context_props=True,
        )
        resp = await ctx.http.get(f"{ctx.api_base}/channels/{channel_id}", headers=headers)
        return resp.json() if resp.status_code == 200 else None

    async def _download(ctx, url):
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=True,
        )
        resp = await ctx.http.get(url, headers=headers)
        return resp.content if resp.status_code == 200 else None

    def _to_data_uri(data):
        if data[:4] == b"\x89PNG":
            mime = "image/png"
        elif data[:3] == b"GIF":
            mime = "image/gif"
        else:
            mime = "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    @handler.command(name="gcicon")
    async def gcicon(ctx, args):
        await ctx.delete()
        if not _is_gc(ctx):
            await ctx.send_timed(ansi.error("This command only works in a group chat."), 8)
            return
        data = await _fetch_channel(ctx, ctx.channel_id)
        if not data:
            await ctx.send_timed(ansi.error("Failed to fetch GC info."), 8)
            return
        icon = data.get("icon")
        if not icon:
            await ctx.send_timed(ansi.error("This GC has no icon set."), 8)
            return
        url = f"https://cdn.discordapp.com/channel-icons/{ctx.channel_id}/{icon}.png?size=4096"
        await ctx.send_timed(ansi.success(f"GC Icon: {url}"), 20)

    @handler.command(name="setgcicon")
    async def setgcicon(ctx, args):
        await ctx.delete()
        if not _is_gc(ctx):
            await ctx.send_timed(ansi.error("This command only works in a group chat."), 8)
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("setgcicon", *COMMANDS_INFO["setgcicon"], prefix), 10)
            return
        img = await _download(ctx, args[0])
        if not img:
            await ctx.send_timed(ansi.error("Failed to download image."), 8)
            return
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/@me/{ctx.channel_id}",
            skip_context_props=True,
        )
        resp = await ctx.http.patch(
            f"{ctx.api_base}/channels/{ctx.channel_id}",
            json={"icon": _to_data_uri(img)},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("GC icon updated." if ok else f"Failed ({resp.status_code})."), 8)

    @handler.command(name="gcadd")
    async def gcadd(ctx, args):
        await ctx.delete()
        if not _is_gc(ctx):
            await ctx.send_timed(ansi.error("This command only works in a group chat."), 8)
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("gcadd", *COMMANDS_INFO["gcadd"], prefix), 10)
            return
        username = " ".join(args).lower()
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=True,
        )
        resp = await ctx.http.get(f"{ctx.api_base}/users/@me/relationships", headers=headers)
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch relationships ({resp.status_code})."), 8)
            return
        friends = [r for r in resp.json() if r.get("type") == 1]
        target  = next((f["user"] for f in friends if f["user"].get("username", "").lower() == username), None)
        if not target:
            await ctx.send_timed(ansi.error(f"No friend found with username **{username}**."), 8)
            return
        add_headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/@me/{ctx.channel_id}",
            skip_context_props=True,
        )
        r = await ctx.http.put(
            f"{ctx.api_base}/channels/{ctx.channel_id}/recipients/{target['id']}",
            json={},
            headers=add_headers,
        )
        if r.status_code in (200, 201, 204):
            await ctx.send_timed(ansi.success(f"Added **{target['username']}** to the GC."), 8)
        elif r.status_code == 400:
            await ctx.send_timed(ansi.error("GC is full (10 members max)."), 8)
        else:
            await ctx.send_timed(ansi.error(f"Failed to add ({r.status_code})."), 8)

    @handler.command(name="gcremove")
    async def gcremove(ctx, args):
        await ctx.delete()
        if not _is_gc(ctx):
            await ctx.send_timed(ansi.error("This command only works in a group chat."), 8)
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("gcremove", *COMMANDS_INFO["gcremove"], prefix), 10)
            return
        username = " ".join(args).lower()
        data = await _fetch_channel(ctx, ctx.channel_id)
        if not data:
            await ctx.send_timed(ansi.error("Failed to fetch GC info."), 8)
            return
        target = next((u for u in data.get("recipients", []) if u.get("username", "").lower() == username), None)
        if not target:
            await ctx.send_timed(ansi.error(f"User **{username}** not found in this GC."), 8)
            return
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/@me/{ctx.channel_id}",
            skip_context_props=True,
        )
        r = await ctx.http.delete(
            f"{ctx.api_base}/channels/{ctx.channel_id}/recipients/{target['id']}",
            headers=headers,
        )
        ok = r.status_code == 204
        await ctx.send_timed((ansi.success if ok else ansi.error)(f"Removed **{target['username']}**." if ok else f"Failed ({r.status_code})."), 8)

    @handler.command(name="gcremoveall")
    async def gcremoveall(ctx, args):
        await ctx.delete()
        if not _is_gc(ctx):
            await ctx.send_timed(ansi.error("This command only works in a group chat."), 8)
            return
        data = await _fetch_channel(ctx, ctx.channel_id)
        if not data:
            await ctx.send_timed(ansi.error("Failed to fetch GC info."), 8)
            return
        me_id   = getattr(handler, "_me_id", ctx.author.get("id"))
        members = [u for u in data.get("recipients", []) if u["id"] != me_id]
        if not members:
            await ctx.send_timed(ansi.error("No members to remove."), 8)
            return
        status  = await ctx.send(ansi.success(f"Removing {len(members)} members..."))
        smid    = (status or {}).get("id")
        removed = 0
        failed  = 0
        for u in members:
            h = ctx.spoofer.get_headers(
                referer=f"https://discord.com/channels/@me/{ctx.channel_id}",
                skip_context_props=True,
            )
            r = await ctx.http.delete(
                f"{ctx.api_base}/channels/{ctx.channel_id}/recipients/{u['id']}",
                headers=h,
            )
            if r.status_code == 204:
                removed += 1
            else:
                failed += 1
            await asyncio.sleep(0.5)
        R = "\u001b[0m"
        result = _block(
            f"{ansi.PURPLE}GC Remove All{R}\n"
            f"{ansi.CYAN}{'Removed':<10}{ansi.DARK}:: {ansi.WHITE}{removed}{R}\n"
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}"
        )
        if smid:
            await ctx.edit(smid, result)
            await asyncio.sleep(10)
            await ctx.delete(smid)
        else:
            await ctx.send_timed(result, 10)

    @handler.command(name="massgcleave", aliases=["gcleaveall"])
    async def massgcleave(ctx, args):
        await ctx.delete()
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=False,
        )
        resp = await ctx.http.get(f"{ctx.api_base}/users/@me/channels", headers=headers)
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch channels ({resp.status_code})."), 8)
            return
        gcs = [ch for ch in resp.json() if ch.get("type") == 3]
        if not gcs:
            await ctx.send_timed(ansi.error("You are not in any group chats."), 8)
            return
        status = await ctx.send(ansi.success(f"Leaving {len(gcs)} group chats..."))
        smid   = (status or {}).get("id")
        left   = 0
        failed = 0
        for gc in gcs:
            gc_id = gc["id"]
            h = ctx.spoofer.get_headers(
                referer=f"https://discord.com/channels/@me/{gc_id}",
                skip_context_props=True,
            )
            r = await ctx.http.delete(f"{ctx.api_base}/channels/{gc_id}", headers=h)
            if r.status_code in (200, 204):
                left += 1
            else:
                failed += 1
            await asyncio.sleep(random.uniform(0.8, 1.5))
        R = "\u001b[0m"
        result = _block(
            f"{ansi.PURPLE}Mass GC Leave{R}\n"
            f"{ansi.CYAN}{'Left':<10}{ansi.DARK}:: {ansi.WHITE}{left}{R}\n"
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}"
        )
        if smid:
            await ctx.edit(smid, result)
            await asyncio.sleep(12)
            await ctx.delete(smid)
        else:
            await ctx.send_timed(result, 12)

    @handler.command(name="friendlink", aliases=["finvite"])
    async def friendlink(ctx, args):
        await ctx.delete()
        try:
            days     = int(args[0]) if len(args) > 0 else 7
            max_uses = int(args[1]) if len(args) > 1 else 10
        except ValueError:
            await ctx.send_timed(ansi.error("Usage: friendlink [days] [max_uses]"), 8)
            return
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=False,
        )
        resp = await ctx.http.post(
            f"{ctx.api_base}/users/@me/invites",
            json={"max_age": days * 86400, "max_uses": max_uses, "temporary": False, "target_type": 2},
            headers=headers,
        )
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to create invite ({resp.status_code})."), 8)
            return
        code = resp.json().get("code", "?")
        R = "\u001b[0m"
        await ctx.send_timed(_block(
            f"{ansi.PURPLE}Friend Invite{R}\n"
            f"{ansi.CYAN}{'Link':<10}{ansi.DARK}:: {ansi.WHITE}discord.gg/{code}{R}\n"
            f"{ansi.CYAN}{'Expires':<10}{ansi.DARK}:: {ansi.WHITE}{days}d{R}\n"
            f"{ansi.CYAN}{'Max Uses':<10}{ansi.DARK}:: {ansi.WHITE}{max_uses}{R}"
        ), 20)