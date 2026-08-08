import os
import discord
import datetime

BOT_TOKEN = os.environ["MTUzNTQ5NzA3ODY3Nzk3MTA0NA.GCNwX2.P5b4FBS_sP9B6OzL3MkUTHk3gPk4kc0Hxsb84E"]
GUILD_ID = int(os.environ["1535491122413961218"])
VERIFY_CHANNEL_ID = int(os.environ["1535504240846438440"])
VERIFY_MESSAGE_ID = int(os.environ["1535504262006579272"])

intents = discord.Intents.all()
activity = discord.Activity(type=discord.ActivityType.watching, name="DEGRADECORE")
client = discord.Client(intents=intents, activity=activity, status=discord.Status.online)


@client.event
async def on_ready():
    print(f"✅ Бот {client.user} запущен на Railway и работает 24/7!")
    print(f"🎯 Сервер: {GUILD_ID}")
    print(f"🛡️ Канал верификации: {VERIFY_CHANNEL_ID}")
    print(f"📌 Сообщение верификации: {VERIFY_MESSAGE_ID}")
    print("💀 DEGRADECORE бот активен.")


@client.event
async def on_raw_reaction_add(payload):
    if payload.channel_id != VERIFY_CHANNEL_ID:
        return
    if payload.message_id != VERIFY_MESSAGE_ID:
        return
    if str(payload.emoji) != "✅":
        return
    if payload.member and payload.member.bot:
        return

    guild = client.get_guild(GUILD_ID)
    if not guild:
        return

    member = payload.member
    if not member:
        try:
            member = await guild.fetch_member(payload.user_id)
        except:
            return

    role = discord.utils.get(guild.roles, name="m3mbR")
    if not role:
        print("⚠️ Роль m3mbR не найдена!")
        return

    if role in member.roles:
        return

    try:
        await member.add_roles(role, reason="DEGRADECORE верификация")

        channel = client.get_channel(VERIFY_CHANNEL_ID)
        if channel:
            message = await channel.fetch_message(VERIFY_MESSAGE_ID)
            await message.remove_reaction("✅", member)

        log_ch = discord.utils.get(guild.text_channels, name="mod-logs")
        if log_ch:
            embed = discord.Embed(
                title="✅ Верификация",
                description=f"{member.mention} (`{member.name}`) прошёл верификацию.",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            await log_ch.send(embed=embed)

        print(f"✅ {member.name} верифицирован")
    except Exception as e:
        print(f"❌ Ошибка: {e}")


@client.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID or member.bot:
        return
    try:
        embed = discord.Embed(
            title="🛡️ Добро пожаловать в DEGRADECORE",
            description=(
                f"Привет, {member.mention}!\n\n"
                "Чтобы получить доступ к серверу:\n"
                "1. Зайди в канал <#" + str(VERIFY_CHANNEL_ID) + ">\n"
                "2. Нажми на ✅ под закреплённым сообщением\n\n"
                "После этого ты получишь роль и сможешь общаться."
            ),
            color=0x8B0000
        )
        await member.send(embed=embed)
    except:
        pass
    print(f"👤 Новый участник: {member.name}")


client.run(BOT_TOKEN)
