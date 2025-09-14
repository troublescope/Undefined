import importlib
import inspect
from types import ModuleType
from typing import TYPE_CHECKING, Any, Iterable, MutableMapping, Optional, Type

from .. import custom_modules, module, modules, util

from .base import ZyraBase

if TYPE_CHECKING:
    from .bot import Zyra


class ModuleExtender(ZyraBase):
    # Initialized during instantiation
    modules: MutableMapping[str, module.Module]

    def __init__(self: "Zyra", **kwargs: Any) -> None:
        self.modules = {}
        super().__init__(**kwargs)

    def load_module(
        self: "Zyra", cls: Type[module.Module], *, comment: Optional[str] = None
    ) -> None:
        self.log.info("Loading %s", cls.format_desc(comment))

        if cls.name in self.modules:
            old = type(self.modules[cls.name])
            raise module.ExistingModuleError(old, cls)

        mod = cls(self)
        mod.comment = comment
        self.register_listeners(mod)
        self.register_commands(mod)
        self.modules[cls.name] = mod

    def unload_module(self: "Zyra", mod: module.Module) -> None:
        cls = type(mod)
        self.log.info("Unloading %s", mod.format_desc(mod.comment))

        self.unregister_listeners(mod)
        self.unregister_commands(mod)
        del self.modules[cls.name]

    def _load_all_from_metamod(
        self: "Zyra",
        submodules: Iterable[ModuleType],
        *,
        comment: Optional[str] = None,
    ) -> None:
        for module_mod in submodules:
            for sym in dir(module_mod):
                cls = getattr(module_mod, sym)
                if (
                    inspect.isclass(cls)
                    and issubclass(cls, module.Module)
                    and not cls.disabled
                ):
                    self.load_module(cls, comment=comment)

    def load_all_modules(self: "Zyra") -> None:
        self.log.info("Loading modules")
        self._load_all_from_metamod(modules.submodules)
        self._load_all_from_metamod(custom_modules.submodules, comment="custom")
        self.log.info("All modules loaded.")

    def unload_all_modules(self: "Zyra") -> None:
        self.log.info("Unloading modules...")

        for mod in list(self.modules.values()):
            self.unload_module(mod)

        self.log.info("All modules unloaded.")

    async def reload_module_pkg(self: "Zyra") -> None:
        self.log.info("Reloading base module class...")
        await util.run_sync(importlib.reload, module)

        self.log.info("Reloading master module...")
        await util.run_sync(importlib.reload, modules)
