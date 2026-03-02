import discord
from discord.ext import commands
import asyncio
import re
from datetime import datetime, timedelta
import os

# ---------------- TOKEN ----------------
TOKEN = os.getenv("DISCORD_TOKEN")

# ---------------- INTENTS ----------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="?",
    intents=intents,
    case_insensitive=True
)

warnings = {}
sniped_messages = {}

EMBED_COLOR = 0x680000

# ---------------- READY EVENT ----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.Game("chilling")
    )

# ---------------- HELPERS ----------------
def parse_duration(duration: str):
    match = re.match(r"(\d+)([smhd])", duration)
    if not match:
        return None
    amount, unit = match.groups()
    return int(amount) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]

def embed_success(title, desc):
    return discord.Embed(title=title, description=desc, color=EMBED_COLOR)

def embed_error(desc):
    return discord.Embed(title="Error", description=desc, color=EMBED_COLOR)

async def get_member(ctx, member_str):
    try:
        return await commands.MemberConverter().convert(ctx, member_str)
    except:
        if member_str and member_str.isdigit():
            try:
                return await ctx.guild.fetch_member(int(member_str))
            except:
                return None
    return None

# ---------------- SNIPE SYSTEM ----------------
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    channel_id = message.channel.id
    entry = {
        "author": message.author,
        "content": message.content,
        "attachments": message.attachments,
        "time": datetime.utcnow()
    }
    sniped_messages.setdefault(channel_id, [])
    sniped_messages[channel_id].insert(0, entry)
    if len(sniped_messages[channel_id]) > 5:
        sniped_messages[channel_id].pop()

@bot.command()
async def snipe(ctx, index: int = 1):
    channel_id = ctx.channel.id
    if channel_id not in sniped_messages or not sniped_messages[channel_id]:
        await ctx.send(embed=embed_error("There's nothing to snipe!"))
        return
    if index < 1 or index > len(sniped_messages[channel_id]):
        await ctx.send(embed=embed_error(
            f"Invalid index! Choose 1-{len(sniped_messages[channel_id])}"
        ))
        return
    data = sniped_messages[channel_id][index - 1]
    embed = discord.Embed(
        title=f"Sniped Message #{index}",
        description=data["content"] or "No text content",
        color=EMBED_COLOR,
        timestamp=data["time"]
    )
    embed.set_author(
        name=str(data["author"]),
        icon_url=data["author"].display_avatar.url
    )
    if data["attachments"]:
        embed.set_image(url=data["attachments"][0].url)
    await ctx.send(embed=embed)

# ---------------- BAN ----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: str = None, *, reason="No reason provided"):
    if not member:
        await ctx.send(embed=embed_error("Usage: ?ban <@user|id> [reason]"))
        return
    try:
        if member.isdigit():
            user = discord.Object(id=int(member))
            await ctx.guild.ban(user, reason=reason)
            await ctx.send(embed=embed_success(
                "User Banned",
                f"<@{member}> | Reason: {reason}"
            ))
        else:
            member_obj = await get_member(ctx, member)
            if not member_obj:
                await ctx.send(embed=embed_error("Member not found."))
                return
            await member_obj.ban(reason=reason)
            await ctx.send(embed=embed_success(
                "User Banned",
                f"{member_obj} | Reason: {reason}"
            ))
    except Exception as e:
        await ctx.send(embed=embed_error(f"Failed: {e}"))

# ---------------- UNBAN ----------------
@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        async for entry in ctx.guild.bans():
            if entry.user.id == user_id:
                await ctx.guild.unban(entry.user)
                await ctx.send(embed=embed_success(
                    "User Unbanned",
                    f"{entry.user} has been unbanned."
                ))
                return
        await ctx.send(embed=embed_error("User not found in bans."))
    except Exception as e:
        await ctx.send(embed=embed_error(f"Failed: {e}"))

# ---------------- RUN ----------------
if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not set in Railway Variables")
    else:
        bot.run(TOKEN)
