import logging

from fastapi import FastAPI
from routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Expel Selfbot",
    redoc_url=None,
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        factory=False,
    )

import asyncio
import importlib.util
import os
import sys
import argparse

_parser = argparse.ArgumentParser()
_parser.add_argument("--token", default="token")
_parser.add_argument("--proxy", default="")
_args, _ = _parser.parse_known_args()
TOKEN  = _args.token
PROXY  = _args.proxy or None
PREFIX = "."

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
COMMANDS_DIR = os.path.join(BASE_DIR, "commands")

sys.path.insert(0, BASE_DIR)

from gateway import Gateway, FatalTokenError
from handler import CommandHandler
import ansi

_loaded_modules = []


def _load_modules(handler):
    global _loaded_modules
    _loaded_modules = []
    for filename in sorted(os.listdir(COMMANDS_DIR)):
        if not filename.endswith(".commands.py"):
            continue
        filepath = os.path.join(COMMANDS_DIR, filename)
        spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules[filename[:-3]] = mod
        try:
            spec.loader.exec_module(mod)
            if hasattr(mod, "setup"):
                mod.setup(handler)
                _loaded_modules.append(mod)
                print(f"[LOADER] Loaded {filename}")
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"[LOADER] Failed {filename}: {e}")


def _apply_theme():
    theme_file = os.path.join(BASE_DIR, "theme.json")
    if not os.path.exists(theme_file):
        return
    try:
        import json
        with open(theme_file) as f:
            t = json.load(f)
        ansi.PURPLE = f"\u001b[{t.get('primary',   '0;35')}m"
        ansi.CYAN   = f"\u001b[{t.get('secondary', '0;36')}m"
        ansi.WHITE  = f"\u001b[{t.get('text',      '0;37')}m"
        ansi.BLUE   = f"\u001b[{t.get('accent',    '0;34')}m"
        ansi.DARK   = f"\u001b[{t.get('dark',      '30'  )}m"
        print("[THEME] Loaded saved theme")
    except Exception as e:
        print(f"[THEME] Failed to load theme: {e}")


def _get_categories():
    cats = {}
    for mod in _loaded_modules:
        cat  = getattr(mod, "CATEGORY", None)
        desc = getattr(mod, "CATEGORY_DESC", "")
        if cat:
            cats[cat] = desc
    return cats


def _get_category_commands(category):
    for mod in _loaded_modules:
        cat = getattr(mod, "CATEGORY", "") or ""
        if cat.lower() == category.lower():
            info = getattr(mod, "COMMANDS_INFO", {})
            return list(info.items())
    return []


def _get_all_commands_info():
    result = {}
    for mod in _loaded_modules:
        info = getattr(mod, "COMMANDS_INFO", {})
        result.update(info)
    return result


def register_help(handler):
    prefix = handler.prefix

    @handler.command(name="help", aliases=["h"])
    async def help_cmd(ctx, args):
        await ctx.delete()
        if not args:
            cats = _get_categories()
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
        cats = _get_categories()
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
            cmds        = _get_category_commands(cat_match)
            per_page    = 5
            total_pages = max(1, (len(cmds) + per_page - 1) // per_page)
            page        = max(1, min(page, total_pages))
            chunk       = cmds[(page - 1) * per_page: page * per_page]
            head        = ansi.header(f"{cat_match.upper()} :: page {page}/{total_pages}")
            body        = ansi.command_list([(n, d) for n, (_, d) in chunk])
            foot        = ansi.footer_page(prefix, cat_match, page, total_pages)
            await ctx.send_timed(head + "\n" + body + "\n" + foot, 10)
            return
        all_info = _get_all_commands_info()
        if query in all_info:
            usage, desc = all_info[query]
            await ctx.send_timed(ansi.command_usage(query, usage, desc, prefix), 10)
            return
        await ctx.send_timed(ansi.error(f"No command or category found: **{query}**"), 10)


async def _unload_modules():
    global _loaded_modules
    for mod in _loaded_modules:
        name = getattr(mod, "__name__", None)
        if name and name in sys.modules:
            del sys.modules[name]
    _loaded_modules = []


async def main():
    handler = CommandHandler(PREFIX)
    _load_modules(handler)
    _apply_theme()
    handler._modules      = _loaded_modules
    handler._commands_dir = COMMANDS_DIR
    register_help(handler)
    print(f"[LOADER] {len(set(handler.commands.values()))} commands | {len(handler.commands)} names")
    gw = Gateway(TOKEN, handler, proxy=PROXY)
    try:
        await gw.run()
    finally:
        await _unload_modules()


if __name__ == "__main__":
    import time as _time
    while True:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(main())
        except KeyboardInterrupt:
            print("[MAIN] Stopped by user")
            loop.close()
            break
        except FatalTokenError as e:
            print(f"[MAIN] Token is dead ({e}) -- not restarting")
            loop.close()
            import subprocess
            try:
                name = os.environ.get("name") or os.environ.get("PM2_APP_NAME")
                if name:
                    subprocess.Popen(["pm2", "delete", name])
            except Exception:
                pass
            break
        except Exception as e:
            print(f"[MAIN] Crashed: {e} -- restarting in 5s")
            _time.sleep(5)
        else:
            print("[MAIN] Exited cleanly -- restarting in 5s")
            _time.sleep(5)
        finally:
            try:
                loop.close()
            except Exception:
                pass