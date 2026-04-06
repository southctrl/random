import httpx as _httpx
import asyncio
import re
import time
import random
import urllib.parse
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY      = "Utility"
CATEGORY_DESC = "Utility / automation commands"

COMMANDS_INFO = {
    "vcjoin":             ("vcjoin <channel_id> [mute] [deaf]",  "Join a voice channel and auto-reconnect if disconnected"),
    "vcleave":            ("vcleave",                             "Leave the current voice channel"),
    "vcmute":             ("vcmute",                              "Toggle self-mute in voice channel"),
    "vcdeafen":           ("vcdeafen",                            "Toggle self-deafen in voice channel"),
    "giveawaysniper":     ("giveawaysniper <on/off>",       "Auto-react to giveaway messages"),
    "giveawaysniperstat": ("giveawaysniperstat",             "Show giveaway sniper stats"),
    "readall":            ("readall [limit]",                "Ack all unread messages in every guild channel"),
    "readalldm":          ("readalldm",                      "Ack all unread DM channels"),
    "setprefix":          ("setprefix <prefix>",             "Change your prefix"),
    "autoreact":          ("autoreact <user> <emoji>",       "Auto-react to every message from a user"),
    "autoreactstop":      ("autoreactstop [user]",           "Stop auto-react"),
    "cyclereact":         ("cyclereact <user> <e1,e2,...>",  "Cycle emojis on each message from user"),
    "cyclereactstop":     ("cyclereactstop [user]",          "Stop cycle-react"),
    "multireact":         ("multireact <user> <e1,e2,...>",  "React with ALL listed emojis on every message"),
    "multireactstop":     ("multireactstop [user]",          "Stop multi-react"),
    "purge":              ("purge <number>",                 "Delete your last N messages in this channel"),
    "purgeall":           ("purgeall",                       "Delete all your messages in this channel"),
    "admin":              ("admin @user",                    "Grant a user access to auth/unauth (owner only)"),
    "unadmin":            ("unadmin @user",                  "Revoke admin access from a user"),
    "blacklist":          ("blacklist <@user>",              "Blacklist a user: kill instances, ban from platform (owner only)"),
    "unblacklist":        ("unblacklist <@user>",            "Remove a user from the blacklist (owner only)"),
    "instance":           ("instance",                       "List all hosted usernames and their instance numbers (owner only)"),
    "auth":               ("auth @user",                     "Authorize a user to host on nevermore.icu"),
    "unauth":             ("unauth @user",                   "Revoke a user's hosting access"),
    "massdm":             ("massdm <1|2|3> <message>",       "Mass DM history / friends / both"),
    "massgc":             ("massgc <message>",               "Mass message all private group chats"),
}

_OWNER_ID = "475336041956376576"

import json as _json, os as _os
_ADMINS_FILE = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "admins.json")

def _load_admins():
    try:
        with open(_ADMINS_FILE) as f:
            data = _json.load(f)
        return set(data) if isinstance(data, list) else set()
    except Exception:
        return set()

def _save_admins(s):
    try:
        with open(_ADMINS_FILE, "w") as f:
            _json.dump(list(s), f)
    except Exception:
        pass

_admins    = _load_admins()
_gw_on     = False
_gw_hits   = 0
_GW_KEYWORDS = ["giveaway","giveaways","give away","nitro giveaway","prize","react to win","react for","free nitro","drop","winner"]
_GW_EMOJI  = "\U0001f389"
_ar_targets = {}
_cr_targets = {}
_cr_index   = {}
_mr_targets = {}

_vc_channel_id  = None
_vc_guild_id    = None
_vc_active      = False
_vc_leaving     = False
_vc_mute        = False
_vc_deaf        = False




def _fmt_emoji(raw):
    return raw.strip()


def _emoji_api_path(emoji):
    if emoji.startswith("<a:") or emoji.startswith("<:"):
        parts = emoji.strip("<>").split(":")
        return f"{parts[1]}:{parts[2]}"
    return urllib.parse.quote(emoji)


async def _react(http, spoofer, api_base, guild_id, channel_id, message_id, emoji):
    path = _emoji_api_path(emoji)
    gid = guild_id or "@me"
    url = f"{api_base}/channels/{channel_id}/messages/{message_id}/reactions/{path}/@me"
    headers = spoofer.get_headers(referer=f"https://discord.com/channels/{gid}/{channel_id}", skip_context_props=True)
    for attempt in range(3):
        resp = await http.put(url, params={"location": "Message Reaction Picker", "type": 0}, headers=headers)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", 1))
            if retry_after > 10:
                return False
            await asyncio.sleep(retry_after)
            continue
        elif resp.status_code >= 500:
            await asyncio.sleep(2 ** attempt)
            continue
        return resp.status_code == 204
    return False


async def _gw_react(http, spoofer, api_base, guild_id, channel_id, message_id):
    await _react(http, spoofer, api_base, guild_id, channel_id, message_id, _GW_EMOJI)


def _is_giveaway(content):
    lower = content.lower()
    return any(kw in lower for kw in _GW_KEYWORDS)


async def _ack_channel(http, spoofer, api_base, channel_id, last_message_id):
    headers = spoofer.get_headers(referer=f"https://discord.com/channels/@me/{channel_id}", skip_context_props=True)
    try:
        resp = await http.post(f"{api_base}/channels/{channel_id}/messages/{last_message_id}/ack", json={"token": None}, headers=headers)
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"[READALL] ack error {channel_id}: {e}")
        return False


