import discord
from discord.ext import commands
import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if BOT_TOKEN is None:
    print("შეცდომა: BOT_TOKEN ვერ მოიძებნა Railway Variables-ში.")
    exit()

# --- Intents ---
intents = discord.Intents.default()
intents.members = True       # Welcome, Autorole, Ticket-ისთვის
intents.message_content = True # მომავალი ფუნქციებისთვის

bot = commands.Bot(command_prefix="!", intents=intents)

# Cog-ების სია
cogs_to_load = [
    'moderation_cog',
    'community_cog',
    'giveaway_cog',
    'ticket_cog',
    'utility_cog'
]

@bot.event
async def on_ready():
    print(f"ბოტი '{bot.user}' ჩაირთო!")
    print("-" * 30)

    # ვტვირთავთ Cog-ებს
    loaded_count = 0
    for cog in cogs_to_load:
        try:
            await bot.load_extension(cog)
            print(f"✅ ჩაიტვირთა: {cog}")
            loaded_count += 1
        except Exception as e:
            print(f"❌ ვერ ჩაიტვირთა {cog}: {e}")

    print("-" * 30)
    print(f"სულ ჩაიტვირთა {loaded_count}/{len(cogs_to_load)} ფუნქციონალური მოდული.")
    print("-" * 30)

    # სლეშ ბრძანებების რეგისტრაცია
    try:
        synced = await bot.tree.sync()
        print(f"წარმატებით დარეგისტრირდა {len(synced)} ბრძანება.")
    except Exception as e:
        print(f"შეცდომა ბრძანებების რეგისტრაციისას: {e}")

    print("-" * 30)

bot.run(BOT_TOKEN)
