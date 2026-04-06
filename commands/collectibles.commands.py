import asyncio
import random
from core.tools import ansi
from core.tools.ansi import _block
from datetime import datetime

CATEGORY = "Collectibles"
CATEGORY_DESC = "Decorations, effects & nameplates"

COMMANDS_INFO = {
    "listcollectibles":   ("listcollectibles",              "List all purchased collectibles"),
    "changedeco":         ("changedeco <index>",            "Equip a decoration by index"),
    "removedeco":         ("removedeco",                    "Remove current decoration"),
    "changeeffect":       ("changeeffect <index>",          "Equip a profile effect by index"),
    "removeeffect":       ("removeeffect",                  "Remove current profile effect"),
    "changenameplate":    ("changenameplate <index>",       "Equip a nameplate by index"),
    "removenameplate":    ("removenameplate",               "Remove current nameplate"),
    "removecollectibles": ("removecollectibles",            "Remove all equipped collectibles"),
    "rotatedeco":         ("rotatedeco <i1> <i2> ...",      "Rotate decorations every 30min"),
    "stoprotatedeco":     ("stoprotatedeco",                "Stop decoration rotation"),
    "rotateeffect":       ("rotateeffect <i1> <i2> ...",    "Rotate profile effects every 30min"),
    "stoprotateeffect":   ("stoprotateeffect",              "Stop profile effect rotation"),
    "rotatenameplate":    ("rotatenameplate <i1> <i2> ...", "Rotate nameplates every 30min"),
    "stoprotatenameplate":("stoprotatenameplate",           "Stop nameplate rotation"),
}

_API = "https://discord.com/api/v9"
_COLLECTIBLES_URL = f"{_API}/users/@me/collectibles-purchases?variants_return_style=2"

_rotate_deco_task      = None
_rotate_effect_task    = None
_rotate_nameplate_task = None

TYPE_ORDER = {"Decoration": 0, "Profile Effect": 1, "Nameplate": 2}


def _collectible_type(c: dict) -> str:
    items = c.get("items", [])
    if not items:
        return "Unknown"
    t = items[0].get("type")
    if t == 0: return "Decoration"
    if t == 1: return "Profile Effect"
    if t == 2: return "Nameplate"
    return "Unknown"


def _sort_collectibles(collectibles: list) -> list:
    return sorted(collectibles, key=lambda c: TYPE_ORDER.get(_collectible_type(c), 99))


async def _fetch_collectibles(ctx) -> list | None:
    headers = ctx.spoofer.get_headers(
        referer="https://discord.com/channels/@me",
        skip_context_props=True,
    )
    resp = await ctx.http.get(_COLLECTIBLES_URL, headers=headers)
    if resp.status_code != 200:
        return None
    return resp.json()


