import discord
from discord.ext import commands, tasks
from discord import app_commands
import json; import os; import random; import datetime; import re
from typing import Optional

SMS_LOG_DB = "sms_logs.json"
def load_data(fp): # ... load_data ...
    if not os.path.exists(fp): return {}
    try:
        with open(fp, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}
def save_data(data, fp): # ... save_data ...
    try:
        with open(fp, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"Save Error ({fp}): {e}")

class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sms_logs = load_data(SMS_LOG_DB)

    def log_sms(self, uid, direction, content, admin_id=None): # ... log_sms ...
        uid_s=str(uid);
        if uid_s not in self.sms_logs: self.sms_logs[uid_s]=[]
        le={"ts":datetime.datetime.utcnow().isoformat(),"dir":direction,"con":content}
        if admin_id: le["aid"]=admin_id
        self.sms_logs[uid_s].append(le); save_data(self.sms_logs, SMS_LOG_DB)

    @app_commands.command(name="message", description="აგზავნის შეტყობინებას ბოტის სახელით")
    @app_commands.describe(channel="არხი სადაც გაიგზავნება", text="შეტყობინების ტექსტი", image_url="სურათის ლინკი (სურვილისამებრ)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def send_message_as_bot(self, interaction: discord.Interaction, channel: discord.TextChannel, text: str, image_url: Optional[str] = None):
        embed = discord.Embed(description=text, color=discord.Color.blue())
        if image_url:
            # ვამოწმებთ ლინკი მართლა სურათია თუ არა (მარტივი შემოწმება)
            if image_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                embed.set_image(url=image_url)
            else:
                 await interaction.response.send_message("მიუთითე სურათის სწორი ლინკი ( მთავრდება .png, .jpg, .gif...)", ephemeral=True); return
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(f"შეტყობინება გაიგზავნა #{channel.name}-ში.", ephemeral=True)
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება გავაგზავნო შეტყობინება მაგ არხში.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    @app_commands.command(name="sms", description="უგზავნის ანონიმურ პირად შეტყობინებას")
    @app_commands.describe(user="მომხმარებელი", text="ტექსტი")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def send_sms(self, i: discord.Interaction, user: discord.Member, text: str):
        if user.bot: await i.response.send_message("ბოტს ვერ გაუგზავნი", ephemeral=True); return
        try:
            msg = f"**შეტყობინება {i.guild.name}-დან:**\n\n{text}"; await user.send(msg)
            self.log_sms(user.id, "outgoing", text, i.user.id)
            await i.response.send_message(f"SMS გაეგზავნა {user.mention}-ს", ephemeral=True)
        except discord.Forbidden: await i.response.send_message(f"ვერ გავუგზავნე {user.mention}-ს (დაბლოკილი/გამორთული PM?)", ephemeral=True)
        except Exception as e: await i.response.send_message(f"SMS შეცდომა: {e}", ephemeral=True)

    @app_commands.command(name="smslog", description="აჩვენებს მიმოწერის ისტორიას")
    @app_commands.describe(user="მომხმარებელი")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def view_sms_log(self, i: discord.Interaction, user: discord.Member):
        uid_s = str(user.id)
        if uid_s not in self.sms_logs or not self.sms_logs[uid_s]: await i.response.send_message("ისტორია ცარიელია", ephemeral=True); return
        logs=self.sms_logs[uid_s]; e=discord.Embed(title=f"SMS ლოგი - {user.display_name}", color=0x7289da); lt=""
        for entry in logs[-10:]:
            ts=discord.utils.format_dt(datetime.datetime.fromisoformat(entry['ts']),'f')
            d="➡️ ადმინი" if entry['dir']=="outgoing" else "⬅️ იუზერი"
            c=entry['con'];
            if len(c)>150:c=c[:147]+"..."
            lt+=f"`{ts}`\n{d}: {c}\n\n"
        if not lt: lt="ცარიელი"; e.description=lt; e.set_footer(text=f"ბოლო {len(logs[-10:])}")
        await i.response.send_message(embed=e, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None and not message.author.bot:
            uid_s = str(message.author.id)
            if uid_s in self.sms_logs: self.log_sms(message.author.id, "incoming", message.content)

async def setup(bot): await bot.add_cog(UtilityCog(bot))
