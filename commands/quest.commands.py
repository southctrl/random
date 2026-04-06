import asyncio
import json
import random
from datetime import datetime, timezone
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "Quests"
CATEGORY_DESC = "Discord quest automation"

COMMANDS_INFO = {
    "qlist":     ("qlist",                              "List all available quests"),
    "qraw":      ("qraw",                               "Get raw quests JSON"),
    "qenroll":   ("qenroll <id>",                       "Enroll in a quest"),
    "qcomplete": ("qcomplete <id>",                     "Fast complete a quest"),
    "qvideo":    ("qvideo <id>",                        "Complete a video quest"),
    "qheartbeat":("qheartbeat <id> [app_id]",           "Send a single heartbeat"),
    "qplayhb":   ("qplayhb <id> <app_id> [duration]",   "Simulate play quest with heartbeats"),
    "qplaystop": ("qplaystop <id>",                     "Stop active play simulation"),
    "qauto":     ("qauto",                              "Auto enroll & complete all quests"),
    "qtest":     ("qtest",                              "Test quest API connection"),
    "qdebug":    ("qdebug [id]",                        "Debug quest endpoints"),
}

_API = "https://discord.com/api/v10"
_active_heartbeats = {}


def _quest_headers(spoofer):
    return spoofer.get_headers(
        referer="https://discord.com/quest-home",
        skip_context_props=True,
    )


