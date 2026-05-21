"""AstrBot code inviter plugin entry point."""

from __future__ import annotations

from pathlib import Path

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class AstrBotCodeInviterPlugin(Star):
    """Minimal plugin shell for AstrBot.

    The first slice keeps the plugin loadable, gives it a stable data
    directory, and leaves the actual code-pool logic for later commits.
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.data_path = Path(get_astrbot_data_path()) / "plugin_data" / self.name
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.export_path = self.data_path / str(self.config.get("csv", {}).get("export_dir", "exports"))
        self.export_path.mkdir(parents=True, exist_ok=True)

    @filter.on_astrbot_loaded()
    async def on_astrbot_loaded(self):
        logger.info(
            f"{self.name} loaded with data path {self.data_path} and export path {self.export_path}."
        )
