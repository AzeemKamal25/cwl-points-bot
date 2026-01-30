import os
import json
import requests
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

# Disable voice support to avoid audioop dependency
discord.VoiceClient = None

# ----------------------------
# ENV + CONFIG
# ----------------------------
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CLASH_API_KEY = os.getenv("CLASH_API_KEY")
CLAN_TAG = "#2YJGJGPJG"

API_HEADERS = {
    "Authorization": f"Bearer {CLASH_API_KEY}",
    "Accept": "application/json"
}

DATA_FILE = "cwl_data.json"

# ----------------------------
# BOT SETUP
# ----------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# DATA LOAD
# ----------------------------
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        cwl_data = json.load(f)
else:
    cwl_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(cwl_data, f, indent=2)

# ----------------------------
# TROPHY LOGIC (UNCHANGED)
# ----------------------------
TROPHY_TABLE = {
    0: [0]*32,
    1: [5,6,7,7,8,8,9,9,10,10,10,11,11,11,11,12,12,12,12,13,13,13,13,14,14,14,14,15,15,15,15,0],
    2: [0,0,0,0,0,0,0,0,0,16,17,18,18,19,20,20,21,22,23,23,24,25,26,26,27,28,29,29,30,31,32,0],
    3: [0]*31 + [40]
}

PERCENT_BUCKETS = [
    0, 10, 19, 20, 28, 30, 37, 40, 46, 50,
    53, 55, 56, 59, 62, 64, 65, 68, 71,
    73, 74, 77, 80, 82, 83, 86, 89,
    91, 92, 95, 98, 100
]

def get_trophies(stars, percent):
    for i, p in enumerate(PERCENT_BUCKETS):
        if percent <= p:
            return TROPHY_TABLE[stars][i]
    return TROPHY_TABLE[stars][-1]

# ----------------------------
# NORMAL WAR HELPERS
# ----------------------------
def fetch_current_war():
    url = f"https://api.clashofclans.com/v1/clans/{CLAN_TAG.replace('#', '%23')}/currentwar"
    response = requests.get(url, headers=API_HEADERS)
    return response

def extract_normal_war_stars(war_data):
    players = []

    for member in war_data["clan"]["members"]:
        name = member["name"]
        attacks = member.get("attacks", [])

        stars = sum(atk.get("stars", 0) for atk in attacks)

        players.append({
            "name": name,
            "stars": stars,
            "attacks": len(attacks)
        })

    return players

# ----------------------------
# EVENTS
# ----------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online as {bot.user}")

# ----------------------------
# SLASH COMMANDS
# ----------------------------

@bot.tree.command(name="ping", description="Check bot status")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot is alive.")

@bot.tree.command(name="register", description="Register a player for CWL tracking")
@app_commands.describe(name="In-game name")
async def register(interaction: discord.Interaction, name: str):
    if name in cwl_data:
        await interaction.response.send_message(f"⚠️ **{name}** is already registered.")
        return

    cwl_data[name] = {
        "offense": [],
        "defense": [],
        "points": 0
    }

    save_data()
    await interaction.response.send_message(f"✅ Registered **{name}**")

# ----------------------------
# NORMAL WAR COMMANDS
# ----------------------------

@bot.tree.command(name="sync_normal_war", description="Sync current NORMAL war stars")
async def sync_normal_war(interaction: discord.Interaction):
    await interaction.response.defer()

    response = fetch_current_war()

    if response.status_code != 200:
        await interaction.followup.send(
            f"❌ Failed to fetch war\nStatus: {response.status_code}\n{response.text}"
        )
        return

    war_data = response.json()

    if war_data.get("state") == "notInWar":
        await interaction.followup.send("⚠️ Clan is not in a normal war right now.")
        return

    players = extract_normal_war_stars(war_data)

    # Save into CWL structure WITHOUT touching CWL logic
    for p in players:
        name = p["name"]

        if name not in cwl_data:
            cwl_data[name] = {"offense": [], "defense": [], "points": 0}

        cwl_data[name]["normal_war_stars"] = p["stars"]
        cwl_data[name]["normal_war_attacks"] = p["attacks"]

    save_data()
    await interaction.followup.send(f"✅ Normal war synced for **{len(players)} players**")

@bot.tree.command(name="normal_war_stars", description="Show stars gained so far in normal war")
async def normal_war_stars(interaction: discord.Interaction):
    msg = "⚔️ **Normal War – Stars So Far** ⚔️\n\n"

    found = False
    for name, data in cwl_data.items():
        if "normal_war_stars" in data:
            found = True
            msg += f"⭐ **{name}** → {data['normal_war_stars']} stars ({data.get('normal_war_attacks',0)} attacks)\n"

    if not found:
        await interaction.response.send_message("⚠️ No normal war data synced yet.")
        return

    await interaction.response.send_message(msg)

# ----------------------------
# RUN
# ----------------------------
bot.run(DISCORD_TOKEN)
