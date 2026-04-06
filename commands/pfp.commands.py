from core.tools import ansi
from core.tools.ansi import _block

CATEGORY = "Profile"
CATEGORY_DESC = "Avatar, banner & profile commands"

COMMANDS_INFO = {
    "pfp":               ("pfp [user]",              "Get avatar URL of a user or yourself"),
    "setpfp":            ("setpfp <url>",             "Set your profile picture from a URL"),
    "stealpfp":          ("stealpfp <user>",          "Copy a user's avatar as your own"),
    "serverpfp":         ("serverpfp <user>",         "Get a user's server-specific avatar"),
    "setserverpfp":      ("setserverpfp <url>",       "Set your server-specific avatar"),
    "stealserverpfp":    ("stealserverpfp <user>",    "Copy a user's server avatar as your own"),
    "banner":            ("banner [user]",            "Get banner URL of a user or yourself"),
    "setbanner":         ("setbanner <url>",          "Set your profile banner from a URL"),
    "stealbanner":       ("stealbanner <user>",       "Copy a user's banner as your own"),
    "serverbanner":      ("serverbanner <user>",      "Get a user's server banner"),
    "setserverbanner":   ("setserverbanner <url>",    "Set your server banner from a URL"),
    "stealserverbanner": ("stealserverbanner <user>", "Copy a user's server banner as your own"),
    "bio":               ("bio <user>",               "Get a user's bio"),
    "setbio":            ("setbio <text>",            "Set your bio"),
    "setserverbio":      ("setserverbio <text>",      "Set your server bio"),
    "stealbio":          ("stealbio <user>",          "Copy a user's bio as your own"),
    "pronouns":          ("pronouns <user>",          "Get a user's pronouns"),
    "setpronouns":       ("setpronouns <text>",       "Set your pronouns"),
    "setserverpronouns": ("setserverpronouns <text>", "Set your server pronouns"),
    "stealpronouns":     ("stealpronouns <user>",     "Copy a user's pronouns as your own"),
    "displayname":       ("displayname <user>",       "Get a user's display name"),
    "setdisplayname":    ("setdisplayname <name>",    "Set your display name"),
    "stealname":         ("stealname <user>",         "Copy a user's display name as your own"),
    "setservername":     ("setservername <name>",     "Set your server nickname"),
    "stealservername":   ("stealservername <user>",   "Copy a user's server nickname"),
    "statusr":           ("statusr <s1> | <s2> | ...", "Rotate custom statuses every 20s"),
    "statusrstop":       ("statusrstop",               "Stop status rotation"),
    "checkname":         ("checkname <username>",         "Check if a username is available"),
    "setusername":       ("setusername <username> <pass>", "Change your account username"),
}

_API = "https://discord.com/api/v9"

_statusr_task = None


