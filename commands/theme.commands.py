import json
import os
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "Theme"
CATEGORY_DESC = "Customize Wisdom V2 colors"

COMMANDS_INFO = {
    "theme":      ("theme",               "Show current theme colors"),
    "settheme":   ("settheme <preset>",   "Apply a color preset"),
    "setcolor":   ("setcolor <key> <hex>","Set a specific color by key"),
    "resettheme": ("resettheme",          "Reset theme to default"),
    "presets":    ("presets",             "List all available presets"),
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEME_FILE = os.path.join(BASE_DIR, "theme.json")

DEFAULT_THEME = {
    "primary":   "0;35",
    "secondary": "0;36",
    "text":      "0;37",
    "accent":    "0;34",
    "dark":      "30",
}

PRESETS = {
    "default": {
        "primary":   "0;35",
        "secondary": "0;36",
        "text":      "0;37",
        "accent":    "0;34",
        "dark":      "30",
    },
    "red": {
        "primary":   "0;31",
        "secondary": "0;91",
        "text":      "0;37",
        "accent":    "0;31",
        "dark":      "30",
    },
    "green": {
        "primary":   "0;32",
        "secondary": "0;92",
        "text":      "0;37",
        "accent":    "0;32",
        "dark":      "30",
    },
    "blue": {
        "primary":   "0;34",
        "secondary": "0;36",
        "text":      "0;37",
        "accent":    "0;94",
        "dark":      "30",
    },
    "yellow": {
        "primary":   "33",
        "secondary": "0;93",
        "text":      "0;37",
        "accent":    "0;33",
        "dark":      "30",
    },
    "pink": {
        "primary":   "0;95",
        "secondary": "0;35",
        "text":      "0;37",
        "accent":    "0;91",
        "dark":      "30",
    },
    "orange": {
        "primary":   "0;33",
        "secondary": "0;91",
        "text":      "0;37",
        "accent":    "0;93",
        "dark":      "30",
    },
    "white": {
        "primary":   "0;97",
        "secondary": "0;37",
        "text":      "0;37",
        "accent":    "0;97",
        "dark":      "30",
    },
}

COLOR_KEYS = {
    "primary":   "Headers & category names",
    "secondary": "Command names",
    "text":      "Descriptions & values",
    "accent":    "Subtitles & labels",
    "dark":      "Separators & dim text",
}

ANSI_COLORS = {
    "30": "Dark/Black", "31": "Red",     "32": "Green",  "33": "Yellow",
    "34": "Blue",       "35": "Magenta", "36": "Cyan",   "37": "White",
    "90": "Dark Gray",  "91": "Bright Red",   "92": "Bright Green",
    "93": "Bright Yellow", "94": "Bright Blue", "95": "Bright Magenta",
    "96": "Bright Cyan", "97": "Bright White",
    "0;30": "Dark/Black", "0;31": "Red",     "0;32": "Green",  "0;33": "Yellow",
    "0;34": "Blue",       "0;35": "Magenta", "0;36": "Cyan",   "0;37": "White",
    "0;90": "Dark Gray",  "0;91": "Bright Red",   "0;92": "Bright Green",
    "0;93": "Bright Yellow", "0;94": "Bright Blue", "0;95": "Bright Magenta",
    "0;96": "Bright Cyan", "0;97": "Bright White",
    "1;31": "Bold Red", "1;32": "Bold Green", "1;33": "Bold Yellow",
    "1;34": "Bold Blue", "1;35": "Bold Magenta", "1;36": "Bold Cyan",
}

def _load_theme() -> dict:
    if os.path.exists(THEME_FILE):
        try:
            with open(THEME_FILE) as f:
                return json.load(f)
        except:
            pass
    return dict(DEFAULT_THEME)

def _save_theme(theme: dict):
    with open(THEME_FILE, "w") as f:
        json.dump(theme, f, indent=2)

def _apply_theme(theme: dict):
    ansi.PURPLE = f"\u001b[{theme['primary']}m"
    ansi.CYAN   = f"\u001b[{theme['secondary']}m"
    ansi.WHITE  = f"\u001b[{theme['text']}m"
    ansi.BLUE   = f"\u001b[{theme['accent']}m"
    ansi.DARK   = f"\u001b[{theme['dark']}m"

def setup(handler):
    theme = _load_theme()
    _apply_theme(theme)
    prefix = handler.prefix

    @handler.command(name="theme")
    async def theme_cmd(ctx, args):
        await ctx.delete()
        t = _load_theme()
        R = "\u001b[0m"
        lines = []
        for key, desc in COLOR_KEYS.items():
            code = t.get(key, DEFAULT_THEME[key])
            c = f"\u001b[{code}m"
            color_name = ANSI_COLORS.get(code, code)
            lines.append(f"{c}{key:<10}\u001b[30m:: \u001b[0;37m{desc} \u001b[30m({color_name}){R}")
        block = "\n".join(f"> {l}" for l in (["```ansi"] + lines + ["```"]))
        await ctx.send_timed(block, 10)

    @handler.command(name="settheme")
    async def settheme(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("settheme", *COMMANDS_INFO["settheme"], prefix), 10)
            return
        name = args[0].lower()
        if name not in PRESETS:
            await ctx.send_timed(ansi.error(f"Unknown preset **{name}**. Use `{prefix}presets` to see options."), 10)
            return
        t = dict(PRESETS[name])
        _save_theme(t)
        _apply_theme(t)
        await ctx.send_timed(ansi.success(f"Theme set to **{name}**."), 10)

    @handler.command(name="setcolor")
    async def setcolor(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            R = "\u001b[0m"
            lines = [f"\u001b[0;37m{k:<10}\u001b[30m:: \u001b[0;37m{v}{R}" for k, v in COLOR_KEYS.items()]
            block = "\n".join(f"> {l}" for l in (["```ansi"] + lines + ["```"]))
            await ctx.send_timed(
                ansi.header("SETCOLOR") + "\n" + block + "\n" +
                ansi.footer_main(),
                10
            )
            return
        key = args[0].lower()
        code = args[1]
        if key not in COLOR_KEYS:
            await ctx.send_timed(ansi.error(f"Invalid key **{key}**. Keys: {', '.join(COLOR_KEYS)}"), 10)
            return
        t = _load_theme()
        t[key] = code
        _save_theme(t)
        _apply_theme(t)
        color_name = ANSI_COLORS.get(code, code)
        await ctx.send_timed(ansi.success(f"Set **{key}** to `{code}` ({color_name})."), 10)

    @handler.command(name="resettheme")
    async def resettheme(ctx, args):
        await ctx.delete()
        _save_theme(dict(DEFAULT_THEME))
        _apply_theme(DEFAULT_THEME)
        await ctx.send_timed(ansi.success("Theme reset to default."), 10)

    @handler.command(name="presets")
    async def presets_cmd(ctx, args):
        await ctx.delete()
        R = "\u001b[0m"
        lines = []
        for name, colors in PRESETS.items():
            c = f"\u001b[{colors['primary']}m"
            lines.append(f"{c}{name}{R}")
        block = "\n".join(f"> {l}" for l in (["```ansi"] + lines + ["```"]))
        await ctx.send_timed(block, 10)