from core.tools import ansi
import base64

CATEGORY      = "Boost"
CATEGORY_DESC = "Server boost management"

COMMANDS_INFO = {
    "boost":         ("boost <server_id>",                           "Boost a server using available slots"),
    "boosttransfer": ("boosttransfer <current_server> <new_server>", "Move a boost from one server to another"),
    "boostslots":    ("boostslots",                                  "List all boost slots and their current status"),
    "boostremove":   ("boostremove <server_id>",                     "Remove your boost from a server"),
}

_CTX_PROPS_BOOST = base64.b64encode(b'{"location":"Guild Boost"}').decode()


def _boost_headers(ctx, guild_id: str) -> dict:
    headers = ctx.spoofer.get_headers(
        referer=f"https://discord.com/channels/{guild_id}",
        skip_context_props=True,
    )
    headers["x-context-properties"] = _CTX_PROPS_BOOST
    return headers


async def _get_slots(ctx) -> list:
    resp = await ctx.http.get(
        f"{ctx.api_base}/users/@me/guilds/premium/subscription-slots",
        headers=ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
        ),
    )
    if resp.status_code != 200:
        return []
    return resp.json()


def setup(handler):

    @handler.command(name="boost")
    async def boost_cmd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("boost", *COMMANDS_INFO["boost"], handler.prefix), 8)
            return

        target_guild = args[0]
        slots = await _get_slots(ctx)
        if not slots:
            await ctx.send_timed(ansi.error("No boost slots found or failed to fetch slots."), 8)
            return

        available = [
            s for s in slots
            if not s.get("canceled")
            and (
                not s.get("premium_guild_subscription")
                or s["premium_guild_subscription"].get("ended")
            )
        ]

        if not available:
            await ctx.send_timed(ansi.error("No available (unboosted) slots found."), 8)
            return

        slot_ids = [s["id"] for s in available]

        headers = _boost_headers(ctx, target_guild)
        resp = await ctx.http.put(
            f"{ctx.api_base}/guilds/{target_guild}/premium/subscriptions",
            json={
                "user_premium_guild_subscription_slot_ids": slot_ids,
                "disable_powerup_auto_apply": False,
            },
            headers=headers,
        )

        if resp.status_code in (200, 201):
            await ctx.send_timed(ansi.success(f"Boosted server {target_guild} with {len(slot_ids)} slot(s)."), 10)
        else:
            await ctx.send_timed(ansi.error(f"Boost failed ({resp.status_code}): {resp.text[:200]}"), 10)

    @handler.command(name="boosttransfer")
    async def boosttransfer_cmd(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("boosttransfer", *COMMANDS_INFO["boosttransfer"], handler.prefix), 8)
            return

        current_guild = args[0]
        new_guild     = args[1]

        slots = await _get_slots(ctx)
        if not slots:
            await ctx.send_timed(ansi.error("Failed to fetch boost slots."), 8)
            return

        boosting_target = [
            s for s in slots
            if s.get("premium_guild_subscription")
            and s["premium_guild_subscription"].get("guild_id") == current_guild
            and not s["premium_guild_subscription"].get("ended")
            and not s.get("canceled")
        ]

        if not boosting_target:
            await ctx.send_timed(ansi.error(f"No active boosts found on server {current_guild}."), 8)
            return

        slot_ids = [s["id"] for s in boosting_target]

        headers = _boost_headers(ctx, new_guild)
        resp = await ctx.http.put(
            f"{ctx.api_base}/guilds/{new_guild}/premium/subscriptions",
            json={
                "user_premium_guild_subscription_slot_ids": slot_ids,
                "disable_powerup_auto_apply": False,
            },
            headers=headers,
        )

        if resp.status_code in (200, 201):
            await ctx.send_timed(
                ansi.success(f"Transferred {len(slot_ids)} boost(s) from {current_guild} to {new_guild}."), 10
            )
        else:
            await ctx.send_timed(ansi.error(f"Transfer failed ({resp.status_code}): {resp.text[:200]}"), 10)

    @handler.command(name="boostslots")
    async def boostslots_cmd(ctx, args):
        await ctx.delete()
        slots = await _get_slots(ctx)
        if not slots:
            await ctx.send_timed(ansi.error("Failed to fetch boost slots or none exist."), 8)
            return

        lines = []
        for i, slot in enumerate(slots, 1):
            slot_id  = slot["id"]
            canceled = slot.get("canceled", False)
            cooldown = slot.get("cooldown_ends_at", "none")
            sub      = slot.get("premium_guild_subscription")

            if sub and not sub.get("ended"):
                guild_id = sub.get("guild_id", "unknown")
                status   = f"boosting {guild_id}"
            else:
                status = "available"

            if canceled:
                status = "canceled"

            lines.append(f"[{i}] {slot_id} -- {status} | cooldown: {cooldown}")

        await ctx.send_timed(ansi.success("\n".join(lines)), 15)

    @handler.command(name="boostremove")
    async def boostremove_cmd(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("boostremove", *COMMANDS_INFO["boostremove"], handler.prefix), 8)
            return

        target_guild = args[0]
        slots = await _get_slots(ctx)
        if not slots:
            await ctx.send_timed(ansi.error("Failed to fetch boost slots."), 8)
            return

        boosting = [
            s for s in slots
            if s.get("premium_guild_subscription")
            and s["premium_guild_subscription"].get("guild_id") == target_guild
            and not s["premium_guild_subscription"].get("ended")
            and not s.get("canceled")
        ]

        if not boosting:
            await ctx.send_timed(ansi.error(f"No active boosts found on server {target_guild}."), 8)
            return

        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{target_guild}",
        )

        failed  = 0
        removed = 0
        for slot in boosting:
            sub_id = slot["premium_guild_subscription"]["id"]
            resp = await ctx.http.delete(
                f"{ctx.api_base}/guilds/{target_guild}/premium/subscriptions/{sub_id}",
                headers=headers,
            )
            if resp.status_code in (200, 204):
                removed += 1
            else:
                failed += 1

        if failed:
            await ctx.send_timed(
                ansi.error(f"Removed {removed} boost(s), {failed} failed on {target_guild}."), 10
            )
        else:
            await ctx.send_timed(ansi.success(f"Removed {removed} boost(s) from {target_guild}."), 10)
