"""Discover Agent subclasses placed in this package."""

import importlib
import inspect
import pkgutil

from core.agent import Agent


def get_agent_name(agent_type):
    return getattr(agent_type, 'name', None) or agent_type.__name__


def discover_agents():
    discovered = {}
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith('_'):
            continue
        module = importlib.import_module(f'{__name__}.{module_info.name}')
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if (candidate is not Agent and issubclass(candidate, Agent)
                    and candidate.__module__ == module.__name__):
                discovered[get_agent_name(candidate)] = candidate
    return dict(sorted(discovered.items()))


AGENTS_MAP = discover_agents()
