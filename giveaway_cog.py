import discord
from discord.ext import commands, tasks
from discord import app_commands
import json; import os; import random; import datetime; import re

GIVEAWAY_DB = "giveaways.json"
def load_data(fp): # ... load_data ...
    if not os.path.exists(fp): return {}
    try:
        with open(fp, "r", encoding='utf-8') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}
def save_data(data, fp): # ... save_data ...
    try:
        with open(fp, "w", encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e: print(f"Save Error ({fp}): {e}")
def parse_duration(ds): # ... parse_duration ...
    r = re.compile(r'(\d+)([smhd])'); p = r.findall(ds.lower()); d = datetime.timedelta()
    for a, u in p: a=int(a); d += datetime.timedelta(**{('seconds' if u=='s' else ('minutes' if u=='m' else ('hours' if u=='h' else 'days'))): a})
    return d

class GiveawayView(discord.ui.View): # ... GiveawayView ...
    def __init__(self, mid): super().__init__(timeout=None); self.giveaway_message_id = mid
    @discord.ui.button(label="მონაწილეობა", style=discord.ButtonStyle.success, custom_id="join_giveaway_button")
    async def join_button(self, i: discord.Interaction, b: discord.ui.Button):
        giveaways = load_data(GIVEAWAY_DB); g = giveaways.get(str(self.giveaway_message_id))
        if not g or g.get('ended', False): await i.response.send_message("გათამაშება დასრულდა/არ არსებობს", ephemeral=True); return
        uid = str(i.user.id)
        if uid not in g['participants']: g['participants'].append(uid); save_data(giveaways, GIVEAWAY_DB); await i.response.send_message("✅ ჩაერთე", ephemeral=True)
        else: await i.response.send_message("⚠️ უკვე მონაწილეობ", ephemeral=True)

class GiveawayCog(commands.Cog): # ... GiveawayCog ...
    def __init__(self, bot): self.bot=bot; self.check_giveaways.start(); self.update_participant_counts.start()
    def cog_unload(self): self.check_giveaways.cancel(); self.update_participant_counts.cancel()

    @app_commands.command(name="giveaway", description="ქმნის ახალ გათამაშებას")
    @app_commands.describe(duration="ხანგრძლივობა (10m 1h 2d)", prize="პრიზი", winners="გამარჯვებული (default 1)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def start_giveaway(self, i: discord.Interaction, duration: str, prize: str, winners: int = 1):
        delta = parse_duration(duration);
        if delta.total_seconds() <= 0: await i.response.send_message("არასწორი დრო", ephemeral=True); return
        et = datetime.datetime.utcnow() + delta; ets = int(et.timestamp())
        e = discord.Embed(title="🎁 გათამაშება 🎁", description=f"**პრიზი:** {prize}\n\nდააჭირე ღილაკს!", color=0xffd700)
        e.add_field(name="მთავრდება:", value=f"<t:{ets}:R>", inline=True); e.add_field(name="გამარჯვებული:", value=f"{winners}", inline=True)
        e.add_field(name="👥 მონაწილე:", value="0", inline=True); e.set_footer(text=f"დაიწყო: {i.user.display_name}")
        await i.response.send_message("გათამაშება იწყება...", ephemeral=True); msg = await i.channel.send(embed=e); v = GiveawayView(msg.id); await msg.edit(view=v)
        gs = load_data(GIVEAWAY_DB); gs[str(msg.id)] = {"channel_id": i.channel.id, "end_time": et.isoformat(), "prize": prize, "winners": winners, "participants": [], "host_id": i.user.id, "ended": False}
        save_data(gs, GIVEAWAY_DB)

    @tasks.loop(seconds=5)
    async def check_giveaways(self):
        await self.bot.wait_until_ready(); gs = load_data(GIVEAWAY_DB); ct = datetime.datetime.utcnow()
        for mid, d in list(gs.items()):
            if d.get('ended', False): continue
            et = datetime.datetime.fromisoformat(d['end_time'])
            if ct >= et:
                ch = self.bot.get_channel(d['channel_id']);
                if not ch: continue
                msg = None;
                try:
                    msg = await ch.fetch_message(int(mid)); p = d['participants']; prize = d.get('prize', '?'); pc = len(p)
                    if not p: wt = "არავინ მონაწილეობდა"; wl = []
                    else: wids = random.sample(p, k=min(d['winners'], len(p))); wl = [f"<@{uid}>" for uid in wids]; wt = ", ".join(wl)
                    we = discord.Embed(title="🎉 გათამაშება დასრულდა", description=f"**პრიზი:** {prize}\n\n**მონაწილე:** {pc}\n\n**გამარჯვებული:** {wt}", color=0x00ff00)
                    await ch.send(content=wt, embed=we);
                    if msg and msg.embeds:
                        oe = msg.embeds[0]; oe.title="🎁 დასრულდა"; oe.description=f"**პრიზი:** {prize}"; oe.color=0x808080
                        oe.set_field_at(0, name="დასრულდა:", value=f"<t:{int(et.timestamp())}:R>", inline=True)
                        if len(oe.fields)>1: oe.set_field_at(1, name="გამარჯვებული:", value=wt if wl else "არავინ", inline=True)
                        if len(oe.fields)>2: oe.set_field_at(2, name="👥 მონაწილე:", value=f"{pc}", inline=True)
                        v = discord.ui.View(); v.add_item(discord.ui.Button(label="მონაწილეობა", style=discord.ButtonStyle.success, disabled=True))
                        await msg.edit(embed=oe, view=v)
                except discord.NotFound: print(f"GW msg {mid} not found.")
                except Exception as e: print(f"Error GW end {mid}: {e}")
                finally: gs[mid]['ended'] = True; save_data(gs, GIVEAWAY_DB)

    @tasks.loop(minutes=1)
    async def update_participant_counts(self):
        await self.bot.wait_until_ready(); gs = load_data(GIVEAWAY_DB)
        for mid, d in gs.items():
            if d.get('ended', False): continue
            ch = self.bot.get_channel(d['channel_id']);
            if not ch: continue
            try:
                msg = await ch.fetch_message(int(mid));
                if not msg.embeds: continue
                ce = msg.embeds[0]; pc = len(d.get('participants', []))
                if len(ce.fields) >= 3:
                    cv = ce.fields[2].value
                    if cv != str(pc): ce.set_field_at(2, name="👥 მონაწილე:", value=str(pc), inline=True); await msg.edit(embed=ce)
            except discord.NotFound: gs[mid]['ended']=True; save_data(gs, GIVEAWAY_DB)
            except discord.Forbidden: print(f"Can't edit GW {mid}"); pass
            except Exception as e: print(f"Update Count Error {mid}: {e}")

async def setup(bot): await bot.add_cog(GiveawayCog(bot))
