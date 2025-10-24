import discord
from discord.ext import commands
from discord import app_commands
import json
import os

TICKET_DB = "ticket_data.json"

def load_ticket_data():
    if not os.path.exists(TICKET_DB): return {}
    try:
        with open(TICKET_DB, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_ticket_data(data):
    try:
        with open(TICKET_DB, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"Ticket Save Error: {e}")

# --- ტიკეტის შექმნის ღილაკი ---
class TicketCreateView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=None) # ღილაკი მუდმივია
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="✉️ ტიკეტის შექმნა", style=discord.ButtonStyle.success, custom_id="create_ticket_button")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True) # დრო ფიქრისთვის

        ticket_data = load_ticket_data()
        guild_settings = ticket_data.get(str(self.guild_id))

        if not guild_settings or 'category_id' not in guild_settings:
            await interaction.followup.send("ტიკეტის სისტემა ამ სერვერზე არ არის დაყენებული.", ephemeral=True)
            return

        category = interaction.guild.get_channel(guild_settings['category_id'])
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send("ტიკეტის კატეგორია ვერ მოიძებნა.", ephemeral=True)
            return

        # ვამოწმებთ, მომხმარებელს უკვე ხომ არ აქვს ღია ტიკეტი
        ticket_name_prefix = f"ticket-{interaction.user.name.lower()}"
        existing_channel = discord.utils.get(category.text_channels, name=ticket_name_prefix) # ვეძებთ არხს
        if existing_channel:
             await interaction.followup.send(f"თქვენ უკვე გაქვთ ღია ტიკეტი: {existing_channel.mention}", ephemeral=True)
             return


        # ვქმნით პრივატულ არხს
        try:
            # ვიღებთ ადმინ/მოდერ როლებს
            support_role_ids = guild_settings.get('support_role_ids', [])
            support_roles = [interaction.guild.get_role(rid) for rid in support_role_ids if interaction.guild.get_role(rid)]

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True) # ბოტს ვაძლევთ უფლებას
            }
            # ვამატებთ უფლებებს support როლებისთვის
            for role in support_roles:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, attach_files=True, embed_links=True)


            ticket_channel = await category.create_text_channel(
                name=ticket_name_prefix,
                overwrites=overwrites,
                topic=f"ტიკეტი მომხმარებლისთვის: {interaction.user.id}"
            )
        except discord.Forbidden:
            await interaction.followup.send("არ მაქვს უფლება შევქმნა არხი ამ კატეგორიაში.", ephemeral=True); return
        except Exception as e:
            await interaction.followup.send(f"ტიკეტის შექმნისას მოხდა შეცდომა: {e}", ephemeral=True); return

        # ვაგზავნით შეტყობინებას ახალ არხში
        close_view = TicketCloseView()
        support_mentions = " ".join([role.mention for role in support_roles]) if support_roles else "@here" # ვთაგავთ როლებს ან @here
        msg_content = f"მოგესალმებით {interaction.user.mention}! გთხოვთ დაწეროთ თქვენი პრობლემა. {support_mentions}"

        await ticket_channel.send(msg_content, view=close_view)
        await interaction.followup.send(f"თქვენი ტიკეტი შეიქმნა: {ticket_channel.mention}", ephemeral=True)

# --- ტიკეტის დახურვის ღილაკი ---
class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 ტიკეტის დახურვა", style=discord.ButtonStyle.danger, custom_id="close_ticket_button")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ვამოწმებთ, აქვს თუ არა მომხმარებელს არხის წაშლის უფლება (ან არის თუ არა ტიკეტის შემქმნელი)
        # მარტივი შემოწმება: თუ აქვს manage_channels უფლება
        if interaction.channel.topic and interaction.channel.topic.startswith("ტიკეტი მომხმარებლისთვის:"):
             creator_id = int(interaction.channel.topic.split(': ')[1])
             if interaction.user.id == creator_id or interaction.user.guild_permissions.manage_channels:
                  await interaction.response.send_message("ტიკეტი იხურება 5 წამში...")
                  await asyncio.sleep(5)
                  await interaction.channel.delete(reason=f"დაიხურა {interaction.user.name}-ის მიერ")
             else:
                  await interaction.response.send_message("თქვენ არ შეგიძლიათ ამ ტიკეტის დახურვა.", ephemeral=True)
        else: # თუ არხი არ არის ტიკეტი
            await interaction.response.send_message("ეს არ არის ტიკეტის არხი.", ephemeral=True)