def _parse_quests(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("quests", "user_quests", "data", "items", "results"):
            v = data.get(key)
            if isinstance(v, list):
                return v
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


def _quest_title(quest: dict) -> str:
    config = quest.get("config", {})
    msgs = config.get("messages", {})
    return msgs.get("quest_name") or msgs.get("name") or quest.get("id", "Unknown")


def _quest_type(quest: dict) -> str:
    return quest.get("config", {}).get("type", "").lower()


def _is_expired(quest: dict) -> bool:
    expires = quest.get("config", {}).get("expires_at") or quest.get("expires_at")
    if not expires:
        return False
    try:
        exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        return exp < datetime.now(timezone.utc)
    except Exception:
        return False


def setup(handler):
    prefix = handler.prefix

    async def _get(ctx, path: str):
        resp = await ctx.http.get(f"{_API}/{path}", headers=_quest_headers(ctx.spoofer))
        return resp.json() if resp.status_code == 200 else None

    async def _post(ctx, path: str, payload: dict):
        resp = await ctx.http.post(f"{_API}/{path}", json=payload, headers=_quest_headers(ctx.spoofer))
        try:
            body = resp.json()
        except Exception:
            body = {}
        return resp.status_code, body

    async def _enroll(ctx, quest_id: str) -> bool:
        status, _ = await _post(ctx, f"quests/{quest_id}/enroll", {
            "is_targeted": False,
            "location": 11,
            "metadata_raw": None,
            "metadata_sealed": None,
        })
        return status == 200

    async def _fast_complete(ctx, quest_id: str) -> bool:
        status, _ = await _post(ctx, f"quests/{quest_id}/video-progress", {"timestamp": 60})
        return status == 200

    async def _send_heartbeat(ctx, quest_id: str, application_id: str) -> bool:
        status, _ = await _post(ctx, f"quests/{quest_id}/heartbeat", {
            "application_id": str(application_id),
            "terminal": False,
            "timestamp": datetime.now().timestamp(),
        })
        return status == 200

    async def _send_play_progress(ctx, quest_id: str, application_id: str, progress: float) -> bool:
        status, data = await _post(ctx, f"quests/{quest_id}/play-progress", {
            "timestamp": progress,
            "application_id": str(application_id),
        })
        return status == 200 and data.get("completed_at") is not None

    async def _do_video_quest(ctx, quest_id: str) -> bool:
        enrolled_at = datetime.now().timestamp()
        current = 0
        target = 60
        speed = 7
        max_future = 10
        completed = False

        while current < target:
            max_allowed = (datetime.now().timestamp() - enrolled_at) + max_future
            if max_allowed > current:
                add = min(speed, target - current, max_allowed - current)
                if add > 0:
                    current += add
                    ts = current + random.random()
                    status, data = await _post(ctx, f"quests/{quest_id}/video-progress", {"timestamp": ts})
                    if status == 200 and data.get("completed_at"):
                        return True
                    if status == 429:
                        await asyncio.sleep(5)
                        continue
            await asyncio.sleep(1)

        status, _ = await _post(ctx, f"quests/{quest_id}/video-progress", {"timestamp": target})
        return status == 200

    async def _simulate_play(ctx, quest_id: str, app_id: str, duration: int) -> tuple[bool, int]:
        details = await _get(ctx, f"quests/{quest_id}")
        if details:
            user_status = details.get("user_status", {})
            if not user_status.get("enrolled_at"):
                await _enroll(ctx, quest_id)
                await asyncio.sleep(1)

        start = datetime.now().timestamp()
        hb_count = 0
        completed = False
        elapsed = 0

        while datetime.now().timestamp() < start + duration and not completed:
            if _active_heartbeats.get(quest_id) is False:
                break
            elapsed = int(datetime.now().timestamp() - start)
            if await _send_heartbeat(ctx, quest_id, app_id):
                hb_count += 1
                if hb_count % 5 == 0:
                    completed = await _send_play_progress(ctx, quest_id, app_id, elapsed)
                    if completed:
                        break
                if hb_count % 15 == 0:
                    pct = min(99, int((elapsed / duration) * 100))
                    await ctx.send_timed(ansi.success(f"Progress: {pct}% ({hb_count} heartbeats)"), 10)
            await asyncio.sleep(random.uniform(2, 5))

        if not completed and elapsed >= duration:
            completed = await _send_play_progress(ctx, quest_id, app_id, duration)

        return completed, hb_count

    @handler.command(name="qlist")
    async def qlist(ctx, args):
        await ctx.delete()
        data = await _get(ctx, "quests/@me")
        quests = _parse_quests(data)
        if not quests:
            await ctx.send_timed(ansi.error("No quests found."), 10)
            return

        R = "\u001b[0m"
        lines = []
        for q in quests:
            qid   = q.get("id", "?")
            title = _quest_title(q)
            qtype = _quest_type(q)
            us    = q.get("user_status") or {}
            expired = _is_expired(q)

            if expired:
                status_sym = ansi.DARK + "X"
            elif us.get("completed_at"):
                status_sym = ansi.CYAN + "\u2713"
            elif us.get("enrolled_at"):
                status_sym = ansi.PURPLE + "~"
            else:
                status_sym = ansi.WHITE + "-"

            exp_tag = f" {ansi.DARK}[expired]{R}" if expired else ""
            lines.append(
                f"{status_sym} {ansi.PURPLE}{title[:20]:<22}{ansi.DARK}:: {ansi.WHITE}{qid}{ansi.DARK} [{qtype}]{exp_tag}{R}"
            )

        await ctx.send_timed(_block("\n".join(lines)), 15)

    @handler.command(name="qraw")
    async def qraw(ctx, args):
        await ctx.delete()
        data = await _get(ctx, "quests/@me")
        if not data:
            await ctx.send_timed(ansi.error("API returned nothing."), 10)
            return
        if isinstance(data, dict):
            await ctx.send_timed(ansi.success(f"Top-level keys: {list(data.keys())}"), 10)
        dump = json.dumps(data, indent=2)
        chunks = [dump[i:i+1800] for i in range(0, min(len(dump), 5400), 1800)]
        for chunk in chunks:
            await ctx.send(f"```json\n{chunk}\n```")
            await asyncio.sleep(0.3)

    @handler.command(name="qenroll")
    async def qenroll(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("qenroll", *COMMANDS_INFO["qenroll"], prefix), 10)
            return
        ok = await _enroll(ctx, args[0])
        msg = f"Enrolled in `{args[0]}`." if ok else f"Failed to enroll in `{args[0]}`."
        await ctx.send_timed((ansi.success if ok else ansi.error)(msg), 10)

    @handler.command(name="qcomplete")
    async def qcomplete(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("qcomplete", *COMMANDS_INFO["qcomplete"], prefix), 10)
            return
        ok = await _fast_complete(ctx, args[0])
        msg = f"Completed `{args[0]}`." if ok else f"Failed to complete `{args[0]}`."
        await ctx.send_timed((ansi.success if ok else ansi.error)(msg), 10)

    @handler.command(name="qvideo")
    async def qvideo(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("qvideo", *COMMANDS_INFO["qvideo"], prefix), 10)
            return
        quest_id = args[0]
        await ctx.send_timed(ansi.success(f"Starting video quest `{quest_id}`..."), 5)
        completed = await _do_video_quest(ctx, quest_id)
        msg = f"Video quest `{quest_id}` complete." if completed else f"Video quest `{quest_id}` failed."
        await ctx.send_timed((ansi.success if completed else ansi.error)(msg), 10)

    @handler.command(name="qheartbeat")
    async def qheartbeat(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("qheartbeat", *COMMANDS_INFO["qheartbeat"], prefix), 10)
            return
        quest_id = args[0]
        app_id = args[1] if len(args) > 1 else None
        if not app_id:
            details = await _get(ctx, f"quests/{quest_id}")
            app_id = (details or {}).get("config", {}).get("application_id") or quest_id
        ok = await _send_heartbeat(ctx, quest_id, app_id)
        msg = f"Heartbeat sent for `{quest_id}`." if ok else f"Heartbeat failed for `{quest_id}`."
        await ctx.send_timed((ansi.success if ok else ansi.error)(msg), 10)

    @handler.command(name="qplayhb")
    async def qplayhb(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("qplayhb", *COMMANDS_INFO["qplayhb"], prefix), 10)
            return
        quest_id = args[0]
        app_id   = args[1] if len(args) > 1 else quest_id
        duration = int(args[2]) if len(args) > 2 else 300

        if _active_heartbeats.get(quest_id):
            await ctx.send_timed(ansi.error(f"Already running for `{quest_id}`. Stop it first with `{prefix}qplaystop`."), 10)
            return

        _active_heartbeats[quest_id] = True
        await ctx.send_timed(ansi.success(f"Play simulation started - {duration}s, app `{app_id}`."), 5)

        try:
            completed, hb_count = await _simulate_play(ctx, quest_id, app_id, duration)
            msg = f"Play quest complete - {hb_count} heartbeats." if completed else f"Play quest ended - {hb_count} heartbeats, not complete."
            await ctx.send_timed((ansi.success if completed else ansi.error)(msg), 15)
        except asyncio.CancelledError:
            _active_heartbeats.pop(quest_id, None)
            raise
        except Exception as e:
            await ctx.send_timed(ansi.error(f"Error: {str(e)[:100]}"), 10)
        finally:
            _active_heartbeats.pop(quest_id, None)

    @handler.command(name="qplaystop")
    async def qplaystop(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("qplaystop", *COMMANDS_INFO["qplaystop"], prefix), 10)
            return
        quest_id = args[0]
        if quest_id in _active_heartbeats:
            _active_heartbeats[quest_id] = False
            await ctx.send_timed(ansi.success(f"Stopping simulation for `{quest_id}`."), 10)
        else:
            await ctx.send_timed(ansi.error(f"No active simulation for `{quest_id}`."), 10)

    @handler.command(name="qauto")
    async def qauto(ctx, args):
        await ctx.delete()
        data = await _get(ctx, "quests/@me")
        quests = _parse_quests(data)
        if not quests:
            await ctx.send_timed(ansi.error("No quests found."), 10)
            return

        # filter out expired and already claimed
        actionable = []
        for q in quests:
            us = q.get("user_status") or {}
            if _is_expired(q):
                continue
            if us.get("claimed_at"):
                continue
            actionable.append(q)

        if not actionable:
            await ctx.send_timed(ansi.success("No actionable quests (all expired or claimed)."), 10)
            return

        await ctx.send_timed(ansi.success(f"Found {len(actionable)} actionable quest(s), processing..."), 5)
        results = []

        for q in actionable:
            quest_id = q.get("id")
            if not quest_id:
                continue
            title = _quest_title(q)[:28]
            us = q.get("user_status") or {}
            qtype = _quest_type(q)

            # enroll if not already
            if not us.get("enrolled_at"):
                ok = await _enroll(ctx, quest_id)
                sym = ansi.CYAN + "\u2713" if ok else ansi.DARK + "\u2717"
                results.append(f"{sym} {ansi.WHITE}Enroll{ansi.DARK}: {title}\u001b[0m")
                if not ok:
                    continue
                await asyncio.sleep(1.5)

            # skip already completed
            if us.get("completed_at"):
                continue

            # complete based on type
            if qtype in ("video", "video_quest", ""):
                ok = await _do_video_quest(ctx, quest_id)
            else:
                # play/heartbeat quest - attempt video-progress anyway as fallback
                ok = await _fast_complete(ctx, quest_id)

            sym = ansi.CYAN + "\u2713" if ok else ansi.DARK + "\u2717"
            results.append(f"{sym} {ansi.WHITE}Complete{ansi.DARK}: {title}\u001b[0m")
            await asyncio.sleep(2)

        await ctx.send_timed(_block("\n".join(results)) if results else ansi.success("Nothing to do."), 20)

    @handler.command(name="qtest")
    async def qtest(ctx, args):
        await ctx.delete()
        data = await _get(ctx, "quests/@me")
        quests = _parse_quests(data)
        if quests is not None:
            await ctx.send_timed(ansi.success(f"API working - {len(quests)} quest(s) found."), 10)
        else:
            await ctx.send_timed(ansi.error("Quest API failed."), 10)

    @handler.command(name="qdebug")
    async def qdebug(ctx, args):
        await ctx.delete()
        if args:
            quest_id = args[0]
            endpoints = [
                ("GET",  f"quests/{quest_id}",               None),
                ("POST", f"quests/{quest_id}/enroll",         {"is_targeted": False, "location": 11, "metadata_raw": None, "metadata_sealed": None}),
                ("POST", f"quests/{quest_id}/video-progress", {"timestamp": 1}),
                ("POST", f"quests/{quest_id}/play-progress",  {"timestamp": 1, "application_id": quest_id}),
            ]
            lines = []
            for method, path, payload in endpoints:
                h = _quest_headers(ctx.spoofer)
                if method == "GET":
                    resp = await ctx.http.get(f"{_API}/{path}", headers=h)
                else:
                    resp = await ctx.http.post(f"{_API}/{path}", json=payload, headers=h)
                lines.append(f"{method} {path}: {resp.status_code}")
            await ctx.send_timed(_block("\n".join(f"{ansi.WHITE}{l}\u001b[0m" for l in lines)), 15)
        else:
            data = await _get(ctx, "users/@me")
            if data:
                await ctx.send_timed(ansi.success(f"Connected as `{data.get('username')}`."), 10)
            else:
                await ctx.send_timed(ansi.error("API check failed."), 10)