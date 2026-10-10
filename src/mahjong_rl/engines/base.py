"""引擎统一接口 —— 所有规则引擎适配器必须实现 MahjongEngine。

设计约定（写新引擎适配器前必读）：
- step() 返回「当前需要做决策的玩家 -> Observation」字典；
  鸣牌窗口会轮流询问每个可鸣牌的玩家（riichienv 语义，新引擎保持同一约定）。
- Observation 至少提供：hands（按玩家遮蔽的视图，hands[player_id] 才是自己手牌）、
  legal_actions()。
- 动作必须用引擎自己的枚举成员比较（如 a.action_type == ActionType.Discard），
  不要依赖 str()/f-string 的文本表示。
"""
from abc import ABC, abstractmethod

from .rule_spec import RuleSpec


class MahjongEngine(ABC):
    """规则引擎抽象基类。observation / action 类型由具体引擎定义。"""

    spec: RuleSpec

    @abstractmethod
    def reset(self, seed: int | None = None):
        """开新一局，返回 dict[player_id, Observation]（只有需行动的玩家有项）。"""

    @abstractmethod
    def step(self, actions: dict):
        """推进决策点。actions: dict[player_id, Action]。

        返回新的 dict[player_id, Observation]；终局后返回空字典。
        """

    @property
    @abstractmethod
    def done(self) -> bool:
        """本局是否结束。"""

    @property
    def obs_shape(self):
        return self.spec.obs_shape

    @property
    def action_space(self) -> int:
        return self.spec.action_space
