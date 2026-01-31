import contextlib
import urllib.parse

import discord
from discord.ext import commands

from utils.constants import RANK_ORDER, TIER_ORDER
from utils.logger_config import logger


class MyHelp(commands.MinimalHelpCommand):
    def __init__(self):
        super().__init__(command_attrs={
            "checks": [commands.bot_has_permissions(
                send_messages=True,
                embed_links=True,
            ).predicate],
            "cooldown": commands.CooldownMapping.from_cooldown(
                1,
                3,
                commands.BucketType.user,
            ),
        })

    def add_bot_commands_formatting(self, commands, _heading):
        """This replaces the category heading with an 'Available Commands' label."""
        if commands:
            self.paginator.add_line("**Available Commands:**")
            for command in commands:
                self.add_subcommand_formatting(command)

    async def send_bot_help(self, mapping):
        self.paginator.add_line(
            "⚠️ **DISCLAIMER**: This bot is a personal project and is not " \
            "affiliated with Riot Games.",
        )
        self.paginator.add_line(
            "**NOTE**: By default, the bot will not send live ranked updates until " \
            "the `!updateshere` command is used",
        )
        self.paginator.add_line()
        await super().send_bot_help(mapping)

    def get_ending_note(self):
        """Adds a blank space before the 'Type !help command for more info' message."""
        return f"\n{super().get_ending_note()}"

    def get_opening_note(self):
        """Only returns the 'help [command]' instruction, removing the category line."""
        command_name = f"{self.context.clean_prefix}{self.invoked_with}"
        return f"Use `{command_name} [command]` for more info on a command."

class MatchDetailsView(discord.ui.View):
    """A view that toggles between a simple rank update and a full match summary."""
    def __init__(self, match_data, ranked_data, riot_id, puuid, region, timeout=259200):
        super().__init__(timeout=timeout)
        self.match_data = match_data
        self.ranked_data = ranked_data
        self.riot_id = riot_id
        self.is_expanded = False
        self.message = None
        self.puuid = puuid
        self.region = region
        self.minimized_embed = self.create_minimized_embed()
        self.maximized_embed = self.create_maximized_embed()
        self.create_profile_buttons()

    def create_profile_buttons(self):
        try:
            link_riot_id = self.riot_id.replace("#","-")
            encoded_riot_id = urllib.parse.quote(link_riot_id)
            opgg_url = f"https://op.gg/lol/summoners/na/{encoded_riot_id}"
            deeplol_url = f"https://www.deeplol.gg/summoner/na/{encoded_riot_id}"
            self.add_item(
                discord.ui.Button(
                    label="OP.GG",
                    url=opgg_url,
                    style=discord.ButtonStyle.link,
                ),
            )
            self.add_item(
                discord.ui.Button(
                    label="DeepLol",
                    url=deeplol_url,
                    style=discord.ButtonStyle.link,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to add profile buttons: {e}")

    def create_minimized_embed(self):
        """Creates the minimized embed with information only on the target player."""
        partial_description = extract_minimized_embed_description(
            self.ranked_data,
            self.riot_id,
        )
        if self.match_data.get("win"):
            color = discord.Color.green()
        else:
            color = discord.Color.red()
        description = partial_description + (
            f"\n{self.match_data.get('target_champion')}"
            f" ({self.match_data.get('target_kda')})"
        )
        embed = discord.Embed(
            title=f"Rank Update ({self.region})",
            description=description,
            color=color,
        )
        return embed

    def create_maximized_embed(self):
        """Creates the maximized embed with information on all players."""
        participants = self.match_data.get("participants")
        role_order = {
            "TOP": 0, #Top
            "JUNGLE": 1, #Jungle
            "MIDDLE": 2, #Mid
            "BOTTOM": 3, #ADC
            "UTILITY": 4, #Support
        }
        sorted_participants = sorted(
            participants,
            key=lambda p: (
                p["teamId"],
                role_order.get(p.get("teamPosition",""), 5),
            ),
        )
        blue_team = []
        red_team = []
        for p in sorted_participants:
            champion = p.get("championName")
            kda = f"{p.get('kills')}/{p.get('deaths')}/{p.get('assists')}"
            game_name = p.get('riotIdGameName')
            tag_line = p.get('riotIdTagline')
            line = f"**{(game_name + '#' + tag_line):<10}** - {champion} ({kda})"
            if p['teamId'] == 100:
                blue_team.append(line)
            else:
                red_team.append(line)
        embed = discord.Embed(
            title="Match Summary",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="🟦 Blue Team",
            value="\n".join(blue_team),
            inline=False,
        )
        embed.add_field(
            name="🟥 Red Team",
            value="\n".join(red_team),
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
            if (
                isinstance(
                    item,
                    discord.ui.Button,
                ) and item.style != discord.ButtonStyle.link
            ):
                item.disabled = True
        if self.message:
            with contextlib.suppress(
                discord.HTTPException,
                discord.NotFound,
                discord.Forbidden,
                ):
                await self.message.edit(view=self)
        self.stop()

def extract_minimized_embed_description(ranked_data, riot_id):
    old_tier = ranked_data.get("old_tier")
    old_rank = ranked_data.get("old_rank")
    old_lp = ranked_data.get("old_lp")
    new_tier = ranked_data.get("new_tier")
    new_rank = ranked_data.get("new_rank")
    new_lp = ranked_data.get("new_lp")
    if TIER_ORDER.get(old_tier) > TIER_ORDER.get(new_tier):
        return f"{riot_id} has DEMOTED from {old_tier} to {new_tier}"
    elif TIER_ORDER.get(old_tier) < TIER_ORDER.get(new_tier):
        return f"{riot_id} has PROMOTED from {old_tier} to {new_tier}"
    elif RANK_ORDER.get(old_rank) > RANK_ORDER.get(new_rank):
        return (
            f"{riot_id} has DEMOTED from {old_tier} {old_rank} to {new_tier} {new_rank}"
        )
    elif RANK_ORDER.get(old_rank) < RANK_ORDER.get(new_rank):
        return (
            f"{riot_id} has PROMOTED from "
            f"{old_tier} {old_rank} to {new_tier} {new_rank}"
        )
    elif old_lp > new_lp:
        return f"{riot_id} lost {old_lp - new_lp} LP"
    elif old_lp < new_lp:
        return f"{riot_id} gained {new_lp - old_lp} LP"
    else:
        # this case only happens when both old and new ranked information are identical
        return "This update should not have happened, WHOOPS!"
