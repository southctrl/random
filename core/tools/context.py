import asyncio
import time
import traceback

try:
    import core.tools.ratelimit as _rl
except Exception:
    _rl = None

try:
    from stats_logger import log_command
except Exception:
    async def log_command(user_id: str, command_name: str):
        return None


async def _request(http, method: str, url: str, **kwargs):
    """
    Uses ratelimit.request(...) if available, otherwise falls back to the raw
    curl_cffi AsyncSession request method.
    """
    if _rl is not None and hasattr(_rl, "request"):
        return await _rl.request(http, method, url, **kwargs)
    return await http.request(method.upper(), url, **kwargs)


class CommandHandler:
    def __init__(self, prefix: str):
        self.prefix = prefix
        self.commands = {}
        self.http = None
        self.token = None
        self.api_base = None
        self.spoofer = None
        self.gateway = None
        self._gateway = None
        self._me_id = None
        self._tasks: set[asyncio.Task] = set()

    def _spawn(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)
        return t

    def command(self, name: str = None, aliases: list = None):
        def decorator(func):
            cmd_name = name or func.__name__
            self.commands[cmd_name] = func
            for alias in (aliases or []):
                self.commands[alias] = func
            return func
        return decorator

    async def handle(self, message: dict):
        author = message.get("author", {})
        if not author:
            return

        content = message.get("content", "")
        if not content.startswith(self.prefix):
            return

        if author.get("bot"):
            return

        me_id = getattr(self, "_me_id", None)
        if me_id and author.get("id") != me_id:
            return

        parts = content[len(self.prefix):].split()
        if not parts:
            return

        cmd_name = parts[0].lower()
        args = parts[1:]

        if cmd_name not in self.commands:
            return

        ctx = Context(
            message=message,
            http=self.http,
            token=self.token,
            api_base=self.api_base,
            spoofer=self.spoofer,
            handler=self,
        )

        try:
            start = time.perf_counter()
            await self.commands[cmd_name](ctx, args)
            elapsed = (time.perf_counter() - start) * 1000
            print(f"[CMD] {cmd_name} | {elapsed:.1f}ms")
            self._spawn(log_command(str(author.get("id", "")), cmd_name))
        except Exception:
            traceback.print_exc()


class Context:
    def __init__(self, message: dict, http, token: str, api_base: str, spoofer, handler=None):
        self.message = message
        self.http = http
        self.token = token
        self.api_base = api_base
        self.spoofer = spoofer
        self._handler = handler

        self.channel_id = message.get("channel_id")
        self.guild_id = message.get("guild_id")
        self.author = message.get("author", {})
        self.content = message.get("content", "")
        self.id = message.get("id")

    def _spawn(self, coro) -> asyncio.Task:
        if self._handler:
            return self._handler._spawn(coro)
        return asyncio.create_task(coro)

    def _referer(self):
        gid = self.guild_id or "@me"
        return f"https://discord.com/channels/{gid}/{self.channel_id}"

    async def send(self, content: str) -> dict:
        r = self.spoofer.send_message(
            self.channel_id,
            content,
            guild_id=self.guild_id or "@me",
        )
        resp = await _request(
            self.http,
            "post",
            r["url"],
            json=r["json"],
            headers=r["headers"],
        )
        return resp.json()

    async def send_timed(self, content: str, seconds: float) -> dict:
        msg = await self.send(content)
        mid = msg.get("id")
        if mid:
            self._spawn(self._delete_after(mid, seconds))
        return msg

    async def _delete_after(self, message_id: str, seconds: float):
        await asyncio.sleep(seconds)
        await self.delete(message_id)

    async def edit(self, message_id: str, content: str) -> dict:
        r = self.spoofer.edit_message(
            self.channel_id,
            message_id,
            content,
            guild_id=self.guild_id or "@me",
        )
        resp = await _request(
            self.http,
            "patch",
            r["url"],
            json=r["json"],
            headers=r["headers"],
        )
        return resp.json()

    async def delete(self, message_id: str = None):
        mid = message_id or self.id
        r = self.spoofer.delete_message(
            self.channel_id,
            mid,
            guild_id=self.guild_id or "@me",
        )
        try:
            await _request(
                self.http,
                "delete",
                r["url"],
                headers=r["headers"],
            )
        except Exception:
            pass

    async def reply(self, content: str) -> dict:
        r = self.spoofer.send_message(
            self.channel_id,
            content,
            guild_id=self.guild_id or "@me",
            reply_to=self.id,
            reply_channel=self.channel_id,
            reply_guild=self.guild_id,
        )
        resp = await _request(
            self.http,
            "post",
            r["url"],
            json=r["json"],
            headers=r["headers"],
        )
        return resp.json()

    async def get_guild(self) -> dict:
        headers = self.spoofer.get_headers(
            referer=f"https://discord.com/channels/{self.guild_id}",
            skip_context_props=True,
        )
        resp = await _request(
            self.http,
            "get",
            f"{self.api_base}/guilds/{self.guild_id}",
            headers=headers,
        )
        return resp.json()

    async def get_channel(self, channel_id: str = None) -> dict:
        cid = channel_id or self.channel_id
        headers = self.spoofer.get_headers(
            referer=self._referer(),
            skip_context_props=True,
        )
        resp = await _request(
            self.http,
            "get",
            f"{self.api_base}/channels/{cid}",
            headers=headers,
        )
        return resp.json()

    async def fetch_user(self, user_id: str) -> dict:
        headers = self.spoofer.get_headers(skip_context_props=True)
        resp = await _request(
            self.http,
            "get",
            f"{self.api_base}/users/{user_id}",
            headers=headers,
        )
        return resp.json()
