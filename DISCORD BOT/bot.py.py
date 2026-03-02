import discord
from discord.ext import commands
import asyncio
import re
from datetime import datetime, timedelta

# ---------------- BOT SETUP ----------------
TOKEN = "MTQ3NzgzMTMxOTA1MTMwOTI2Nw.G4jupQ.YVRLl0MRJTR-aSyC208K28ToahSiaNfti0Z-iM"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="?", intents=intents, case_insensitive=True)
warnings = {}
sniped_messages = {}  # Store last deleted messages per channel (up to 5)

# ---------------- EMBED COLOR ----------------
EMBED_COLOR = 0x680000  # hex #680000 for all embeds

# ---------------- READY EVENT ----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(status=discord.Status.dnd, activity=discord.Game("chilling"))

# ---------------- HELPERS ----------------
def parse_duration(duration: str):
    match = re.match(r"(\d+)([smhd])", duration)
    if not match:
        return None
    amount, unit = match.groups()
    return int(amount) * {"s":1, "m":60, "h":3600, "d":86400}[unit]

def embed_success(title, desc):
    return discord.Embed(title=title, description=desc, color=EMBED_COLOR)

def embed_error(desc):
    return discord.Embed(title="Error", description=desc, color=EMBED_COLOR)

async def wait_for_command(ctx, command_name, timeout=60):
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower().startswith(f"?{command_name.lower()}")
    try:
        return await bot.wait_for("message", check=check, timeout=timeout)
    except asyncio.TimeoutError:
        await ctx.send(embed=embed_error(f"{command_name.capitalize()} command timed out. Please try again."))
        return None

async def get_member(ctx, member_str):
    if not member_str:
        return None
    try:
        return await commands.MemberConverter().convert(ctx, member_str)
    except commands.MemberNotFound:
        if member_str.isdigit():
            try:
                return await ctx.guild.fetch_member(int(member_str))
            except discord.NotFound:
                return None
    return None

async def extract_member_info(ctx, msg, require_duration=False):
    parts = msg.content.split()
    if len(parts) < 2:
        await ctx.send(embed=embed_error("You didn’t mention anyone. Canceling command."))
        return None, None, None
    member_str = parts[1]
    member = await get_member(ctx, member_str)
    if require_duration:
        duration = parts[2] if len(parts) > 2 else None
        reason = " ".join(parts[3:]) if len(parts) > 3 else "No reason provided"
        return member, duration, reason
    else:
        reason = " ".join(parts[2:]) if len(parts) > 2 else "No reason provided"
        return member, reason, None

# ---------------- PROMPTS ----------------
def embed_ban_prompt(): return discord.Embed(title="Who would you like to ban", description="Use `?ban <@user|user_id> [reason]`", color=EMBED_COLOR)
def embed_kick_prompt(): return discord.Embed(title="Who would you like to kick", description="Use `?kick <@user|user_id> [reason]`", color=EMBED_COLOR)
def embed_mute_prompt(): return discord.Embed(title="Who would you like to mute", description="Use `?mute <@user|user_id> <duration> [reason]`", color=EMBED_COLOR)
def embed_warn_prompt(): return discord.Embed(title="Who would you like to warn", description="Use `?warn <@user|user_id> [reason]`", color=EMBED_COLOR)
def embed_unban_prompt(): return discord.Embed(title="Who would you like to unban", description="Use `?unban <user_id|username#1234>`", color=EMBED_COLOR)

# ---------------- SNIPED MESSAGES ----------------
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
    if channel_id not in sniped_messages:
        sniped_messages[channel_id] = []
    sniped_messages[channel_id].insert(0, entry)  # newest first
    if len(sniped_messages[channel_id]) > 5:  # keep last 5
        sniped_messages[channel_id].pop()

@bot.command()
async def snipe(ctx, index: int = 1):
    """Snipe deleted messages. Use ?snipe 1 for last, 2 for before that, etc."""
    channel_id = ctx.channel.id
    if channel_id not in sniped_messages or not sniped_messages[channel_id]:
        await ctx.send(embed=embed_error("There's nothing to snipe!"))
        return
    if index < 1 or index > len(sniped_messages[channel_id]):
        await ctx.send(embed=embed_error(f"Invalid index! Only 1-{len(sniped_messages[channel_id])} available."))
        return

    data = sniped_messages[channel_id][index - 1]
    embed = discord.Embed(
        title=f"📝 Sniped Message #{index}",
        description=data["content"] or "No text content",
        color=EMBED_COLOR,
        timestamp=data["time"]
    )
    embed.set_author(name=str(data["author"]), icon_url=data["author"].display_avatar.url)
    if data["attachments"]:
        embed.set_image(url=data["attachments"][0].url)
    await ctx.send(embed=embed)

