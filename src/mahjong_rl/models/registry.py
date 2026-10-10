"""模型模块注册表 —— 模块融合 = 声明 manifest，不改代码。

每个模块（encoder / head）用 @register_module("discard_v2") 登记；
一份实验 manifest 声明用哪些模块的哪个版本组合成网络，见 configs/models/。
"""
import json
from pathlib import Path

_REGISTRY: dict[str, dict] = {}


def register_module(name: str, version: int = 1):
    """登记一个可复用模块。version 递增表示不兼容的结构变更。"""
    key = f"{name}_v{version}"
    def wrap(cls):
        _REGISTRY[key] = {"name": name, "version": version, "cls": cls}
        return cls
    return wrap


def resolve(key: str):
    if key not in _REGISTRY:
        raise KeyError(f"unknown module {key!r}; available: {sorted(_REGISTRY)}")
    return _REGISTRY[key]["cls"]


def load_manifest(path: str | Path, strict: bool = False) -> dict:
    """读取模块融合 manifest（JSON），返回 {"encoder": {...}, "heads": [...]}。

    默认只做解析 + 软校验（未登记的模块给警告）：manifest 是配置层，
    严格解析留给 assemble()（构建网络时）。
    """
    import warnings
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    refs = [m["encoder"]] if "encoder" in m else []
    refs += m.get("heads", [])
    for r in refs:
        key = f"{r['name']}_v{r['version']}"
        if key not in _REGISTRY:
            msg = f"module {key!r} not registered yet"
            if strict:
                raise KeyError(f"{msg}; available: {sorted(_REGISTRY)}")
            warnings.warn(msg)
    return m


def assemble(manifest: dict):
    """按 manifest 组装网络（严格模式解析所有模块引用）。

    TODO(阶段 2)：实例化 encoder + heads，处理 source_checkpoint 权重手术
    （删规则相关输入面 / 新增目标规则 head）。
    """
    refs = [manifest["encoder"]] if "encoder" in manifest else []
    refs += manifest.get("heads", [])
    for r in refs:
        resolve(f"{r['name']}_v{r['version']}")
    raise NotImplementedError("assemble() 待阶段 2 实现：模块实例化 + 权重迁移手术")
