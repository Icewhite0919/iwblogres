from heapq import merge

from www import config_default

configs = config_default.configs

try:
    import www.config_override
    configs = merge(configs, www.config_override.configs)
except ImportError:
    pass