# ---------------- MODERATION COMMANDS ----------------
# ----- BAN -----
@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: str = None, *, reason="No reason provided"):
    if not member:
        await ctx.send(embed=embed_ban_prompt())
        msg = await wait_for_command(ctx, "ban")
        if not msg: return
        member, reason, _ = await extract_member_info(ctx, msg)
        if not member: return
    try:
        if member.isdigit():
            user = discord.Object(id=int(member))
            await ctx.guild.ban(user, reason=reason)
            await ctx.send(embed=embed_success("Banned", f"<@{member}> | Reason: {reason}"))
        else:
            member_obj = await get_member(ctx, member)
            if not member_obj:
                await ctx.send(embed=embed_error(f"Could not find member: {member}"))
                return
            await member_obj.ban(reason=reason)
            await ctx.send(embed=embed_success("Banned", f"{member_obj} | Reason: {reason}"))
    except Exception as e:
        await ctx.send(embed=embed_error(f"Failed to ban {member}: {e}"))

# ----- UNBAN -----
@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user: str = None):
    if not user:
        await ctx.send(embed=embed_unban_prompt())
        msg = await wait_for_command(ctx, "unban")
        if not msg: return
        user = msg.content.split()[1]
    try:
        if user.isdigit():
            user_id = int(user)
            async for entry in ctx.guild.bans():
                if entry.user.id == user_id:
                    await ctx.guild.unban(entry.user)
                    await ctx.send(embed=embed_success("Unbanned User", f"{entry.user} has been unbanned."))
                    return
            await ctx.send(embed=embed_error(f"No banned user found with ID {user_id}"))
        else:
            async for entry in ctx.guild.bans():
                if str(entry.user) == user:
                    await ctx.guild.unban(entry.user)
                    await ctx.send(embed=embed_success("Unbanned User", f"{entry.user} has been unbanned."))
                    return
            await ctx.send(embed=embed_error(f"No banned user found with username {user}"))
    except Exception as e:
        await ctx.send(embed=embed_error(f"Failed to unban {user}: {e}"))

# ----- KICK -----
@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: str = None, *, reason="No reason provided"):
    if not member:
        await ctx.send(embed=embed_kick_prompt())
        msg = await wait_for_command(ctx, "kick")
        if not msg: return
        member, reason, _ = await extract_member_info(ctx, msg)
        if not member: return
    member_obj = await get_member(ctx, member)
    if not member_obj:
        await ctx.send(embed=embed_error(f"Could not find member: {member}"))
        return
    try:
        await member_obj.kick(reason=reason)
        await ctx.send(embed=embed_success("Kicked Member", f"{member_obj} | Reason: {reason}"))
    except Exception as e:
        await ctx.send(embed=embed_error(f"Failed to kick {member}: {e}"))

# ----- MUTE -----
@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: str = None, duration: str = None, *, reason="No reason provided"):
    if not member:
        await ctx.send(embed=embed_mute_prompt())
        msg = await wait_for_command(ctx, "mute")
        if not msg: return
        member, duration, reason = await extract_member_info(ctx, msg, require_duration=True)
        if not member: return
    member_obj = await get_member(ctx, member)
    if not member_obj:
        await ctx.send(embed=embed_error(f"Could not find member: {member}"))
        return
    try:
        until = datetime.utcnow() + timedelta(seconds=parse_duration(duration)) if duration else datetime.utcnow() + timedelta(days=28)
        await member_obj.timeout(until, reason=reason)
        await ctx.send(embed=embed_success("Muted Member", f"{member_obj} for {duration or 'indefinitely'} | Reason: {reason}"))
    except Exception as e:
        await ctx.send(embed=embed_error(f"Failed to mute {member}: {e}"))

# ----- WARN -----
@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: str = None, *, reason="No reason provided"):
    if not member:
        await ctx.send(embed=embed_warn_prompt())
        msg = await wait_for_command(ctx, "warn")
        if not msg: return
        member, reason, _ = await extract_member_info(ctx, msg)
        if not member: return
    member_obj = await get_member(ctx, member)
    if not member_obj:
        await ctx.send(embed=embed_error(f"Could not find member: {member}"))
        return
    warnings.setdefault(member_obj.id, []).append(reason)
    await ctx.send(embed=embed_success("Warned Member", f"{member_obj} | Reason: {reason} | Total warns: {len(warnings[member_obj.id])}"))

# ---------------- RUN BOT ----------------
bot.run(TOKEN)