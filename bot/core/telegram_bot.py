import asyncio
import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List

from telegram import Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
)

HandlerFunc = Callable[["TelegramBot", Update, CallbackContext], Awaitable[Any]]


@dataclass
class CommandSpec:
    names: List[str]
    callback: HandlerFunc
    block: bool = True


_registry: Dict[str, List[HandlerFunc]] = {"on_load": [], "on_start": []}
_commands: List[CommandSpec] = []


def command(*names: str, block: bool = True) -> Callable[[HandlerFunc], HandlerFunc]:
    def deco(fn: HandlerFunc) -> HandlerFunc:
        _commands.append(CommandSpec(names=list(names), callback=fn, block=block))
        return fn

    return deco


def on_load(fn: HandlerFunc) -> HandlerFunc:
    _registry["on_load"].append(fn)
    return fn


def on_start(fn: HandlerFunc) -> HandlerFunc:
    _registry["on_start"].append(fn)
    return fn


class TelegramBot:
    def __init__(
        self,
        token: str,
        modules_package: str = "modules",
        prefix: str = "/",
        colorlog_enable: bool = False,
    ):
        self.log = logging.getLogger("Bot")
        if not self.log.handlers:
            logging.basicConfig(
                level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s"
            )
        self.prefix = prefix
        self._modules_pkg = modules_package
        self.application: Application = (
            ApplicationBuilder()
            .token(token)
            .concurrent_updates(True)
            .rate_limiter(AIORateLimiter())
            .build()
        )
        self.client = self.application.bot
        self._loaded_modules: List[str] = []

    async def start(self) -> None:
        await self._load_modules()
        await self._run_on_load()
        self._register_commands()
        self.application.add_error_handler(self._on_error)
        await self._run_on_start_when_ready()
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=None)
        try:
            await asyncio.Event().wait()
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def _load_modules(self) -> None:
        pkg_name = self._modules_pkg
        try:
            pkg = importlib.import_module(pkg_name)
        except ModuleNotFoundError as e:
            raise RuntimeError(f"Package '{pkg_name}' not found") from e
        pkg_path = pkg.__path__  # type: ignore[attr-defined]
        for m in pkgutil.iter_modules(pkg_path):
            mod_full = f"{pkg_name}.{m.name}"
            importlib.import_module(mod_full)
            self._loaded_modules.append(mod_full)
        self.log.info(
            f"Loaded modules: {', '.join(self._loaded_modules) if self._loaded_modules else 'none'}"
        )

    def _wrap(
        self, fn: HandlerFunc
    ) -> Callable[[Update, CallbackContext], Awaitable[Any]]:
        async def _inner(update: Update, ctx: CallbackContext) -> Any:
            return await fn(self, update, ctx)

        return _inner

    def _register_commands(self) -> None:
        for spec in _commands:
            h = CommandHandler(
                command=spec.names, callback=self._wrap(spec.callback), block=spec.block
            )
            self.application.add_handler(h)
        self.log.info(f"Registered {len(_commands)} command group(s)")

    async def _run_on_load(self) -> None:
        for fn in _registry["on_load"]:
            await self._maybe_await(fn)

    async def _run_on_start_when_ready(self) -> None:
        async def _after_start(_: Application) -> None:
            for fn in _registry["on_start"]:
                await self._maybe_await(fn)

        self.application.post_init = _after_start  # type: ignore[attr-defined]

    async def _maybe_await(self, fn: HandlerFunc | Callable[[], Any]) -> Any:
        if len(inspect.signature(fn).parameters) == 0:
            res = fn()  # type: ignore[misc]
        else:
            res = fn(self, None, None)  # type: ignore[arg-type]
        if inspect.isawaitable(res):
            return await res
        return res

    async def _on_error(self, update: object, context: CallbackContext) -> None:
        err = context.error
        msg = None
        if isinstance(update, Update):
            msg = update.effective_message
        text = f"❌ Error: {type(err).__name__}: {err}"
        if msg and msg.can_reply:
            try:
                await msg.reply_text(text)
            except Exception:
                pass
        self.log.exception("Handler error", exc_info=err)