# --- მთავარი კლასი ---
class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ვამატებთ persistent view-ებს ბოტის ჩართვისას
        ticket_data = load_ticket_data()
        for guild_id in ticket_data:
             if 'panel_message_id' in ticket_data[guild_id]:
                  # ვამატებთ მხოლოდ ერთხელ, თუ ბევრი სერვერია
                  if not hasattr(self, 'added_ticket_view'):
                       self.bot.add_view(TicketCreateView(self.bot, int(guild_id)))
                       self.added_ticket_view = True
                  # ვამატებთ დახურვის ღილაკსაც, თუმცა ეს შეიძლება არ იყოს საჭირო, რადგან ყოველ ჯერზე იქმნება
                  # if not hasattr(self, 'added_close_view'):
                  #      self.bot.add_view(TicketCloseView())
                  #      self.added_close_view = True


    @app_commands.command(name="ticket", description="აყენებს ტიკეტის სისტემას")
    @app_commands.describe(
        channel="არხი სადაც დაიდება 'ტიკეტის შექმნა' ღილაკი",
        category="კატეგორია სადაც შეიქმნება პრივატული ტიკეტები",
        support_role="როლი რომელიც ნახავს ტიკეტებს (სურვილისამებრ)"
    )
    @app_commands.checks.has_permissions(administrator=True) # მხოლოდ ადმინს შეუძლია დაყენება
    async def ticket_setup(self, interaction: discord.Interaction, channel: discord.TextChannel, category: discord.CategoryChannel, support_role: Optional[discord.Role] = None):
        ticket_data = load_ticket_data()
        guild_id = str(interaction.guild.id)

        # ვქმნით Embed შეტყობინებას ღილაკისთვის
        embed = discord.Embed(
            title="დახმარების ცენტრი",
            description="პრობლემის ან კითხვის შემთხვევაში, გთხოვთ გახსნათ ტიკეტი ღილაკზე დაჭერით.",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="მადლობა!")

        view = TicketCreateView(self.bot, interaction.guild.id)

        try:
            panel_message = await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            await interaction.response.send_message("არ მაქვს უფლება გავაგზავნო შეტყობინება მითითებულ არხში.", ephemeral=True); return
        except Exception as e:
            await interaction.response.send_message(f"პანელის შექმნისას მოხდა შეცდომა: {e}", ephemeral=True); return

        # ვინახავთ პარამეტრებს
        support_role_ids = [support_role.id] if support_role else []
        ticket_data[guild_id] = {
            "category_id": category.id,
            "panel_channel_id": channel.id,
            "panel_message_id": panel_message.id,
            "support_role_ids": support_role_ids
        }
        save_ticket_data(ticket_data)

        # ვამატებთ view-ს ბოტს, რომ გადატვირთვის მერეც იმუშაოს
        if not hasattr(self, 'added_ticket_view'):
             self.bot.add_view(view)
             self.added_ticket_view = True


        await interaction.response.send_message(f"ტიკეტის სისტემა დაყენებულია #{channel.name}-ში!", ephemeral=True)

async def setup(bot: commands.Bot):
    # დავამატოთ asyncio იმპორტი დახურვის ღილაკისთვის
    import asyncio
    globals()['asyncio'] = asyncio # ვაქცევთ გლობალურად ხელმისაწვდომს View-სთვის
    await bot.add_cog(TicketCog(bot))
