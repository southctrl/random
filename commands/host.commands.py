import asyncio
import importlib.util
import json
import os
import sys
import time

from curl_cffi import AsyncSession
from core.tools.headers import Headers

from core.tools import ansi
from core.tools.ansi import _block


CATEGORY      = "Host"
CATEGORY_DESC = "Multi-account session hosting"

COMMANDS_INFO = {
    "host":       ("host <token>",            "Host another account on this selfbot"),
    "hostlist":   ("hostlist",                "List all hosted accounts"),
    "hoststop":   ("hoststop <index>",        "Stop a hosted account by index"),
    "hoststopall":("hoststopall",             "Stop all hosted accounts"),
    "hostexec":   ("hostexec <i> <cmd>",      "Run a command as a hosted account"),
    "hostping":   ("hostping <i>",            "Ping a hosted account's API"),
}

_OWNER_ID = "475336041956376576"

_sessions: list = []

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOKENS_FILE  = os.path.join(_BASE_DIR, "hosted_tokens.json")
# premium.json: {"discord_id": true/false, ...}
_PREMIUM_FILE = os.path.join(_BASE_DIR, "premium.json")


def _save_tokens():
    active = [s["token"] for s in _sessions if s["status"] != "stopped"]
    try:
        with open(_TOKENS_FILE, "w") as f:
            json.dump(active, f)
    except Exception as e:
        print(f"[HOST] Could not save tokens: {e}")


def _load_tokens() -> list:
    try:
        with open(_TOKENS_FILE) as f:
            data = json.load(f)
        if isinstance(data, list):
            return [t for t in data if isinstance(t, str) and len(t) > 50]
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[HOST] Could not load tokens: {e}")
    return []


def _is_premium(discord_id: str) -> bool:
    try:
        with open(_PREMIUM_FILE) as f:
            data = json.load(f)
        return bool(data.get(str(discord_id), False))
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"[HOST] Could not read premium file: {e}")
        return False


