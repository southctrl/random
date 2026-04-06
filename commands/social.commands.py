import asyncio
import random
import re
import urllib.parse
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY      = "Social"
CATEGORY_DESC = "Urban Dictionary, TikTok, typing & mimic"

COMMANDS_INFO = {
    "urban":      ("urban <term>",       "Look up a term on Urban Dictionary (top 3 defs)"),
    "tiktok":     ("tiktok <url>",       "Download and send a TikTok video (no watermark)"),
    "typing":     ("typing",             "Start fake typing in this channel"),
    "typingstop": ("typingstop",         "Stop fake typing in this channel"),
    "mimic":      ("mimic <@user>",      "Repeat everything a user says"),
    "mimicstop":  ("mimicstop [@user]",  "Stop mimicking a user (or all)"),
}

_typing_tasks: dict = {}
_mimic_targets: set = set()

_BAD_RE = re.compile(
    r"\b\d+\b|"
    r"\b(cp|loli|illegal|address|phone|ssn|password|credit\s*card|im\s+\d)\b",
    re.IGNORECASE,
)


def _sanitize(text):
    if _BAD_RE.search(text):
        return None
    cleaned = text.strip()
    return cleaned if cleaned else None


def setup(handler):
    prefix = handler.prefix

    _orig_handle = handler.handle

    async def _hooked_handle(message):
        author    = message.get("author") or {}
        author_id = author.get("id")
        content   = message.get("content", "")
        ch_id     = message.get("channel_id")
        guild_id  = message.get("guild_id")
        me_id     = getattr(handler, "_me_id", None)

        if (
            author_id
            and not author.get("bot")
            and author_id != me_id
            and author_id in _mimic_targets
            and content
            and not content.startswith(prefix)
        ):
            safe = _sanitize(content)
            if safe:
                import core.tools.ratelimit as _rl
                h = handler.spoofer.send_message(ch_id, safe, guild_id=guild_id or "@me")
                handler._spawn(_rl.request(handler.http, "post", h["url"], json=h["json"], headers=h["headers"]))

        await _orig_handle(message)

    handler.handle = _hooked_handle

    @handler.command(name="urban", aliases=["ud"])
    async def urban(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("urban", *COMMANDS_INFO["urban"], prefix), 10)
            return
        term    = " ".join(args)
        encoded = urllib.parse.quote(term)
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=True,
        )
        resp = await ctx.http.get(
            f"https://api.urbandictionary.com/v0/define?term={encoded}",
            headers=headers,
        )
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Urban Dictionary request failed ({resp.status_code})."), 8)
            return
        defs = resp.json().get("list", [])[:3]
        if not defs:
            await ctx.send_timed(ansi.error(f"No definitions found for **{term}**."), 8)
            return
        R = "\u001b[0m"
        lines = [f"{ansi.PURPLE}Urban Dictionary{R} {ansi.DARK}::{R} {ansi.WHITE}{term}{R}"]
        for i, entry in enumerate(defs, 1):
            defn    = re.sub(r"[\[\]]", "", entry.get("definition", "")).strip()
            example = re.sub(r"[\[\]]", "", entry.get("example", "")).strip()
            lines.append(f"\n{ansi.CYAN}{i}.{R} {ansi.WHITE}{defn[:300]}{R}")
            if example:
                lines.append(f"   {ansi.DARK}{example[:200]}{R}")
        await ctx.send_timed(_block("\n".join(lines)), 25)

    @handler.command(name="tiktok", aliases=["tt"])
    async def tiktok(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("tiktok", *COMMANDS_INFO["tiktok"], prefix), 10)
            return
        url    = args[0]
        status = await ctx.send(ansi.success("Fetching TikTok..."))
        smid   = (status or {}).get("id")

        async def _edit(t):
            if smid:
                await ctx.edit(smid, t)

        try:
            api_headers = ctx.spoofer.get_headers(
                referer="https://discord.com/channels/@me",
                skip_context_props=True,
            )
            api_resp = await ctx.http.get(
                f"https://www.tikwm.com/api/?url={url}",
                headers=api_headers,
            )
            data     = api_resp.json()
            play_url = (data.get("data") or {}).get("play")
            if not play_url:
                await _edit(ansi.error("Could not extract video URL."))
                return

            dl_headers   = ctx.spoofer.get_headers(
                referer="https://www.tikwm.com/",
                skip_context_props=True,
            )
            video_resp   = await ctx.http.get(play_url, headers=dl_headers)
            if video_resp.status_code != 200:
                await _edit(ansi.error(f"Video download failed ({video_resp.status_code})."))
                return
            video_bytes = video_resp.content

            vid_id   = url.rstrip("/").split("/")[-1]
            filename = f"tiktok-{vid_id}.mp4"

            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp.write(video_bytes)
                tmp_path = tmp.name

            send_r    = ctx.spoofer.send_message(ctx.channel_id, "", guild_id=ctx.guild_id or "@me")
            send_hdrs = {k: v for k, v in send_r["headers"].items() if k.lower() != "content-type"}

            from curl_cffi import CurlMime
            import core.tools.ratelimit as _rl
            mime = CurlMime()
            mime.addpart(name="payload_json", data=b'{"content":""}', content_type="application/json")
            mime.addpart(name="files[0]", local_path=tmp_path, filename=filename, content_type="video/mp4")
            await _rl.request(
                ctx.http, "post", send_r["url"],
                multipart=mime,
                headers=send_hdrs,
            )
            os.unlink(tmp_path)

            if smid:
                await ctx.delete(smid)

        except Exception as e:
            await _edit(ansi.error(f"TikTok failed: {e}"))

    @handler.command(name="typing")
    async def typing_start(ctx, args):
        await ctx.delete()
        cid = ctx.channel_id
        if cid in _typing_tasks and not _typing_tasks[cid].done():
            await ctx.send_timed(ansi.error("Already typing in this channel."), 6)
            return

        async def _loop():
            try:
                while True:
                    h = handler.spoofer.get_headers(
                        referer=f"https://discord.com/channels/{ctx.guild_id or '@me'}/{cid}",
                        skip_context_props=True,
                    )
                    await handler.http.post(f"{handler.api_base}/channels/{cid}/typing", headers=h)
                    await asyncio.sleep(8)
            except asyncio.CancelledError:
                pass

        _typing_tasks[cid] = handler._spawn(_loop())
        await ctx.send_timed(ansi.success("Fake typing started."), 6)

    @handler.command(name="typingstop")
    async def typing_stop(ctx, args):
        await ctx.delete()
        cid  = ctx.channel_id
        task = _typing_tasks.pop(cid, None)
        if task and not task.done():
            task.cancel()
            await ctx.send_timed(ansi.success("Fake typing stopped."), 6)
        else:
            await ctx.send_timed(ansi.error("No typing active in this channel."), 6)

    @handler.command(name="mimic")
    async def mimic(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("mimic", *COMMANDS_INFO["mimic"], prefix), 10)
            return
        uid = args[0].strip("<@!>")
        if not uid.isdigit():
            await ctx.send_timed(ansi.error("Invalid user mention or ID."), 8)
            return
        _mimic_targets.add(uid)
        await ctx.send_timed(ansi.success(f"Mimicking <@{uid}>."), 8)

    @handler.command(name="mimicstop")
    async def mimicstop(ctx, args):
        await ctx.delete()
        if not args:
            n = len(_mimic_targets)
            _mimic_targets.clear()
            await ctx.send_timed(ansi.success(f"Mimic stopped for all **{n}** users."), 8)
            return
        uid = args[0].strip("<@!>")
        if uid in _mimic_targets:
            _mimic_targets.discard(uid)
            await ctx.send_timed(ansi.success(f"Mimic stopped for <@{uid}>."), 8)
        else:
            await ctx.send_timed(ansi.error("Not mimicking that user."), 8)