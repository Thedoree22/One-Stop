import discord
from discord.ext import commands
from discord import app_commands

class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="clear", description="შლის შეტყობინებებს არხში")
    @app_commands.describe(amount="რაოდენობა (მაქს 100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount <= 0 : await interaction.response.send_message("რაოდენობა 0-ზე მეტი უნდა იყოს", ephemeral=True); return
        if amount > 100: await interaction.response.send_message("100-ზე მეტის წაშლა არ შემიძლია", ephemeral=True); return
        await interaction.response.defer(ephemeral=True); deleted_messages = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"წაიშალა {len(deleted_messages)} შეტყობინება")

    @app_commands.command(name="close", description="კეტავს ამ არხს")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock_channel(self, interaction: discord.Interaction):
        channel = interaction.channel; everyone_role = interaction.guild.default_role
        overwrites = channel.overwrites_for(everyone_role); overwrites.send_messages = False
        try: await channel.set_permissions(everyone_role, overwrite=overwrites); await interaction.response.send_message("არხი დაიკეტა")
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება შევცვალო პარამეტრები", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    @app_commands.command(name="open", description="აღებს ამ არხს")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock_channel(self, interaction: discord.Interaction):
        channel = interaction.channel; everyone_role = interaction.guild.default_role
        overwrites = channel.overwrites_for(everyone_role); overwrites.send_messages = None
        try: await channel.set_permissions(everyone_role, overwrite=overwrites); await interaction.response.send_message("არხი გაიღო")
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება შევცვალო პარამეტრები", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationCog(bot))
