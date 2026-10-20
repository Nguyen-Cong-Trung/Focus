import random
from utils.constants import HEALTH_TIPS


class HealthReminder:
    def __init__(self):
        self._tip_index: int = 0
        self._tips: list[str] = HEALTH_TIPS

    def get_next_tip(self) -> str:
        if not self._tips:
            return ""
        tip = self._tips[self._tip_index]
        self._tip_index = (self._tip_index + 1) % len(self._tips)
        return tip

    def get_random_tip(self) -> str:
        if not self._tips:
            return ""
        return random.choice(self._tips)

    def get_break_message(self, break_type: str) -> tuple[str, str]:
        if break_type == "short_break":
            title = "⏸ Short Break!"
            message = f"Time for a break!\n\n{self.get_next_tip()}\n\nNext session will start after the break."
        elif break_type == "long_break":
            title = "🎉 Long Break!"
            message = f"You've completed 4 sessions!\n\n{self.get_next_tip()}\n\nTake a walk, drink water, and relax."
        else:
            title = "Break Time"
            message = self.get_next_tip()
        
        return title, message

    def get_focus_start_message(self) -> tuple[str, str]:
        title = "🔥 Focus Mode!"
        message = "Turn off notifications, put on headphones, and start working.\nDistracting websites and apps have been blocked."
        return title, message
