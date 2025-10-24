import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import requests
import io
from typing import Optional

WELCOME_DB = "welcome_data.json"
AUTOROLE_DB = "autorole_data.json"

def load_data(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_data(data, file):
    try:
        with open(file, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"ფაილში შენახვის შეცდომა ({file}): {e}")

class CommunityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def create_welcome_image(self, member: discord.Member) -> Optional[discord.File]:
        try:
            guild = member.guild
            W, H = (1000, 300) # უფრო ჰორიზონტალური სურათი
            BG_COLOR = (20, 20, 30, 255) # მუქი ლურჯი-იასამნისფერი ფონი

            img = Image.new("RGBA", (W, H), BG_COLOR)
            draw = ImageDraw.Draw(img)

            # სერვერის იკონკა (მრგვალი, მარცხნივ ზემოთ)
            ICON_SIZE = 80
            icon_pos = (40, 30)
            if guild.icon:
                try:
                    icon_response = requests.get(guild.icon.url, timeout=5); icon_response.raise_for_status()
                    server_icon = Image.open(io.BytesIO(icon_response.content)).convert("RGBA")
                    server_icon = server_icon.resize((ICON_SIZE, ICON_SIZE))
                    mask = Image.new("L", (ICON_SIZE, ICON_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, ICON_SIZE, ICON_SIZE), fill=255)
                    img.paste(server_icon, icon_pos, mask)
                except Exception as e: print(f"სერვერის იკონკის ჩატვირთვის შეცდომა: {e}")

            # სერვერის სახელი (იკონკის მარჯვნივ)
            try: font_server = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 40)
            except IOError: print("!!! სერვერის სახელის ფონტი ვერ მოიძებნა !!!"); return None
            server_name_x = icon_pos[0] + ICON_SIZE + 20
            server_name_y = icon_pos[1] + ICON_SIZE // 2
            draw.text((server_name_x, server_name_y), guild.name, fill=(200, 200, 220), font=font_server, anchor="lm") # left-middle

            # მომხმარებლის ავატარი (მრგვალი, ცენტრში ქვემოთ)
            AVATAR_SIZE = 150
            avatar_pos = (W // 2 - AVATAR_SIZE // 2, 110) # Y კოორდინატი ქვემოთ
            avatar_url = member.display_avatar.url # ვიყენებთ display_avatar-ს
            try:
                response = requests.get(avatar_url, timeout=10); response.raise_for_status()
                avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                img.paste(avatar_image, avatar_pos, mask)
            except Exception as e:
                print(f"ავატარის ჩატვირთვის შეცდომა: {e}"); draw.ellipse([avatar_pos, (avatar_pos[0]+AVATAR_SIZE, avatar_pos[1]+AVATAR_SIZE)], outline="grey", width=3)

            # ტექსტი (ავატარის ქვემოთ, ცენტრში)
            try:
                font_welcome = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 35)
                font_name = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 50)
            except IOError: print("!!! მისალმების ფონტები ვერ მოიძებნა !!!"); return None

            text_y = avatar_pos[1] + AVATAR_SIZE + 25 # Y კოორდინატი ავატარის ქვემოთ

            # მომხმარებლის სახელი
            user_name = member.display_name # ვიყენებთ display_name-ს (შეიძლება იყოს ნიკნეიმი)
            draw.text((W / 2, text_y), user_name, fill=(255, 255, 255), font=font_name, anchor="ms") # middle-top

            # მისალმების ტექსტი
            welcome_text = f"კეთილი იყოს შენი მობრძანება!"
            text_y += 60 # დაშორება
            draw.text((W / 2, text_y), welcome_text, fill=(180, 180, 200), font=font_welcome, anchor="ms")

            final_buffer = io.BytesIO(); img.save(final_buffer, "PNG"); final_buffer.seek(0)
            return discord.File(fp=final_buffer, filename="welcome.png")
        except Exception as e: print(f"Welcome სურათის შექმნის შეცდომა: {e}"); import traceback; traceback.print_exc(); return None

    @app_commands.command(name="welcome", description="აყენებს მისალმების არხს")
    @app_commands.describe(channel="აირჩიე არხი")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def welcome_setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data(WELCOME_DB); data[str(interaction.guild.id)] = {"channel_id": channel.id}; save_data(data, WELCOME_DB)
        await interaction.response.send_message(f"მისალმების არხი არის {channel.mention}", ephemeral=True)

    @app_commands.command(name="autorole", description="აყენებს როლს ახალი წევრებისთვის")
    @app_commands.describe(role="აირჩიე როლი")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_setup(self, interaction: discord.Interaction, role: discord.Role):
        if interaction.guild.me.top_role <= role:
            await interaction.response.send_message("ამ როლის მინიჭება არ შემიძლია (ჩემზე მაღლაა)", ephemeral=True); return
        data = load_data(AUTOROLE_DB); data[str(interaction.guild.id)] = {"role_id": role.id}; save_data(data, AUTOROLE_DB)
        await interaction.response.send_message(f"ავტო როლი დაყენდა: **{role.name}**", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild_id = str(member.guild.id)
        # როლი
        autorole_data = load_data(AUTOROLE_DB)
        if guild_id in autorole_data:
            role_id = autorole_data[guild_id].get("role_id"); role = member.guild.get_role(role_id)
            if role: try: await member.add_roles(role) except Exception as e: print(f"როლის მიჭების შეცდომა: {e}")
        # მისალმება
        welcome_data = load_data(WELCOME_DB)
        if guild_id in welcome_data:
            channel_id = welcome_data[guild_id].get("channel_id"); channel = member.guild.get_channel(channel_id)
            if channel:
                welcome_file = await self.create_welcome_image(member)
                if welcome_file: await channel.send(f"შემოგვიერთდა {member.mention}!", file=welcome_file)
                else: await channel.send(f"შემოგვიერთდა {member.mention}!")

async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCog(bot))
