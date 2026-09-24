from enum import Enum


class BotStatus(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"


class BotState:
    def __init__(self) -> None:
        self._status = BotStatus.STOPPED

    @property
    def status(self) -> BotStatus:
        return self._status

    def start(self) -> BotStatus:
        self._status = BotStatus.RUNNING
        return self._status

    def stop(self) -> BotStatus:
        self._status = BotStatus.STOPPED
        return self._status


bot_state = BotState()
