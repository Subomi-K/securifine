"""Integration hooks for external tools."""

from securifine.integration.hooks import (
    HookResult,
    HookConfig,
    HookRunner,
    HookError,
    HookValidationError,
    get_deepteam_hook_config,
    get_pyrit_hook_config,
    hook_config_to_dict,
    dict_to_hook_config,
    hook_result_to_dict,
    load_hook_config,
    save_hook_config,
)

__all__ = [
    "HookResult",
    "HookConfig",
    "HookRunner",
    "HookError",
    "HookValidationError",
    "get_deepteam_hook_config",
    "get_pyrit_hook_config",
    "hook_config_to_dict",
    "dict_to_hook_config",
    "hook_result_to_dict",
    "load_hook_config",
    "save_hook_config",
]
