import asyncio
import json
import re
import time
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "RPC"
CATEGORY_DESC = "Rich Presence / activity status"

COMMANDS_INFO = {
    "rpc":     ("rpc <type> [key=value ...]", "Set a rich presence activity"),
    "rpcstop": ("rpcstop",                    "Clear current rich presence"),
    "rpchelp": ("rpchelp [type]",             "Show RPC type usage"),
}

_RPC_TYPES = [
    "custom_status", "playing", "watching", "listening", "streaming",
    "competing", "spotify", "youtube", "xbox", "playstation",
    "crunchyroll", "custom", "channel_watcher", "clear",
]

_active_cmd: dict = {}
_CDN_PAT = r"https?://(?:cdn\.discordapp\.com|media\.discordapp\.net)/attachments/(\d+)/(\d+)/(.+)"

_KEEPALIVE_INTERVAL = 25 * 60
_DEFAULT_ROTATE_INTERVAL = 20

_rotation_tasks: dict = {}

_ROTATABLE_FIELDS = [
    "text", "state", "details", "name", "song", "artist", "album",
    "video_title", "channel_name", "anime_title", "episode_title",
    "game_name", "large_text", "small_text",
]


def _split_rotatable(cmd: dict) -> list:
    splits = {}
    for field in _ROTATABLE_FIELDS:
        val = cmd.get(field, "")
        if val and "," in str(val):
            parts = [p.strip() for p in str(val).split(",")]
            splits[field] = parts
    if not splits:
        return [cmd]
    max_len = max(len(v) for v in splits.values())
    variants = []
    for i in range(max_len):
        variant = dict(cmd)
        for field, parts in splits.items():
            variant[field] = parts[i % len(parts)]
        variants.append(variant)
    return variants


def _stop_rotation(rpc_type: str):
    task = _rotation_tasks.pop(rpc_type, None)
    if task and not task.done():
        task.cancel()


async def _refresh_cdn_url(http, spoofer, url: str) -> str:
    try:
        headers = spoofer.get_headers(skip_context_props=True)
        r = await http.post(
            "https://discord.com/api/v9/attachments/refresh-urls",
            json={"attachment_urls": [url]},
            headers=headers,
        )
        if r.status_code == 200:
            refreshed = r.json().get("refreshed_urls", [])
            if refreshed:
                return refreshed[0].get("refreshed", url)
    except Exception as e:
        print(f"[RPC] refresh url error: {e}")
    return url


_ASSET_CHANNEL_ID = "1477758738772525239"

async def _upload_n_get_asset_key(http, spoofer, image_url: str):
    if re.search(r'https?://(?:cdn\.discordapp\.com|media\.discordapp\.net)', image_url) and '?' in image_url:
        image_url = await _refresh_cdn_url(http, spoofer, image_url)
    match = re.search(_CDN_PAT, image_url)
    if match:
        ch, att, fn = match.groups()
        return f"mp:attachments/{ch}/{att}/{fn}"
    try:
        r = await http.get(image_url)
        if r.status_code != 200:
            return None
        image_bytes = r.content
        ct = r.headers.get("content-type", r.headers.get("Content-Type", ""))
        filename = image_url.split("/")[-1].split("?")[0]
        if "." not in filename or len(filename) > 50:
            filename = "asset.gif" if "gif" in ct else "asset.png"
        up_headers = spoofer.get_headers(referer=f"https://discord.com/channels/@me/{_ASSET_CHANNEL_ID}", skip_context_props=True)
        up_headers = {k: v for k, v in up_headers.items() if k.lower() != "content-type"}
        msg_resp = await http.post(
            f"https://discord.com/api/v9/channels/{_ASSET_CHANNEL_ID}/messages",
            headers=up_headers,
            files={
                "files[0]": (filename, image_bytes, ct or "image/png"),
                "payload_json": (None, '{"content":""}', "application/json"),
            },
        )
        if msg_resp.status_code not in (200, 201):
            return None
        attachments = msg_resp.json().get("attachments", [])
        if not attachments:
            return None
        msg_id = msg_resp.json()["id"]
        m2 = re.search(_CDN_PAT, attachments[0]["url"])
        if not m2:
            return None
        c2, a2, f2 = m2.groups()
        asset_key = f"mp:attachments/{c2}/{a2}/{f2}"
        try:
            del_headers = spoofer.get_headers(skip_context_props=True)
            await http.delete(f"https://discord.com/api/v9/channels/{_ASSET_CHANNEL_ID}/messages/{msg_id}", headers=del_headers)
        except Exception:
            pass
        return asset_key
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"[RPC] asset upload error: {e}")
        return None