async def _readall(ctx, limit):
    http = ctx.http
    spoofer = ctx.spoofer
    api_base = ctx.api_base
    headers = spoofer.get_headers(referer="https://discord.com/channels/@me", skip_context_props=True)
    resp = await http.get(f"{api_base}/users/@me/guilds", headers=headers)
    if resp.status_code != 200:
        return 0, f"Failed to fetch guilds ({resp.status_code})"
    guilds = resp.json()
    if not isinstance(guilds, list):
        return 0, "Unexpected guilds response"
    total_acked = 0
    total_skipped = 0
    for guild in guilds[:limit]:
        gid = guild.get("id")
        if not gid:
            continue
        g_headers = spoofer.get_headers(referer=f"https://discord.com/channels/{gid}", skip_context_props=True)
        ch_resp = await http.get(f"{api_base}/guilds/{gid}/channels", headers=g_headers)
        if ch_resp.status_code != 200:
            continue
        channels = ch_resp.json()
        if not isinstance(channels, list):
            continue
        for ch in [c for c in channels if c.get("type") in (0, 5, 15, 16)]:
            ch_id = ch.get("id")
            last_msg = ch.get("last_message_id")
            if not ch_id or not last_msg:
                total_skipped += 1
                continue
            ok = await _ack_channel(http, spoofer, api_base, ch_id, last_msg)
            if ok:
                total_acked += 1
            else:
                total_skipped += 1
            await asyncio.sleep(0.15)
    return total_acked, None


def _nonce():
    import secrets
    return str(int(time.time() * 1000) << 22 | secrets.randbits(22))