def setup(handler):
    prefix = handler.prefix

    async def _download(ctx, url: str):
        resp = await ctx.http.get(url, headers={"User-Agent": ctx.spoofer.profile.user_agent})
        if resp.status_code != 200:
            return None, None
        ct = resp.headers.get("content-type", "")
        mime = "image/gif" if "gif" in ct else "image/jpeg" if "jpeg" in ct else "image/png"
        return resp.content, mime

    async def _get_profile(ctx, user_id: str) -> dict | None:
        r = ctx.spoofer.get_profile(user_id)
        resp = await ctx.http.get(r["url"], headers=r["headers"])
        return resp.json() if resp.status_code == 200 else None

    async def _get_member(ctx, guild_id: str, user_id: str) -> dict | None:
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{guild_id}",
            skip_context_props=True,
        )
        resp = await ctx.http.get(f"{_API}/guilds/{guild_id}/members/{user_id}", headers=headers)
        return resp.json() if resp.status_code == 200 else None

    def _avatar_url(user_id: str, avatar_hash: str, size: int = 4096) -> str:
        fmt = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{fmt}?size={size}"

    def _banner_url(user_id: str, banner_hash: str, size: int = 4096) -> str:
        fmt = "gif" if banner_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/banners/{user_id}/{banner_hash}.{fmt}?size={size}"

    def _guild_avatar_url(guild_id: str, user_id: str, avatar_hash: str) -> str:
        fmt = "gif" if avatar_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/guilds/{guild_id}/users/{user_id}/avatars/{avatar_hash}.{fmt}?size=4096"

    def _guild_banner_url(guild_id: str, user_id: str, banner_hash: str) -> str:
        fmt = "gif" if banner_hash.startswith("a_") else "png"
        return f"https://cdn.discordapp.com/guilds/{guild_id}/users/{user_id}/banners/{banner_hash}.{fmt}?size=4096"

    # -- Avatar ----------------------------------------------------------------

    @handler.command(name="pfp")
    async def pfp(ctx, args):
        await ctx.delete()
        target_id = args[0].strip("<@!>") if args else ctx.author.get("id")
        profile = await _get_profile(ctx, target_id)
        avatar = (profile or {}).get("user", {}).get("avatar") if profile else None
        if not avatar:
            await ctx.send(f"https://cdn.discordapp.com/embed/avatars/0.png")
            return
        await ctx.send(_avatar_url(target_id, avatar))

    @handler.command(name="setpfp")
    async def setpfp(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setpfp", *COMMANDS_INFO["setpfp"], prefix), 10)
            return
        image_bytes, mime = await _download(ctx, args[0])
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download image."), 10)
            return
        r = ctx.spoofer.patch_avatar(image_bytes, mime)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("PFP updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealpfp")
    async def stealpfp(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("stealpfp", *COMMANDS_INFO["stealpfp"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        avatar = (profile or {}).get("user", {}).get("avatar")
        if not avatar:
            await ctx.send_timed(ansi.error("User has no avatar."), 10)
            return
        url = _avatar_url(target_id, avatar)
        image_bytes, mime = await _download(ctx, url)
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download avatar."), 10)
            return
        r = ctx.spoofer.patch_avatar(image_bytes, mime)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("PFP stolen." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="serverpfp")
    async def serverpfp(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("serverpfp", *COMMANDS_INFO["serverpfp"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        member = await _get_member(ctx, ctx.guild_id, target_id)
        if not member:
            await ctx.send_timed(ansi.error("Failed to fetch member."), 10)
            return
        avatar = member.get("avatar")
        if avatar:
            await ctx.send(_guild_avatar_url(ctx.guild_id, target_id, avatar))
        else:
            global_avatar = member.get("user", {}).get("avatar")
            if global_avatar:
                await ctx.send(_avatar_url(target_id, global_avatar))
            else:
                await ctx.send_timed(ansi.error("User has no avatar."), 10)

    @handler.command(name="setserverpfp")
    async def setserverpfp(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("setserverpfp", *COMMANDS_INFO["setserverpfp"], prefix), 10)
            return
        image_bytes, mime = await _download(ctx, args[0])
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download image."), 10)
            return
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id}",
            context_location="user_profile",
        )
        resp = await ctx.http.patch(
            f"{_API}/guilds/{ctx.guild_id}/members/@me",
            json={"avatar": ctx.spoofer.build_avatar_data_uri(image_bytes, mime)},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server PFP updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealserverpfp")
    async def stealserverpfp(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("stealserverpfp", *COMMANDS_INFO["stealserverpfp"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        member = await _get_member(ctx, ctx.guild_id, target_id)
        if not member:
            await ctx.send_timed(ansi.error("Failed to fetch member."), 10)
            return
        avatar = member.get("avatar") or member.get("user", {}).get("avatar")
        if not avatar:
            await ctx.send_timed(ansi.error("User has no avatar."), 10)
            return
        url = _guild_avatar_url(ctx.guild_id, target_id, avatar) if member.get("avatar") else _avatar_url(target_id, avatar)
        image_bytes, mime = await _download(ctx, url)
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download avatar."), 10)
            return
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id}",
            context_location="user_profile",
        )
        resp = await ctx.http.patch(
            f"{_API}/guilds/{ctx.guild_id}/members/@me",
            json={"avatar": ctx.spoofer.build_avatar_data_uri(image_bytes, mime)},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server PFP stolen." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    # -- Banner ----------------------------------------------------------------

    @handler.command(name="banner")
    async def banner(ctx, args):
        await ctx.delete()
        target_id = args[0].strip("<@!>") if args else ctx.author.get("id")
        profile = await _get_profile(ctx, target_id)
        b = (profile or {}).get("user", {}).get("banner")
        if not b:
            await ctx.send_timed(ansi.error("User has no banner."), 10)
            return
        await ctx.send(_banner_url(target_id, b))

    @handler.command(name="setbanner")
    async def setbanner(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setbanner", *COMMANDS_INFO["setbanner"], prefix), 10)
            return
        image_bytes, mime = await _download(ctx, args[0])
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download image."), 10)
            return
        r = ctx.spoofer.patch_banner(image_bytes, mime)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Banner updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealbanner")
    async def stealbanner(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("stealbanner", *COMMANDS_INFO["stealbanner"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        b = (profile or {}).get("user", {}).get("banner")
        if not b:
            await ctx.send_timed(ansi.error("User has no banner."), 10)
            return
        url = _banner_url(target_id, b)
        image_bytes, mime = await _download(ctx, url)
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download banner."), 10)
            return
        r = ctx.spoofer.patch_banner(image_bytes, mime)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Banner stolen." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="serverbanner")
    async def serverbanner(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("serverbanner", *COMMANDS_INFO["serverbanner"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        member = await _get_member(ctx, ctx.guild_id, target_id)
        if not member:
            await ctx.send_timed(ansi.error("Failed to fetch member."), 10)
            return
        b = member.get("banner")
        if not b:
            await ctx.send_timed(ansi.error("User has no server banner."), 10)
            return
        await ctx.send(_guild_banner_url(ctx.guild_id, target_id, b))

    @handler.command(name="setserverbanner")
    async def setserverbanner(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("setserverbanner", *COMMANDS_INFO["setserverbanner"], prefix), 10)
            return
        image_bytes, mime = await _download(ctx, args[0])
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download image."), 10)
            return
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id}",
            context_location="user_profile",
        )
        resp = await ctx.http.patch(
            f"{_API}/guilds/{ctx.guild_id}/members/@me",
            json={"banner": ctx.spoofer.build_avatar_data_uri(image_bytes, mime)},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server banner updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealserverbanner")
    async def stealserverbanner(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("stealserverbanner", *COMMANDS_INFO["stealserverbanner"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        member = await _get_member(ctx, ctx.guild_id, target_id)
        if not member:
            await ctx.send_timed(ansi.error("Failed to fetch member."), 10)
            return
        b = member.get("banner")
        if not b:
            await ctx.send_timed(ansi.error("User has no server banner."), 10)
            return
        url = _guild_banner_url(ctx.guild_id, target_id, b)
        image_bytes, mime = await _download(ctx, url)
        if not image_bytes:
            await ctx.send_timed(ansi.error("Failed to download banner."), 10)
            return
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id}",
            context_location="user_profile",
        )
        resp = await ctx.http.patch(
            f"{_API}/guilds/{ctx.guild_id}/members/@me",
            json={"banner": ctx.spoofer.build_avatar_data_uri(image_bytes, mime)},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server banner stolen." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    # -- Bio -------------------------------------------------------------------

    @handler.command(name="bio")
    async def bio(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("bio", *COMMANDS_INFO["bio"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        b = (profile or {}).get("user_profile", {}).get("bio", "")
        if not b:
            await ctx.send_timed(ansi.error("User has no bio."), 10)
            return
        await ctx.send_timed(ansi.success(f"Bio: {b}"), 15)

    @handler.command(name="setbio")
    async def setbio(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setbio", *COMMANDS_INFO["setbio"], prefix), 10)
            return
        bio_text = " ".join(args)
        r = ctx.spoofer.patch_profile(bio=bio_text)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Bio updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="setserverbio")
    async def setserverbio(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("setserverbio", *COMMANDS_INFO["setserverbio"], prefix), 10)
            return
        bio_text = " ".join(args)
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id}",
            context_location="user_profile",
        )
        resp = await ctx.http.patch(
            f"{_API}/guilds/{ctx.guild_id}/members/@me",
            json={"bio": bio_text},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server bio updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealbio")
    async def stealbio(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("stealbio", *COMMANDS_INFO["stealbio"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        b = (profile or {}).get("user_profile", {}).get("bio", "")
        if not b:
            await ctx.send_timed(ansi.error("User has no bio."), 10)
            return
        r = ctx.spoofer.patch_profile(bio=b)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Bio stolen." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    # -- Pronouns --------------------------------------------------------------

    @handler.command(name="pronouns")
    async def pronouns(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("pronouns", *COMMANDS_INFO["pronouns"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        p = (profile or {}).get("user_profile", {}).get("pronouns", "")
        if not p:
            await ctx.send_timed(ansi.error("User has no pronouns set."), 10)
            return
        await ctx.send_timed(ansi.success(f"Pronouns: {p}"), 15)

    @handler.command(name="setpronouns")
    async def setpronouns(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setpronouns", *COMMANDS_INFO["setpronouns"], prefix), 10)
            return
        p = " ".join(args)
        r = ctx.spoofer.patch_profile(pronouns=p)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Pronouns updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="setserverpronouns")
    async def setserverpronouns(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("setserverpronouns", *COMMANDS_INFO["setserverpronouns"], prefix), 10)
            return
        p = " ".join(args)
        headers = ctx.spoofer.get_headers(
            referer=f"https://discord.com/channels/{ctx.guild_id}",
            context_location="user_profile",
        )
        resp = await ctx.http.patch(
            f"{_API}/guilds/{ctx.guild_id}/members/@me",
            json={"pronouns": p},
            headers=headers,
        )
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server pronouns updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealpronouns")
    async def stealpronouns(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("stealpronouns", *COMMANDS_INFO["stealpronouns"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        p = (profile or {}).get("user_profile", {}).get("pronouns", "")
        if not p:
            await ctx.send_timed(ansi.error("User has no pronouns."), 10)
            return
        r = ctx.spoofer.patch_profile(pronouns=p)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Pronouns stolen." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    # -- Display Name ----------------------------------------------------------

    @handler.command(name="displayname")
    async def displayname(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("displayname", *COMMANDS_INFO["displayname"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        dn = (profile or {}).get("user", {}).get("global_name") or "N/A"
        await ctx.send_timed(ansi.success(f"Display name: **{dn}**"), 15)

    @handler.command(name="setdisplayname")
    async def setdisplayname(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("setdisplayname", *COMMANDS_INFO["setdisplayname"], prefix), 10)
            return
        name = " ".join(args)
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(f"{_API}/users/@me", json={"global_name": name}, headers=headers)
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)(f"Display name set to **{name}**." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealname")
    async def stealname(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("stealname", *COMMANDS_INFO["stealname"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        profile = await _get_profile(ctx, target_id)
        dn = (profile or {}).get("user", {}).get("global_name") or (profile or {}).get("user", {}).get("username")
        if not dn:
            await ctx.send_timed(ansi.error("Could not fetch display name."), 10)
            return
        headers = ctx.spoofer.get_headers(skip_context_props=True)
        resp = await ctx.http.patch(f"{_API}/users/@me", json={"global_name": dn}, headers=headers)
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)(f"Display name stolen: **{dn}**." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="setservername")
    async def setservername(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("setservername", *COMMANDS_INFO["setservername"], prefix), 10)
            return
        r = ctx.spoofer.change_nickname(ctx.guild_id, " ".join(args))
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)("Server nickname updated." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    @handler.command(name="stealservername")
    async def stealservername(ctx, args):
        await ctx.delete()
        if not args or not ctx.guild_id:
            await ctx.send_timed(ansi.command_usage("stealservername", *COMMANDS_INFO["stealservername"], prefix), 10)
            return
        target_id = args[0].strip("<@!>")
        member = await _get_member(ctx, ctx.guild_id, target_id)
        if not member:
            await ctx.send_timed(ansi.error("Failed to fetch member."), 10)
            return
        nick = member.get("nick") or member.get("user", {}).get("global_name") or member.get("user", {}).get("username", "")
        if not nick:
            await ctx.send_timed(ansi.error("User has no server nickname."), 10)
            return
        r = ctx.spoofer.change_nickname(ctx.guild_id, nick)
        resp = await ctx.http.patch(r["url"], json=r["json"], headers=r["headers"])
        ok = resp.status_code == 200
        await ctx.send_timed((ansi.success if ok else ansi.error)(f"Server nickname stolen: **{nick}**." if ok else f"Failed: {resp.status_code} {resp.text[:100]}"), 10)

    # -- Status Rotation -------------------------------------------------------

    async def _set_custom_status(ctx_http, ctx_spoofer, text: str):
        headers = ctx_spoofer.get_headers(skip_context_props=True)
        await ctx_http.patch(
            f"{_API}/users/@me/settings",
            json={"custom_status": {"text": text, "emoji_name": None, "expires_at": None}},
            headers=headers,
        )

    @handler.command(name="statusr")
    async def statusr(ctx, args):
        import asyncio as _asyncio
        global _statusr_task
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("statusr", *COMMANDS_INFO["statusr"], prefix), 10)
            return

        raw = " ".join(args)
        statuses = [s.strip() for s in raw.split("|") if s.strip()]
        if len(statuses) < 2:
            await ctx.send_timed(ansi.error("Provide at least 2 statuses separated by `|`."), 10)
            return

        if _statusr_task and not _statusr_task.done():
            _statusr_task.cancel()

        http_ref    = ctx.http
        spoofer_ref = ctx.spoofer

        async def _rotate():
            idx = 0
            try:
                while True:
                    try:
                        await _set_custom_status(http_ref, spoofer_ref, statuses[idx % len(statuses)])
                    except Exception as e:
                        print(f"[STATUSR] error: {e}")
                    idx += 1
                    await _asyncio.sleep(20)
            except _asyncio.CancelledError:
                pass

        _statusr_task = _asyncio.create_task(_rotate())
        await ctx.send_timed(ansi.success(f"Rotating **{len(statuses)}** statuses every 20s."), 10)

    @handler.command(name="statusrstop")
    async def statusrstop(ctx, args):
        global _statusr_task
        await ctx.delete()
        if _statusr_task and not _statusr_task.done():
            _statusr_task.cancel()
            _statusr_task = None
            await ctx.send_timed(ansi.success("Status rotation stopped."), 10)
        else:
            await ctx.send_timed(ansi.error("No status rotation is running."), 10)
    @handler.command(name="checkname", aliases=["cn"])
    async def checkname(ctx, args):
        await ctx.delete()
        if not args:
            await ctx.send_timed(ansi.command_usage("checkname", *COMMANDS_INFO["checkname"], prefix), 10)
            return
        username = args[0].strip().lower()
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=False,
        )
        resp = await ctx.http.post(
            f"{_API}/users/@me/pomelo-attempt",
            json={"username": username},
            headers=headers,
        )
        R = "\u001b[0m"
        if resp.status_code == 200:
            data   = resp.json()
            taken  = data.get("taken", True)
            status = f"{ansi.PURPLE}taken{R}" if taken else f"{ansi.CYAN}available{R}"
            await ctx.send_timed(_block(
                f"{ansi.PURPLE}Username Check{R}\n"
                f"{ansi.CYAN}{'Name':<10}{ansi.DARK}:: {ansi.WHITE}{username}{R}\n"
                f"{ansi.CYAN}{'Status':<10}{ansi.DARK}:: {status}"
            ), 12)
        else:
            await ctx.send_timed(ansi.error(f"Request failed ({resp.status_code})."), 8)

    @handler.command(name="setusername", aliases=["changeuser", "chuser"])
    async def setusername(ctx, args):
        await ctx.delete()
        if len(args) < 2:
            await ctx.send_timed(ansi.command_usage("setusername", *COMMANDS_INFO["setusername"], prefix), 10)
            return
        new_username = args[0].strip()
        password     = " ".join(args[1:])
        headers = ctx.spoofer.get_headers(
            referer="https://discord.com/channels/@me",
            skip_context_props=False,
        )
        resp = await ctx.http.patch(
            f"{_API}/users/@me",
            json={"username": new_username, "password": password},
            headers=headers,
        )
        R = "\u001b[0m"
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("username", new_username)
            await ctx.send_timed(_block(
                f"{ansi.PURPLE}Username Changed{R}\n"
                f"{ansi.CYAN}{'Username':<10}{ansi.DARK}:: {ansi.WHITE}{name}{R}"
            ), 10)
        else:
            try:
                err = resp.json()
                msg = (err.get("errors") or {}).get("username", {}).get("_errors", [{}])[0].get("message", "") or err.get("message", str(resp.status_code))
            except Exception:
                msg = str(resp.status_code)
            await ctx.send_timed(ansi.error(f"Failed: {msg}"), 10)