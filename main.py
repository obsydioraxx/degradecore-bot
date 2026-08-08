import os
import discord
import datetime
import json
import re
import asyncio
from discord import app_commands
from discord.ext import commands

# ═══════════════════════════════════════════════
# ENVIRONMENT
# ═══════════════════════════════════════════════
BOT_TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
VERIFY_CHANNEL_ID = int(os.environ["VERIFY_CHANNEL_ID"])
VERIFY_MESSAGE_ID = int(os.environ["VERIFY_MESSAGE_ID"])
GENDER_CHANNEL_ID = int(os.environ.get("GENDER_CHANNEL_ID", 0))
GENDER_MESSAGE_ID = int(os.environ.get("GENDER_MESSAGE_ID", 0))

# ═══════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════
ECONOMY_FILE = "economy.json"
INVENTORY_FILE = "inventory.json"
VOICE_FILE = "voice_sessions.json"
COINS_PER_HOUR = 25
CUSTOM_ROLE_PRICE = 7000

SHOP_ITEMS = {
    "^^": {"price": 1000, "description": "VIP — проверенный тролль. Особый статус.", "color": "teal"},
    "***": {"price": 5000, "description": "Элита — доступ к закрытым каналам и войсам.", "color": "purple"},
    "toxiclord": {"price": 15000, "description": "Toxic Lord — вершина иерархии троллей.", "color": "orange"},
    "bigboystep": {"price": 3000, "description": "Big Boy Step — косметическая роль для стиля.", "color": "green"},
    "nightcrawler": {"price": 3000, "description": "Night Crawler — косметическая роль для стиля.", "color": "dark_purple"},
    "voidwalker": {"price": 3000, "description": "Void Walker — косметическая роль для стиля.", "color": "cyan"},
}

