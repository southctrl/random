import asyncio
import random
from core.tools import ansi
from core.tools.ansi import _block
import core.tools.ratelimit as _rl

CATEGORY      = "Friends"
CATEGORY_DESC = "Friends list, pending, bulk actions & auto-reply"

COMMANDS_INFO = {
    "friendcount":   ("friendcount",                 "Show your friend/block/pending counts"),
    "pending":       ("pending",                     "Show incoming & outgoing friend requests"),
    "massunfriend":  ("massunfriend",                "Remove all friends one by one"),
    "closedms":      ("closedms",                    "Close all open DM channels"),
    "autoreply":     ("autoreply <@user> <message>", "Auto-reply to every message from a user"),
    "autoreplystop": ("autoreplystop [@user]",       "Stop auto-reply for a user or all"),
}

_autoreply_targets: dict = {}


def _headers(ctx):
    return ctx.spoofer.get_headers(
        referer="https://discord.com/channels/@me",
        skip_context_props=True,
    )


def setup(handler):
    prefix = handler.prefix

    _orig_handle = handler.handle

    async def _hooked_handle(message):
        author     = message.get("author") or {}
        author_id  = author.get("id")
        content    = message.get("content", "")
        channel_id = message.get("channel_id")
        guild_id   = message.get("guild_id")
        msg_id     = message.get("id")
        me_id      = getattr(handler, "_me_id", None)

        if (
            author_id
            and not author.get("bot")
            and author_id != me_id
            and author_id in _autoreply_targets
            and content
        ):
            h = handler.spoofer.send_message(
                channel_id,
                _autoreply_targets[author_id],
                guild_id=guild_id or "@me",
                reply_to=msg_id,
                reply_channel=channel_id,
                reply_guild=guild_id,
            )
            handler._spawn(_rl.request(handler.http, "post", h["url"], json=h["json"], headers=h["headers"]))

        await _orig_handle(message)

    handler.handle = _hooked_handle

    @handler.command(name="friendcount", aliases=["fc"])
    async def friendcount(ctx, args):
        await ctx.delete()
        resp = await ctx.http.get(
            f"{ctx.api_base}/users/@me/relationships",
            headers=_headers(ctx),
        )
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch relationships ({resp.status_code})."), 8)
            return
        rels     = resp.json()
        friends  = sum(1 for r in rels if r.get("type") == 1)
        blocked  = sum(1 for r in rels if r.get("type") == 2)
        incoming = sum(1 for r in rels if r.get("type") == 3)
        outgoing = sum(1 for r in rels if r.get("type") == 4)
        R = "\u001b[0m"
        await ctx.send_timed(_block(
            f"{ansi.PURPLE}Friend Stats{R}\n"
            f"{ansi.CYAN}{'Friends':<12}{ansi.DARK}:: {ansi.WHITE}{friends}{R}\n"
            f"{ansi.CYAN}{'Blocked':<12}{ansi.DARK}:: {ansi.WHITE}{blocked}{R}\n"
            f"{ansi.CYAN}{'Incoming':<12}{ansi.DARK}:: {ansi.WHITE}{incoming}{R}\n"
            f"{ansi.CYAN}{'Outgoing':<12}{ansi.DARK}:: {ansi.WHITE}{outgoing}{R}"
        ), 15)

    @handler.command(name="pending")
    async def pending(ctx, args):
        await ctx.delete()
        resp = await ctx.http.get(
            f"{ctx.api_base}/users/@me/relationships",
            headers=_headers(ctx),
        )
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch relationships ({resp.status_code})."), 8)
            return
        incoming = []
        outgoing = []
        for r in resp.json():
            user  = r.get("user", {})
            uid   = user.get("id", "?")
            uname = user.get("username", "?")
            gname = user.get("global_name", "")
            label = f"{gname} ({uname})" if gname else uname
            if r.get("type") == 3:
                incoming.append(f"{label} -- {uid}")
            elif r.get("type") == 4:
                outgoing.append(f"{label} -- {uid}")
        R = "\u001b[0m"
        lines = [f"{ansi.PURPLE}Pending Requests{R}"]
        lines.append(f"{ansi.CYAN}Incoming ({len(incoming)}){R}")
        for ln in (incoming or ["none"]):
            lines.append(f"  {ansi.WHITE}{ln}{R}")
        lines.append(f"{ansi.CYAN}Outgoing ({len(outgoing)}){R}")
        for ln in (outgoing or ["none"]):
            lines.append(f"  {ansi.WHITE}{ln}{R}")
        await ctx.send_timed(_block("\n".join(lines)), 20)

    @handler.command(name="massunfriend", aliases=["unfriendall"])
    async def massunfriend(ctx, args):
        await ctx.delete()
        hdrs = _headers(ctx)
        resp = await ctx.http.get(
            f"{ctx.api_base}/users/@me/relationships",
            headers=hdrs,
        )
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch relationships ({resp.status_code})."), 8)
            return
        friends = [r for r in resp.json() if r.get("type") == 1]
        if not friends:
            await ctx.send_timed(ansi.error("You have no friends to remove."), 8)
            return
        status  = await ctx.send(ansi.success(f"Removing {len(friends)} friends..."))
        smid    = (status or {}).get("id")
        removed = 0
        failed  = 0
        for rel in friends:
            uid = rel["user"]["id"]
            r = await ctx.http.delete(
                f"{ctx.api_base}/users/@me/relationships/{uid}",
                headers=hdrs,
            )
            if r.status_code in (200, 204):
                removed += 1
            else:
                failed += 1
            await asyncio.sleep(random.uniform(0.6, 1.2))
        R = "\u001b[0m"
        result = _block(
            f"{ansi.PURPLE}Mass Unfriend{R}\n"
            f"{ansi.CYAN}{'Removed':<10}{ansi.DARK}:: {ansi.WHITE}{removed}{R}\n"
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}"
        )
        if smid:
            await ctx.edit(smid, result)
            await asyncio.sleep(12)
            await ctx.delete(smid)
        else:
            await ctx.send_timed(result, 12)

    @handler.command(name="closedms", aliases=["cleardms"])
    async def closedms(ctx, args):
        await ctx.delete()
        hdrs = _headers(ctx)
        resp = await ctx.http.get(
            f"{ctx.api_base}/users/@me/channels",
            headers=hdrs,
        )
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch DMs ({resp.status_code})."), 8)
            return
        dms = [ch for ch in resp.json() if ch.get("type") == 1]
        if not dms:
            await ctx.send_timed(ansi.error("No open DM channels."), 8)
            return
        status = await ctx.send(ansi.success(f"Closing {len(dms)} DM channels..."))
        smid   = (status or {}).get("id")
        closed = 0
        failed = 0
        for dm in dms:
            cid = dm["id"]
            r = await ctx.http.delete(
                f"{ctx.api_base}/channels/{cid}",
                headers=hdrs,
            )
            if r.status_code in (200, 204):
                closed += 1
            else:
                failed += 1
            await asyncio.sleep(0.3)
        R = "\u001b[0m"
        result = _block(
            f"{ansi.PURPLE}Close DMs{R}\n"
            f"{ansi.CYAN}{'Closed':<10}{ansi.DARK}:: {ansi.WHITE}{closed}{R}\n"
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}"
        )
        if smid:
            await ctx.edit(smid, result)
            await asyncio.sleep(10)
            await ctx.delete(smid)
        else:
            await ctx.send_timed(result, 10)

    @handler.command(name="autoreply")
    async def autoreply(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("autoreply", *COMMANDS_INFO["autoreply"], prefix), 10)
            return
        uid = args[0].strip("<@!>")
        if not uid.isdigit():
            await ctx.send_timed(ansi.error("Invalid user mention or ID."), 8)
            return
        _autoreply_targets[uid] = " ".join(args[1:])
        await ctx.send_timed(ansi.success(f"Auto-reply set for <@{uid}>."), 8)

    @handler.command(name="autoreplystop")
    async def autoreplystop(ctx, args):
        await ctx.delete()
        if not args:
            n = len(_autoreply_targets)
            _autoreply_targets.clear()
            await ctx.send_timed(ansi.success(f"Auto-reply cleared for all **{n}** users."), 8)
            return
        uid = args[0].strip("<@!>")
        if uid in _autoreply_targets:
            del _autoreply_targets[uid]
            await ctx.send_timed(ansi.success(f"Auto-reply stopped for <@{uid}>."), 8)
        else:
            await ctx.send_timed(ansi.error("No auto-reply active for that user."), 8)