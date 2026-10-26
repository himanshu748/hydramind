from __future__ import annotations

import asyncio
import importlib
import inspect


def _call(module_name: str, names: tuple[str, ...]) -> object:
    module = importlib.import_module(module_name)
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            result = fn()
            if inspect.isawaitable(result):
                return asyncio.run(result)
            return result
    raise SystemExit(f'{module_name} has no callable entry point')


def server_main() -> object:
    return _call('hydramind.server', ('main', 'run', 'run_server', 'cli', 'serve'))


def http_main() -> object:
    return _call('hydramind.web', ('main', 'run', 'run_server', 'cli', 'serve'))


def ui_main() -> object:
    return _call('hydramind.web', ('ui_main', 'main', 'run', 'ui'))