# ═══════════════════════════════════════════════
# DATA MANAGER
# ═══════════════════════════════════════════════
class DataManager:
    def __init__(self):
        self.economy = self._load(ECONOMY_FILE)
        self.inventory = self._load(INVENTORY_FILE)
        self.voice_sessions = self._load(VOICE_FILE)

    def _load(self, file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return {}

    def save_economy(self):
        with open(ECONOMY_FILE, "w") as f:
            json.dump(self.economy, f, indent=2)

    def save_inventory(self):
        with open(INVENTORY_FILE, "w") as f:
            json.dump(self.inventory, f, indent=2)

    def save_voice(self):
        with open(VOICE_FILE, "w") as f:
            json.dump(self.voice_sessions, f, indent=2)

data = DataManager()

# ═══════════════════════════════════════════════
# BOT SETUP
# ═══════════════════════════════════════════════
intents = discord.Intents.all()
activity = discord.Activity(type=discord.ActivityType.watching, name="DEGRADECORE")
bot = commands.Bot(command_prefix="!", intents=intents, activity=activity, status=discord.Status.online)
bot.remove_command("help")

# ═══════════════════════════════════════════════
# VIEWS & UI
# ═══════════════════════════════════════════════

class ShopSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for role_name, item in SHOP_ITEMS.items():
            options.append(discord.SelectOption(
                label=role_name,
                description=f"{item['price']}🪙 — {item['description'][:50]}",
                value=role_name,
                emoji="🛒"
            ))
        super().__init__(placeholder="Выбери роль для покупки...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        role_name = self.values[0]
        item = SHOP_ITEMS[role_name]
        uid = str(interaction.user.id)
        bal = data.economy.get(uid, 0)

        if bal < item["price"]:
            return await interaction.response.send_message(f"❌ Недостаточно монет. У тебя **{bal}**🪙, нужно **{item['price']}**🪙.", ephemeral=True)

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            return await interaction.response.send_message("❌ Роль не найдена на сервере.", ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message("❌ У тебя уже есть эта роль.", ephemeral=True)

        data.economy[uid] = bal - item["price"]
        data.save_economy()

        if uid not in data.inventory:
            data.inventory[uid] = {"roles": [], "hidden": []}
        if role_name not in data.inventory[uid]["roles"]:
            data.inventory[uid]["roles"].append(role_name)
        data.save_inventory()

        await interaction.user.add_roles(role, reason="Куплено в Toxic Market")
        await interaction.response.send_message(f"✅ Ты купил роль **{role_name}** за {item['price']}🪙! Баланс: **{data.economy[uid]}**🪙.", ephemeral=True)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopSelect())

class InventoryButton(discord.ui.Button):
    def __init__(self, role_name, action):
        self.role_name = role_name
        self.action = action
        label = "👁️ Показать" if action == "show" else "🙈 Скрыть"
        style = discord.ButtonStyle.green if action == "show" else discord.ButtonStyle.red
        super().__init__(label=label, style=style, custom_id=f"inv_{action}_{role_name}")

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if not role:
            return await interaction.response.send_message("❌ Роль не найдена.", ephemeral=True)

        inv = data.inventory.get(uid, {"roles": [], "hidden": []})

        if self.action == "hide":
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Скрыто через инвентарь")
                if self.role_name not in inv["hidden"]:
                    inv["hidden"].append(self.role_name)
                data.inventory[uid] = inv
                data.save_inventory()
                await interaction.response.send_message(f"🙈 Роль **{self.role_name}** скрыта.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Роль уже скрыта.", ephemeral=True)
        else:
            if role not in interaction.user.roles:
                await interaction.user.add_roles(role, reason="Показано через инвентарь")
                if self.role_name in inv["hidden"]:
                    inv["hidden"].remove(self.role_name)
                data.inventory[uid] = inv
                data.save_inventory()
                await interaction.response.send_message(f"👁️ Роль **{self.role_name}** показана.", ephemeral=True)

class CreateRoleModal(discord.ui.Modal, title="Создать свою роль"):
    role_name = discord.ui.TextInput(label="Название роли", placeholder="mycoolrole", max_length=32, required=True)
    role_color = discord.ui.TextInput(label="Цвет (hex, без #)", placeholder="FF5733", max_length=6, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        bal = data.economy.get(uid, 0)

        if bal < CUSTOM_ROLE_PRICE:
            return await interaction.response.send_message(f"❌ Недостаточно монет. Нужно **{CUSTOM_ROLE_PRICE}**🪙, у тебя **{bal}**🪙.", ephemeral=True)

        name = str(self.role_name).strip().replace(" ", "").replace("-", "")
        if len(name) < 2 or len(name) > 32:
            return await interaction.response.send_message("❌ Название должно быть от 2 до 32 символов (без пробелов и дефисов).", ephemeral=True)

        color_str = str(self.role_color).strip().replace("#", "")
        try:
            color = discord.Color(int(color_str, 16))
        except:
            return await interaction.response.send_message("❌ Неверный формат цвета. Пример: FF5733", ephemeral=True)

        existing = discord.utils.get(interaction.guild.roles, name=name)
        if existing:
            return await interaction.response.send_message("❌ Роль с таким названием уже существует.", ephemeral=True)

        try:
            new_role = await interaction.guild.create_role(
                name=name, color=color, hoist=True, mentionable=True,
                permissions=discord.Permissions.none(),
                reason=f"Кастомная роль от {interaction.user.name}"
            )
        except Exception as e:
            return await interaction.response.send_message(f"❌ Ошибка создания роли: {e}", ephemeral=True)

        data.economy[uid] = bal - CUSTOM_ROLE_PRICE
        data.save_economy()

        if uid not in data.inventory:
            data.inventory[uid] = {"roles": [], "hidden": []}
        data.inventory[uid]["roles"].append(name)
        data.save_inventory()

        await interaction.user.add_roles(new_role, reason="Создана через /createrole")
        await interaction.response.send_message(
            f"✅ Роль **{name}** создана! Цвет: `#{color_str}`. Стоимость: **{CUSTOM_ROLE_PRICE}**🪙. Баланс: **{data.economy[uid]}**🪙.",
            ephemeral=True
        )

# ═══════════════════════════════════════════════
# SLASH COMMANDS
# ═══════════════════════════════════════════════

@bot.tree.command(name="store", description="🛒 Магазин ролей")
async def store_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    embed = discord.Embed(
        title="🛒 TOXIC MARKET",
        description=f"Покупай роли за монеты. Зарабатывай **{COINS_PER_HOUR}🪙/час** в голосовых каналах.\n\nСоздай свою роль: `/createrole` (**{CUSTOM_ROLE_PRICE}**🪙)",
        color=0x8B0000
    )
    for role_name, item in SHOP_ITEMS.items():
        embed.add_field(name=f"`{role_name}` — {item['price']}🪙", value=item["description"], inline=False)
    embed.set_footer(text="Выбери роль из меню ниже ↓")
    await interaction.response.send_message(embed=embed, view=ShopView(), ephemeral=True)

@bot.tree.command(name="inventory", description="🎒 Твои роли")
async def inventory_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    inv = data.inventory.get(uid, {"roles": [], "hidden": []})

    if not inv["roles"]:
        return await interaction.response.send_message("🎒 У тебя пока нет ролей. Купи в `/store` или создай `/createrole`.", ephemeral=True)

    embed = discord.Embed(title="🎒 Инвентарь ролей", color=0x8B0000)
    embed.description = f"Баланс: **{data.economy.get(uid, 0)}**🪙\n\n"

    view = discord.ui.View(timeout=60)
    for role_name in inv["roles"]:
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        status = "🙈 Скрыта" if role_name in inv["hidden"] else "👁️ Видна"
        if role:
            embed.description += f"{status} — <@&{role.id}> (`{role_name}`)\n"
            if role_name in inv["hidden"]:
                view.add_item(InventoryButton(role_name, "show"))
            else:
                view.add_item(InventoryButton(role_name, "hide"))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="createrole", description="✨ Создать свою кастомную роль (7000🪙)")
async def createrole_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    await interaction.response.send_modal(CreateRoleModal())

@bot.tree.command(name="bal", description="💰 Проверить баланс")
async def bal_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    coins = data.economy.get(uid, 0)
    embed = discord.Embed(title="💰 Баланс", description=f"**{coins}**🪙", color=0xFFD700)
    embed.set_footer(text=f"Зарабатывай {COINS_PER_HOUR}🪙/час в голосовом канале.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="top", description="🏆 Топ богачей")
async def top_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    if not data.economy:
        return await interaction.response.send_message("📊 Пока никто не заработал монет.", ephemeral=True)
    sorted_econ = sorted(data.economy.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Топ богачей DEGRADECORE", color=0xFFD700)
    for i, (uid_str, coins) in enumerate(sorted_econ, 1):
        user = interaction.guild.get_member(int(uid_str))
        name = user.mention if user else f"`ID:{uid_str}`"
        embed.add_field(name=f"{i}. {name}", value=f"{coins}🪙", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setupinfo", description="📋 Отправить инфо во все каналы (только @#!)")
@app_commands.checks.has_role("@#!")
async def setupinfo_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    await interaction.response.defer(ephemeral=True)

    channels_info = {
        "sacred-scrolls": {
            "title": "📜 ПРАВИЛА DEGRADECORE",
            "desc": (
                "**Это не обычный сервер. Это локалка интернет-троллей.**\n\n"
                "📌 **Концепт:**\n"
                "• Здесь можно обзываться, троллить, токсить\n"
                "• Любой троллинг / токсичность НЕ модерируется\n"
                "• Свобода слова в полном объеме\n\n"
                "⚠️ **Запрещено (это не троллинг, это преступление):**\n"
                "1. Доксинг (распространение личных данных)\n"
                "2. Слив личной информации без согласия\n"
                "3. Угрозы реальной жизни / насилие IRL\n"
                "4. CP / любой контент с участием несовершеннолетних\n"
                "5. Реклама сторонних серверов / спам\n"
                "6. Фишинг / скам ссылки\n"
                "7. Обход банов через альты\n"
                "8. Взлом аккаунтов / социнженерия\n\n"
                f"💰 **Экономика:**\n"
                f"• {COINS_PER_HOUR}🪙 = 1 час в голосовом канале\n"
                "• Покупай роли в </store:0>\n"
                "• Создай свою роль: </createrole:0> (7000🪙)\n\n"
                "🔒 **Ограничения:**\n"
                "• Ссылки и изображения может постить только @#!\n"
                "• Остальные — текстовые сообщения"
            )
        },
        "echo-chamber": {"title": "📢 НОВОСТИ", "desc": "Официальные объявления. Писать может только `@#!`."},
        "role-ritual": {"title": "🎭 РОЛИ", "desc": "Дополнительные роли через реакции (если настроено)."},
        "verify-gate": {"title": "🛡️ ВЕРИФИКАЦИЯ", "desc": "Нажми ✅ чтобы получить роли `m3mbR` + `boy` и доступ к серверу."},
        "gendercheck": {"title": "🔔 ПРОВЕРКА ГЕНДЕРА", "desc": "Девушки — нажми 🔔. Модератор проверит и выдаст роль `girl`."},
        "snitchguide": {"title": "📖 ГАЙД ДЛЯ НОВИЧКОВ", "desc": "Полный обзор сервера: что где, зачем и как тут общаться.\n\n**Кратко:**\n• Прочитай правила в <#sacred-scrolls>\n• Зарабатывай монеты в голосовых каналах\n• Покупай роли в </store:0>\n• Общайся в <#void-chatter>\n• Троллинг — норма, но без докса и угроз IRL"},
        "void-chatter": {"title": "💬 ОБЩИЙ ЧАТ", "desc": "Говори что угодно. Тролль кого угодно. Токсичность — норма."},
        "meme-dimension": {"title": "🖼️ МЕМЫ", "desc": "Мемы и медиа. Загрузка файлов только для `@#!`."},
        "offtopic-abyss": {"title": "🌀 ОФФТОП", "desc": "Любые темы вне контекста. Полный хаос приветствуется."},
        "bot-commands": {"title": "🤖 СТОРОННИЕ БОТЫ", "desc": "Команды других ботов."},
        "commandline": {"title": "⌨️ КОМАНДЫ DEGRADECORE", "desc": "Используй slash-команды:\n</store:0> — магазин\n</inventory:0> — твои роли\n</createrole:0> — создать роль\n</bal:0> — баланс\n</top:0> — топ богачей"},
        "toxic-market": {"title": "🛒 TOXIC MARKET", "desc": f"Магазин ролей. Зарабатывай **{COINS_PER_HOUR}🪙/час** в голосовых каналах. Используй </store:0>."},
        "star-vault": {"title": "🔒 ЭЛИТНЫЙ ЧАТ", "desc": "Закрытый чат для роли `***`. Только для избранных троллей."},
        "mod-logs": {"title": "🛡️ ЛОГИ", "desc": "Журнал действий модераторов и бота."},
        "mod-chat": {"title": "🛡️ МОД-ЧАТ", "desc": "Чат для команды модерации."},
        "reports": {"title": "📩 ЖАЛОБЫ", "desc": "Если кто-то вышел за рамки (докс, угрозы IRL) — пиши сюда."},
    }

    sent = 0
    for ch_name, info in channels_info.items():
        ch = discord.utils.get(interaction.guild.text_channels, name=ch_name)
        if ch:
            embed = discord.Embed(title=info["title"], description=info["desc"], color=0x8B0000)
            embed.set_footer(text="DEGRADECORE | Автоматическое сообщение")
            try:
                await ch.send(embed=embed)
                sent += 1
            except:
                pass
    await interaction.followup.send(f"✅ Информация отправлена в **{sent}** каналов.", ephemeral=True)

@bot.tree.command(name="givecoins", description="💰 Выдать монеты (только @#!)")
@app_commands.checks.has_role("@#!")
@app_commands.describe(member="Кому выдать", amount="Сколько")
async def givecoins_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild.id != GUILD_ID:
        return
    if amount <= 0:
        return await interaction.response.send_message("❌ Сумма должна быть положительной.", ephemeral=True)
    uid = str(member.id)
    data.economy[uid] = data.economy.get(uid, 0) + amount
    data.save_economy()
    await interaction.response.send_message(f"✅ Выдано **{amount}**🪙 {member.mention}. Баланс: **{data.economy[uid]}**🪙.", ephemeral=True)

@bot.tree.command(name="takecoins", description="💰 Забрать монеты (только @#!)")
@app_commands.checks.has_role("@#!")
@app_commands.describe(member="У кого забрать", amount="Сколько")
async def takecoins_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(member.id)
    current = data.economy.get(uid, 0)
    new_bal = max(0, current - amount)
    data.economy[uid] = new_bal
    data.save_economy()
    await interaction.response.send_message(f"✅ Снято **{amount}**🪙 у {member.mention}. Баланс: **{new_bal}**🪙.", ephemeral=True)

@bot.tree.command(name="closevoice", description="🔒 Закрыть временный войс проверки (только %&)")
@app_commands.checks.has_any_role("%&", "@#!")
async def closevoice_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    for ch in interaction.guild.voice_channels:
        if ch.name.startswith("gender-check-") or ch.name.startswith("verify-"):
            try:
                await ch.delete(reason="Проверка завершена")
                return await interaction.response.send_message("✅ Временный голосовой канал удалён.", ephemeral=True)
            except:
                pass
    await interaction.response.send_message("❌ Временный голосовой канал не найден.", ephemeral=True)

# ═══════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Бот {bot.user} запущен на Railway и работает 24/7!")
    print(f"🎯 Сервер: {GUILD_ID}")
    print(f"🛡️ Verify: {VERIFY_CHANNEL_ID}/{VERIFY_MESSAGE_ID}")
    print(f"🔔 Gender: {GENDER_CHANNEL_ID}/{GENDER_MESSAGE_ID}")
    print(f"💰 {COINS_PER_HOUR}🪙/час | Кастом роль: {CUSTOM_ROLE_PRICE}🪙")
    print("💀 DEGRADECORE Advanced Bot активен.")

@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID or member.bot:
        return
    try:
        embed = discord.Embed(
            title="🛡️ Добро пожаловать в DEGRADECORE",
            description=(
                f"Привет, {member.mention}!\n\n"
                "Чтобы получить доступ:\n"
                f"1. Зайди в <#{VERIFY_CHANNEL_ID}> и нажми ✅\n"
                "2. (Девушки) Зайди в <#gendercheck> и нажми 🔔\n\n"
                f"💰 Зарабатывай {COINS_PER_HOUR}🪙/час в войсах!"
            ),
            color=0x8B0000
        )
        await member.send(embed=embed)
    except:
        pass

@bot.event
async def on_raw_reaction_add(payload):
    if payload.member and payload.member.bot:
        return
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    # VERIFY GATE — ✅ = boy + m3mbR
    if payload.channel_id == VERIFY_CHANNEL_ID and payload.message_id == VERIFY_MESSAGE_ID and str(payload.emoji) == "✅":
        member = payload.member or await guild.fetch_member(payload.user_id)
        if not member:
            return

        boy_role = discord.utils.get(guild.roles, name="boy")
        member_role = discord.utils.get(guild.roles, name="m3mbR")

        if boy_role and boy_role not in member.roles:
            await member.add_roles(boy_role, reason="Верификация")
        if member_role and member_role not in member.roles:
            await member.add_roles(member_role, reason="Верификация")

        channel = bot.get_channel(VERIFY_CHANNEL_ID)
        if channel:
            msg = await channel.fetch_message(VERIFY_MESSAGE_ID)
            await msg.remove_reaction("✅", member)

        log_ch = discord.utils.get(guild.text_channels, name="mod-logs")
        if log_ch:
            await log_ch.send(f"✅ {member.mention} (`{member.name}`) верифицирован.")
        print(f"✅ {member.name} верифицирован (boy + m3mbR)")

    # GENDERCHECK — 🔔 = create temp voice + ping mods
    elif payload.channel_id == GENDER_CHANNEL_ID and payload.message_id == GENDER_MESSAGE_ID and str(payload.emoji) == "🔔":
        member = payload.member or await guild.fetch_member(payload.user_id)
        if not member:
            return

        girl_role = discord.utils.get(guild.roles, name="girl")
        if girl_role and girl_role in member.roles:
            return

        channel = bot.get_channel(GENDER_CHANNEL_ID)
        if channel:
            msg = await channel.fetch_message(GENDER_MESSAGE_ID)
            await msg.remove_reaction("🔔", member)

        mod_cat = discord.utils.get(guild.categories, name="MODERATION")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
        }
        mod_role = discord.utils.get(guild.roles, name="%&")
        owner_role = discord.utils.get(guild.roles, name="@#!")
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, move_members=True)
        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, move_members=True)

        try:
            temp_ch = await guild.create_voice_channel(
                name=f"gender-check-{member.name[:10]}",
                category=mod_cat,
                overwrites=overwrites,
                reason=f"Проверка гендера для {member.name}"
            )

            invite = await temp_ch.create_invite(max_age=600, max_uses=5, reason="Проверка гендера")

            ping = f"<@&{mod_role.id}>" if mod_role else "@here"
            await channel.send(
                f"🔔 {ping}\n"
                f"Пользователь {member.mention} запросил проверку гендера.\n"
                f"🔗 Временный канал: {invite.url}\n"
                f"⏳ Канал удалится через 10 минут автоматически."
            )

            await asyncio.sleep(600)
            try:
                await temp_ch.delete(reason="Время проверки истекло")
            except:
                pass

        except Exception as e:
            await channel.send(f"❌ Ошибка создания канала: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot or member.guild.id != GUILD_ID:
        return
    uid = str(member.id)
    now = datetime.datetime.utcnow().timestamp()

    if before.channel is None and after.channel is not None:
        data.voice_sessions[uid] = now
        data.save_voice()
    elif before.channel is not None and after.channel is None:
        join_time = data.voice_sessions.pop(uid, None)
        if join_time:
            hours = (now - join_time) / 3600
            coins = int(hours * COINS_PER_HOUR)
            if coins > 0:
                data.economy[uid] = data.economy.get(uid, 0) + coins
                data.save_economy()
                print(f"💰 {member.name} +{coins}🪙 ({hours:.2f}ч)")
    elif before.channel is not None and after.channel is not None and before.channel != after.channel:
        join_time = data.voice_sessions.pop(uid, None)
        if join_time:
            hours = (now - join_time) / 3600
            coins = int(hours * COINS_PER_HOUR)
            if coins > 0:
                data.economy[uid] = data.economy.get(uid, 0) + coins
                data.save_economy()
        data.voice_sessions[uid] = now
        data.save_voice()

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or message.guild.id != GUILD_ID:
        await bot.process_commands(message)
        return

    owner_role = discord.utils.get(message.guild.roles, name="@#!")
    if owner_role and owner_role in message.author.roles:
        await bot.process_commands(message)
        return

    link_pattern = re.compile(r'http[s]?://|www\.|discord\.gg|discord\.com/invite|t\.me|youtube\.com/watch|youtu\.be', re.IGNORECASE)
    if link_pattern.search(message.content):
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} ссылки запрещены. Только @#! может постить ссылки.", delete_after=5)
        except:
            pass
        return

    if message.attachments:
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} изображения и файлы запрещены. Только @#! может загружать вложения.", delete_after=5)
        except:
            pass
        return

    await bot.process_commands(message)

# ═══════════════════════════════════════════════
# START
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_БОТА_СЮДА":
        print("❌ BOT_TOKEN не задан!")
    elif GUILD_ID == 1234567890123456789:
        print("❌ GUILD_ID не задан!")
    elif VERIFY_CHANNEL_ID == 1234567890123456789:
        print("❌ VERIFY_CHANNEL_ID не задан!")
    else:
        print("🚀 Запуск DEGRADECORE v3...")
        bot.run(BOT_TOKEN)
