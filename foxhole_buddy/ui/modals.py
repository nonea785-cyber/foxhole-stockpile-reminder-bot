import discord
from typing import TYPE_CHECKING
from foxhole_buddy.utils.formatting import unix_ts
from foxhole_buddy.ui.embeds import stockpile_embed, resource_need_embed, factory_alarm_embed

if TYPE_CHECKING:
    from foxhole_buddy.core.bot import StockpileBot
    from foxhole_buddy.ui.views import StockpileView

class AddStockpileModal(discord.ui.Modal, title="Add Stockpile"):
    name_input = discord.ui.TextInput(
        label="Stockpile Name",
        placeholder='e.g. "Bmats Reserve"',
        max_length=100,
    )
    location_input = discord.ui.TextInput(
        label="Location",
        placeholder='e.g. "Callahan\'s Passage"',
        max_length=100,
    )

    def __init__(self, bot: "StockpileBot", stockpile_type: str):
        super().__init__()
        self.bot = bot
        self.stockpile_type = stockpile_type

    async def on_submit(self, interaction: discord.Interaction) -> None:
        stockpile = self.bot.store.create(
            guild_id=interaction.guild_id or 0,
            channel_id=interaction.channel_id,
            name=self.name_input.value,
            location=self.location_input.value,
            stockpile_type=self.stockpile_type,
            user_id=interaction.user.id,
        )
        # Import inside to avoid circular imports if needed, though TYPE_CHECKING usually handles it.
        from foxhole_buddy.ui.views import StockpileView
        await interaction.response.send_message(
            embed=stockpile_embed(stockpile),
            view=StockpileView(self.bot, stockpile.id),
        )
        message = await interaction.original_response()
        self.bot.store.set_message_id(stockpile.id, message.id)


