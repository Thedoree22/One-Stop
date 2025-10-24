import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import datetime
from typing import Optional
import traceback # დეტალური ლოგირებისთვის

SMS_LOG_DB = "sms_logs.json"

# --- მონაცემთა ბაზის ფუნქციები (გაუმჯობესებული ლოგირებით) ---
def load_data(file_path):
    if not os.path.exists(file_path):
        print(f"INFO (load_data): ფაილი '{file_path}' არ არსებობს, ვქმნი ცარიელ dict-ს.")
        return {}
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            data = json.load(f)
            print(f"INFO (load_data): მონაცემები '{file_path}'-დან ჩაიტვირთა.")
            return data
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"ERROR (load_data): '{file_path}'-ის ჩატვირთვის შეცდომა: {e}. ვბრუნებ ცარიელს.")
        try: os.rename(file_path, f"{file_path}.corrupted_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}")
        except OSError: pass
        return {}
    except Exception as e:
        print(f"!!! მოულოდნელი შეცდომა '{file_path}'-ის ჩატვირთვისას: {e}. ვბრუნებ ცარიელს.")
        return {}

def save_data(data, file_path):
    try:
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            # print(f"DEBUG (save_data): მონაცემები შეინახა '{file_path}'-ში.") # შეგიძლია ჩართო დეტალური ლოგისთვის
    except Exception as e:
        print(f"ERROR (save_data): '{file_path}'-ში შენახვის შეცდომა: {e}")

