import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from PIL import Image, ImageDraw, ImageFont
import requests
import io
from typing import Optional
import traceback # დავამატეთ დეტალური ლოგირებისთვის

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
        anchor_arg = {}
        # ვცდილობთ გამოვიყენოთ Pillow-ს ახალი მეთოდები ზუსტი პოზიციონირებისთვის
        if hasattr(font, 'getbbox'):
             bbox = font.getbbox(text, anchor="lm") # ვიღებთ bbox-ს left-middle anchor-ით
             # anchor="lm"-ის ემულაცია (დაახლოებით)
             x_main = x
             y_main = y #- bbox[1] # ვასწორებთ Y კოორდინატს baseline-ის მიხედვით
             x_shadow = x + sx
             y_shadow = y + sy #- bbox[1]
             # Pillow 10+ ვერსიებში draw.text-ს აღარ აქვს anchor პარამეტრი პირდაპირ getbbox-თან ერთად
             # draw.text-ს გადავცემთ გამოთვლილ კოორდინატებს
             draw.text((x_shadow, y_shadow), text, font=font, fill=shadow_color)
             draw.text((x_main, y_main), text, font=font, fill=fill_color)

        else: # ძველი Pillow ვერსიები პირდაპირ anchor-ს იყენებენ
            anchor_arg = {'anchor': 'lm'}
            draw.text((x + sx, y + sy), text, font=font, fill=shadow_color, **anchor_arg)
            draw.text(xy, text, font=font, fill=fill_color, **anchor_arg)


    # --- Welcome სურათის გენერირების ფუნქცია (აწეული ელემენტებით) ---
    async def create_welcome_image(self, member: discord.Member) -> Optional[discord.File]:
        try:
            guild = member.guild
            W, H = (1000, 300) # სურათის ზომა
            BG_COLOR = (20, 20, 30, 255) # ფონი

            img = Image.new("RGBA", (W, H), BG_COLOR)
            draw = ImageDraw.Draw(img)

            # სერვერის იკონკა (მრგვალი, მარცხნივ ზემოთ - ოდნავ ავწიოთ)
            ICON_SIZE = 80
            icon_pos = (40, 25) # <<<--- Y კოორდინატი შევცვალეთ 30 -> 25
            server_icon = None
            if guild.icon:
                try:
                    icon_response = requests.get(guild.icon.url, timeout=5); icon_response.raise_for_status()
                    server_icon_img = Image.open(io.BytesIO(icon_response.content)).convert("RGBA")
                    server_icon_img = server_icon_img.resize((ICON_SIZE, ICON_SIZE))
                    mask = Image.new("L", (ICON_SIZE, ICON_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, ICON_SIZE, ICON_SIZE), fill=255)
                    img.paste(server_icon_img, icon_pos, mask)
                    server_icon = True
                except Exception as e: print(f"სერვერის იკონკის ჩატვირთვის შეცდომა: {e}"); server_icon = None

            # სერვერის სახელი (ოდნავ ავწიოთ)
            try: font_server = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 40)
            except IOError: print("!!! ფონტი NotoSansGeorgian-Bold.ttf ვერ მოიძებნა !!!"); return None

            server_name_x = icon_pos[0] + ICON_SIZE + 20
            if not server_icon: server_name_x = icon_pos[0]
            server_name_y = icon_pos[1] + ICON_SIZE // 2 # Y კოორდინატი (ვერტიკალურად ცენტრში იკონკასთან)
            self.draw_text_with_shadow(draw, (server_name_x, server_name_y), guild.name, font_server, fill_color=(200, 200, 220))

            # მომხმარებლის ავატარი (მრგვალი, ცენტრში ქვემოთ - ოდნავ ავწიოთ)
            AVATAR_SIZE = 140 # ოდნავ დავაპატარავოთ
            avatar_pos = (W // 2 - AVATAR_SIZE // 2, 95) # <<<--- Y კოორდინატი შევცვალეთ 110 -> 95
            avatar_url = member.display_avatar.url
            try:
                response = requests.get(avatar_url, timeout=10); response.raise_for_status()
                avatar_image = Image.open(io.BytesIO(response.content)).convert("RGBA")
                avatar_image = avatar_image.resize((AVATAR_SIZE, AVATAR_SIZE))
                mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0); draw_mask = ImageDraw.Draw(mask); draw_mask.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                img.paste(avatar_image, avatar_pos, mask)
            except Exception as e:
                print(f"ავატარის ჩატვირთვის შეცდომა: {e}"); draw.ellipse([avatar_pos, (avatar_pos[0]+AVATAR_SIZE, avatar_pos[1]+AVATAR_SIZE)], outline="grey", width=3)

            # ტექსტი (ავატარის ქვემოთ, ცენტრში - ოდნავ ავწიოთ)
            try:
                font_welcome = ImageFont.truetype("NotoSansGeorgian-Regular.ttf", 35)
                font_name = ImageFont.truetype("NotoSansGeorgian-Bold.ttf", 50)
            except IOError: print("!!! ფონტები NotoSansGeorgian ვერ მოიძებნა !!!"); return None

            text_y_start = avatar_pos[1] + AVATAR_SIZE + 15 # <<<--- დაშორება შევამცირეთ 25 -> 15

            # მომხმარებლის სახელი
            user_name = member.display_name
            if hasattr(font_name, 'getbbox'): bbox_user = font_name.getbbox(user_name); text_width_user = bbox_user[2] - bbox_user[0]; text_height_user = bbox_user[3] - bbox_user[1]
            else: text_width_user, text_height_user = font_name.getsize(user_name)
            self.draw_text_with_shadow(draw, (W // 2 - text_width_user // 2, text_y_start + text_height_user//2), user_name, font_name, fill_color=(255, 255, 255)) # ვიყენებთ lm anchor-ის ემულაციას

            # მისასალმებელი ტექსტი
            welcome_text = f"კეთილი იყოს შენი მობრძანება!"
            text_y_welcome = text_y_start + text_height_user + 10 # დაშორება სახელის შემდეგ
            if hasattr(font_welcome, 'getbbox'): bbox_welcome = font_welcome.getbbox(welcome_text); text_width_welcome = bbox_welcome[2] - bbox_welcome[0]; text_height_welcome = bbox_welcome[3] - bbox_welcome[1]
            else: text_width_welcome, text_height_welcome = font_welcome.getsize(welcome_text)
            self.draw_text_with_shadow(draw, (W // 2 - text_width_welcome // 2, text_y_welcome + text_height_welcome//2), welcome_text, font_welcome, fill_color=(180, 180, 200)) # ვიყენებთ lm anchor-ის ემულაციას


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
