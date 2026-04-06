import asyncio
import urllib.parse
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "Reactions"
CATEGORY_DESC = "Super reaction automation"

COMMANDS_INFO = {
    "superreact":          ("superreact <user> <emoji>",          "Super react to every message from a user"),
    "superreactstop":      ("superreactstop <user>",              "Stop super reacting to a user"),
    "cyclesuperreact":     ("cyclesuperreact <user> <e1,e2,...>", "Cycle through emojis on each message"),
    "cyclesuperreactstop": ("cyclesuperreactstop <user>",         "Stop cycle super react on a user"),
    "multisuperreact":     ("multisuperreact <user> <e1,e2,...>", "React with multiple emojis on every message"),
    "multisuperreactstop": ("multisuperreactstop <user>",         "Stop multi super react on a user"),
}

_targets     = {}
_csr_targets = {}
_msr_targets = {}


def _emoji_path(emoji: str) -> str:
    if emoji.startswith("<a:") or emoji.startswith("<:"):
        parts = emoji.strip("<>").split(":")
        return f"{parts[1]}:{parts[2]}"
    return urllib.parse.quote(emoji)


async def _react(http, spoofer, api_base, guild_id, channel_id, message_id, emoji):
    path = _emoji_path(emoji)
    gid = guild_id or "@me"
    url = f"{api_base}/channels/{channel_id}/messages/{message_id}/reactions/{path}/@me"
    headers = spoofer.get_headers(
        referer=f"https://discord.com/channels/{gid}/{channel_id}",
        skip_context_props=True,
    )
    for attempt in range(3):
        resp = await http.put(url, params={"location": "Message Reaction Picker", "type": 1}, headers=headers)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", 1))
            # FIX: don't sleep 10+ minutes for a reaction - just bail
            if retry_after > 10:
                print(f"[REACT] rate limited with retry_after={retry_after}s, dropping task")
                return False
            print(f"[REACT] rate limited, retrying in {retry_after}s")
            await asyncio.sleep(retry_after)
            continue
        elif resp.status_code >= 500:
            await asyncio.sleep(2 ** attempt)
            continue
        return resp.status_code == 204
    return False


def setup(handler):
    prefix = handler.prefix

    def _parse_id(arg: str) -> str | None:
        cleaned = arg.strip("<@!>").replace("&", "")
        return cleaned if cleaned.isdigit() else None

    _orig_handle = handler.handle

    async def _hooked_handle(message: dict):
        author_id  = message.get("author", {}).get("id")
        channel_id = message.get("channel_id")
        guild_id   = message.get("guild_id")
        msg_id     = message.get("id")

        if author_id and channel_id and msg_id:
            h  = handler.http
            sp = handler.spoofer
            ab = handler.api_base

            # FIX: use handler._spawn instead of bare asyncio.create_task so tasks
            # are tracked and don't leak when they pile up under rate limiting
            if author_id in _targets:
                handler._spawn(_react(h, sp, ab, guild_id, channel_id, msg_id, _targets[author_id]))

            if author_id in _csr_targets:
                emojis, idx = _csr_targets[author_id]
                handler._spawn(_react(h, sp, ab, guild_id, channel_id, msg_id, emojis[idx]))
                _csr_targets[author_id] = (emojis, (idx + 1) % len(emojis))

            if author_id in _msr_targets:
                for emoji in _msr_targets[author_id]:
                    handler._spawn(_react(h, sp, ab, guild_id, channel_id, msg_id, emoji))

        await _orig_handle(message)

    handler.handle = _hooked_handle

    @handler.command(name="superreact", aliases=["sr"])
    async def superreact(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("superreact", *COMMANDS_INFO["superreact"], prefix), 10)
            return
        target_id = _parse_id(args[0])
        if not target_id:
            await ctx.send_timed(ansi.error("Invalid user."), 10)
            return
        _targets[target_id] = args[1]
        await ctx.send_timed(ansi.success(f"Super reacting to <@{target_id}> with {args[1]}."), 10)

    @handler.command(name="superreactstop", aliases=["srstop"])
    async def superreactstop(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("superreactstop", *COMMANDS_INFO["superreactstop"], prefix), 10)
            return
        target_id = _parse_id(args[0])
        if target_id in _targets:
            del _targets[target_id]
            await ctx.send_timed(ansi.success(f"Stopped super reacting to <@{target_id}>."), 10)
        else:
            await ctx.send_timed(ansi.error("No active super react for that user."), 10)

    @handler.command(name="cyclesuperreact", aliases=["csr"])
    async def cyclesuperreact(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("cyclesuperreact", *COMMANDS_INFO["cyclesuperreact"], prefix), 10)
            return
        target_id = _parse_id(args[0])
        emojis = [e.strip() for e in " ".join(args[1:]).split(",") if e.strip()]
        if not target_id or not emojis:
            await ctx.send_timed(ansi.error("Invalid user or emoji list."), 10)
            return
        _csr_targets[target_id] = (emojis, 0)
        await ctx.send_timed(ansi.success(f"Cycling {', '.join(emojis)} on <@{target_id}>."), 10)

    @handler.command(name="cyclesuperreactstop", aliases=["csrstop"])
    async def cyclesuperreactstop(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("cyclesuperreactstop", *COMMANDS_INFO["cyclesuperreactstop"], prefix), 10)
            return
        target_id = _parse_id(args[0])
        if target_id in _csr_targets:
            del _csr_targets[target_id]
            await ctx.send_timed(ansi.success(f"Stopped cycle react on <@{target_id}>."), 10)
        else:
            await ctx.send_timed(ansi.error("No active cycle react for that user."), 10)

    @handler.command(name="multisuperreact", aliases=["msr"])
    async def multisuperreact(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("multisuperreact", *COMMANDS_INFO["multisuperreact"], prefix), 10)
            return
        target_id = _parse_id(args[0])
        emojis = [e.strip() for e in " ".join(args[1:]).split(",") if e.strip()]
        if not target_id or not emojis:
            await ctx.send_timed(ansi.error("Invalid user or emoji list."), 10)
            return
        _msr_targets[target_id] = emojis
        await ctx.send_timed(ansi.success(f"Multi reacting with {', '.join(emojis)} on <@{target_id}>."), 10)

    @handler.command(name="multisuperreactstop", aliases=["msrstop"])
    async def multisuperreactstop(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("multisuperreactstop", *COMMANDS_INFO["multisuperreactstop"], prefix), 10)
            return
        target_id = _parse_id(args[0])
        if target_id in _msr_targets:
            del _msr_targets[target_id]
            await ctx.send_timed(ansi.success(f"Stopped multi react on <@{target_id}>."), 10)
        else:
            await ctx.send_timed(ansi.error("No active multi react for that user."), 10)