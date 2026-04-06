import asyncio
import re
import time
import json
import os
from datetime import datetime
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "Sniper"
CATEGORY_DESC = "Nitro gift code sniper"

COMMANDS_INFO = {
    "nitrosniper": ("nitrosniper <on/off>", "Toggle nitro sniper"),
    "nitroclear":  ("nitroclear",           "Clear cached used codes"),
    "nitrostats":  ("nitrostats",           "Show sniper stats"),
}

_sniper_on  = True
_used_codes: set = set()
_claimed    = 0
_claim_log: list = []

_MAX_CACHED_CODES = 5000
_MAX_LOG = 50

_PATTERNS = [
    re.compile(r"discord\.gift/(\w{16,24})", re.IGNORECASE),
    re.compile(r"discordapp\.com/gifts/(\w{16,24})", re.IGNORECASE),
    re.compile(r"discord\.com/gifts/(\w{16,24})", re.IGNORECASE),
    re.compile(r"discord\.com/billing/promotions/(\w{16,24})", re.IGNORECASE),
]


def _state_file(token: str) -> str:
    safe = token[:20].replace("/", "_").replace(".", "_")
    return f"/root/sb/sniper_state_{safe}.json"


def _load_state(token: str):
    global _claimed, _claim_log
    path = _state_file(token)
    if not os.path.exists(path):
        return
    try:
        data = json.loads(open(path).read())
        _claimed = data.get("claimed", 0)
        _claim_log = data.get("claim_log", [])
    except Exception:
        pass


def _save_state(token: str):
    path = _state_file(token)
    try:
        open(path, "w").write(json.dumps({
            "claimed": _claimed,
            "claim_log": _claim_log[-_MAX_LOG:],
        }))
    except Exception:
        pass


def _extract_codes(content: str) -> list:
    codes = []
    seen = set()
    for pat in _PATTERNS:
        for code in pat.findall(content):
            if code not in seen:
                seen.add(code)
                codes.append(code)
    return codes


async def _claim(http, spoofer, code: str, author: str, channel_id: str, guild_id: str, token: str):
    global _claimed
    headers = spoofer.get_headers(
        referer="https://discord.com/channels/@me",
        skip_context_props=True,
    )
    start = time.perf_counter()
    ts = datetime.now().strftime("%H:%M:%S")
    try:
        resp = await http.post(
            f"https://discord.com/api/v9/entitlements/gift-codes/{code}/redeem",
            json={},
            headers=headers,
        )
        ms = (time.perf_counter() - start) * 1000
        text = resp.text

        if resp.status_code == 200:
            if "subscription_plan" in text:
                _claimed += 1
                _claim_log.append({
                    "code": code,
                    "author": author,
                    "channel": channel_id,
                    "guild": guild_id,
                    "ms": round(ms, 1),
                    "ts": ts,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                })
                _save_state(token)
                print(f"[{ts}] NITRO CLAIMED {code} ({ms:.1f}ms) from {author} in {guild_id}/{channel_id}")
            elif "redeemed already" in text:
                print(f"[{ts}] Already claimed {code} ({ms:.1f}ms)")
            elif "Unknown Gift Code" in text:
                print(f"[{ts}] Invalid code {code} ({ms:.1f}ms)")
            else:
                print(f"[{ts}] Unknown 200 {code} ({ms:.1f}ms)")
        elif resp.status_code == 429:
            retry = float(resp.headers.get("retry-after", 1))
            print(f"[{ts}] Rate limited {code}, retry in {retry}s ({ms:.1f}ms)")
        else:
            print(f"[{ts}] Failed {code} -- {resp.status_code} ({ms:.1f}ms)")
    except Exception as e:
        ms = (time.perf_counter() - start) * 1000
        print(f"[{ts}] Error claiming {code}: {e} ({ms:.1f}ms)")


def setup(handler):
    token = handler.token
    _load_state(token) if token else None

    _orig_handle = handler.handle

    async def _hooked_handle(message: dict):
        if _sniper_on:
            author = message.get("author", {})
            if not author.get("bot"):
                content = message.get("content", "")
                if content:
                    codes = _extract_codes(content)
                    author_tag = f"{author.get('username')}#{author.get('discriminator', '0')}"
                    for code in codes:
                        if code not in _used_codes:
                            if len(_used_codes) >= _MAX_CACHED_CODES:
                                _used_codes.clear()
                            _used_codes.add(code)
                            handler._spawn(_claim(handler.http, handler.spoofer, code, author_tag, message.get("channel_id", ""), message.get("guild_id", "DM"), token))
        await _orig_handle(message)

    handler.handle = _hooked_handle

    @handler.command(name="nitrosniper", aliases=["nitro"])
    async def nitrosniper(ctx, args):
        global _sniper_on
        await ctx.delete()
        if not args:
            state = "ON" if _sniper_on else "OFF"
            await ctx.send_timed(ansi.success(f"Nitro sniper is **{state}**."), 10)
            return
        s = args[0].lower()
        if s in ("on", "true", "enable", "yes", "start"):
            _sniper_on = True
            await ctx.send_timed(ansi.success("Nitro sniper **enabled**."), 10)
        elif s in ("off", "false", "disable", "no", "stop"):
            _sniper_on = False
            await ctx.send_timed(ansi.success("Nitro sniper **disabled**."), 10)
        else:
            await ctx.send_timed(ansi.error("Specify **on** or **off**."), 10)

    @handler.command(name="nitroclear")
    async def nitroclear(ctx, args):
        await ctx.delete()
        n = len(_used_codes)
        _used_codes.clear()
        await ctx.send_timed(ansi.success(f"Cleared **{n}** cached codes."), 10)

    @handler.command(name="nitrostats")
    async def nitrostats(ctx, args):
        await ctx.delete()
        state  = "ON" if _sniper_on else "OFF"
        cached = len(_used_codes)
        R = "\u001b[0m"
        lines = [
            f"{ansi.CYAN}{'Status':<10}{ansi.DARK}:: {ansi.PURPLE}{state}{R}",
            f"{ansi.CYAN}{'Claimed':<10}{ansi.DARK}:: {ansi.WHITE}{_claimed}{R}",
            f"{ansi.CYAN}{'Cached':<10}{ansi.DARK}:: {ansi.WHITE}{cached} codes{R}",
        ]
        if _claim_log:
            lines.append("")
            lines.append(f"{ansi.CYAN}Recent Claims{R}")
            for entry in _claim_log[-5:]:
                guild = entry.get("guild") or "DM"
                date = entry.get("date", "")
                lines.append(f"  {ansi.WHITE}{entry['ts']} {date}{ansi.DARK} | {ansi.PURPLE}{entry['code'][:8]}...{ansi.DARK} | {ansi.WHITE}{entry['author']}{ansi.DARK} | {ansi.CYAN}{guild}{R} {ansi.WHITE}({entry['ms']}ms){R}")
        await ctx.send_timed(_block("\n".join(lines)), 20)
