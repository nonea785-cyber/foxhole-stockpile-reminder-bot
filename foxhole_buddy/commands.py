import discord
from discord import app_commands
from foxhole_buddy.core.store import EXPIRY_HOURS
from foxhole_buddy.ui.embeds import main_menu_embed
from foxhole_buddy.ui.views import MainMenuView

def register_commands(bot) -> None:
    stockpile_group = app_commands.Group(name="foxhole_buddy", description="Foxhole stockpile reminders.")

    @stockpile_group.command(name="setup", description="Set this channel as the Foxhole Buddy reminder channel for this server.")
    @app_commands.default_permissions(manage_guild=True)
    async def stockpile_setup(
        interaction: discord.Interaction,
        urgent_role: discord.Role | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        urgent_role_id = urgent_role.id if urgent_role else None
        bot.store.set_guild_config(interaction.guild_id, interaction.channel_id, urgent_role_id)

        embed = discord.Embed(
            title="✅ Foxhole Buddy Setup Complete",
            description=(
                f"<#{interaction.channel_id}> is now the Foxhole Buddy reminder channel for this server.\n"
                "All stockpile commands and alerts will be routed here."
            ),
            color=0x2D7D46,
        )
        if urgent_role:
            embed.add_field(name="Urgent Role (2h ping)", value=urgent_role.mention, inline=True)
        embed.add_field(
            name="Next Step",
            value="Run `/foxhole_buddy add` to create your first stockpile timer.",
            inline=False,
        )
        embed.set_footer(text="Foxhole Buddy | Ready for logistics")
        await interaction.response.send_message(embed=embed)

    @stockpile_group.command(name="help", description="Show information about the Foxhole Buddy bot.")
    async def stockpile_help(interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Foxhole Buddy Help",
            description="A lightweight logistics timer for Foxhole reserve stockpiles.",
            color=0x2D7D46,
        )
        embed.add_field(
            name="Getting Started",
            value=(
                "1. An admin runs `/foxhole_buddy setup` in the reminder channel.\n"
                "2. Use `/foxhole_buddy manage` to open the interactive menu.\n"
                "3. Add stockpiles, then press **Mark Refreshed** after each in-game refresh."
            ),
            inline=False,
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/foxhole_buddy setup` — (admin) register a reminder channel\n"
                "`/foxhole_buddy manage` — open the regiment management menu\n"
                "`/foxhole_buddy help` — show this info panel"
            ),
            inline=False,
        )
        embed.add_field(
            name="Timer Rules",
            value=(
                f"Each refresh arms a **{EXPIRY_HOURS}h** window. "
                "Alerts fire at **24h**, **6h**, **2h**, and once after expiry."
            ),
            inline=False,
        )
        embed.add_field(
            name="Refresh Protocol",
            value=(
                "Always refresh the stockpile **in-game first**, then press "
                "**Mark Refreshed** on the Discord card. "
                "Foxhole Buddy tracks the timer — it cannot touch the game."
            ),
            inline=False,
        )
        embed.set_footer(text="Foxhole Buddy | Keep the depot private")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stockpile_group.command(name="manage", description="Open the regiment management menu.")
    async def regiment_manage(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=main_menu_embed(),
            view=MainMenuView(bot),
            ephemeral=True,
        )

    bot.tree.add_command(stockpile_group)