def _set_premium(discord_id: str, value: bool):
    try:
        try:
            with open(_PREMIUM_FILE) as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        data[str(discord_id)] = value
        with open(_PREMIUM_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[HOST] Could not write premium file: {e}")


def _token_user_id(token: str) -> str:
    """Decode user ID from a Discord token (base64 first segment)."""
    import base64
    try:
        seg = token.split(".")[0]
        pad = seg + "=" * (-len(seg) % 4)
        return base64.b64decode(pad).decode()
    except Exception:
        return ""


def _fmt_index(i: int) -> str:
    return str(i + 1)


def _get_session(arg: str):
    try:
        idx = int(arg) - 1
        if 0 <= idx < len(_sessions):
            return _sessions[idx]
    except (ValueError, IndexError):
        pass
    low = arg.lower()
    for s in _sessions:
        if s.get("username", "").lower() == low:
            return s
    return None


async def _load_commands_for(handler, commands_dir: str, modules: list, master_prefix: str) -> list:
    fresh_modules = []
    for mod in modules:
        if getattr(mod, "CATEGORY", "") == "Host":
            continue
        try:
            src_file = mod.__spec__.origin if mod.__spec__ else None
            if not src_file or not os.path.exists(src_file):
                continue
            mod_name = f"_hosted_{handler._host_index}_{os.path.basename(src_file)[:-3]}"
            spec = importlib.util.spec_from_file_location(mod_name, src_file)
            fresh = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = fresh
            spec.loader.exec_module(fresh)
            if hasattr(fresh, "setup"):
                fresh.setup(handler)
                fresh_modules.append(fresh)
        except Exception as e:
            cat = getattr(mod, "CATEGORY", mod.__name__)
            print(f"[HOST] failed to load '{cat}' for guest: {e}")
    return fresh_modules


async def _validate_token(token: str, api_base: str):
    try:
        spoofer = Headers(token)
        headers = spoofer.get_headers(skip_context_props=True)
        async with AsyncSession(impersonate="chrome136") as session:
            resp = await session.get(f"{api_base}/users/@me", headers=headers)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        print(f"[HOST] token validate error: {e}")
    return None


def _register_help_for(handler, modules: list):
    prefix = handler.prefix

    def _cats():
        return {
            getattr(m, "CATEGORY", None): getattr(m, "CATEGORY_DESC", "")
            for m in modules if getattr(m, "CATEGORY", None)
        }

    def _cat_cmds(category):
        for m in modules:
            if getattr(m, "CATEGORY", "").lower() == category.lower():
                return list(getattr(m, "COMMANDS_INFO", {}).items())
        return []

    def _all_cmds():
        result = {}
        for m in modules:
            result.update(getattr(m, "COMMANDS_INFO", {}))
        return result

    @handler.command(name="help", aliases=["h"])
    async def _hosted_help(ctx, args):
        await ctx.delete()
        if not args:
            cats = _cats()
            head = ansi.header(f"{prefix}help <category>  or  {prefix}help <command>")
            body = ansi.category_list(cats)
            foot = ansi.footer_main()
            await ctx.send_timed(head + "\n" + body + "\n" + foot, 10)
            return
        query = args[0].lower()
        page  = 1
        if len(args) > 1:
            try:
                page = int(args[1])
            except ValueError:
                pass
        cats = _cats()
        def _cat_match(k, q):
            kl = k.lower()
            if kl == q: return True
            if kl.replace(" ", "") == q.replace(" ", ""): return True
            if kl.startswith(q): return True
            initials = "".join(w[0] for w in k.split())
            if initials.lower() == q: return True
            return False
        cat_match = next((k for k in cats if _cat_match(k, query)), None)
        if cat_match:
            cmds      = _cat_cmds(cat_match)
            per_page  = 5
            total_pgs = max(1, (len(cmds) + per_page - 1) // per_page)
            page      = max(1, min(page, total_pgs))
            chunk     = cmds[(page - 1) * per_page: page * per_page]
            head = ansi.header(f"{cat_match.upper()} :: page {page}/{total_pgs}")
            body = ansi.command_list([(n, d) for n, (_, d) in chunk])
            foot = ansi.footer_page(prefix, cat_match, page, total_pgs)
            await ctx.send_timed(head + "\n" + body + "\n" + foot, 10)
            return
        all_info = _all_cmds()
        if query in all_info:
            usage, desc = all_info[query]
            await ctx.send_timed(ansi.command_usage(query, usage, desc, prefix), 10)
            return
        await ctx.send_timed(ansi.error(f"No command or category found: **{query}**"), 10)


async def _run_hosted(session: dict, commands_dir: str, modules: list):
    from core import Gateway
    from core.tools import CommandHandler

    token   = session["token"]
    handler = CommandHandler(session["prefix"])
    handler._host_index = id(session)
    handler._is_hosted  = True
    gateway = Gateway(token, handler)

    handler.spoofer  = gateway.spoofer
    handler.api_base = "https://discord.com/api/v10"

    session["handler"] = handler
    session["gateway"] = gateway

    async def _on_ready():
        try:
            headers = handler.spoofer.get_headers(skip_context_props=True)
            me = await handler.http.get(f"{handler.api_base}/users/@me", headers=headers)
            if me.status_code == 200:
                data = me.json()
                session["username"] = data.get("global_name") or data.get("username", "?")
                session["user_id"]  = data.get("id", "")
                handler._me_id      = session["user_id"]
        except Exception as e:
            print(f"[HOST] could not fetch hosted user info: {e}")
        session["status"] = "online"
        print(f"[HOST] Session #{_sessions.index(session)+1} online as {session['username']}")

    handler.on_ready = _on_ready

    await gateway._init_http()

    fresh_mods = await _load_commands_for(handler, commands_dir, modules, session["prefix"])
    print(f"[HOST] loaded {len(fresh_mods)} modules for guest")
    _register_help_for(handler, fresh_mods)

    session["status"] = "connecting"
    max_reconnects = 3
    fails = 0
    try:
        while gateway._running and fails < max_reconnects:
            try:
                await gateway._connect()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[HOST] Session error: {e}")
            if not gateway._running:
                break
            fails += 1
            if fails >= max_reconnects:
                print(f"[HOST] Session for {session.get('username', '?')} hit max reconnects - stopping")
                break
            delay = min(gateway._reconnect_delay * (2 ** (fails - 1)), 60)
            print(f"[HOST] Reconnecting in {delay}s... ({fails}/{max_reconnects})")
            await asyncio.sleep(delay)
    except asyncio.CancelledError:
        pass
    finally:
        session["status"] = "stopped"
        print(f"[HOST] Session for {session.get('username', '?')} stopped")
        session["handler"] = None
        session["gateway"] = None



async def _web_exec_poller(handler, sessions_ref):
    import os, json, asyncio
    last_ts = {}
    while True:
        await asyncio.sleep(2)
        try:
            for s in list(sessions_ref):
                uid = s.get("user_id", "")
                if not uid or s.get("status") != "online":
                    continue
                fpath = f"/tmp/exec_{uid}.json"
                if not os.path.exists(fpath):
                    continue
                with open(fpath) as f:
                    data = json.load(f)
                ts = data.get("_ts", 0)
                if ts <= last_ts.get(uid, 0):
                    continue
                last_ts[uid] = ts
                cmd = data.get("command", "").strip()
                if not cmd:
                    continue
                h = s.get("handler")
                if not h:
                    continue
                fake = {
                    "id": "0",
                    "channel_id": "0",
                    "guild_id": None,
                    "author": {
                        "id": uid,
                        "username": s.get("username", "?"),
                        "discriminator": "0",
                        "bot": False,
                    },
                    "content": f"{h.prefix}{cmd}",
                }
                print(f"[HOST] Web exec for {s.get('username','?')}: {cmd}")
                await h.handle(fake)
        except Exception as e:
            print(f"[HOST] web exec poller error: {e}")

def setup(handler):
    prefix     = handler.prefix
    _is_hosted = getattr(handler, "_is_hosted", False)

    if not _is_hosted:
        import asyncio as _aio
        _aio.get_event_loop().create_task(_web_exec_poller(handler, _sessions))

        _orig_on_ready = getattr(handler, "on_ready", None)
        async def _rehost_on_ready():
            if _orig_on_ready:
                await _orig_on_ready()
            saved = _load_tokens()
            if not saved:
                return
            print(f"[HOST] Auto-rehosting {len(saved)} saved token(s)")
            await asyncio.sleep(3)
            master_modules      = getattr(handler, "_modules",      [])
            master_commands_dir = getattr(handler, "_commands_dir", "")
            for token in saved:
                if any(s["token"] == token and s["status"] != "stopped" for s in _sessions):
                    continue
                session = {
                    "token":    token,
                    "handler":  None,
                    "gateway":  None,
                    "task":     None,
                    "username": "connecting",
                    "user_id":  "",
                    "started":  time.time(),
                    "status":   "connecting",
                    "prefix":   prefix,
                }
                _sessions.append(session)
                task = asyncio.create_task(
                    _run_hosted(session, master_commands_dir, master_modules)
                )
                session["task"] = task
                print(f"[HOST] Auto-rehosting token ...{token[-6:]}")
        handler.on_ready = _rehost_on_ready

    @handler.command(name="host")
    async def host(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if _is_hosted:
            return
        if not args:
            await ctx.send_timed(
                ansi.command_usage("host", *COMMANDS_INFO["host"], prefix), 10
            )
            return

        token = args[0].strip()
        if len(token) < 50:
            await ctx.send_timed(ansi.error("That doesn't look like a valid token."), 10)
            return

        for s in _sessions:
            if s["token"] == token and s["status"] != "stopped":
                await ctx.send_timed(ansi.error("That token is already being hosted."), 10)
                return

        validating_msg = await ctx.send(ansi.success("Validating token..."))
        vm_id = (validating_msg or {}).get("id")
        user_data = await _validate_token(token, ctx.api_base)
        if not user_data:
            if vm_id:
                await ctx.edit(vm_id, ansi.error("Invalid or unauthorised token - not hosting."))
                await asyncio.sleep(6)
                await ctx.delete(vm_id)
            return

        display = user_data.get("global_name") or user_data.get("username", "?")
        token_uid = user_data.get("id", "")

        # Owner can host anyone; others must own the token or have premium
        requester_id = ctx.author.get("id", "")
        if requester_id != _OWNER_ID:
            token_matches = (token_uid == requester_id)
            if not token_matches and not _is_premium(requester_id):
                if vm_id:
                    await ctx.edit(vm_id, ansi.error(
                        "You can only host your own token. Upgrade to **premium** to host others."
                    ))
                    await asyncio.sleep(8)
                    await ctx.delete(vm_id)
                return

        master_modules      = getattr(handler, "_modules",      [])
        master_commands_dir = getattr(handler, "_commands_dir", "")

        session = {
            "token":    token,
            "handler":  None,
            "gateway":  None,
            "task":     None,
            "username": display,
            "user_id":  token_uid,
            "started":  time.time(),
            "status":   "connecting",
            "prefix":   prefix,
        }
        _sessions.append(session)
        idx = len(_sessions)

        task = asyncio.create_task(
            _run_hosted(session, master_commands_dir, master_modules)
        )
        session["task"] = task
        _save_tokens()

        if vm_id:
            await ctx.edit(vm_id, ansi.success(f"Hosting **{display}** as session **#{idx}** - connecting..."))
            await asyncio.sleep(10)
            await ctx.delete(vm_id)
        else:
            await ctx.send_timed(ansi.success(f"Hosting **{display}** as session **#{idx}**."), 10)

    @handler.command(name="hostlist", aliases=["hosts"])
    async def hostlist(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not _sessions:
            await ctx.send_timed(ansi.error("No accounts are being hosted."), 10)
            return

        R    = "\u001b[0m"
        rows = []
        for i, s in enumerate(_sessions):
            status = s["status"]
            color  = ansi.PURPLE if status == "online" else (
                     ansi.CYAN   if status == "connecting" else ansi.DARK)
            name   = s.get("username", "?")
            uid    = s.get("user_id", "")
            up_s   = int(time.time() - s["started"])
            up_str = f"{up_s//3600}h{(up_s%3600)//60}m{up_s%60}s"
            rows.append(
                f"{ansi.CYAN}#{i+1:<3}{R} "
                f"{ansi.WHITE}{name:<20}{R} "
                f"{color}{status:<11}{R} "
                f"{ansi.DARK}up {up_str}  id:{uid}{R}"
            )

        await ctx.send_timed(_block("\n".join(rows)), 20)

    @handler.command(name="hoststop")
    async def hoststop(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not args:
            await ctx.send_timed(
                ansi.command_usage("hoststop", *COMMANDS_INFO["hoststop"], prefix), 10
            )
            return

        s = _get_session(args[0])
        if not s:
            await ctx.send_timed(ansi.error(f"No session **#{args[0]}** found."), 10)
            return
        if s["status"] == "stopped":
            await ctx.send_timed(ansi.error("That session is already stopped."), 10)
            return

        task = s.get("task")
        if task and not task.done():
            task.cancel()

        gw = s.get("gateway")
        if gw:
            gw._running = False
            ws = getattr(gw, "_ws", None)
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass

        s["status"] = "stopped"
        s["handler"] = None
        s["gateway"] = None
        name = s.get("username", "?")
        _sessions[:] = [x for x in _sessions if x["status"] != "stopped"]
        _save_tokens()
        await ctx.send_timed(ansi.success(f"Stopped hosted session **{name}**."), 10)

    @handler.command(name="hoststopall")
    async def hoststopall(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not _sessions:
            await ctx.send_timed(ansi.error("No active sessions."), 10)
            return

        stopped = 0
        for s in _sessions:
            if s["status"] == "stopped":
                continue
            task = s.get("task")
            if task and not task.done():
                task.cancel()
            gw = s.get("gateway")
            if gw:
                gw._running = False
                ws = getattr(gw, "_ws", None)
                if ws:
                    try:
                        await ws.close()
                    except Exception:
                        pass
            s["status"] = "stopped"
            s["handler"] = None
            s["gateway"] = None
            stopped += 1

        _sessions.clear()
        _save_tokens()
        await ctx.send_timed(ansi.success(f"Stopped **{stopped}** hosted session(s)."), 10)

    @handler.command(name="hostexec", aliases=["hx"])
    async def hostexec(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if len(args) < 2:
            await ctx.send_timed(
                ansi.command_usage("hostexec", *COMMANDS_INFO["hostexec"], prefix), 10
            )
            return

        s = _get_session(args[0])
        if not s:
            await ctx.send_timed(ansi.error(f"No session **#{args[0]}** found."), 10)
            return
        if s["status"] != "online":
            await ctx.send_timed(ansi.error(f"Session **#{args[0]}** is not online yet."), 10)
            return

        h        = s["handler"]
        cmd_text = " ".join(args[1:])

        fake_message = {
            "id":         ctx.id,
            "channel_id": ctx.channel_id,
            "guild_id":   ctx.guild_id,
            "author": {
                "id":            s.get("user_id", "0"),
                "username":      s.get("username", "?"),
                "discriminator": "0",
                "bot":           False,
            },
            "content": f"{h.prefix}{cmd_text}",
        }
        await h.handle(fake_message)

    @handler.command(name="hostping", aliases=["hp"])
    async def hostping(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if not args:
            await ctx.send_timed(
                ansi.command_usage("hostping", *COMMANDS_INFO["hostping"], prefix), 10
            )
            return

        s = _get_session(args[0])
        if not s:
            await ctx.send_timed(ansi.error(f"No session **#{args[0]}** found."), 10)
            return
        if s["status"] != "online":
            await ctx.send_timed(ansi.error("Session is not online."), 10)
            return

        h = s["handler"]
        headers = h.spoofer.get_headers(skip_context_props=True)
        t0 = time.perf_counter()
        try:
            resp = await h.http.get(f"{h.api_base}/users/@me", headers=headers)
            ms   = (time.perf_counter() - t0) * 1000
            ok   = resp.status_code == 200
        except Exception:
            ms   = (time.perf_counter() - t0) * 1000
            ok   = False

        name = s.get("username", "?")
        R    = "\u001b[0m"
        lines = [
            f"{ansi.CYAN}{'Account':<10}{ansi.DARK}:: {ansi.WHITE}{name}{R}",
            f"{ansi.CYAN}{'Status':<10}{ansi.DARK}:: {ansi.PURPLE}{'ok' if ok else 'error'}{R}",
            f"{ansi.CYAN}{'Latency':<10}{ansi.DARK}:: {ansi.WHITE}{ms:.1f}ms{R}",
        ]
        await ctx.send_timed(_block("\n".join(lines)), 12)

    # -- Premium management (owner only) --------------------------------------

    @handler.command(name="premium")
    async def premium(ctx, args):
        await ctx.delete()
        if ctx.author.get("id") != _OWNER_ID:
            return
        if len(args) < 2:
            await ctx.send_timed(
                ansi.command_usage("premium", "premium <add|remove> <discord_id>", "Grant or revoke premium", prefix), 10
            )
            return
        action = args[0].lower()
        target = args[1].strip()
        if action == "add":
            _set_premium(target, True)
            await ctx.send_timed(ansi.success(f"Granted premium to **{target}**."), 10)
        elif action == "remove":
            _set_premium(target, False)
            await ctx.send_timed(ansi.success(f"Revoked premium from **{target}**."), 10)
        else:
            await ctx.send_timed(ansi.error("Usage: premium add|remove <discord_id>"), 10)