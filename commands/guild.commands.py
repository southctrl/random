import asyncio
import random
from core.tools import ansi
from core.tools.ansi import _block

CATEGORY      = "Guild"
CATEGORY_DESC = "Server list, bulk leave & clan tag"

COMMANDS_INFO = {
    "guilds":    ("guilds [page]",              "List all servers you are in with member counts"),
    "massleave": ("massleave [id,id,...]",      "Leave all non-owned servers (optional exclude list)"),
    "setclan":   ("setclan <guild_id>",         "Set your clan tag to a server you're in"),
    "clearclan": ("clearclan",                  "Clear your current clan tag"),
}


def setup(handler):
    prefix = handler.prefix

    @handler.command(name="guilds", aliases=["servers", "guildlist"])
    async def guilds(ctx, args):
        await ctx.delete()
        try:
            page = max(1, int(args[0])) if args else 1
        except ValueError:
            page = 1
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=True,
        )
        resp = await ctx.http.get(f"{ctx.api_base}/users/@me/guilds?with_counts=true", headers=headers)
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch guilds ({resp.status_code})."), 8)
            return
        all_guilds  = resp.json()
        PER_PAGE    = 8
        total       = len(all_guilds)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
        page        = min(page, total_pages)
        chunk       = all_guilds[(page - 1) * PER_PAGE : page * PER_PAGE]
        R = "\u001b[0m"
        lines = [f"{ansi.PURPLE}Guilds{R} {ansi.DARK}[{total} total]{R}"]
        for g in chunk:
            gid   = g.get("id", "?")
            name  = (g.get("name") or "?")[:28]
            owner = g.get("owner", False)
            count = g.get("approximate_member_count", "?")
            tag   = f" {ansi.PURPLE}owner{R}" if owner else ""
            lines.append(
                f"{ansi.CYAN}{name:<28}{R} "
                f"{ansi.DARK}{gid}{R} "
                f"{ansi.WHITE}{str(count):<8}{R}"
                f"{tag}"
            )
        lines.append(f"\n{ansi.DARK}{prefix}guilds [page]  -  {page}/{total_pages}{R}")
        await ctx.send_timed(_block("\n".join(lines)), 25)

    @handler.command(name="massleave", aliases=["leaveall"])
    async def massleave(ctx, args):
        await ctx.delete()
        exclude = set()
        if args:
            for part in " ".join(args).split(","):
                p = part.strip()
                if p:
                    exclude.add(p)
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=True,
        )
        resp = await ctx.http.get(f"{ctx.api_base}/users/@me/guilds", headers=headers)
        if resp.status_code != 200:
            await ctx.send_timed(ansi.error(f"Failed to fetch guilds ({resp.status_code})."), 8)
            return
        targets = [
            g for g in resp.json()
            if not g.get("owner") and g.get("id") not in exclude
        ]
        if not targets:
            await ctx.send_timed(ansi.error("No leavable guilds (skipping owned & excluded)."), 8)
            return
        status = await ctx.send(ansi.success(f"Leaving {len(targets)} servers..."))
        smid   = (status or {}).get("id")
        left   = 0
        failed = 0

        def _progress():
            R = "\u001b[0m"
            return _block(
                f"{ansi.PURPLE}Mass Leave{R}\n"
                f"{ansi.CYAN}{'Left':<10}{ansi.DARK}:: {ansi.WHITE}{left}{R}\n"
                f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}\n"
                f"{ansi.CYAN}{'Remaining':<10}{ansi.DARK}:: {ansi.WHITE}{len(targets) - left - failed}{R}"
            )

        for g in targets:
            gid = g["id"]
            h = ctx.spoofer.get_headers(
                referer=f"https://discord.com/channels/{gid}",
                skip_context_props=True,
            )
            r = await ctx.http.delete(
                f"{ctx.api_base}/users/@me/guilds/{gid}",
                json={"lurking": False},
                headers=h,
            )
            if r.status_code in (200, 204):
                left += 1
            else:
                failed += 1
            if smid and (left + failed) % 5 == 0:
                await ctx.edit(smid, _progress())
            await asyncio.sleep(random.uniform(1.0, 2.0))

        R = "\u001b[0m"
        result = _block(
            f"{ansi.PURPLE}Mass Leave :: Done{R}\n"
            f"{ansi.CYAN}{'Left':<10}{ansi.DARK}:: {ansi.WHITE}{left}/{len(targets)}{R}\n"
            f"{ansi.CYAN}{'Failed':<10}{ansi.DARK}:: {ansi.WHITE}{failed}{R}"
        )
        if smid:
            await ctx.edit(smid, result)
            await asyncio.sleep(15)
            await ctx.delete(smid)
        else:
            await ctx.send_timed(result, 15)

    @handler.command(name="setclan", aliases=["clanset", "settag"])
    async def setclan(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setclan", *COMMANDS_INFO["setclan"], prefix), 10)
            return
        guild_id = args[0].strip()
        if not guild_id.isdigit():
            await ctx.send_timed(ansi.error("Invalid guild ID."), 8)
            return
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=False,
        )
        resp = await ctx.http.put(
            f"{ctx.api_base}/users/@me/clan",
            json={"identity_guild_id": guild_id, "identity_enabled": True},
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            clan = data.get("clan") or data.get("primary_guild") or {}
            tag  = clan.get("tag", "?")
            await ctx.send_timed(ansi.success(f"Clan tag set to **[{tag}]** (guild `{guild_id}`)."), 10)
        else:
            await ctx.send_timed(ansi.error(f"Failed to set clan ({resp.status_code})."), 8)

    @handler.command(name="clearclan", aliases=["removeclan", "cleartag"])
    async def clearclan(ctx, args):
        await ctx.delete()
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=False,
        )
        resp = await ctx.http.put(
            f"{ctx.api_base}/users/@me/clan",
            json={"identity_guild_id": None, "identity_enabled": False},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed(
            (ansi.success if ok else ansi.error)("Clan tag cleared." if ok else f"Failed ({resp.status_code})."),
            8,
        )