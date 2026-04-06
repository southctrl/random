import asyncio
import json
import os

CATEGORY = None


def setup(handler):
    _cw_task = [None]

    _orig_handle = handler.handle

    async def _patched_handle(message: dict):
        author = message.get("author", {})
        me_id  = getattr(handler, "_me_id", None)
        if me_id is None:
            me_id = author.get("id")
            if me_id:
                handler._me_id = me_id
        if me_id and author.get("id") == me_id:
            channel_id = message.get("channel_id")
            guild_id   = message.get("guild_id")
            if channel_id:
                _write_last_channel(me_id, channel_id, guild_id)
        await _orig_handle(message)

    handler.handle = _patched_handle

    def _fpath(me_id):
        return f"/tmp/rpc_{me_id}.json"

    def _read_file(me_id):
        p = _fpath(me_id)
        if not os.path.exists(p):
            return {}
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_file(me_id, data):
        with open(_fpath(me_id), "w") as f:
            json.dump(data, f)

    def _write_last_channel(me_id, channel_id, guild_id):
        data = _read_file(me_id)
        data["_last_channel"] = {"channel_id": channel_id, "guild_id": guild_id}
        _write_file(me_id, data)

    async def _cw_loop(me_id):
        last_applied_channel = None
        print("[RPC_WEB] Channel watcher started")
        try:
            while True:
                await asyncio.sleep(2)
                try:
                    data = _read_file(me_id)
                    if not data.get("_cw_enabled"):
                        print("[RPC_WEB] Channel watcher disabled")
                        break
                    lc = data.get("_last_channel")
                    if not lc:
                        continue
                    channel_id = lc.get("channel_id")
                    if not channel_id or channel_id == last_applied_channel:
                        continue
                    rpc_mod = _get_rpc_mod()
                    if rpc_mod is None:
                        continue
                    cmd = {"rpc_type": "channel_watcher", "channel_id": channel_id}
                    activities = data.get("_activities", {})
                    activities["channel_watcher"] = cmd
                    data["_activities"] = activities
                    _write_file(me_id, data)
                    rpc_mod._active_cmd["channel_watcher"] = cmd
                    try:
                        await rpc_mod._build_and_send(handler, cmd)
                        last_applied_channel = channel_id
                        print(f"[RPC_WEB] Channel watcher updated to {channel_id}")
                    except Exception as e:
                        print(f"[RPC_WEB] Channel watcher send error: {e}")
                except Exception as e:
                    print(f"[RPC_WEB] Channel watcher loop error: {e}")
        except asyncio.CancelledError:
            pass
        print("[RPC_WEB] Channel watcher stopped")

    def _start_cw(me_id):
        if _cw_task[0] and not _cw_task[0].done():
            return
        _cw_task[0] = asyncio.create_task(_cw_loop(me_id))

    def _stop_cw():
        if _cw_task[0] and not _cw_task[0].done():
            _cw_task[0].cancel()
        _cw_task[0] = None

    async def _poll_loop():
        me_id = None
        last_ts = 0
        last_statusr_sig = None
        last_cw_enabled = False
        restored = False
        _statusr_task = None

        while True:
            await asyncio.sleep(2)
            try:
                if me_id is None:
                    me_id = getattr(handler, "_me_id", None)
                if me_id is None:
                    continue
                fpath = _fpath(me_id)
                if not os.path.exists(fpath):
                    continue
                with open(fpath) as f:
                    data = json.load(f)
                ts = data.get("_ts", 0)

                if not restored:
                    restored = True
                    activities = _extract_activities(data)
                    if activities:
                        last_ts = ts
                        rpc_mod = _get_rpc_mod()
                        if rpc_mod:
                            for cmd in activities:
                                rpc_mod._stop_rotation(cmd.get("rpc_type", ""))
                                rpc_mod._active_cmd[cmd.get("rpc_type", "unknown")] = cmd
                            non_cw = [c for c in activities if c.get("rpc_type") != "channel_watcher"]
                            await _send_all(handler, rpc_mod, non_cw)
                            for cmd in non_cw:
                                _maybe_start_rotation(handler, rpc_mod, cmd)
                    statusr_statuses = data.get("_statusr")
                    if statusr_statuses and isinstance(statusr_statuses, list) and len(statusr_statuses) >= 2:
                        last_statusr_sig = str(statusr_statuses)
                        _statusr_task = asyncio.create_task(_run_statusr(handler, statusr_statuses))
                        print(f"[RPC_WEB] Restored statusr: {len(statusr_statuses)} statuses")
                    cw_enabled = bool(data.get("_cw_enabled"))
                    last_cw_enabled = cw_enabled
                    if cw_enabled:
                        _start_cw(me_id)
                        print("[RPC_WEB] Restored channel watcher")
                    continue

                cw_enabled = bool(data.get("_cw_enabled"))
                if cw_enabled != last_cw_enabled:
                    last_cw_enabled = cw_enabled
                    if cw_enabled:
                        _start_cw(me_id)
                        print("[RPC_WEB] Channel watcher enabled")
                    else:
                        _stop_cw()
                        rpc_mod = _get_rpc_mod()
                        if rpc_mod:
                            rpc_mod._active_cmd.pop("channel_watcher", None)
                            acts = []
                            for c in rpc_mod._active_cmd.values():
                                a = await rpc_mod._build_activity(handler, c)
                                if a:
                                    acts.append(a)
                            await rpc_mod._send_payload(handler, acts)
                        print("[RPC_WEB] Channel watcher disabled")

                statusr_statuses = data.get("_statusr")
                current_sig = str(statusr_statuses) if statusr_statuses else None
                if current_sig != last_statusr_sig:
                    last_statusr_sig = current_sig
                    if _statusr_task and not _statusr_task.done():
                        _statusr_task.cancel()
                        _statusr_task = None
                    if statusr_statuses and isinstance(statusr_statuses, list) and len(statusr_statuses) >= 2:
                        _statusr_task = asyncio.create_task(_run_statusr(handler, statusr_statuses))
                        print(f"[RPC_WEB] Started statusr: {len(statusr_statuses)} statuses")
                    else:
                        print("[RPC_WEB] Statusr cleared")

                if ts <= last_ts:
                    continue
                last_ts = ts

                rpc_mod = _get_rpc_mod()
                if rpc_mod is None:
                    print("[RPC_WEB] Could not find rpc module")
                    continue

                if data.get("rpc_type") == "clear":
                    print("[RPC_WEB] Clearing all RPC")
                    _stop_cw()
                    last_cw_enabled = False
                    for rt in list(rpc_mod._rotation_tasks.keys()):
                        rpc_mod._stop_rotation(rt)
                    await rpc_mod._send_payload(handler, [])
                    rpc_mod._active_cmd.clear()
                    continue

                activities = _extract_activities(data)
                if not activities:
                    continue

                non_cw = [c for c in activities if c.get("rpc_type") != "channel_watcher"]
                print(f"[RPC_WEB] Applying {len(non_cw)} activities")
                for rt in list(rpc_mod._rotation_tasks.keys()):
                    rpc_mod._stop_rotation(rt)
                rpc_mod._active_cmd = {k: v for k, v in rpc_mod._active_cmd.items() if k == "channel_watcher"}
                for cmd in non_cw:
                    rpc_mod._active_cmd[cmd.get("rpc_type", "unknown")] = cmd
                await _send_all(handler, rpc_mod, list(rpc_mod._active_cmd.values()))
                for cmd in non_cw:
                    _maybe_start_rotation(handler, rpc_mod, cmd)

            except Exception as e:
                print(f"[RPC_WEB] Error: {e}")

    async def _run_statusr(handler, statuses):
        http = getattr(handler, "http", None)
        spoofer = getattr(handler, "spoofer", None)
        if not http or not spoofer:
            return
        idx = 0
        try:
            while True:
                try:
                    headers = spoofer.get_headers(skip_context_props=True)
                    await http.patch(
                        "https://discord.com/api/v9/users/@me/settings",
                        json={"custom_status": {"text": statuses[idx % len(statuses)], "emoji_name": None, "expires_at": None}},
                        headers=headers,
                    )
                except Exception as e:
                    print(f"[RPC_WEB] statusr error: {e}")
                idx += 1
                await asyncio.sleep(20)
        except asyncio.CancelledError:
            pass

    def _extract_activities(data):
        if data.get("rpc_type") == "clear":
            return []
        if "_activities" in data:
            return [v for v in data["_activities"].values() if v.get("rpc_type") and v.get("rpc_type") != "clear"]
        if data.get("rpc_type"):
            return [data]
        return []

    def _maybe_start_rotation(handler, rpc_mod, cmd):
        variants = rpc_mod._split_rotatable(cmd)
        if len(variants) <= 1:
            return
        rpc_type = cmd.get("rpc_type", "unknown")
        interval = int(cmd.get("rotate_interval", rpc_mod._DEFAULT_ROTATE_INTERVAL))
        task = asyncio.create_task(rpc_mod._run_rotation(handler, rpc_type, variants, interval))
        rpc_mod._rotation_tasks[rpc_type] = task
        print(f"[RPC_WEB] Started rotation for {rpc_type}: {len(variants)} variants every {interval}s")

    async def _send_all(handler, rpc_mod, activities):
        acts = []
        for cmd in activities:
            a = await rpc_mod._build_activity(handler, cmd)
            if a:
                acts.append(a)
        if acts:
            await rpc_mod._send_payload(handler, acts)

    def _get_rpc_mod():
        return getattr(handler, "_rpc_module", None)

    asyncio.get_event_loop().create_task(_poll_loop())