def setup(handler):
    _orig_handle = handler.handle

    async def _hooked_handle(message):
        global _gw_on, _gw_hits
        author     = message.get("author", {})
        author_id  = author.get("id")
        me_id      = getattr(handler, "_me_id", None)
        channel_id = message.get("channel_id")
        guild_id   = message.get("guild_id")
        msg_id     = message.get("id")
        content    = message.get("content", "")
        is_other   = author_id and not author.get("bot")

        if is_other and channel_id and msg_id:
            h  = handler.http
            sp = handler.spoofer
            ab = handler.api_base

            if _gw_on and content and _is_giveaway(content):
                _gw_hits += 1
                handler._spawn(_gw_react(h, sp, ab, guild_id, channel_id, msg_id))
            if author_id in _ar_targets:
                handler._spawn(_react(h, sp, ab, guild_id, channel_id, msg_id, _ar_targets[author_id]))
            if author_id in _cr_targets:
                emojis = _cr_targets[author_id]
                idx = _cr_index.get(author_id, 0)
                handler._spawn(_react(h, sp, ab, guild_id, channel_id, msg_id, emojis[idx]))
                _cr_index[author_id] = (idx + 1) % len(emojis)
            if author_id in _mr_targets:
                for em in _mr_targets[author_id]:
                    handler._spawn(_react(h, sp, ab, guild_id, channel_id, msg_id, em))

        await _orig_handle(message)

    handler.handle = _hooked_handle

    _orig_on_ready = getattr(handler, "on_ready", None)

    async def _on_ready_hook():
        if _orig_on_ready:
            await _orig_on_ready()
        try:
            headers = handler.spoofer.get_headers(skip_context_props=True)
            me = await handler.http.get(f"{handler.api_base}/users/@me", headers=headers)
            if me.status_code == 200:
                handler._me_id = me.json().get("id")
                print(f"[UTIL] cached own ID: {handler._me_id}")
        except Exception as e:
            print(f"[UTIL] could not cache own ID: {e}")

    handler.on_ready = _on_ready_hook

    def _parse_uid(arg):
        cleaned = arg.strip("<@!>")
        return cleaned if cleaned.isdigit() else None


    @handler.command(name="massdm", aliases=["mdm"])
    async def massdm(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("massdm", *COMMANDS_INFO["massdm"], handler.prefix), 12)
            return
        try:
            option = int(args[0])
        except ValueError:
            await ctx.send_timed(ansi.error("Option must be 1, 2, or 3."), 8)
            return
        if option not in (1, 2, 3):
            await ctx.send_timed(ansi.error("Option must be 1, 2, or 3."), 8)
            return
        message = " ".join(args[1:])

        http     = ctx.http
        spoofer  = ctx.spoofer
        api_base = ctx.api_base
        headers  = spoofer.get_headers(referer="https://discord.com/channels/@me", skip_context_props=False)

        status_msg = await ctx.send(ansi.success("Mass DM :: Fetching targets..."))
        smid = (status_msg or {}).get("id")

        async def _edit(text):
            if smid:
                await ctx.edit(smid, text)

        r = await http.get(f"{api_base}/users/@me/channels", headers=headers)
        if r.status_code != 200:
            await _edit(ansi.error(f"Failed to fetch DMs ({r.status_code})."))
            return

        dms = r.json()
        existing_dm_channels: dict[str, tuple] = {}
        for dm in dms:
            if dm.get("type") == 1 and dm.get("last_message_id") and dm.get("recipients"):
                recipient = dm["recipients"][0] if dm["recipients"] else {}
                uid = recipient.get("id")
                uname = recipient.get("username", "?")
                if uid:
                    existing_dm_channels[uid] = (dm["id"], uname)

        targets: list[tuple] = []
        seen_ids: set[str]   = set()

        if option in (1, 3):
            for uid, (cid, uname) in existing_dm_channels.items():
                if uid not in seen_ids:
                    targets.append((cid, uname, "dm_history"))
                    seen_ids.add(uid)

        if option in (2, 3):
            fr_headers = spoofer.get_headers(referer="https://discord.com/channels/@me", skip_context_props=True)
            fr = await http.get(f"{api_base}/users/@me/relationships", headers=fr_headers)
            if fr.status_code == 200:
                for rel in fr.json():
                    if rel.get("type") != 1:
                        continue
                    user = rel.get("user", {})
                    uid  = user.get("id")
                    if uid and uid in existing_dm_channels and uid not in seen_ids:
                        cid, _ = existing_dm_channels[uid]
                        targets.append((cid, user.get("username", "?"), "friend"))
                        seen_ids.add(uid)
            elif option == 2:
                await _edit(ansi.error(f"Failed to fetch friends ({fr.status_code})."))
                return

        if not targets:
            await _edit(ansi.error("No targets found."))
            return

        total  = len(targets)
        sent   = 0
        failed = 0
        mode_label = {1: "DM History", 2: "Friends", 3: "Both"}[option]

        R = "\u001b[0m"

        def _status_block():
            lines = [
                f"{ansi.PURPLE}Mass DM{R}",
                f"{ansi.CYAN}{'Mode':<10}{ansi.DARK}:: {ansi.WHITE}{mode_label}{R}",
                f"{ansi.CYAN}{'Targets':<10}{ansi.DARK}:: {ansi.WHITE}{total}{R}",
                f"{ansi.CYAN}{'Sent':<10}{ansi.DARK}:: {ansi.WHITE}{sent}/{total}{R}",
                f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}",
            ]
            return _block("\n".join(lines))

        for i, (cid, uname, kind) in enumerate(targets):
            payload = {"content": message, "nonce": _nonce(), "tts": False, "flags": 0}
            url     = f"{api_base}/channels/{cid}/messages"
            hdrs    = spoofer.get_headers(referer=f"https://discord.com/channels/@me/{cid}", skip_context_props=False)

            success = False
            for attempt in range(4):
                resp = await http.post(url, headers=hdrs, json=payload)
                if resp.status_code == 200:
                    success = True
                    break
                elif resp.status_code == 429:
                    try:
                        wait = resp.json().get("retry_after", 5) + random.uniform(0.5, 1.5)
                    except Exception:
                        wait = 5
                    if wait > 30:
                        break
                    await asyncio.sleep(wait)
                elif resp.status_code in (400, 401, 403):
                    break
                else:
                    await asyncio.sleep(2 ** attempt)

            if success:
                sent += 1
            else:
                failed += 1

            if (i + 1) % 5 == 0 or i == total - 1:
                if smid:
                    await ctx.edit(smid, _status_block())

            await asyncio.sleep(random.uniform(2.5, 4.0))

        final_lines = [
            f"{ansi.PURPLE}Mass DM :: Done{ansi.RESET if hasattr(ansi,'RESET') else ansi.WHITE}",
            f"{ansi.CYAN}{'Mode':<10}{ansi.DARK}:: {ansi.WHITE}{mode_label}",
            f"{ansi.CYAN}{'Sent':<10}{ansi.DARK}:: {ansi.WHITE}{sent}/{total}",
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}",
        ]
        if smid:
            await ctx.edit(smid, _block("\n".join(final_lines)))
            await asyncio.sleep(15)
            await ctx.delete(smid)


    @handler.command(name="massgc", aliases=["mgc"])
    async def massgc(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("massgc", *COMMANDS_INFO["massgc"], handler.prefix), 10)
            return
        message  = " ".join(args)
        http     = ctx.http
        spoofer  = ctx.spoofer
        api_base = ctx.api_base
        headers  = spoofer.get_headers(referer="https://discord.com/channels/@me", skip_context_props=False)

        status_msg = await ctx.send(ansi.success("Mass GC :: Fetching group chats..."))
        smid = (status_msg or {}).get("id")

        async def _edit(text):
            if smid:
                await ctx.edit(smid, text)

        r = await http.get(f"{api_base}/users/@me/channels", headers=headers)
        if r.status_code != 200:
            await _edit(ansi.error(f"Failed to fetch channels ({r.status_code})."))
            return

        group_chats = [ch for ch in r.json() if ch.get("type") == 3]
        total = len(group_chats)
        if total == 0:
            await _edit(ansi.error("You are not in any private group chats."))
            return

        sent   = 0
        failed = 0
        R      = "\u001b[0m"

        def _status_block(current=""):
            lines = [
                f"{ansi.PURPLE}Mass GC{R}",
                f"{ansi.CYAN}{'Total':<10}{ansi.DARK}:: {ansi.WHITE}{total}{R}",
                f"{ansi.CYAN}{'Sent':<10}{ansi.DARK}:: {ansi.WHITE}{sent}{R}",
                f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}",
            ]
            if current:
                lines.append(f"{ansi.CYAN}{'Current':<10}{ansi.DARK}:: {ansi.WHITE}{current[:40]}{R}")
            return _block("\n".join(lines))

        for gc in group_chats:
            gc_id   = gc["id"]
            gc_name = gc.get("name") or "Unnamed Group"
            members = len(gc.get("recipients", []))
            label   = f"{gc_name} ({members})"

            payload = {"content": message, "nonce": _nonce(), "tts": False, "flags": 0}
            url     = f"{api_base}/channels/{gc_id}/messages"
            hdrs    = spoofer.get_headers(referer=f"https://discord.com/channels/@me/{gc_id}", skip_context_props=False)

            success = False
            for attempt in range(6):
                resp = await http.post(url, headers=hdrs, json=payload)
                if resp.status_code == 200:
                    success = True
                    break
                elif resp.status_code == 429:
                    try:
                        wait = resp.json().get("retry_after", 5) + random.uniform(1, 3)
                    except Exception:
                        wait = 5
                    if wait > 60:
                        break
                    await asyncio.sleep(wait)
                elif resp.status_code in (10003, 50001, 50013, 403):
                    break
                else:
                    await asyncio.sleep(3)

            if success:
                sent += 1
            else:
                failed += 1

            if smid:
                await ctx.edit(smid, _status_block(label))

            await asyncio.sleep(random.uniform(3.5, 6.0))

        final = _block("\n".join([
            f"{ansi.PURPLE}Mass GC :: Done{R}",
            f"{ansi.CYAN}{'Sent':<10}{ansi.DARK}:: {ansi.WHITE}{sent}/{total}{R}",
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}",
        ]))
        if smid:
            await ctx.edit(smid, final)
            await asyncio.sleep(15)
            await ctx.delete(smid)


    async def _vc_send_state(guild_id, channel_id):
        gw = getattr(handler, "_gateway", None) or getattr(handler, "gateway", None)
        if gw is None:
            return
        await gw._send({
            "op": 4,
            "d": {
                "guild_id":   guild_id,
                "channel_id": channel_id,
                "self_mute":  _vc_mute,
                "self_deaf":  _vc_deaf,
            }
        })

    _orig_on_voice_state = getattr(handler, "_on_voice_state_update", None)

    async def _on_voice_state_update(data):
        global _vc_active, _vc_leaving
        me_id = getattr(handler, "_me_id", None)
        uid   = data.get("user_id") or (data.get("member") or {}).get("user", {}).get("id")
        if uid and uid == me_id:
            ch = data.get("channel_id")
            if ch is None and _vc_active and not _vc_leaving:
                print(f"[VC] Disconnected, reconnecting to {_vc_channel_id}...")
                await asyncio.sleep(1.5)
                if _vc_active and not _vc_leaving:
                    await _vc_send_state(_vc_guild_id, _vc_channel_id)
        if _orig_on_voice_state:
            await _orig_on_voice_state(data)

    handler._on_voice_state_update = _on_voice_state_update

    def _patch_gateway_voice():
        pass

    _orig_on_ready2 = getattr(handler, "on_ready", None)

    async def _on_ready_vc_patch():
        if _orig_on_ready2:
            await _orig_on_ready2()
        _patch_gateway_voice()
        if _vc_active and not _vc_leaving and _vc_channel_id:
            print("[VC] Reconnected to gateway -- rejoining VC...")
            await asyncio.sleep(2)
            await _vc_send_state(_vc_guild_id, _vc_channel_id)

    handler.on_ready = _on_ready_vc_patch

    @handler.command(name="vcjoin", aliases=["joinvc", "vc"])
    async def vcjoin(ctx, args):
        global _vc_channel_id, _vc_guild_id, _vc_active, _vc_leaving, _vc_mute, _vc_deaf
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("vcjoin", *COMMANDS_INFO["vcjoin"], handler.prefix), 10)
            return
        channel_id = args[0].strip()
        if not channel_id.isdigit():
            await ctx.send_timed(ansi.error("Invalid channel ID."), 8)
            return
        flags = [a.lower() for a in args[1:]]
        _vc_mute       = "mute" in flags
        _vc_deaf       = "deaf" in flags
        guild_id       = ctx.guild_id or None
        _vc_channel_id = channel_id
        _vc_guild_id   = guild_id
        _vc_active     = True
        _vc_leaving    = False

        await _vc_send_state(guild_id, channel_id)

        R = "\u001b[0m"
        lines = [
            f"{ansi.PURPLE}Voice Join{R}",
            f"{ansi.CYAN}{'Channel':<10}{ansi.DARK}:: {ansi.WHITE}{channel_id}{R}",
            f"{ansi.CYAN}{'Mute':<10}{ansi.DARK}:: {ansi.WHITE}{'yes' if _vc_mute else 'no'}{R}",
            f"{ansi.CYAN}{'Deaf':<10}{ansi.DARK}:: {ansi.WHITE}{'yes' if _vc_deaf else 'no'}{R}",
            f"{ansi.CYAN}{'Reconnect':<10}{ansi.DARK}:: {ansi.WHITE}auto{R}",
        ]
        await ctx.send_timed(_block("\n".join(lines)), 10)

    @handler.command(name="vcmute", aliases=["mute"])
    async def vcmute(ctx, args):
        global _vc_mute
        await ctx.delete()
        if not _vc_active or not _vc_channel_id:
            await ctx.send_timed(ansi.error("Not currently in a voice channel."), 8)
            return
        _vc_mute = not _vc_mute
        await _vc_send_state(_vc_guild_id, _vc_channel_id)
        await ctx.send_timed(ansi.success(f"Self-mute **{'on' if _vc_mute else 'off'}**."), 8)

    @handler.command(name="vcdeafen", aliases=["deaf"])
    async def vcdeafen(ctx, args):
        global _vc_deaf
        await ctx.delete()
        if not _vc_active or not _vc_channel_id:
            await ctx.send_timed(ansi.error("Not currently in a voice channel."), 8)
            return
        _vc_deaf = not _vc_deaf
        await _vc_send_state(_vc_guild_id, _vc_channel_id)
        await ctx.send_timed(ansi.success(f"Self-deafen **{'on' if _vc_deaf else 'off'}**."), 8)

    @handler.command(name="vcleave", aliases=["leavevc"])
    async def vcleave(ctx, args):
        global _vc_active, _vc_leaving
        await ctx.delete()
        if not _vc_active or not _vc_channel_id:
            await ctx.send_timed(ansi.error("Not currently in a voice channel."), 8)
            return

        _vc_leaving = True
        _vc_active  = False

        await _vc_send_state(_vc_guild_id, None)

        await ctx.send_timed(ansi.success("Left voice channel."), 8)


    @handler.command(name="setprefix")
    async def setprefix(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setprefix", *COMMANDS_INFO["setprefix"], handler.prefix), 10)
            return
        new = args[0]
        old = handler.prefix
        handler.prefix = new
        await ctx.send_timed(ansi.success(f"Prefix changed {old} to {new}."), 10)

    @handler.command(name="giveawaysniper", aliases=["gwsniper", "gws"])
    async def giveawaysniper(ctx, args):
        global _gw_on
        await ctx.delete()
        if not args:
            state = "ON" if _gw_on else "OFF"
            await ctx.send_timed(ansi.success(f"Giveaway sniper is **{state}**."), 10)
            return
        s = args[0].lower()
        if s in ("on", "true", "enable", "yes", "start"):
            _gw_on = True
            await ctx.send_timed(ansi.success("Giveaway sniper **enabled**."), 10)
        elif s in ("off", "false", "disable", "no", "stop"):
            _gw_on = False
            await ctx.send_timed(ansi.success("Giveaway sniper **disabled**."), 10)
        else:
            await ctx.send_timed(ansi.error("Specify **on** or **off**."), 10)

    @handler.command(name="giveawaysniperstat", aliases=["gwstat", "gwstats"])
    async def giveawaysniperstat(ctx, args):
        await ctx.delete()
        state = "ON" if _gw_on else "OFF"
        R = "\u001b[0m"
        kws = ", ".join(_GW_KEYWORDS[:6]) + "..."
        lines = [
            f"{ansi.CYAN}{'Status':<12}{ansi.DARK}:: {ansi.PURPLE}{state}{R}",
            f"{ansi.CYAN}{'Reacted':<12}{ansi.DARK}:: {ansi.WHITE}{_gw_hits} messages{R}",
            f"{ansi.CYAN}{'Keywords':<12}{ansi.DARK}:: {ansi.WHITE}{kws}{R}",
        ]
        await ctx.send_timed(_block("\n".join(lines)), 15)

    @handler.command(name="readalldm", aliases=["ackdm", "readdm"])
    async def readalldm(ctx, args):
        await ctx.delete()
        http = ctx.http
        spoofer = ctx.spoofer
        api_base = ctx.api_base
        headers = spoofer.get_headers(referer="https://discord.com/channels/@me", skip_context_props=True)
        resp = await http.get(f"{api_base}/users/@me/channels", headers=headers)
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch DMs ({resp.status_code})."), 10)
            return
        channels = resp.json()
        if not isinstance(channels, list):
            await ctx.send_timed(ansi.error("Unexpected DM response."), 10)
            return
        msg = await ctx.send(ansi.success(f"Reading all DMs ({len(channels)} channels)..."))
        mid = (msg or {}).get("id")
        acked = 0
        for ch in channels:
            ch_id = ch.get("id")
            last_msg = ch.get("last_message_id")
            if not ch_id or not last_msg:
                continue
            ok = await _ack_channel(http, spoofer, api_base, ch_id, last_msg)
            if ok:
                acked += 1
            await asyncio.sleep(0.15)
        result = ansi.success(f"Done! Acked **{acked}** DM channels.")
        if mid:
            await ctx.edit(mid, result)
            await asyncio.sleep(8)
            await ctx.delete(mid)
        else:
            await ctx.send_timed(result, 8)

    @handler.command(name="readall", aliases=["ackall"])
    async def readall(ctx, args):
        await ctx.delete()
        try:
            limit = int(args[0]) if args else 999
        except ValueError:
            limit = 999
        msg = await ctx.send(ansi.success(f"Reading all messages (up to {limit} guilds)..."))
        mid = (msg or {}).get("id")
        acked, err = await _readall(ctx, limit)
        result_text = ansi.error(f"readall failed: {err}") if err else ansi.success(f"Done! Acked **{acked}** channels.")
        if mid:
            await ctx.edit(mid, result_text)
            await asyncio.sleep(8)
            await ctx.delete(mid)
        else:
            await ctx.send_timed(result_text, 8)

    @handler.command(name="autoreact", aliases=["ar"])
    async def autoreact(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("autoreact", *COMMANDS_INFO["autoreact"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user."), 10)
            return
        emoji = _fmt_emoji(args[1])
        _ar_targets[uid] = emoji
        await ctx.send_timed(ansi.success(f"AutoReact started reacting {emoji} to <@{uid}>."), 10)

    @handler.command(name="autoreactstop", aliases=["arstop"])
    async def autoreactstop(ctx, args):
        await ctx.delete()
        if not args:
            n = len(_ar_targets)
            _ar_targets.clear()
            await ctx.send_timed(ansi.success(f"AutoReact stopped for all **{n}** users."), 10)
            return
        uid = _parse_uid(args[0])
        if uid and uid in _ar_targets:
            del _ar_targets[uid]
            await ctx.send_timed(ansi.success(f"AutoReact stopped for <@{uid}>."), 10)
        else:
            await ctx.send_timed(ansi.error("No autoreact active for that user."), 10)

    @handler.command(name="cyclereact", aliases=["cr"])
    async def cyclereact(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("cyclereact", *COMMANDS_INFO["cyclereact"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user."), 10)
            return
        emojis = [_fmt_emoji(e) for e in " ".join(args[1:]).split(",") if e.strip()]
        if len(emojis) < 2:
            await ctx.send_timed(ansi.error("Provide at least **2** emojis separated by commas."), 10)
            return
        _cr_targets[uid] = emojis
        _cr_index[uid] = 0
        await ctx.send_timed(ansi.success(f"CycleReact started on <@{uid}>."), 10)

    @handler.command(name="cyclereactstop", aliases=["crstop"])
    async def cyclereactstop(ctx, args):
        await ctx.delete()
        if not args:
            n = len(_cr_targets)
            _cr_targets.clear()
            _cr_index.clear()
            await ctx.send_timed(ansi.success(f"CycleReact stopped for all **{n}** users."), 10)
            return
        uid = _parse_uid(args[0])
        if uid and uid in _cr_targets:
            _cr_targets.pop(uid, None)
            _cr_index.pop(uid, None)
            await ctx.send_timed(ansi.success(f"CycleReact stopped for <@{uid}>."), 10)
        else:
            await ctx.send_timed(ansi.error("No cyclereact active for that user."), 10)

    @handler.command(name="multireact", aliases=["mr"])
    async def multireact(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("multireact", *COMMANDS_INFO["multireact"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user."), 10)
            return
        emojis = [_fmt_emoji(e) for e in " ".join(args[1:]).split(",") if e.strip()]
        if not (2 <= len(emojis) <= 20):
            await ctx.send_timed(ansi.error("You can only use 2-20 emojis for multireact."), 10)
            return
        _mr_targets[uid] = emojis
        await ctx.send_timed(ansi.success(f"MultiReact started on <@{uid}>."), 10)

    @handler.command(name="multireactstop", aliases=["mrstop"])
    async def multireactstop(ctx, args):
        await ctx.delete()
        if not args:
            n = len(_mr_targets)
            _mr_targets.clear()
            await ctx.send_timed(ansi.success(f"MultiReact stopped for all **{n}** users."), 10)
            return
        uid = _parse_uid(args[0])
        if uid and uid in _mr_targets:
            del _mr_targets[uid]
            await ctx.send_timed(ansi.success(f"MultiReact stopped for <@{uid}>."), 10)
        else:
            await ctx.send_timed(ansi.error("No multireact active for that user."), 10)

    import os as _os
    _WEB_URL    = _os.environ.get("NEVERMORE_API_URL", "http://127.0.0.1:5000")
    _WEB_SECRET = "e294750d45901ee598707b92204dcd87805bb267f788b083ed2cee0c0b6d18f5"

    @handler.command(name="admin", aliases=["addadmin"])
    async def admin(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("admin", *COMMANDS_INFO["admin"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user."), 10)
            return
        _admins.add(uid)
        _save_admins(_admins)
        await ctx.send_timed(ansi.success(f"<@{uid}> can now use auth/unauth."), 10)

    @handler.command(name="unadmin", aliases=["removeadmin"])
    async def unadmin(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("unadmin", *COMMANDS_INFO["unadmin"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user."), 10)
            return
        _admins.discard(uid)
        _save_admins(_admins)
        await ctx.send_timed(ansi.success(f"<@{uid}> admin access revoked."), 10)

    @handler.command(name="purge")
    async def purge(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("purge", *COMMANDS_INFO["purge"], handler.prefix), 10)
            return
        try:
            limit = int(args[0])
        except ValueError:
            await ctx.send_timed(ansi.error("Provide a number."), 10)
            return
        me_id    = getattr(handler, "_me_id", ctx.author.get("id"))
        api_base = ctx.api_base
        headers  = ctx.spoofer.get_headers(referer=f"https://discord.com/channels/@me/{ctx.channel_id}", skip_context_props=True)
        fetched  = 0
        deleted  = 0
        last_id  = None
        while deleted < limit:
            params = {"limit": 100}
            if last_id:
                params["before"] = last_id
            resp = await ctx.http.get(f"{api_base}/channels/{ctx.channel_id}/messages", params=params, headers=headers)
            if resp.status_code != 200:
                break
            msgs = resp.json()
            if not msgs:
                break
            last_id = msgs[-1]["id"]
            for m in msgs:
                if deleted >= limit:
                    break
                if m.get("author", {}).get("id") == me_id:
                    del_resp = await ctx.http.delete(f"{api_base}/channels/{ctx.channel_id}/messages/{m['id']}", headers=headers)
                    if del_resp.status_code == 204:
                        deleted += 1
                    await asyncio.sleep(0.5)
            fetched += len(msgs)
            if fetched >= 500:
                break
        await ctx.send_timed(ansi.success(f"Purged **{deleted}** messages."), 8)

    @handler.command(name="purgeall")
    async def purgeall(ctx, args):
        await ctx.delete()
        me_id    = getattr(handler, "_me_id", ctx.author.get("id"))
        api_base = ctx.api_base
        headers  = ctx.spoofer.get_headers(referer=f"https://discord.com/channels/@me/{ctx.channel_id}", skip_context_props=True)
        deleted  = 0
        last_id  = None
        while True:
            params = {"limit": 100}
            if last_id:
                params["before"] = last_id
            resp = await ctx.http.get(f"{api_base}/channels/{ctx.channel_id}/messages", params=params, headers=headers)
            if resp.status_code != 200:
                break
            msgs = resp.json()
            if not msgs:
                break
            last_id = msgs[-1]["id"]
            found = False
            for m in msgs:
                if m.get("author", {}).get("id") == me_id:
                    del_resp = await ctx.http.delete(f"{api_base}/channels/{ctx.channel_id}/messages/{m['id']}", headers=headers)
                    if del_resp.status_code == 204:
                        deleted += 1
                    found = True
                    await asyncio.sleep(0.5)
            if not found and len(msgs) < 100:
                break
        await ctx.send_timed(ansi.success(f"Purged all **{deleted}** messages."), 8)

    @handler.command(name="auth", aliases=["authuser"])
    async def auth_user(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID and ctx.author.get("id") not in _admins:
            await ctx.send_timed(ansi.error("no permission."), 5)
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("auth", *COMMANDS_INFO["auth"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user mention or ID."), 10)
            return
        try:
            r = _httpx.post(f"{_WEB_URL}/api/internal/auth", json={"discord_id": uid, "action": "auth"}, headers={"X-Internal-Secret": _WEB_SECRET}, timeout=5)
            if r.status_code == 200:
                await ctx.send_timed(ansi.success(f"<@{uid}> authorized on nevermore.icu."), 10)
            else:
                await ctx.send_timed(ansi.error(f"Web panel returned {r.status_code}."), 10)
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Could not reach web panel: {e}"), 10)

    @handler.command(name="unauth", aliases=["unauthuser"])
    async def unauth_user(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID and ctx.author.get("id") not in _admins:
            await ctx.send_timed(ansi.error("no permission."), 5)
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("unauth", *COMMANDS_INFO["unauth"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user mention or ID."), 10)
            return
        try:
            r = _httpx.post(f"{_WEB_URL}/api/internal/auth", json={"discord_id": uid, "action": "unauth"}, headers={"X-Internal-Secret": _WEB_SECRET}, timeout=5)
            if r.status_code == 200:
                await ctx.send_timed(ansi.success(f"<@{uid}> revoked from nevermore.icu."), 10)
            else:
                await ctx.send_timed(ansi.error(f"Web panel returned {r.status_code}."), 10)
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Could not reach web panel: {e}"), 10)

    @handler.command(name="blacklist", aliases=["bl"])
    async def blacklist(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("blacklist", *COMMANDS_INFO["blacklist"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user mention or ID."), 10)
            return
        try:
            r = _httpx.post(f"{_WEB_URL}/api/admin/actions", json={"action": "blacklist", "discord_id": uid}, headers={"X-Internal-Secret": _WEB_SECRET}, timeout=10)
            if r.status_code == 200:
                await ctx.send_timed(ansi.success(f"<@{uid}> blacklisted - instances killed, account banned."), 10)
            else:
                await ctx.send_timed(ansi.error(f"Web panel returned {r.status_code}."), 10)
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Could not reach web panel: {e}"), 10)

    @handler.command(name="unblacklist", aliases=["ubl"])
    async def unblacklist(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not args:
            await ctx.send_timed(ansi.command_usage("unblacklist", *COMMANDS_INFO["unblacklist"], handler.prefix), 10)
            return
        uid = _parse_uid(args[0])
        if not uid:
            await ctx.send_timed(ansi.error("Invalid user mention or ID."), 10)
            return
        try:
            r = _httpx.post(f"{_WEB_URL}/api/admin/actions", json={"action": "unblacklist", "discord_id": uid}, headers={"X-Internal-Secret": _WEB_SECRET}, timeout=10)
            if r.status_code == 200:
                await ctx.send_timed(ansi.success(f"<@{uid}> removed from blacklist."), 10)
            else:
                await ctx.send_timed(ansi.error(f"Web panel returned {r.status_code}."), 10)
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Could not reach web panel: {e}"), 10)

    @handler.command(name="instance", aliases=["instances"])
    async def instance(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return

        import sqlite3 as _sq, subprocess as _sp, json as _jsn

        _pm2_uptime: dict = {}
        _pm2_restarts: dict = {}
        try:
            raw = _sp.check_output(["pm2", "jlist"], timeout=5).decode()
            pm2_list = _jsn.loads(raw)
            for proc in pm2_list:
                pname = proc.get("name", "")
                pm2_env = proc.get("pm2_env", {})
                created = pm2_env.get("created_at", 0)
                if created:
                    elapsed = int(time.time() * 1000) - created
                    s = elapsed // 1000
                    if s < 60:      up = f"{s}s"
                    elif s < 3600:  up = f"{s//60}m{s%60:02d}s"
                    elif s < 86400: up = f"{s//3600}h{(s%3600)//60:02d}m"
                    else:           up = f"{s//86400}d{(s%86400)//3600:02d}h"
                else:
                    up = "?"
                _pm2_uptime[pname]    = up
                _pm2_restarts[pname]  = pm2_env.get("unstable_restarts", 0) or proc.get("pm2_env", {}).get("restart_time", 0)
        except Exception:
            pass

        db_path = "/root/nevermore-next/nevermore.db"

        arg = args[0].strip() if args else None

        target_discord_id = None
        target_inst_id    = None
        page              = 1

        if arg:
            clean = arg.strip("<@!>")
            if clean.isdigit() and len(clean) >= 15:
                target_discord_id = clean
            elif clean.isdigit():
                target_inst_id = int(clean)
            else:
                target_discord_id = None
                target_inst_id    = None

        try:
            conn = _sq.connect(db_path)

            i_cols = [r[1] for r in conn.execute("PRAGMA table_info(instances)").fetchall()]
            u_cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]

            _SKIP = {"token", "password", "secret", "hash", "salt", "key"}

            if arg:
                if target_inst_id is not None:
                    row = conn.execute(
                        "SELECT i.*, u.username, u.discord_id as u_did "
                        "FROM instances i LEFT JOIN users u ON i.discord_id = u.discord_id "
                        "WHERE i.id = ?", (target_inst_id,)
                    ).fetchone()
                    row_desc = conn.execute(
                        "SELECT i.*, u.username, u.discord_id as u_did "
                        "FROM instances i LEFT JOIN users u ON i.discord_id = u.discord_id "
                        "WHERE i.id = ?", (target_inst_id,)
                    ).description if row else None
                    cur = conn.execute(
                        "SELECT i.*, u.username, u.discord_id as u_did "
                        "FROM instances i LEFT JOIN users u ON i.discord_id = u.discord_id "
                        "WHERE i.id = ?", (target_inst_id,)
                    )
                    row = cur.fetchone()
                    col_names = [d[0] for d in cur.description] if cur.description else []
                elif target_discord_id is not None:
                    cur = conn.execute(
                        "SELECT i.*, u.username, u.discord_id as u_did "
                        "FROM instances i LEFT JOIN users u ON i.discord_id = u.discord_id "
                        "WHERE i.discord_id = ? ORDER BY i.id DESC LIMIT 1", (target_discord_id,)
                    )
                    row = cur.fetchone()
                    col_names = [d[0] for d in cur.description] if cur.description else []
                else:
                    cur = conn.execute(
                        "SELECT i.*, u.username, u.discord_id as u_did "
                        "FROM instances i LEFT JOIN users u ON i.discord_id = u.discord_id "
                        "WHERE lower(u.username) LIKE lower(?) ORDER BY i.id DESC LIMIT 1",
                        (f"%{arg}%",)
                    )
                    row = cur.fetchone()
                    col_names = [d[0] for d in cur.description] if cur.description else []

                conn.close()

                if not row:
                    await ctx.send_timed(ansi.error(f"No instance found for **{arg}**."), 10)
                    return

                data   = dict(zip(col_names, row))
                pm2    = data.get("pm2_name", "")
                uptime = _pm2_uptime.get(pm2, "?")
                restarts = _pm2_restarts.get(pm2, "?")

                R = "\u001b[0m"
                lines = [f"{ansi.PURPLE}instance #{data.get('id', '?')}{R}"]

                PRIORITY = ["id", "pm2_name", "status", "discord_id", "username", "prefix"]
                shown = set()
                for k in PRIORITY:
                    if k in data and data[k] is not None:
                        v = str(data[k])
                        sc = ansi.PURPLE if k == "status" and v == "online" else ansi.WHITE
                        lines.append(f"{ansi.CYAN}{k:<16}{ansi.DARK}:: {sc}{v}{R}")
                        shown.add(k)

                lines.append(f"{ansi.CYAN}{'uptime':<16}{ansi.DARK}:: {ansi.WHITE}{uptime}{R}")
                lines.append(f"{ansi.CYAN}{'restarts':<16}{ansi.DARK}:: {ansi.WHITE}{restarts}{R}")

                for k, v in data.items():
                    if k in shown or k in _SKIP or k == "u_did" or v is None:
                        continue
                    lines.append(f"{ansi.CYAN}{k:<16}{ansi.DARK}:: {ansi.WHITE}{str(v)[:60]}{R}")

                await ctx.send_timed(_block("\n".join(lines)), 30)

            else:
                try:
                    page = max(1, int(args[1])) if len(args) > 1 else 1
                except (ValueError, IndexError):
                    page = 1

                insts = conn.execute(
                    "SELECT i.id, i.pm2_name, i.status, i.discord_id, u.username "
                    "FROM instances i LEFT JOIN users u ON i.discord_id = u.discord_id "
                    "WHERE i.status != 'stopped' ORDER BY i.id"
                ).fetchall()
                conn.close()

                if not insts:
                    await ctx.send_timed(ansi.error("No active web instances."), 10)
                    return

                PER_PAGE    = 10
                total       = len(insts)
                total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
                page        = min(page, total_pages)
                chunk       = insts[(page - 1) * PER_PAGE : page * PER_PAGE]

                R = "\u001b[0m"
                rows = []
                for row in chunk:
                    iid, pm2, status, did, uname = row
                    name   = (uname or did or "?")[:18]
                    uptime = _pm2_uptime.get(pm2, "?")
                    color  = ansi.PURPLE if status == "online" else ansi.CYAN
                    rows.append(
                        f"{ansi.CYAN}{name:<18}{R} "
                        f"{ansi.DARK}#{str(iid):<5}{R} "
                        f"{color}{uptime:<8}{R} "
                        f"{ansi.DARK}{status}{R}"
                    )

                head = f"{ansi.PURPLE}instances{R} {ansi.DARK}[{total} total]{R}\n"
                body = "\n".join(rows)
                foot = f"\n{ansi.DARK}{handler.prefix}instance [#id|@user]  |  {page}/{total_pages}{R}"
                await ctx.send_timed(_block(head + body + foot), 25)

        except Exception as e:
            await ctx.send_timed(ansi.error(f"DB error: {e}"), 10)
            return