# --- მთავარი კლასი ---
class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("--- UtilityCog: SMS ლოგების ჩატვირთვა ---")
        self.sms_logs = load_data(SMS_LOG_DB)
        print(f"ჩატვირთული SMS ლოგები: {len(self.sms_logs)} მომხმარებელი")
        print("---------------------------------------")

    # --- დამხმარე ფუნქცია SMS ლოგირებისთვის (გაუმჯობესებული) ---
    def log_sms(self, user_id: int, direction: str, content: str, admin_id: Optional[int] = None):
        """Logs an SMS message."""
        user_id_str = str(user_id)
        if user_id_str not in self.sms_logs:
            self.sms_logs[user_id_str] = []

        # ვამოწმებთ, ხომ არ არის კონტენტი ცარიელი
        if not content or not content.strip():
            print(f"DEBUG (log_sms): ცარიელი შეტყობინების დალოგვის მცდელობა user {user_id_str}-თვის.")
            return

        log_entry = {
            "ts": datetime.datetime.utcnow().isoformat(), # შევამოკლეთ გასაღები "timestamp" -> "ts"
            "dir": direction, # შევამოკლეთ გასაღები "direction" -> "dir"
            "con": content    # შევამოკლეთ გასაღები "content" -> "con"
        }
        if admin_id:
            log_entry["aid"] = admin_id # შევამოკლეთ გასაღები "admin_id" -> "aid"

        self.sms_logs[user_id_str].append(log_entry)
        # ვინახავთ ყოველი ახალი ლოგის შემდეგ
        save_data(self.sms_logs, SMS_LOG_DB)
        print(f"DEBUG (log_sms): დაემატა ლოგი user {user_id_str}-თვის ({direction}).")

    # --- /message ბრძანება ---
    @app_commands.command(name="message", description="აგზავნის შეტყობინებას ბოტის სახელით")
    @app_commands.describe(channel="არხი სადაც გაიგზავნება", text="შეტყობინების ტექსტი", image_url="სურათის ლინკი (სურვილისამებრ)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def send_message_as_bot(self, interaction: discord.Interaction, channel: discord.TextChannel, text: str, image_url: Optional[str] = None):
        embed = discord.Embed(description=text, color=discord.Color.blue())
        if image_url:
            if image_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')): embed.set_image(url=image_url)
            else: await interaction.response.send_message("მიუთითე სურათის სწორი ლინკი", ephemeral=True); return
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(f"შეტყობინება გაიგზავნა #{channel.name}-ში.", ephemeral=True)
        except discord.Forbidden: await interaction.response.send_message("არ მაქვს უფლება გავაგზავნო შეტყობინება მაგ არხში.", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"მოხდა შეცდომა: {e}", ephemeral=True)

    # --- /sms ბრძანება ---
    @app_commands.command(name="sms", description="უგზავნის ანონიმურ პირად შეტყობინებას")
    @app_commands.describe(user="მომხმარებელი", text="ტექსტი")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def send_sms(self, interaction: discord.Interaction, user: discord.Member, text: str):
        if user.bot: await interaction.response.send_message("ბოტს ვერ გაუგზავნი", ephemeral=True); return
        try:
            message_to_send = f"**შეტყობინება {interaction.guild.name}-დან:**\n\n{text}"; await user.send(message_to_send)
            self.log_sms(user.id, "outgoing", text, interaction.user.id) # ვიყენებთ განახლებულ log_sms-ს
            await interaction.response.send_message(f"SMS გაეგზავნა {user.mention}-ს", ephemeral=True)
        except discord.Forbidden: await interaction.response.send_message(f"ვერ გავუგზავნე {user.mention}-ს (დაბლოკილი/გამორთული PM?)", ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"SMS შეცდომა: {e}", ephemeral=True)

    # --- /smslog ბრძანება (გაუმჯობესებული) ---
    @app_commands.command(name="smslog", description="აჩვენებს მიმოწერის ისტორიას")
    @app_commands.describe(user="მომხმარებელი")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def view_sms_log(self, interaction: discord.Interaction, user: discord.Member):
        user_id_str = str(user.id)
        # ვტვირთავთ ლოგებს ფაილიდან ყოველ ჯერზე, რომ უახლესი ვნახოთ
        current_logs = load_data(SMS_LOG_DB)
        user_logs = current_logs.get(user_id_str, [])

        if not user_logs:
            await interaction.response.send_message(f"{user.mention}-თან მიმოწერის ისტორია ცარიელია.", ephemeral=True); return

        embed = discord.Embed(title=f"SMS ლოგი - {user.display_name}", color=0x7289da); log_text = ""
        # ვაჩვენოთ ბოლო 15 შეტყობინება
        for entry in user_logs[-15:]:
            try:
                # ვცდილობთ დროის პარსირებას, თუ ვერ მოხერხდა, ვაიგნორებთ
                timestamp = discord.utils.format_dt(datetime.datetime.fromisoformat(entry.get('ts', '')), style='f') if entry.get('ts') else "[დრო უცნობია]"
            except ValueError:
                timestamp = "[დროის ფორმატი არასწორია]"

            direction = "➡️ ადმინი" if entry.get('dir') == "outgoing" else "⬅️ იუზერი"
            content = entry.get('con', '[შინაარსი არ არის]') # ვიღებთ შემოკლებული გასაღებით

            if len(content) > 150: content = content[:147] + "..."
            log_text += f"`{timestamp}`\n{direction}: {content}\n\n"

        if not log_text: log_text = "ლოგები ცარიელია ან არასწორი ფორმატი აქვს.";

        embed.description = log_text[:4090] # Embed-ის აღწერის ლიმიტი
        embed.set_footer(text=f"ნაჩვენებია ბოლო {len(user_logs[-15:])} შეტყობინება")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- ივენთი შემომავალი DM ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ვამოწმებთ არის თუ არა DM, არა ბოტისგან და არა ცარიელი
        if message.guild is None and not message.author.bot and message.content:
            user_id_str = str(message.author.id)
            # ვლოგავთ მხოლოდ იმ მომხმარებლების პასუხებს, ვისაც ჩვენ ოდესმე მივწერეთ
            # ვტვირთავთ ლოგებს აქაც, რომ დავრწმუნდეთ user_id_str არსებობს
            current_logs = load_data(SMS_LOG_DB)
            if user_id_str in current_logs:
                self.log_sms(user_id=message.author.id, direction="incoming", content=message.content)

# Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
