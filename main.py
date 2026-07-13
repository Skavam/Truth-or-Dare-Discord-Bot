# A Discord Free and Open-Source made by @Skavam that remake the Truth or Dare game inside of Discord with spicy questions

import discord
from discord import app_commands
import random
import json
import logging
import os
import string
import time
from pathlib import Path
from dotenv import load_dotenv

_here = Path(__file__).resolve().parent
_candidates = [_here / ".env", _here.parent / ".env"]
for _candidate in _candidates:
    if _candidate.exists():
        load_dotenv(dotenv_path=_candidate)
        break
else:
    load_dotenv()  
 
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("truth-or-dare-bot")

TRUTHS = [
    "This is where you can add your questions!",
    "You can add an infinite amount!",
]

DARES = [
    "This is where you can add your dares!",
    "You can add an infinite amount!",
]

NSFW_TRUTHS = [
    "This is where you can add your NSFW questions!",
    "You can add an infinite amount!",
]

NSFW_DARES = [
    "This is where you can add your NSFW dares!",
    "You can add an infinite amount!",
]

DEFAULT_RATINGS = {
    "truth": "PG",
    "dare": "PG",
    "nsfw_truth": "18+",
    "nsfw_dare": "18+",
}

KIND_LABELS = {
    "truth": "TRUTH",
    "dare": "DARE",
    "nsfw_truth": "TRUTH",
    "nsfw_dare": "DARE",
}

BUTTON_COOLDOWN_SECONDS = 3.0

def gen_id(length: int = 10) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))
 
def get_prompt_text(entry) -> str:
    return entry["text"] if isinstance(entry, dict) else entry
 
def get_prompt_rating(entry, kind: str) -> str:
    if isinstance(entry, dict) and "rating" in entry:
        return entry["rating"]
    return DEFAULT_RATINGS[kind]
 
def pick_unique(pool: list, last_map: dict[int, object], channel_id: int):
    if not pool:
        return None
    choice = random.choice(pool)
    if len(pool) > 1:
        while choice == last_map.get(channel_id):
            choice = random.choice(pool)
    last_map[channel_id] = choice
    return choice

def is_nsfw_channel(channel) -> bool:
    """Return True if the channel (or, for threads, its parent channel) is marked NSFW."""
    if isinstance(channel, discord.Thread):
        parent = channel.parent
        return bool(getattr(parent, "is_nsfw", lambda: False)()) if parent is not None else False
    return bool(getattr(channel, "is_nsfw", lambda: False)())
 
intents = discord.Intents.default()
intents.message_content = True
 
class TruthOrDareClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.last_shown: dict[str, dict[int, object]] = {
            "truth": {},
            "dare": {},
            "nsfw_truth": {},
            "nsfw_dare": {},
        }
        self.last_click: dict[int, float] = {}
 
    async def setup_hook(self):
        await self.tree.sync()
 
client = TruthOrDareClient()
 
POOLS = {
    "truth": TRUTHS,
    "dare": DARES,
    "nsfw_truth": NSFW_TRUTHS,
    "nsfw_dare": NSFW_DARES,
}
 
def build_embed(kind: str, prompt_text: str, rating: str, requester: discord.abc.User) -> discord.Embed:
    label = KIND_LABELS[kind]
    color = discord.Color.green() if label == "TRUTH" else discord.Color.red()
 
    embed = discord.Embed(color=color)
    embed.set_author(name=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)
    embed.description = f"**{prompt_text}**"
    embed.add_field(
        name="",
        value=f"Type: {label} | Rating: {rating} | ID: {gen_id()}",
        inline=False,
    )
    return embed
 
class TruthOrDareView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  

    def _check_cooldown(self, user_id: int) -> float:
        now = time.monotonic()
        last = client.last_click.get(user_id)
        if last is not None:
            elapsed = now - last
            if elapsed < BUTTON_COOLDOWN_SECONDS:
                return BUTTON_COOLDOWN_SECONDS - elapsed
        client.last_click[user_id] = now
        return 0.0
 
    async def _send_prompt(self, interaction: discord.Interaction, kind: str):
        remaining = self._check_cooldown(interaction.user.id)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Slow down! You can click again in {remaining:.1f}s.",
                ephemeral=True,
            )
            return

        if kind.startswith("nsfw"):
            channel = interaction.channel
            if not is_nsfw_channel(channel):
                await interaction.response.send_message(
                    "🔒 NSFW prompts can only be used in a channel marked as NSFW in Discord's channel settings.",
                    ephemeral=True,
                )
                return
                
        pool = POOLS[kind]
        if not pool:
            await interaction.response.send_message(
                f"No prompts have been added to the `{kind}` pool yet — ask the bot owner to fill it in.",
                ephemeral=True,
            )
            return
 
        entry = pick_unique(pool, client.last_shown[kind], interaction.channel_id)
        text = get_prompt_text(entry)
        rating = get_prompt_rating(entry, kind)
 
        embed = build_embed(kind, text, rating, interaction.user)
        await interaction.response.send_message(embed=embed, view=TruthOrDareView())
 
    @discord.ui.button(label="Truth", style=discord.ButtonStyle.success, custom_id="tod:truth")
    async def truth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_prompt(interaction, "truth")
 
    @discord.ui.button(label="Dare", style=discord.ButtonStyle.danger, custom_id="tod:dare")
    async def dare_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_prompt(interaction, "dare")
 
    @discord.ui.button(label="NSFW Truth", style=discord.ButtonStyle.secondary, custom_id="tod:nsfw_truth")
    async def nsfw_truth_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_prompt(interaction, "nsfw_truth")
 
    @discord.ui.button(label="NSFW Dare", style=discord.ButtonStyle.secondary, custom_id="tod:nsfw_dare")
    async def nsfw_dare_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._send_prompt(interaction, "nsfw_dare")
 
@client.event
async def on_ready():
    client.add_view(TruthOrDareView())
    log.info(f"Logged in as {client.user} (ID: {client.user.id})")
    log.info("Slash commands synced and ready.")
 
@client.tree.command(name="truthordare", description="Start a game of Truth or Dare")
async def truthordare(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Truth or Dare",
        description="Pick a button below to get a prompt.",
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=TruthOrDareView())

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set the DISCORD_TOKEN environment variable before running the bot.")
    client.run(token)
