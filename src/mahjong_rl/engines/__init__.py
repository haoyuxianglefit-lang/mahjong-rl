"""引擎注册表 —— 按规则名创建引擎实例。

用法：
    from mahjong_rl.engines import make_engine, list_engines
    env = make_engine("riichi", seed=42)
"""
from .base import MahjongEngine
from .rule_spec import RuleSpec

_REGISTRY: dict[str, type[MahjongEngine]] = {}


def register_engine(name: str):
    """类装饰器：@register_engine("riichi")"""
    def wrap(cls):
        if name in _REGISTRY and _REGISTRY[name] is not cls:
            raise ValueError(f"engine {name!r} already registered: {_REGISTRY[name]}")
        _REGISTRY[name] = cls
        cls.spec = getattr(cls, "SPEC")
        return cls
    return wrap


def make_engine(name: str, **kwargs) -> MahjongEngine:
    if name not in _REGISTRY:
        raise KeyError(f"unknown engine {name!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[name](**kwargs)


def list_engines() -> list[str]:
    return sorted(_REGISTRY)


# 内置规则的内置 spec（与 configs/rules/*.yaml 保持一致，yaml 为实验配置入口）
from .riichi import RIICHI_SPEC  # noqa: E402,F401
from .riichi import adapter  # noqa: E402,F401  (副作用：@register_engine("riichi"))