def setup(handler):
    prefix = handler.prefix

    async def _apply_deco(ctx, index: int, collectibles: list) -> bool:
        selected = collectibles[index - 1]
        if _collectible_type(selected) != "Decoration":
            await ctx.send_timed(ansi.error("Selected item is not a decoration."), 10)
            return False
        sku = selected.get("sku_id")
        if not sku:
            await ctx.send_timed(ansi.error("Missing SKU ID."), 10)
            return False
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(
            f"{_API}/users/@me",
            json={"avatar_decoration_sku_id": str(sku)},
            headers=headers,
        )
        return resp.status_code in (200, 204)

    async def _apply_effect(ctx, index: int, collectibles: list) -> bool:
        selected = collectibles[index - 1]
        if _collectible_type(selected) != "Profile Effect":
            await ctx.send_timed(ansi.error("Selected item is not a profile effect."), 10)
            return False
        effect_id = selected.get("items", [{}])[0].get("id")
        if not effect_id:
            await ctx.send_timed(ansi.error("Missing effect ID."), 10)
            return False
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(
            f"{_API}/users/@me/profile",
            json={"profile_effect_id": str(effect_id)},
            headers=headers,
        )
        return resp.status_code == 200

    async def _apply_nameplate(ctx, index: int, collectibles: list) -> bool:
        selected = collectibles[index - 1]
        if _collectible_type(selected) != "Nameplate":
            await ctx.send_timed(ansi.error("Selected item is not a nameplate."), 10)
            return False
        sku = selected.get("sku_id")
        if not sku:
            await ctx.send_timed(ansi.error("Missing SKU ID."), 10)
            return False
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(
            f"{_API}/users/@me",
            json={"nameplate_sku_id": str(sku)},
            headers=headers,
        )
        return resp.status_code in (200, 204)

    @handler.command(name="listcollectibles")
    async def listcollectibles(ctx, args):
        await ctx.delete()
        collectibles = await _fetch_collectibles(ctx)
        if collectibles is None:
            await ctx.send_timed(ansi.error("Failed to fetch collectibles."), 10)
            return
        if not collectibles:
            await ctx.send_timed(ansi.error("No collectibles found."), 10)
            return

        collectibles = _sort_collectibles(collectibles)
        R = "\u001b[0m"
        lines = []
        for idx, c in enumerate(collectibles, 1):
            ctype  = _collectible_type(c)
            name   = c.get("name", "Unknown")
            sku    = c.get("sku_id", "N/A")
            ptype_color = {
                "Decoration":    ansi.CYAN,
                "Profile Effect":ansi.PURPLE,
                "Nameplate":     ansi.BLUE,
            }.get(ctype, ansi.WHITE)
            lines.append(
                f"{ansi.DARK}{idx:>2}. {ptype_color}{name[:25]:<26}{ansi.DARK}:: {ansi.WHITE}{sku}{ansi.DARK} [{ctype}]{R}"
            )

        # send in chunks of 20
        for i in range(0, len(lines), 20):
            chunk = lines[i:i+20]
            await ctx.send(_block("\n".join(chunk)))
            await asyncio.sleep(0.4)

    @handler.command(name="changedeco")
    async def changedeco(ctx, args):
        await ctx.delete()
        if not args or not args[0].isdigit():
            await ctx.send_timed(ansi.command_usage("changedeco", *COMMANDS_INFO["changedeco"], prefix), 10)
            return
        collectibles = await _fetch_collectibles(ctx)
        if not collectibles:
            await ctx.send_timed(ansi.error("Failed to fetch collectibles."), 10)
            return
        collectibles = _sort_collectibles(collectibles)
        idx = int(args[0])
        if idx < 1 or idx > len(collectibles):
            await ctx.send_timed(ansi.error(f"Invalid index. Use `{prefix}listcollectibles` to see indexes."), 10)
            return
        ok = await _apply_deco(ctx, idx, collectibles)
        name = collectibles[idx-1].get("name", "Unknown")
        msg = f"Equipped decoration **{name}**." if ok else f"Failed to equip decoration."
        await ctx.send_timed((ansi.success if ok else ansi.error)(msg), 10)

    @handler.command(name="removedeco")
    async def removedeco(ctx, args):
        await ctx.delete()
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(f"{_API}/users/@me", json={"avatar_decoration_sku_id": None}, headers=headers)
        ok = resp.status_code in (200, 204)
        await ctx.send_timed((ansi.success if ok else ansi.error)("Decoration removed." if ok else "Failed to remove decoration."), 10)

    @handler.command(name="changeeffect")
    async def changeeffect(ctx, args):
        await ctx.delete()
        if not args or not args[0].isdigit():
            await ctx.send_timed(ansi.command_usage("changeeffect", *COMMANDS_INFO["changeeffect"], prefix), 10)
            return
        collectibles = await _fetch_collectibles(ctx)
        if not collectibles:
            await ctx.send_timed(ansi.error("Failed to fetch collectibles."), 10)
            return
        collectibles = _sort_collectibles(collectibles)
        idx = int(args[0])
        if idx < 1 or idx > len(collectibles):
            await ctx.send_timed(ansi.error(f"Invalid index. Use `{prefix}listcollectibles` to see indexes."), 10)
            return
        ok = await _apply_effect(ctx, idx, collectibles)
        name = collectibles[idx-1].get("name", "Unknown")
        msg = f"Equipped effect **{name}**." if ok else "Failed to equip effect."
        await ctx.send_timed((ansi.success if ok else ansi.error)(msg), 10)

    @handler.command(name="removeeffect")
    async def removeeffect(ctx, args):
        await ctx.delete()
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(f"{_API}/users/@me/profile", json={"profile_effect_sku_id": None}, headers=headers)
        ok = resp.status_code in (200, 204)
        await ctx.send_timed((ansi.success if ok else ansi.error)("Profile effect removed." if ok else "Failed to remove effect."), 10)

    @handler.command(name="changenameplate")
    async def changenameplate(ctx, args):
        await ctx.delete()
        if not args or not args[0].isdigit():
            await ctx.send_timed(ansi.command_usage("changenameplate", *COMMANDS_INFO["changenameplate"], prefix), 10)
            return
        collectibles = await _fetch_collectibles(ctx)
        if not collectibles:
            await ctx.send_timed(ansi.error("Failed to fetch collectibles."), 10)
            return
        collectibles = _sort_collectibles(collectibles)
        idx = int(args[0])
        if idx < 1 or idx > len(collectibles):
            await ctx.send_timed(ansi.error(f"Invalid index. Use `{prefix}listcollectibles` to see indexes."), 10)
            return
        ok = await _apply_nameplate(ctx, idx, collectibles)
        name = collectibles[idx-1].get("name", "Unknown")
        msg = f"Equipped nameplate **{name}**." if ok else "Failed to equip nameplate."
        await ctx.send_timed((ansi.success if ok else ansi.error)(msg), 10)

    @handler.command(name="removenameplate")
    async def removenameplate(ctx, args):
        await ctx.delete()
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(f"{_API}/users/@me", json={"nameplate_sku_id": None}, headers=headers)
        ok = resp.status_code in (200, 204)
        await ctx.send_timed((ansi.success if ok else ansi.error)("Nameplate removed." if ok else "Failed to remove nameplate."), 10)

    @handler.command(name="removecollectibles")
    async def removecollectibles(ctx, args):
        await ctx.delete()
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        removed = []
        r1 = await ctx.http.patch(
            f"{_API}/users/@me",
            json={"avatar_decoration_sku_id": None, "nameplate_sku_id": None},
            headers=headers,
        )
        if r1.status_code in (200, 204):
            removed += ["Decoration", "Nameplate"]
        r2 = await ctx.http.patch(
            f"{_API}/users/@me/profile",
            json={"profile_effect_sku_id": None},
            headers=headers,
        )
        if r2.status_code in (200, 204):
            removed.append("Profile Effect")
        if removed:
            await ctx.send_timed(ansi.success(f"Removed: **{', '.join(removed)}**."), 10)
        else:
            await ctx.send_timed(ansi.error("Failed to remove collectibles."), 10)

    # -- Rotation ------------------------------------------------------------

    async def _rotation_loop(indexes: list, apply_fn, counter_key: str):
        while True:
            try:
                if not indexes:
                    break
                i = counter_ref[counter_key] % len(indexes)
                # Build a minimal fake ctx from handler's live http/spoofer
                class _RotCtx:
                    def __init__(self):
                        self.http     = handler.http
                        self.spoofer  = handler.spoofer
                        self.api_base = handler.api_base
                    async def send_timed(self, *a, **k): pass
                collectibles = await _fetch_collectibles(_RotCtx())
                if collectibles:
                    collectibles = _sort_collectibles(collectibles)
                    await apply_fn(_RotCtx(), indexes[i], collectibles)
                counter_ref[counter_key] = i + 1
            except Exception as e:
                print(f"[ROTATE] Error: {e}")
            await asyncio.sleep(1800)

    counter_ref = {"deco": 0, "effect": 0, "nameplate": 0}

    @handler.command(name="rotatedeco")
    async def rotatedeco(ctx, args):
        global _rotate_deco_task
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("rotatedeco", *COMMANDS_INFO["rotatedeco"], prefix), 10)
            return
        try:
            indexes = [int(a) for a in args]
        except ValueError:
            await ctx.send_timed(ansi.error("Indexes must be integers."), 10)
            return
        if _rotate_deco_task and not _rotate_deco_task.done():
            _rotate_deco_task.cancel()
        counter_ref["deco"] = 0
        _rotate_deco_task = handler._spawn(
            _rotation_loop(indexes, _apply_deco, "deco")
        )
        await ctx.send_timed(ansi.success(f"Rotating {len(indexes)} decoration(s) every 30min."), 10)

    @handler.command(name="stoprotatedeco")
    async def stoprotatedeco(ctx, args):
        global _rotate_deco_task
        await ctx.delete()
        if _rotate_deco_task and not _rotate_deco_task.done():
            _rotate_deco_task.cancel()
            _rotate_deco_task = None
            await ctx.send_timed(ansi.success("Stopped decoration rotation."), 10)
        else:
            await ctx.send_timed(ansi.error("No decoration rotation active."), 10)

    @handler.command(name="rotateeffect")
    async def rotateeffect(ctx, args):
        global _rotate_effect_task
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("rotateeffect", *COMMANDS_INFO["rotateeffect"], prefix), 10)
            return
        try:
            indexes = [int(a) for a in args]
        except ValueError:
            await ctx.send_timed(ansi.error("Indexes must be integers."), 10)
            return
        if _rotate_effect_task and not _rotate_effect_task.done():
            _rotate_effect_task.cancel()
        counter_ref["effect"] = 0
        _rotate_effect_task = handler._spawn(
            _rotation_loop(indexes, _apply_effect, "effect")
        )
        await ctx.send_timed(ansi.success(f"Rotating {len(indexes)} effect(s) every 30min."), 10)

    @handler.command(name="stoprotateeffect")
    async def stoprotateeffect(ctx, args):
        global _rotate_effect_task
        await ctx.delete()
        if _rotate_effect_task and not _rotate_effect_task.done():
            _rotate_effect_task.cancel()
            _rotate_effect_task = None
            await ctx.send_timed(ansi.success("Stopped effect rotation."), 10)
        else:
            await ctx.send_timed(ansi.error("No effect rotation active."), 10)

    @handler.command(name="rotatenameplate")
    async def rotatenameplate(ctx, args):
        global _rotate_nameplate_task
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("rotatenameplate", *COMMANDS_INFO["rotatenameplate"], prefix), 10)
            return
        try:
            indexes = [int(a) for a in args]
        except ValueError:
            await ctx.send_timed(ansi.error("Indexes must be integers."), 10)
            return
        if _rotate_nameplate_task and not _rotate_nameplate_task.done():
            _rotate_nameplate_task.cancel()
        counter_ref["nameplate"] = 0
        _rotate_nameplate_task = handler._spawn(
            _rotation_loop(indexes, _apply_nameplate, "nameplate")
        )
        await ctx.send_timed(ansi.success(f"Rotating {len(indexes)} nameplate(s) every 30min."), 10)

    @handler.command(name="stoprotatenameplate")
    async def stoprotatenameplate(ctx, args):
        global _rotate_nameplate_task
        await ctx.delete()
        if _rotate_nameplate_task and not _rotate_nameplate_task.done():
            _rotate_nameplate_task.cancel()
            _rotate_nameplate_task = None
            await ctx.send_timed(ansi.success("Stopped nameplate rotation."), 10)
        else:
            await ctx.send_timed(ansi.error("No nameplate rotation active."), 10)