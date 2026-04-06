import asyncio
from core.tools import ansi

CATEGORY = "Group Chat"
CATEGORY_DESC = "GC lockdown, anti-add & whitelist"

COMMANDS_INFO = {
    "gclockdown":   ("gclockdown <on/off>",    "Lock GC membership - re-adds removed users"),
    "gcantiadd":    ("gcantiadd <on/off>",      "Kick any user added to the GC"),
    "gcwhitelist":  ("gcwhitelist <user>",      "Whitelist a user from GC protection"),
    "gcunwhitelist":("gcunwhitelist <user>",    "Remove a user from the GC whitelist"),
}

_gc_lockdown   = {}
_gc_antiadd    = {}
_gc_whitelist  = {}
_lockdown_task = None
_antiadd_task  = None

def setup(handler):
    prefix = handler.prefix

    async def _add(ctx, channel_id: str, user_id: str):
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/@me/{channel_id}",
            skip_context_props=True,
        )
        resp = await ctx.http.put(
            f"{ctx.api_base}/channels/{channel_id}/recipients/{user_id}",
            json={},
            headers=headers,
        )
        return resp.status_code in (200, 201, 204)

    async def _kick(ctx, channel_id: str, user_id: str):
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/@me/{channel_id}",
            skip_context_props=True,
        )
        resp = await ctx.http.delete(
            f"{ctx.api_base}/channels/{channel_id}/recipients/{user_id}",
            headers=headers,
        )
        return resp.status_code == 204

    async def _get_gc_members(ctx, channel_id: str) -> dict:
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.get(
            f"{ctx.api_base}/channels/{channel_id}",
            headers=headers,
        )
        data = resp.json()
        recipients = data.get("recipients", [])
        return {r["id"]: r for r in recipients}

    # FIX: lockdown/antiadd loops previously captured ctx.http/spoofer at task
    # spawn time via positional args. After a gateway reconnect, handler.http is
    # replaced with a new AsyncSession, leaving the loop holding a dead session.
    # Now the loops read handler.http/spoofer dynamically each iteration so they
    # always use the live session post-reconnect.

    async def _lockdown_loop():
        while True:
            try:
                if not _gc_lockdown:
                    await asyncio.sleep(5)
                    continue

                # Read from handler each iteration - always live after reconnects
                http_ref     = handler.http
                spoofer_ref  = handler.spoofer
                api_base     = handler.api_base

                for channel_id, tracked in list(_gc_lockdown.items()):
                    headers = spoofer_ref.get_headers(skip_context_props=True)
                    resp = await http_ref.get(
                        f"{api_base}/channels/{channel_id}",
                        headers=headers,
                    )
                    data = resp.json()
                    current = {r["id"]: r for r in data.get("recipients", [])}

                    missing = [
                        u for uid, u in tracked.items()
                        if uid not in current
                        and uid not in _gc_whitelist.get(channel_id, set())
                    ]

                    if missing:
                        print(f"[GC] {len(missing)} missing in {channel_id}, re-adding")
                        tasks = []
                        for user in missing:
                            h = spoofer_ref.get_headers(
                                referer=f"https://discord.com/channels/@me/{channel_id}",
                                skip_context_props=True,
                            )
                            tasks.append(http_ref.put(
                                f"{api_base}/channels/{channel_id}/recipients/{user['id']}",
                                json={},
                                headers=h,
                            ))
                        await asyncio.gather(*tasks, return_exceptions=True)

                    updated = {r["id"]: r for r in data.get("recipients", [])}
                    _gc_lockdown[channel_id] = updated

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[GC] lockdown error: {e}")

            # Poll every 3s per GC to avoid hammering the API
            await asyncio.sleep(max(3, len(_gc_lockdown) * 1))

    async def _antiadd_loop():
        while True:
            try:
                if not _gc_antiadd:
                    await asyncio.sleep(5)
                    continue

                # Read from handler each iteration - always live after reconnects
                http_ref    = handler.http
                spoofer_ref = handler.spoofer
                api_base    = handler.api_base

                for channel_id, tracked in list(_gc_antiadd.items()):
                    headers = spoofer_ref.get_headers(skip_context_props=True)
                    resp = await http_ref.get(
                        f"{api_base}/channels/{channel_id}",
                        headers=headers,
                    )
                    data = resp.json()
                    current = {r["id"]: r for r in data.get("recipients", [])}

                    new_users = [
                        u for uid, u in current.items()
                        if uid not in tracked
                        and uid not in _gc_whitelist.get(channel_id, set())
                    ]

                    if new_users:
                        print(f"[GC] {len(new_users)} new users in {channel_id}, kicking")
                        tasks = []
                        for user in new_users:
                            h = spoofer_ref.get_headers(
                                referer=f"https://discord.com/channels/@me/{channel_id}",
                                skip_context_props=True,
                            )
                            tasks.append(http_ref.delete(
                                f"{api_base}/channels/{channel_id}/recipients/{user['id']}",
                                headers=h,
                            ))
                        await asyncio.gather(*tasks, return_exceptions=True)

                    _gc_antiadd[channel_id] = tracked

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[GC] antiadd error: {e}")

            await asyncio.sleep(max(3, len(_gc_antiadd) * 1))

    @handler.command(name="gclockdown", aliases=["gcld"])
    async def gclockdown(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("gclockdown", *COMMANDS_INFO["gclockdown"], prefix), 10)
            return

        state = args[0].lower()
        if state not in ("on", "off"):
            await ctx.send_timed(ansi.error("Specify **on** or **off**."), 10)
            return

        channel_id = ctx.channel_id

        if state == "on":
            members = await _get_gc_members(ctx, channel_id)
            _gc_lockdown[channel_id] = members

            global _lockdown_task
            if _lockdown_task is None or _lockdown_task.done():
                _lockdown_task = handler._spawn(_lockdown_loop())

            await ctx.send_timed(ansi.success(f"GC lockdown enabled - tracking {len(members)} members."), 10)
        else:
            _gc_lockdown.pop(channel_id, None)
            await ctx.send_timed(ansi.success("GC lockdown disabled."), 10)

    @handler.command(name="gcantiadd", aliases=["gcaa"])
    async def gcantiadd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("gcantiadd", *COMMANDS_INFO["gcantiadd"], prefix), 10)
            return

        state = args[0].lower()
        if state not in ("on", "off"):
            await ctx.send_timed(ansi.error("Specify **on** or **off**."), 10)
            return

        channel_id = ctx.channel_id

        if state == "on":
            members = await _get_gc_members(ctx, channel_id)
            _gc_antiadd[channel_id] = members

            global _antiadd_task
            if _antiadd_task is None or _antiadd_task.done():
                _antiadd_task = handler._spawn(_antiadd_loop())

            await ctx.send_timed(ansi.success(f"GC anti-add enabled - tracking {len(members)} members."), 10)
        else:
            _gc_antiadd.pop(channel_id, None)
            await ctx.send_timed(ansi.success("GC anti-add disabled."), 10)

    @handler.command(name="gcwhitelist", aliases=["gcwl"])
    async def gcwhitelist(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("gcwhitelist", *COMMANDS_INFO["gcwhitelist"], prefix), 10)
            return

        channel_id = ctx.channel_id
        user_id = args[0].strip("<@!>")

        if channel_id not in _gc_whitelist:
            _gc_whitelist[channel_id] = set()
        _gc_whitelist[channel_id].add(user_id)

        await ctx.send_timed(ansi.success(f"Whitelisted `{user_id}` in this GC."), 10)

    @handler.command(name="gcunwhitelist", aliases=["gcunwl"])
    async def gcunwhitelist(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("gcunwhitelist", *COMMANDS_INFO["gcunwhitelist"], prefix), 10)
            return

        channel_id = ctx.channel_id
        user_id = args[0].strip("<@!>")

        if channel_id not in _gc_whitelist or user_id not in _gc_whitelist[channel_id]:
            await ctx.send_timed(ansi.error(f"`{user_id}` is not whitelisted in this GC."), 10)
            return

        _gc_whitelist[channel_id].discard(user_id)
        await ctx.send_timed(ansi.success(f"Unwhitelisted `{user_id}` from this GC."), 10)