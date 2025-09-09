import logging
import sys
import types
from typing import List

from telegram.ext import Application

from .dispatcher import CommandSpec, EventDispatcher


class TelegramBot(EventDispatcher):
    """Telegram bot core with dispatcher integration."""

    def __init__(self, token: str, modules_package: str = "modules", prefix: str = "/"):
        self.log = logging.getLogger("Bot")
        self.prefix = prefix
        self._modules_pkg = modules_package
        self.application: Application = self._build_application(token)
        self.client = self.application.bot
        self._loaded_modules: List[str] = []

    async def start(self) -> None:
        _, mod_names = self._discover_package(self._modules_pkg)
        for full in mod_names:
            __import__(full)
        self._loaded_modules = mod_names
        self.log.info("Loaded modules: %s", ", ".join(self._loaded_modules) or "none")

        cmd_specs: list[tuple[CommandSpec, callable]] = []
        hooks_load = []
        hooks_start = []
        hooks_stop = []
        pkg_prefix = (
            f"{self._modules_pkg}."
            if "." in self._modules_pkg
            else f"{self._modules_pkg}."
        )
        for name, mod in list(sys.modules.items()):
            if not isinstance(mod, types.ModuleType):
                continue
            if not (name == self._modules_pkg or name.startswith(pkg_prefix)):
                continue
            cmd_specs.extend(self._collect_commands(mod))
            hooks_load.extend(self._collect_hooks(mod, "__hook_on_load__"))
            hooks_start.extend(self._collect_hooks(mod, "__hook_on_start__"))
            hooks_stop.extend(self._collect_hooks(mod, "__hook_on_stop__"))

        n_cmds = self._register_ptb_commands(cmd_specs)
        self.log.info("Registered %d command group(s)", n_cmds)
        self.application.add_error_handler(self._reply_error)

        await self._run_hooks(hooks_load)

        async def _after_init(_: Application) -> None:
            await self._run_hooks(hooks_start)

        self.application.post_init = _after_init  # type: ignore[attr-defined]

        await self._start_polling()
        await self._idle_forever(hooks_stop)