async def _send_payload(handler, activities: list):
    gateway = getattr(handler, "gateway", None)
    if not gateway:
        raise RuntimeError("Gateway not connected")
    ws = getattr(gateway, "_ws", None)
    if not ws:
        raise RuntimeError("Gateway not connected")
    await ws.send_str(json.dumps({"op": 3, "d": {"since": 0, "activities": activities, "status": "online", "afk": False}}))


async def _build_activity(handler, cmd: dict):
    http = handler.http
    spoofer = handler.spoofer
    rpc_type = cmd.get("rpc_type", "").lower()
    t = int(time.time() * 1000)

    def ts_now(): return {"start": t}
    def ts_prog(el, tot):
        cur = int(float(el) * 60000)
        return {"start": t - cur, "end": t - cur + int(float(tot) * 60000)}
    def mk_buttons(act):
        btns = cmd.get("buttons") or []
        burls = cmd.get("button_urls") or []
        pairs = [(b, u) for b, u in zip(btns, burls) if b and u][:2]
        if pairs:
            act["buttons"] = [p[0] for p in pairs]
            act.setdefault("metadata", {})["button_urls"] = [p[1] for p in pairs]
    async def img(fallback):
        u = cmd.get("image_url", "")
        if not u or not u.startswith("http"): return fallback
        key = await _upload_n_get_asset_key(http, spoofer, u)
        return key if key else fallback
    async def small_img():
        u = cmd.get("small_image_url", "")
        if not u or not u.startswith("http"): return None
        key = await _upload_n_get_asset_key(http, spoofer, u)
        return key if key else None
    def mk_assets(large_image, large_text="", small_image="", small_text=""):
        a = {}
        if large_image: a["large_image"] = large_image
        if large_text:  a["large_text"]  = large_text
        if small_image: a["small_image"] = small_image
        if small_text:  a["small_text"]  = small_text
        return a if a else None

    if rpc_type == "clear": return None
    if rpc_type == "custom_status":
        invis = cmd.get("invisible", False)
        txt = "\u200e" if invis else cmd.get("text", "")[:128]
        emoji = cmd.get("emoji", "")
        act = {"type": 4, "name": "Custom Status", "state": txt}
        if emoji: act["emoji"] = {"name": emoji, "id": None, "animated": False}
        return act
    if rpc_type == "spotify":
        song = cmd.get("song", "Unknown"); artist = cmd.get("artist", "Unknown"); album = cmd.get("album", "")
        dur = float(cmd.get("duration", 3.5)); pos = float(cmd.get("current_position", 0))
        cur_ms = int(pos * 60000); tot_ms = int(dur * 60000)
        start = t - cur_ms; end = start + tot_ms
        tid = "0VjIjW4GlUZAMYd2vXMi3b"; aid = "4yP0hdKOZPNshxUOjY0cZj"; arid = "1Xyo4u8uXC1ZmMpatF05PJ"
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 2, "name": "Spotify", "details": song[:128], "state": artist[:128],
               "timestamps": {"start": start, "end": end}, "application_id": "3201606009684",
               "sync_id": tid, "session_id": f"spotify:{tid}", "party": {"id": f"spotify:{tid}", "size": [1, 1]},
               "secrets": {"join": tid, "spectate": tid, "match": tid}, "instance": True, "flags": 48,
               "metadata": {"context_uri": f"spotify:album:{aid}", "album_id": aid, "artist_ids": [arid], "track_id": tid},
               **({"assets": mk_assets(asset_key, f"{album} on Spotify" if album else "", small_key, cmd.get("small_text",""))} if (asset_key or album or small_key) else {})}
        mk_buttons(act); return act
    if rpc_type == "youtube":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 3, "name": "YouTube", "details": cmd.get("video_title","Video")[:128], "state": cmd.get("channel_name","Channel")[:128],
               "application_id": "111299001912", "timestamps": ts_prog(float(cmd.get("elapsed_minutes",0)), float(cmd.get("duration_minutes",10))),
               **({"assets": mk_assets(asset_key, "", small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        mk_buttons(act); return act
    if rpc_type == "xbox":
        asset_key = await img(None)
        act = {"type": 0, "name": cmd.get("game_name","Game")[:128], "application_id": "622174530214821906", "platform": "xbox", "timestamps": ts_now(),
               **({"assets": mk_assets(asset_key)} if mk_assets(asset_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        pc, pm = cmd.get("party_cur"), cmd.get("party_max")
        if pc and pm: act["party"] = {"id": "xbox-party", "size": [int(pc), int(pm)]}
        mk_buttons(act); return act
    if rpc_type in ("playstation", "ps4", "ps5"):
        asset_key = await img(None)
        act = {"type": 0, "name": cmd.get("game_name","Game")[:128], "application_id": "1470539864909943067",
               "platform": cmd.get("platform","ps5"), "timestamps": ts_now(),
               **({"assets": mk_assets(asset_key)} if mk_assets(asset_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        pc, pm = cmd.get("party_cur"), cmd.get("party_max")
        if pc and pm: act["party"] = {"id": "ps-party", "size": [int(pc), int(pm)]}
        mk_buttons(act); return act
    if rpc_type == "crunchyroll":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 3, "name": "Crunchyroll", "details": cmd.get("anime_title","Anime")[:128],
               "application_id": "981509069309354054", "timestamps": ts_prog(float(cmd.get("elapsed_minutes",0)), float(cmd.get("total_minutes",24))),
               **({"assets": mk_assets(asset_key, "", small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        if cmd.get("episode_title"): act["state"] = cmd["episode_title"][:128]
        mk_buttons(act); return act
    if rpc_type == "playing":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 0, "name": cmd.get("name","Game")[:128], "application_id": cmd.get("app_id") or "367827983903490050",
               "timestamps": ts_now(), **({"assets": mk_assets(asset_key, cmd.get("large_text",""), small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        pc, pm = cmd.get("party_cur"), cmd.get("party_max")
        if pc and pm: act["party"] = {"id": "game-party", "size": [int(pc), int(pm)]}
        mk_buttons(act); return act
    if rpc_type == "watching":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 3, "name": cmd.get("name","Show")[:128], "application_id": cmd.get("app_id") or "367827983903490050",
               **({"assets": mk_assets(asset_key, cmd.get("large_text",""), small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        tot = float(cmd.get("total_minutes", 0))
        if tot: act["timestamps"] = ts_prog(float(cmd.get("elapsed_minutes",0)), tot)
        mk_buttons(act); return act
    if rpc_type == "listening":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 2, "name": cmd.get("name","Music")[:128], "application_id": cmd.get("app_id") or "534203414247112723",
               **({"assets": mk_assets(asset_key, cmd.get("large_text",""), small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        tot = float(cmd.get("total_minutes", 0))
        if tot: act["timestamps"] = ts_prog(float(cmd.get("elapsed_minutes",0)), tot)
        mk_buttons(act); return act
    if rpc_type == "streaming":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 1, "name": cmd.get("name","Stream")[:128], "url": cmd.get("stream_url") or "https://twitch.tv/kaicenat",
               "application_id": cmd.get("app_id") or "111299001912", "timestamps": ts_now(),
               **({"assets": mk_assets(asset_key, cmd.get("large_text",""), small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        mk_buttons(act); return act
    if rpc_type == "competing":
        asset_key = await img(None)
        small_key = await small_img()
        act = {"type": 5, "name": cmd.get("name","Tournament")[:128], "application_id": cmd.get("app_id") or "367827983903490050",
               "timestamps": ts_now(), **({"assets": mk_assets(asset_key, cmd.get("large_text",""), small_key, cmd.get("small_text",""))} if (asset_key or small_key) else {})}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        mk_buttons(act); return act
    if rpc_type == "channel_watcher":
        channel_id = cmd.get("channel_id", "")
        dm_image = "https://media.discordapp.net/attachments/1477084885528346826/1482167475494719558/733700_chat_512x512-removebg-preview.png?ex=69b5f787&is=69b4a607&hm=c08e3e05b2a1ddecbfc548fc3a0fc9ea588816ffc0704ba295f8a7c1397d01f2&=&format=webp&quality=lossless&width=115&height=115"
        try:
            ch_headers = spoofer.get_headers(skip_context_props=False)
            ch_resp = await http.get(
                f"https://discord.com/api/v9/channels/{channel_id}",
                headers=ch_headers,
            )
            if ch_resp.status_code != 200:
                return None
            ch = ch_resp.json()
            ch_type = ch.get("type", -1)
            is_dm = ch_type in (1, 3)
            if is_dm:
                if ch_type == 1:
                    recipients = ch.get("recipients", [])
                    other = recipients[0] if recipients else {}
                    display_name = other.get("global_name") or other.get("username") or "Unknown"
                    activity_name = "Discord"
                    details = f"DM with {display_name}"
                else:
                    activity_name = ch.get("name") or "Group DM"
                    details = "typing..."
                large_image_key = await _upload_n_get_asset_key(http, spoofer, dm_image)
            else:
                guild_id = ch.get("guild_id", "")
                ch_name = ch.get("name", "unknown")
                activity_name = "Server"
                details = f"#{ch_name}"
                # try guild fetch for name + icon, don't fail if 403s
                large_image_key = None
                try:
                    g_resp = await http.get(
                        f"https://discord.com/api/v9/guilds/{guild_id}",
                        headers=ch_headers,
                    )
                    if g_resp.status_code == 200:
                        guild = g_resp.json()
                        activity_name = guild.get("name", "Server")
                        icon_hash = guild.get("icon")
                        if icon_hash:
                            ext = "gif" if icon_hash.startswith("a_") else "png"
                            icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.{ext}?size=256"
                            large_image_key = await _upload_n_get_asset_key(http, spoofer, icon_url)
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[RPC] channel_watcher fetch error: {e}")
            return None
        act = {
            "type": 0,
            "name": activity_name[:128],
            "details": details[:128],
            "timestamps": ts_now(),
        }
        if large_image_key:
            act["application_id"] = cmd.get("app_id") or "367827983903490050"
            act["assets"] = {"large_image": large_image_key, "large_text": activity_name[:128]}
        return act
    if rpc_type == "custom":
        name = cmd.get("name","Activity")[:128]; act_type = int(cmd.get("activity_type",0))
        act = {"type": act_type, "name": name, "application_id": cmd.get("app_id") or "367827983903490050"}
        if cmd.get("details"): act["details"] = cmd["details"][:128]
        if cmd.get("state"): act["state"] = cmd["state"][:128]
        if act_type == 1 and cmd.get("stream_url"): act["url"] = cmd["stream_url"]
        li_url = cmd.get("large_image",""); si_url = cmd.get("small_image","")
        if li_url or si_url:
            act["assets"] = {}
            if li_url: act["assets"]["large_image"] = li_url; act["assets"]["large_text"] = cmd.get("large_text", name)[:128]
            if si_url: act["assets"]["small_image"] = si_url; act["assets"]["small_text"] = cmd.get("small_text","")[:128]
        tot_v = cmd.get("total_minutes")
        act["timestamps"] = ts_prog(float(cmd.get("elapsed_minutes",0)), float(tot_v)) if tot_v else ts_now()
        pc, pm = cmd.get("party_cur"), cmd.get("party_max")
        if pc and pm: act["party"] = {"id": "custom-party", "size": [int(pc), int(pm)]}
        mk_buttons(act); return act
    return None


async def _build_and_send(handler, cmd: dict):
    rpc_type = cmd.get("rpc_type", "").lower()
    if rpc_type == "clear":
        await _send_payload(handler, [])
        return
    act = await _build_activity(handler, cmd)
    if act is None: return
    merged = []
    for rt, existing_cmd in list(_active_cmd.items()):
        if rt == rpc_type: continue
        existing_act = await _build_activity(handler, existing_cmd)
        if existing_act: merged.append(existing_act)
    merged.append(act)
    await _send_payload(handler, merged)


async def _run_rotation(handler, rpc_type: str, variants: list, interval: int):
    idx = 0
    try:
        while True:
            variant = variants[idx % len(variants)]
            _active_cmd[rpc_type] = variant
            try:
                await _build_and_send(handler, variant)
            except Exception as e:
                print(f"[RPC] rotation send error: {e}")
            idx += 1
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        pass


def setup(handler):
    import sys as _sys
    handler._rpc_module = _sys.modules[__name__]

    prefix = handler.prefix

    def _get_active_activities():
        return _active_cmd.copy() if _active_cmd else None
    handler._get_active_activities = _get_active_activities

    _orig_on_ready = getattr(handler, "on_ready", None)
    async def _on_ready_hook():
        if _orig_on_ready: await _orig_on_ready()
        if _active_cmd:
            await asyncio.sleep(3)
            try:
                acts = []
                for rt_cmd in list(_active_cmd.values()):
                    a = await _build_activity(handler, rt_cmd)
                    if a: acts.append(a)
                if acts: await _send_payload(handler, acts)
                print("[RPC] Reapplied presence after reconnect")
            except Exception as e:
                print(f"[RPC] Reapply failed: {e}")
    handler.on_ready = _on_ready_hook

    if not getattr(handler, "_rpc_keepalive_task", None):
        async def _keepalive_loop():
            while True:
                await asyncio.sleep(_KEEPALIVE_INTERVAL)
                if not _active_cmd: continue
                gateway = getattr(handler, "gateway", None)
                ws = getattr(gateway, "_ws", None) if gateway else None
                if not ws: continue
                try:
                    acts = []
                    for rt_cmd in list(_active_cmd.values()):
                        a = await _build_activity(handler, rt_cmd)
                        if a: acts.append(a)
                    if acts: await _send_payload(handler, acts)
                    print("[RPC] keepalive resent presence")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"[RPC] keepalive failed: {e}")
        handler._rpc_keepalive_task = handler._spawn(_keepalive_loop())

    def _parse_kv(args: list) -> dict:
        cmd = {}
        if not args: return cmd
        cmd["rpc_type"] = args[0].lower()
        raw = " ".join(args[1:]).strip()
        if not raw: return cmd
        tokens = re.split(r'(?:(?:^| )([a-zA-Z_]\w*)=)', raw)
        i = 1
        while i < len(tokens) - 1:
            k = tokens[i]
            if not k: i += 2; continue
            v = tokens[i + 1].strip() if tokens[i + 1] else ""
            if k in ("buttons", "button_urls"): cmd.setdefault(k, []).append(v)
            else: cmd[k] = v
            i += 2
        return cmd

    @handler.command(name="rpc")
    async def rpc(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("rpc", *COMMANDS_INFO["rpc"], prefix), 15)
            return
        cmd = _parse_kv(args)
        rpc_type = cmd.get("rpc_type", "")
        if rpc_type not in _RPC_TYPES:
            await ctx.send_timed(ansi.error(f"Unknown type **{rpc_type}**. Types: {', '.join(_RPC_TYPES)}"), 15)
            return
        _stop_rotation(rpc_type)
        try:
            if rpc_type == "clear":
                await _build_and_send(handler, cmd)
                _active_cmd.clear()
                await ctx.send_timed(ansi.success("Rich presence cleared."), 10)
                return
            interval = int(cmd.get("rotate_interval", _DEFAULT_ROTATE_INTERVAL))
            variants = _split_rotatable(cmd)
            rotating = len(variants) > 1
            _active_cmd[rpc_type] = variants[0]
            await _build_and_send(handler, variants[0])
            active_types = ", ".join(_active_cmd.keys())
            extra = f" Rotating {len(variants)} variants every {interval}s." if rotating else ""
            await ctx.send_timed(ansi.success(f"RPC set to **{rpc_type}**. Active: {active_types}.{extra} Keepalive active (resends every 25m)."), 10)
            if rotating:
                task = asyncio.create_task(_run_rotation(handler, rpc_type, variants, interval))
                _rotation_tasks[rpc_type] = task
            else:
                await asyncio.sleep(2)
                try: await _build_and_send(handler, cmd)
                except asyncio.CancelledError: raise
                except Exception: pass
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Failed: {e}"), 10)

    @handler.command(name="rpcstop")
    async def rpcstop(ctx, args):
        await ctx.delete()
        try:
            for rt in list(_rotation_tasks.keys()): _stop_rotation(rt)
            await _send_payload(handler, [])
            _active_cmd.clear()
            await ctx.send_timed(ansi.success("Rich presence cleared."), 10)
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Failed: {e}"), 10)

    @handler.command(name="rpchelp")
    async def rpchelp(ctx, args):
        await ctx.delete()
        R = "\u001b[0m"
        _usage = {
            "custom_status": "rpc custom_status text=<t1,t2,t3> [emoji=<e>] [invisible=true] [rotate_interval=20]",
            "playing":       "rpc playing name=<g1,g2> [details=<d1,d2>] [state=<s1,s2>] [image_url=<url>] [rotate_interval=20]",
            "watching":      "rpc watching name=<show> [details=<d>] [state=<s>] [elapsed_minutes=N] [total_minutes=N]",
            "listening":     "rpc listening name=<m1,m2> [details=<d>] [state=<s>] [elapsed_minutes=N] [total_minutes=N]",
            "streaming":     "rpc streaming name=<title> [stream_url=<url>] [details=<d>] [state=<s>]",
            "competing":     "rpc competing name=<t1,t2> [details=<d>] [state=<s>]",
            "spotify":       "rpc spotify song=<s1,s2> artist=<a1,a2> [album=<a>] [duration=3.5] [rotate_interval=20]",
            "youtube":       "rpc youtube video_title=<t1,t2> channel_name=<ch> [elapsed_minutes=N] [duration_minutes=N]",
            "xbox":          "rpc xbox game_name=<g1,g2> [details=<d>] [state=<s>] [image_url=<url>]",
            "playstation":   "rpc playstation game_name=<g1,g2> [platform=ps5] [details=<d>] [state=<s>]",
            "crunchyroll":   "rpc crunchyroll anime_title=<a1,a2> episode_title=<ep> [elapsed_minutes=N] [total_minutes=24]",
            "custom":        "rpc custom name=<n> [activity_type=0] [app_id=<id>] [details=<d>] [state=<s>]",
            "channel_watcher": "rpc channel_watcher channel_id=<id>",
            "clear":         "rpc clear",
        }
        if not args:
            lines = [f"{ansi.CYAN}{tp}{R}" for tp in _RPC_TYPES]
            note = f"\n{ansi.DARK}Tip: comma-separate any text field to rotate. e.g. state=idle,gaming,afk [rotate_interval=20]{R}"
            await ctx.send_timed(_block("  ".join(lines) + note), 20)
            return
        t = args[0].lower()
        usage = _usage.get(t)
        if not usage:
            await ctx.send_timed(ansi.error(f"Unknown type **{t}**."), 10)
            return
        await ctx.send_timed(_block(f"{ansi.CYAN}{t}{R}\n{ansi.WHITE}{usage}{R}"), 20)