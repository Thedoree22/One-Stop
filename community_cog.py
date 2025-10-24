import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random
from typing import Optional
import traceback # დეტალური ლოგირებისთვის

WELCOME_DB = "welcome_data.json"
AUTOROLE_DB = "autorole_data.json"

# --- მონაცემთა ბაზის ფუნქციები ---
def load_data(file):
    if not os.path.exists(file): return {}
    try:
        with open(file, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def save_data(data, file):
    try:
        with open(file, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"ფაილში შენახვის შეცდომა ({file}): {e}")

# --- მთავარი კლასი ---
class CommunityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- ტექსტის დახატვის დამხმარე ფუნქცია Shadow ეფექტით ---
    def draw_text_with_shadow(self, draw, xy, text, font, fill_color, shadow_color=(0, 0, 0, 150), shadow_offset=(2, 2)):
        x, y = xy
        sx, sy = shadow_offset
        # ვხატავთ ჩრდილს
        draw.text((x + sx, y + sy), text, font=font, fill=shadow_color, anchor="lt") # ვიყენებთ lt (left-top) anchor-ს
        # ვხატავთ მთავარ ტექსტს
        draw.text(xy, text, font=font, fill=fill_color, anchor="lt")

    # --- Welcome სურათის გენერირების ფუნქცია (წითელ-შავი ფონი) ---
    async def create_welcome_image(self, member: discord.Member) -> Optional[discord.File]:
        try:
            guild = member.guild
            W, H = (1000, 400) # დავაბრუნოთ ძველი ზომა

            # ფონი: მუქი წითელ-შავი გრადიენტი + ვარსკვლავები
            img = Image.new("RGBA", (W, H))
            draw = ImageDraw.Draw(img)
            start_color = (80, 0, 10) # მუქი წითელი
            end_color = (0, 0, 0)     # შავი
            for i in range(H):
                ratio=i/H; r=int(start_color[0]*(1-ratio)+end_color[0]*ratio); g=int(start_color[1]*(1-ratio)+end_color[1]*ratio); b=int(start_color[2]*(1-ratio)+end_color[2]*ratio)
                draw.line([(0,i),(W,i)], fill=(r,g,b))
            star_color = (255, 255, 255, 150) # თეთრი ვარსკვლავები
            for _ in range(100):
                x=random.randint(0,W); y=random.randint(0,H); size=random.randint(1,3)
                draw.ellipse([(x,y),(x+size,y+size)], fill=star_color)

            # ავატარი (ისევ მარცხნივ, ცენტრში)
            AVATAR_SIZE = 180; avatar_pos = (80, (H // 2) - (AVATAR_SIZE // 2))
            avatar_url = member.display_avatar.url
            try:
                response = requests.get(avatar_url, timeout=10); response.raise_for_status()
                avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                img.paste(avatar_image, avatar_pos, mask)
            except Exception as e:
                print(f"ავატარის ჩატვირთვის შეცდომა: {e}"); draw.ellipse([avatar_pos, (avatar_pos[0]+AVATAR_SIZE, avatar_pos[1]+AVATAR_SIZE)], outline="grey", width=3)

            # ტექსტის დამატება (3 ხაზად, მარჯვნივ)
            draw = ImageDraw.Draw(img)
            try:
                # დავაბრუნოთ წინა ფონტის ზომები
                font_regular = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 50)
                font_bold = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 65) # სახელი
                font_server = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 40)
            except IOError: print("!!! ფონტები ვერ მოიძებნა !!!"); return None

            text_x = avatar_pos[0] + AVATAR_SIZE + 50 # ტექსტის X კოორდინატი

            # ტექსტები
            welcome_text = "მოგესალმებით"
            user_name = member.display_name
            if len(user_name) > 18: user_name = user_name[:15] + "..."
            server_text = f"{guild.name} - ში!"

            # ტექსტის სიმაღლეების გამოთვლა
            bbox_welcome = font_regular.getbbox(welcome_text); h_welcome = bbox_welcome[3] - bbox_welcome[1]
            bbox_user = font_bold.getbbox(user_name); h_user = bbox_user[3] - bbox_user[1]
            bbox_server = font_server.getbbox(server_text); h_server = bbox_server[3] - bbox_server[1]
            line_spacing = 15
            total_text_height = h_welcome + h_user + h_server + (line_spacing * 2)
            current_y = (H // 2) - (total_text_height // 2) # დავიწყოთ ცენტრიდან

            # ვხატავთ ტექსტს Shadow ეფექტით
            self.draw_text_with_shadow(draw, (text_x, current_y), welcome_text, font_regular, fill_color=(220, 220, 220))
            current_y += h_welcome + line_spacing
            self.draw_text_with_shadow(draw, (text_x, current_y), user_name, font_bold, fill_color=(255, 255, 255))
            current_y += h_user + line_spacing
            self.draw_text_with_shadow(draw, (text_x, current_y), server_text, font_server, fill_color=(180, 180, 180))


            final_buffer = io.BytesIO(); img.save(final_buffer, "PNG"); final_buffer.seek(0)
            return discord.File(fp=final_buffer, filename="welcome.png")
        except Exception as e: print(f"Welcome სურათის შექმნის შეცდომა: {e}"); traceback.print_exc(); return None

    # --- Setup ბრძანებები ---
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

    # --- ივენთები ---
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
                if welcome_file:
                    try: await channel.send(f"შემოგვიერთდა {member.mention}!", file=welcome_file)
                    except discord.Forbidden: print(f"არ მაქვს უფლება გავაგზავნო Welcome #{channel.name}-ში")
                    except Exception as e: print(f"Welcome გაგზავნის შეცდომა: {e}")
                else: # თუ სურათი ვერ შეიქმნა
                    try: await channel.send(f"შემოგვიერთდა {member.mention}!")
                    except Exception as e: print(f"Welcome ტექსტის გაგზავნის შეცდომა: {e}")

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(CommunityCog(bot))
