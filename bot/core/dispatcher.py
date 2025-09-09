import asyncio
import importlib
import inspect
import logging
import os
import pkgutil
import signal
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Awaitable, Callable, Iterable, List, Protocol, Union

from telegram import Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackContext,
    CommandHandler,
)


@dataclass
class CommandSpec:
    names: List[str]
    block: bool = True


def command(*names: str, block: bool = True):
    """Decorator to register a command handler."""
    if not names:
        raise ValueError("command() requires at least one name")

    def deco(fn: Callable[..., Awaitable[Any]]):
        setattr(fn, "__cmd_spec__", CommandSpec(names=list(names), block=block))
        return fn

    return deco


def on_load(fn: Callable[..., Awaitable[Any]]):
    """Decorator to run on module load."""
    setattr(fn, "__hook_on_load__", True)
    return fn


def on_start(fn: Callable[..., Awaitable[Any]]):
    """Decorator to run after bot starts."""
    setattr(fn, "__hook_on_start__", True)
    return fn


def on_stop(fn: Callable[..., Awaitable[Any]]):
    """Decorator to run before shutdown."""
    setattr(fn, "__hook_on_stop__", True)
    return fn


class HasLog(Protocol):
    log: logging.Logger


HandlerFunc = Callable[["EventDispatcher", Update, CallbackContext], Awaitable[Any]]
HookFunc = Union[
    Callable[[], Awaitable[Any]],
    Callable[
        ["EventDispatcher", Update | None, CallbackContext | None], Awaitable[Any]
    ],
]


class EventDispatcher(HasLog):
    """Collects commands, hooks, and manages Application lifecycle."""

    prefix: str
    _modules_pkg: str
    _loaded_modules: List[str]
    application: Application

    def _iter_module_funcs(self, mod: ModuleType) -> Iterable[Callable[..., Any]]:
        for _, obj in vars(mod).items():
            if callable(obj):
                yield obj

    def _collect_commands(
        self, mod: ModuleType
    ) -> List[tuple[CommandSpec, HandlerFunc]]:
        out: List[tuple[CommandSpec, HandlerFunc]] = []
        for fn in self._iter_module_funcs(mod):
            spec = getattr(fn, "__cmd_spec__", None)
            if isinstance(spec, CommandSpec):

                async def _wrapped(update: Update, ctx: CallbackContext, _fn=fn):
                    return await _fn(self, update, ctx)  # type: ignore[arg-type]

                out.append((spec, _wrapped))
        return out

    def _collect_hooks(self, mod: ModuleType, attr: str) -> List[HookFunc]:
        out: List[HookFunc] = []
        for fn in self._iter_module_funcs(mod):
            if getattr(fn, attr, False):
                out.append(fn)  # type: ignore[assignment]
        return out

    def _discover_package(self, dotted_or_path: str) -> tuple[str, list[str]]:
        try:
            pkg = importlib.import_module(dotted_or_path)
            pkg_name = dotted_or_path
            pkg_paths = pkg.__path__  # type: ignore[attr-defined]
        except ModuleNotFoundError:
            abs_path = os.path.abspath(dotted_or_path)
            if not os.path.isdir(abs_path):
                raise RuntimeError(f"Package '{dotted_or_path}' not found")
            parent = os.path.dirname(abs_path)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            pkg_name = os.path.basename(abs_path)
            pkg = importlib.import_module(pkg_name)
            pkg_paths = pkg.__path__  # type: ignore[attr-defined]
        mods: List[str] = []
        for m in pkgutil.iter_modules(pkg_paths):
            mods.append(f"{pkg_name}.{m.name}")
        return pkg_name, mods

    def _build_application(self, token: str) -> Application:
        return (
            ApplicationBuilder()
            .token(token)
            .concurrent_updates(True)
            .rate_limiter(AIORateLimiter())
            .build()
        )

    def _register_ptb_commands(
        self, cmd_specs: List[tuple[CommandSpec, HandlerFunc]]
    ) -> int:
        for spec, cb in cmd_specs:
            self.application.add_handler(
                CommandHandler(command=spec.names, callback=cb, block=spec.block)
            )
        return len(cmd_specs)

    async def _run_hooks(self, hooks: List[HookFunc]) -> None:
        for fn in hooks:
            try:
                await self._maybe_await_hook(fn)
            except Exception:
                self.log.exception("Hook error")

    async def _maybe_await_hook(self, fn: HookFunc) -> Any:
        if len(inspect.signature(fn).parameters) == 0:
            res = fn()  # type: ignore[misc]
        else:
            res = fn(self, None, None)  # type: ignore[arg-type]
        if inspect.isawaitable(res):
            return await res
        return res

    async def _reply_error(self, update: object, ctx: CallbackContext) -> None:
        err = ctx.error
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    f"❌ {type(err).__name__}: {err}"
                )
            except Exception:
                pass
        self.log.exception("Handler error", exc_info=err)

    def _install_signal_handlers(self) -> None:
        loop = asyncio.get_running_loop()
        self._stop_event = getattr(self, "_stop_event", asyncio.Event())
        try:
            loop.add_signal_handler(signal.SIGINT, self._stop_event.set)
            loop.add_signal_handler(signal.SIGTERM, self._stop_event.set)
        except NotImplementedError:
            pass

    async def _start_polling(self) -> None:
        self._stop_event = asyncio.Event()
        self._install_signal_handlers()
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(allowed_updates=None)

    async def _idle_forever(self, hooks_stop: List[HookFunc]) -> None:
        try:
            await self._stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            await self._run_hooks(hooks_stop)
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

    async def stop(self) -> None:
        """Request shutdown."""
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
