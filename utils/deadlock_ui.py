import contextlib

import discord

from utils.deadlock_api import badge_name, entry_won, is_ranked


def _kda(entry):
    return (
        f"{entry.get('player_kills')}/{entry.get('player_deaths')}"
        f"/{entry.get('player_assists')}"
    )


class DeadlockMatchView(discord.ui.View):
    """Toggles between the short per-match line and a few more match stats.

    Mirrors MatchDetailsView's layout: a colored embed, a one-line headline plus
    hero (K/D/A), and a button that expands it.
    """

    def __init__(self, entry, hero_name, player_label, timeout=259200):
        super().__init__(timeout=timeout)
        self.entry = entry
        self.hero_name = hero_name
        self.player_label = player_label
        self.is_expanded = False
        self.message = None
        self.minimized_embed = self.create_minimized_embed()
        self.maximized_embed = self.create_maximized_embed()

    def _headline(self):
        won = entry_won(self.entry)
        result = "won" if won else "lost"
        if not is_ranked(self.entry):
            return f"{self.player_label} {result} a normal match"
        calibrating = bool(self.entry.get("ranked_calibration_match"))
        badge = badge_name(self.entry.get("ranked_display_badge"))
        delta = self.entry.get("ranked_delta")
        line = f"{self.player_label} {result} a ranked match"
        if calibrating:
            line += " (calibration)"
        if badge:
            line += f"\nRank: {badge}"
        if delta is not None:
            # An estimate from the community API, never an exact MMR figure.
            line += f"\nEstimated rank progress: {delta:+d}"
        return line

    def create_minimized_embed(self):
        color = discord.Color.green() if entry_won(self.entry) else discord.Color.red()
        title = (
            "Ranked Update (Deadlock)"
            if is_ranked(self.entry)
            else ("Match Update (Deadlock)")
        )
        description = f"{self._headline()}\n{self.hero_name} ({_kda(self.entry)})"
        return discord.Embed(title=title, description=description, color=color)

    def create_maximized_embed(self):
        minutes, seconds = divmod(self.entry.get("match_duration_s") or 0, 60)
        embed = discord.Embed(
            title="Match Summary (Deadlock)", color=discord.Color.purple()
        )
        embed.add_field(
            name=f"{self.player_label} - {self.hero_name}",
            value=(
                f"K/D/A: {_kda(self.entry)}\n"
                f"Hero level: {self.entry.get('hero_level')}\n"
                f"Net worth: {self.entry.get('net_worth')}\n"
                f"Last hits / denies: {self.entry.get('last_hits')}"
                f" / {self.entry.get('denies')}\n"
                f"Duration: {minutes}:{seconds:02d}"
            ),
            inline=False,
        )
        return embed

    @discord.ui.button(
        label="Show Match Details",
        style=discord.ButtonStyle.secondary,
    )
    async def toggle_details(self, interaction, button):
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            embed = self.maximized_embed
            button.label = "Show Minimized View"
        else:
            embed = self.minimized_embed
            button.label = "Show Match Summary"
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            with contextlib.suppress(
                discord.HTTPException,
                discord.NotFound,
                discord.Forbidden,
            ):
                await self.message.edit(view=self)
        self.stop()
