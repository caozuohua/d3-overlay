"""D3OA — 轻量类型化事件总线

目标：把原先裸 list 的 log_events 改成按类型分发，
供后续插件/外部系统按 event_type 订阅，避免每轮遍历全量事件。
"""

from typing import Any, Callable, Dict, List


EventType = str
Event = Dict[str, Any]
EventListener = Callable[[Event], None]


class EventBus:
    """最小可用 EventBus：订阅 + 发布 + 批量处理原始日志事件。"""

    def __init__(self) -> None:
        self._listeners: Dict[EventType, List[EventListener]] = {}

    def subscribe(self, event_type: EventType, callback: EventListener) -> None:
        """订阅指定事件类型。同一类型可注册多个回调。"""
        self._listeners.setdefault(event_type, []).append(callback)

    def publish(self, event_type: EventType, event: Event) -> None:
        """向该事件类型的所有订阅者同步派发事件。"""
        for cb in self._listeners.get(event_type, []):
            cb(event)

    def process_log_events(self, events: List[Event]) -> None:
        """遍历一帧得到的原始日志事件列表，按 event['type'] 派发。"""
        seen: Dict[EventType, Event] = {}
        for ev in events:
            etype = ev.get("type")
            if not etype:
                continue
            # 同一类型只派发一次，避免插件每轮收到重复事件
            if etype in seen:
                continue
            seen[etype] = ev
            self.publish(etype, ev)