class RefreshStockpileModal(discord.ui.Modal, title="Refresh Stockpile"):
    stockpile_id_input = discord.ui.TextInput(
        label="Stockpile ID",
        placeholder="8-character ID shown on the stockpile card",
        min_length=8,
        max_length=8,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            stockpile = self.bot.store.refresh(
                self.stockpile_id_input.value.strip(),
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
            )
        except KeyError:
            await interaction.response.send_message(
                "Unknown stockpile ID. Use the **List** button to find IDs.", ephemeral=True
            )
            return
        await self.bot.update_stockpile_message(stockpile)
        await interaction.response.send_message(
            f"✅ Refreshed `{stockpile.name}`. Expires <t:{unix_ts(stockpile.expires_datetime)}:R>.",
            ephemeral=True,
        )


class DeleteStockpileModal(discord.ui.Modal, title="Delete Stockpile"):
    stockpile_id_input = discord.ui.TextInput(
        label="Stockpile ID",
        placeholder="8-character ID shown on the stockpile card",
        min_length=8,
        max_length=8,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        deleted = self.bot.store.delete(
            self.stockpile_id_input.value.strip(),
            guild_id=interaction.guild_id,
        )
        if deleted:
            await interaction.response.send_message(
                f"🗑️ Removed stockpile `{self.stockpile_id_input.value.strip()}`.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Unknown stockpile ID. Use the **List** button to find IDs.", ephemeral=True
            )


class PostNeedModal(discord.ui.Modal, title="Post Resource Need"):
    material_input = discord.ui.TextInput(
        label="Material",
        placeholder='e.g. "Basic Materials" or "Diesel"',
        max_length=100,
    )
    amount_input = discord.ui.TextInput(
        label="Amount Needed",
        placeholder="e.g. 5000",
        max_length=12,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(self.amount_input.value.replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Amount must be a positive whole number.", ephemeral=True)
            return
        need = self.bot.store.create_resource_need(
            guild_id=interaction.guild_id or 0,
            channel_id=interaction.channel_id,
            material=self.material_input.value,
            amount_needed=amount,
            user_id=interaction.user.id,
        )
        await interaction.response.send_message(embed=resource_need_embed(need))
        msg = await interaction.original_response()
        self.bot.store.set_resource_need_message_id(need.id, msg.id)


class ClaimResourceModal(discord.ui.Modal, title="I Can Farm This"):
    need_id_input = discord.ui.TextInput(
        label="Need ID",
        placeholder="8-character ID from the need card",
        min_length=8,
        max_length=8,
    )
    amount_input = discord.ui.TextInput(
        label="Amount I'll Farm",
        placeholder="e.g. 500",
        max_length=12,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(self.amount_input.value.replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Amount must be a positive whole number.", ephemeral=True)
            return
        try:
            need = self.bot.store.claim_resource(
                self.need_id_input.value.strip(),
                user_id=interaction.user.id,
                amount=amount,
                guild_id=interaction.guild_id,
            )
        except KeyError:
            await interaction.response.send_message("Unknown Need ID. Use **Needs Board** to find IDs.", ephemeral=True)
            return
        await self.bot.update_resource_need_message(need)
        await interaction.response.send_message(
            f"⚒️ Pledged `{amount:,}` of **{need.material}**. See you out there!", ephemeral=True
        )


class LogFarmedModal(discord.ui.Modal, title="Log Farmed Resources"):
    need_id_input = discord.ui.TextInput(
        label="Need ID",
        placeholder="8-character ID from the need card",
        min_length=8,
        max_length=8,
    )
    amount_input = discord.ui.TextInput(
        label="Amount I Farmed",
        placeholder="e.g. 250",
        max_length=12,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = int(self.amount_input.value.replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Amount must be a positive whole number.", ephemeral=True)
            return
        try:
            need = self.bot.store.log_farmed(
                self.need_id_input.value.strip(),
                user_id=interaction.user.id,
                amount=amount,
                guild_id=interaction.guild_id,
            )
        except KeyError:
            await interaction.response.send_message("Unknown Need ID. Use **Needs Board** to find IDs.", ephemeral=True)
            return
        await self.bot.update_resource_need_message(need)
        msg = f"✅ Logged `{amount:,}` farmed for **{need.material}**."
        if need.fulfilled:
            msg += " 🎉 **Need fulfilled! Great work!**"
        await interaction.response.send_message(msg, ephemeral=True)


class AddInventoryModal(discord.ui.Modal, title="Add to Base Inventory"):
    material_input = discord.ui.TextInput(
        label="Material Name",
        placeholder='e.g. "Bmats" or "Diesel"',
        max_length=100,
    )
    amount_input = discord.ui.TextInput(
        label="Amount",
        placeholder="e.g. 10.5 or 500",
        max_length=20,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = float(self.amount_input.value.replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Amount must be a number greater than 0.", ephemeral=True)
            return
            
        guild_id = interaction.guild_id or 0
        material = self.material_input.value
        
        self.bot.store.add_to_base_inventory(guild_id, material, amount)
        qty_str = f"{int(amount)}" if amount.is_integer() else f"{amount:.2f}"
        await interaction.response.send_message(f"✅ Added `{qty_str}` of **{material.title()}** to base inventory.", ephemeral=True)


class RemoveInventoryModal(discord.ui.Modal, title="Remove from Base Inventory"):
    material_input = discord.ui.TextInput(
        label="Material Name",
        placeholder='e.g. "Bmats" or "Diesel"',
        max_length=100,
    )
    amount_input = discord.ui.TextInput(
        label="Amount",
        placeholder="e.g. 10.5 or 500",
        max_length=20,
    )

    def __init__(self, bot: "StockpileBot"):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            amount = float(self.amount_input.value.replace(",", "").strip())
            if amount <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("Amount must be a number greater than 0.", ephemeral=True)
            return
            
        guild_id = interaction.guild_id or 0
        material = self.material_input.value
        
        try:
            self.bot.store.remove_from_base_inventory(guild_id, material, amount)
            qty_str = f"{int(amount)}" if amount.is_integer() else f"{amount:.2f}"
            await interaction.response.send_message(f"➖ Removed `{qty_str}` of **{material.title()}** from base inventory.", ephemeral=True)
        except KeyError:
            await interaction.response.send_message(f"❌ **{material.title()}** is not in the base inventory.", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)


class AddFactoryAlarmModal(discord.ui.Modal, title="Set Factory Alarm"):
    facility_input = discord.ui.TextInput(
        label="Facility Name",
        placeholder='e.g. "Coke Refinery" or "Blast Furnace"',
        max_length=100,
    )
    duration_input = discord.ui.TextInput(
        label="Duration (in minutes)",
        placeholder="e.g. 60 for 1h (Rounded to nearest 5m)",
        max_length=40,
    )

    def __init__(self, bot: "StockpileBot", single_ping: bool):
        super().__init__()
        self.bot = bot
        self.single_ping = single_ping

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            duration = int(self.duration_input.value.strip())
            if duration < 5:
                raise ValueError("Duration must be at least 5 minutes.")
        except ValueError:
            await interaction.response.send_message("Please enter a valid number of minutes (minimum 5).", ephemeral=True)
            return

        # Round to nearest 5
        remainder = duration % 5
        if remainder > 0:
            if remainder >= 3:
                duration += (5 - remainder)
            else:
                duration -= remainder

        alarm = self.bot.store.create_factory_alarm(
            guild_id=interaction.guild_id or 0,
            channel_id=interaction.channel_id,
            facility_name=self.facility_input.value,
            duration_minutes=duration,
            single_ping=self.single_ping,
            user_id=interaction.user.id,
        )

        from foxhole_buddy.ui.views import FactoryAlarmCardView
        await interaction.response.send_message(
            embed=factory_alarm_embed(alarm),
            view=FactoryAlarmCardView(self.bot, alarm.id),
        )
        message = await interaction.original_response()
        self.bot.store.set_factory_alarm_message_id(alarm.id, message.id)
