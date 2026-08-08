import os
import discord
import datetime
import json
import re
import asyncio
from discord import app_commands
from discord.ext import commands

BOT_TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = int(os.environ["GUILD_ID"])
VERIFY_CHANNEL_ID = int(os.environ["VERIFY_CHANNEL_ID"])
VERIFY_MESSAGE_ID = int(os.environ["VERIFY_MESSAGE_ID"])
GENDER_CHANNEL_ID = int(os.environ.get("GENDER_CHANNEL_ID", 0))
GENDER_MESSAGE_ID = int(os.environ.get("GENDER_MESSAGE_ID", 0))

ECONOMY_FILE = "economy.json"
INVENTORY_FILE = "inventory.json"
VOICE_FILE = "voice_sessions.json"
COINS_PER_HOUR = 25
CUSTOM_ROLE_PRICE = 7000

SHOP_ITEMS = {
    "^^": {"price": 1000, "color": "teal"},
    "***": {"price": 5000, "color": "purple"},
    "toxiclord": {"price": 15000, "color": "orange"},
    "bigboystep": {"price": 3000, "color": "green"},
    "nightcrawler": {"price": 3000, "color": "dark_purple"},
    "voidwalker": {"price": 3000, "color": "cyan"},
}

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

intents = discord.Intents.all()
activity = discord.Activity(type=discord.ActivityType.watching, name="DEGRADECORE")
bot = commands.Bot(command_prefix="!", intents=intents, activity=activity, status=discord.Status.online)
bot.remove_command("help")

WHITE = 0xFFFFFF

class ShopSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for role_name, item in SHOP_ITEMS.items():
            options.append(discord.SelectOption(
                label=role_name,
                description=f"{item['price']} coin",
                value=role_name,
                emoji="🛒"
            ))
        super().__init__(placeholder="Выбери роль", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        role_name = self.values[0]
        item = SHOP_ITEMS[role_name]
        uid = str(interaction.user.id)
        bal = data.economy.get(uid, 0)

        if bal < item["price"]:
            return await interaction.response.send_message(f"У тебя {bal} coin. Нужно {item['price']}. Иди в войс.", ephemeral=True)

        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            return await interaction.response.send_message("Роли нет. Пиши владельцу.", ephemeral=True)
        if role in interaction.user.roles:
            return await interaction.response.send_message("У тебя уже есть эта роль, дебил.", ephemeral=True)

        data.economy[uid] = bal - item["price"]
        data.save_economy()

        if uid not in data.inventory:
            data.inventory[uid] = {"roles": [], "hidden": []}
        if role_name not in data.inventory[uid]["roles"]:
            data.inventory[uid]["roles"].append(role_name)
        data.save_inventory()

        await interaction.user.add_roles(role, reason="Куплено")
        await interaction.response.send_message(f"Купил {role_name} за {item['price']} coin. Баланс: {data.economy[uid]} coin.", ephemeral=True)

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopSelect())

class InventoryButton(discord.ui.Button):
    def __init__(self, role_name, action):
        self.role_name = role_name
        self.action = action
        label = "Показать" if action == "show" else "Скрыть"
        style = discord.ButtonStyle.green if action == "show" else discord.ButtonStyle.red
        super().__init__(label=label, style=style, custom_id=f"inv_{action}_{role_name}")

    async def callback(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        role = discord.utils.get(interaction.guild.roles, name=self.role_name)
        if not role:
            return await interaction.response.send_message("Роли нет.", ephemeral=True)

        inv = data.inventory.get(uid, {"roles": [], "hidden": []})

        if self.action == "hide":
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role, reason="Скрыто")
                if self.role_name not in inv["hidden"]:
                    inv["hidden"].append(self.role_name)
                data.inventory[uid] = inv
                data.save_inventory()
                await interaction.response.send_message(f"{self.role_name} скрыта.", ephemeral=True)
            else:
                await interaction.response.send_message("Уже скрыта.", ephemeral=True)
        else:
            if role not in interaction.user.roles:
                await interaction.user.add_roles(role, reason="Показано")
                if self.role_name in inv["hidden"]:
                    inv["hidden"].remove(self.role_name)
                data.inventory[uid] = inv
                data.save_inventory()
                await interaction.response.send_message(f"{self.role_name} видна.", ephemeral=True)

class CreateRoleModal(discord.ui.Modal, title="Создать роль"):
    role_name = discord.ui.TextInput(label="Название", placeholder="mycoolrole", max_length=32, required=True)
    role_color = discord.ui.TextInput(label="Цвет HEX без #", placeholder="FF5733", max_length=6, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        bal = data.economy.get(uid, 0)

        if bal < CUSTOM_ROLE_PRICE:
            return await interaction.response.send_message(f"Нужно {CUSTOM_ROLE_PRICE} coin, у тебя {bal}. Иди в войс.", ephemeral=True)

        name = str(self.role_name).strip().replace(" ", "").replace("-", "")
        if len(name) < 2 or len(name) > 32:
            return await interaction.response.send_message("От 2 до 32 символов, без пробелов и дефисов.", ephemeral=True)

        color_str = str(self.role_color).strip().replace("#", "")
        try:
            color = discord.Color(int(color_str, 16))
        except:
            return await interaction.response.send_message("Неверный HEX. Пример: FF5733", ephemeral=True)

        existing = discord.utils.get(interaction.guild.roles, name=name)
        if existing:
            return await interaction.response.send_message("Такая роль уже есть.", ephemeral=True)

        try:
            new_role = await interaction.guild.create_role(
                name=name, color=color, hoist=True, mentionable=True,
                permissions=discord.Permissions.none(),
                reason=f"Кастом от {interaction.user.name}"
            )
        except Exception as e:
            return await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

        data.economy[uid] = bal - CUSTOM_ROLE_PRICE
        data.save_economy()

        if uid not in data.inventory:
            data.inventory[uid] = {"roles": [], "hidden": []}
        data.inventory[uid]["roles"].append(name)
        data.save_inventory()

        await interaction.user.add_roles(new_role, reason="Создана")
        await interaction.response.send_message(
            f"Роль {name} создана. Цвет #{color_str}. Стоимость {CUSTOM_ROLE_PRICE} coin. Баланс {data.economy[uid]} coin.",
            ephemeral=True
        )

def is_custom_role(uid, role_name):
    inv = data.inventory.get(uid, {"roles": [], "hidden": []})
    return role_name in inv["roles"] and role_name not in SHOP_ITEMS

@bot.tree.command(name="store", description="Магазин ролей")
async def store_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    embed = discord.Embed(
        title="TOXIC MARKET",
        description=f"Покупай роли. {COINS_PER_HOUR} coin/час в войсах. Своя роль: /createrole {CUSTOM_ROLE_PRICE} coin",
        color=WHITE
    )
    for role_name, item in SHOP_ITEMS.items():
        embed.add_field(name=f"{role_name} — {item['price']} coin", value="⠀", inline=False)
    embed.set_footer(text="Выбери роль ниже")
    await interaction.response.send_message(embed=embed, view=ShopView(), ephemeral=True)

@bot.tree.command(name="inventory", description="Твои роли")
async def inventory_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    inv = data.inventory.get(uid, {"roles": [], "hidden": []})

    if not inv["roles"]:
        return await interaction.response.send_message("У тебя нет ролей. Купи в /store или создай /createrole.", ephemeral=True)

    embed = discord.Embed(title="Инвентарь", color=WHITE)
    embed.description = f"Баланс: {data.economy.get(uid, 0)} coin\n\n"

    view = discord.ui.View(timeout=60)
    for role_name in inv["roles"]:
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        status = "Скрыта" if role_name in inv["hidden"] else "Видна"
        if role:
            embed.description += f"{status} — <@&{role.id}> {role_name}\n"
            if role_name in inv["hidden"]:
                view.add_item(InventoryButton(role_name, "show"))
            else:
                view.add_item(InventoryButton(role_name, "hide"))

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

@bot.tree.command(name="createrole", description="Создать свою роль 7000 coin")
async def createrole_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    await interaction.response.send_modal(CreateRoleModal())

@bot.tree.command(name="rolecolor", description="Сменить цвет своей роли")
@app_commands.describe(role="Твоя роль", color="HEX без #")
async def rolecolor_cmd(interaction: discord.Interaction, role: discord.Role, color: str):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    if not is_custom_role(uid, role.name):
        return await interaction.response.send_message("Это не твоя кастомная роль.", ephemeral=True)
    color_str = color.strip().replace("#", "")
    try:
        new_color = discord.Color(int(color_str, 16))
    except:
        return await interaction.response.send_message("Неверный HEX. Пример: FF5733", ephemeral=True)
    try:
        await role.edit(color=new_color, reason=f"{interaction.user.name}")
        await interaction.response.send_message(f"Цвет {role.name} изменён на #{color_str}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

@bot.tree.command(name="rolename", description="Переименовать свою роль")
@app_commands.describe(role="Твоя роль", name="Новое имя")
async def rolename_cmd(interaction: discord.Interaction, role: discord.Role, name: str):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    if not is_custom_role(uid, role.name):
        return await interaction.response.send_message("Это не твоя кастомная роль.", ephemeral=True)
    new_name = name.strip().replace(" ", "").replace("-", "")
    if len(new_name) < 2 or len(new_name) > 32:
        return await interaction.response.send_message("От 2 до 32 символов.", ephemeral=True)
    existing = discord.utils.get(interaction.guild.roles, name=new_name)
    if existing:
        return await interaction.response.send_message("Такая роль уже есть.", ephemeral=True)
    try:
        old_name = role.name
        await role.edit(name=new_name, reason=f"{interaction.user.name}")
        inv = data.inventory.get(uid, {"roles": [], "hidden": []})
        if old_name in inv["roles"]:
            inv["roles"].remove(old_name)
            inv["roles"].append(new_name)
        if old_name in inv.get("hidden", []):
            inv["hidden"].remove(old_name)
            inv["hidden"].append(new_name)
        data.inventory[uid] = inv
        data.save_inventory()
        await interaction.response.send_message(f"Роль переименована в {new_name}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

@bot.tree.command(name="roleicon", description="Сменить иконку роли")
@app_commands.describe(role="Твоя роль", image="Прикрепи картинку PNG или JPG")
async def roleicon_cmd(interaction: discord.Interaction, role: discord.Role, image: discord.Attachment):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    if not is_custom_role(uid, role.name):
        return await interaction.response.send_message("Это не твоя кастомная роль.", ephemeral=True)
    if not image.content_type or not image.content_type.startswith("image/"):
        return await interaction.response.send_message("Нужна картинка.", ephemeral=True)
    try:
        img_bytes = await image.read()
        await role.edit(icon=img_bytes, reason=f"{interaction.user.name}")
        await interaction.response.send_message(f"Иконка {role.name} обновлена.", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Сервер должен иметь буст 2 уровня для иконок ролей.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

@bot.tree.command(name="roledelete", description="Удалить свою роль")
@app_commands.describe(role="Твоя роль")
async def roledelete_cmd(interaction: discord.Interaction, role: discord.Role):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    if not is_custom_role(uid, role.name):
        return await interaction.response.send_message("Это не твоя кастомная роль.", ephemeral=True)
    try:
        await role.delete(reason=f"{interaction.user.name}")
        inv = data.inventory.get(uid, {"roles": [], "hidden": []})
        if role.name in inv["roles"]:
            inv["roles"].remove(role.name)
        if role.name in inv.get("hidden", []):
            inv["hidden"].remove(role.name)
        data.inventory[uid] = inv
        data.save_inventory()
        await interaction.response.send_message(f"Роль {role.name} удалена.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

@bot.tree.command(name="rolehoist", description="Поднять или опустить роль в списке")
@app_commands.describe(role="Твоя роль")
async def rolehoist_cmd(interaction: discord.Interaction, role: discord.Role):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    if not is_custom_role(uid, role.name):
        return await interaction.response.send_message("Это не твоя кастомная роль.", ephemeral=True)
    try:
        new_hoist = not role.hoist
        await role.edit(hoist=new_hoist, reason=f"{interaction.user.name}")
        status = "поднята" if new_hoist else "опущена"
        await interaction.response.send_message(f"Роль {role.name} {status}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Ошибка: {e}", ephemeral=True)

@bot.tree.command(name="bal", description="Баланс")
async def bal_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(interaction.user.id)
    coins = data.economy.get(uid, 0)
    embed = discord.Embed(title="Баланс", description=f"{coins} coin", color=WHITE)
    embed.set_footer(text=f"{COINS_PER_HOUR} coin/час в войсе")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="top", description="Топ богачей")
async def top_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    if not data.economy:
        return await interaction.response.send_message("Никто ничего не заработал.", ephemeral=True)
    sorted_econ = sorted(data.economy.items(), key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="Топ богачей", color=WHITE)
    for i, (uid_str, coins) in enumerate(sorted_econ, 1):
        user = interaction.guild.get_member(int(uid_str))
        name = user.mention if user else f"ID:{uid_str}"
        embed.add_field(name=f"{i}. {name}", value=f"{coins} coin", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="setupinfo", description="Залить инфу во все каналы только @#!")
@app_commands.checks.has_role("@#!")
async def setupinfo_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    await interaction.response.defer(ephemeral=True)

    channels_info = {
        "sacred-scrolls": {
            "title": "ПРАВИЛА DEGRADECORE",
            "desc": (
                "Здесь анархия. Делай что хочешь.\n\n"
                "Запрещено только:\n"
                "1. Докс\n"
                "2. Угрозы IRL\n"
                "3. CP\n"
                "4. Спам рекламой\n"
                "5. Фишинг\n"
                "6. Обход банов\n\n"
                "Всё остальное разрешено. Тролль, токси, оскорбляй — пока не забанят.\n\n"
                f"Экономика: {COINS_PER_HOUR} coin/час в войсе. Покупай роли в /store. Своя роль: /createrole {CUSTOM_ROLE_PRICE} coin"
            )
        },
        "echo-chamber": {"title": "НОВОСТИ", "desc": "Официальные объявления. Писать только @#!."},
        "role-ritual": {"title": "РОЛИ", "desc": "Дополнительные роли через реакции."},
        "verify-gate": {"title": "ВЕРИФИКАЦИЯ", "desc": "Нажми ✅. Получишь m3mbR + boy и доступ к серверу."},
        "gendercheck": {"title": "ПРОВЕРКА", "desc": "Девушки — жми 🔔. Модер проверит и выдаст girl."},
        "snitchguide": {"title": "ГАЙД", "desc": "Кратко:\n• Правила в sacred-scrolls\n• Монеты в войсах\n• Роли в /store\n• Общий чат void-chatter\n• Троллинг норма, без докса и угроз IRL"},
        "void-chatter": {"title": "ОБЩИЙ ЧАТ", "desc": "Говори что хочешь. Тролль кого хочешь."},
        "meme-dimension": {"title": "МЕМЫ", "desc": "Мемы и медиа. Загрузка только @#!."},
        "offtopic-abyss": {"title": "ОФФТОП", "desc": "Любые темы. Полный хаос."},
        "bot-commands": {"title": "СТОРОННИЕ БОТЫ", "desc": "Команды других ботов."},
        "commandline": {"title": "КОМАНДЫ БОТА", "desc": "/store — магазин\n/inventory — роли\n/createrole — создать роль\n/rolecolor — цвет\n/rolename — переименовать\n/roleicon — иконка\n/rolehoist — поднять/опустить\n/roledelete — удалить\n/bal — баланс\n/top — топ"},
        "toxic-market": {"title": "TOXIC MARKET", "desc": f"Магазин ролей. {COINS_PER_HOUR} coin/час в войсах. Используй /store."},
        "star-vault": {"title": "ЭЛИТНЫЙ ЧАТ", "desc": "Закрытый чат для ***. Только избранные."},
        "mod-logs": {"title": "ЛОГИ", "desc": "Журнал действий."},
        "mod-chat": {"title": "МОД-ЧАТ", "desc": "Чат для модерации."},
    }

    sent = 0
    for ch_name, info in channels_info.items():
        ch = discord.utils.get(interaction.guild.text_channels, name=ch_name)
        if ch:
            embed = discord.Embed(title=info["title"], description=info["desc"], color=WHITE)
            embed.set_footer(text="DEGRADECORE")
            try:
                await ch.send(embed=embed)
                sent += 1
            except:
                pass
    await interaction.followup.send(f"Инфа залита в {sent} каналов.", ephemeral=True)

@bot.tree.command(name="givecoins", description="Выдать монеты только @#!")
@app_commands.checks.has_role("@#!")
@app_commands.describe(member="Кому", amount="Сколько")
async def givecoins_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild.id != GUILD_ID:
        return
    if amount <= 0:
        return await interaction.response.send_message("Сумма положительная.", ephemeral=True)
    uid = str(member.id)
    data.economy[uid] = data.economy.get(uid, 0) + amount
    data.save_economy()
    await interaction.response.send_message(f"Выдано {amount} coin {member.mention}. Баланс: {data.economy[uid]} coin.", ephemeral=True)

@bot.tree.command(name="takecoins", description="Забрать монеты только @#!")
@app_commands.checks.has_role("@#!")
@app_commands.describe(member="У кого", amount="Сколько")
async def takecoins_cmd(interaction: discord.Interaction, member: discord.Member, amount: int):
    if interaction.guild.id != GUILD_ID:
        return
    uid = str(member.id)
    current = data.economy.get(uid, 0)
    new_bal = max(0, current - amount)
    data.economy[uid] = new_bal
    data.save_economy()
    await interaction.response.send_message(f"Снято {amount} coin у {member.mention}. Баланс: {new_bal} coin.", ephemeral=True)

@bot.tree.command(name="closevoice", description="Удалить временный войс только %&")
@app_commands.checks.has_any_role("%&", "@#!")
async def closevoice_cmd(interaction: discord.Interaction):
    if interaction.guild.id != GUILD_ID:
        return
    for ch in interaction.guild.voice_channels:
        if ch.name.startswith("gender-check-") or ch.name.startswith("verify-"):
            try:
                await ch.delete(reason="Проверка завершена")
                return await interaction.response.send_message("Временный канал удалён.", ephemeral=True)
            except:
                pass
    await interaction.response.send_message("Временный канал не найден.", ephemeral=True)

async def delete_temp_voice_after(channel, delay):
    await asyncio.sleep(delay)
    try:
        await channel.delete(reason="Время вышло")
    except:
        pass

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Бот {bot.user} онлайн.")
    print(f"Сервер: {GUILD_ID}")
    print(f"Verify: {VERIFY_CHANNEL_ID}/{VERIFY_MESSAGE_ID}")
    print(f"Gender: {GENDER_CHANNEL_ID}/{GENDER_MESSAGE_ID}")
    print(f"{COINS_PER_HOUR} coin/час | Кастом: {CUSTOM_ROLE_PRICE} coin")
    print("DEGRADECORE активен.")

@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID or member.bot:
        return
    try:
        embed = discord.Embed(
            title="Добро пожаловать в DEGRADECORE",
            description=(
                f"{member.mention}\n\n"
                f"1. Жми ✅ в <#{VERIFY_CHANNEL_ID}>\n"
                "2. Девушки — жми 🔔 в gendercheck\n\n"
                f"{COINS_PER_HOUR} coin/час в войсах."
            ),
            color=WHITE
        )
        await member.send(embed=embed)
    except:
        pass

@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    # VERIFY GATE
    if payload.channel_id == VERIFY_CHANNEL_ID and payload.message_id == VERIFY_MESSAGE_ID and str(payload.emoji) == "✅":
        try:
            member = payload.member
            if not member:
                try:
                    member = await guild.fetch_member(payload.user_id)
                except Exception as e:
                    print(f"VERIFY: не удалось получить member {payload.user_id}: {e}")
                    return
            if not member:
                return

            boy_role = discord.utils.get(guild.roles, name="boy")
            member_role = discord.utils.get(guild.roles, name="m3mbR")

            if boy_role and boy_role not in member.roles:
                await member.add_roles(boy_role, reason="Вериф")
                print(f"VERIFY: выдана boy {member.name}")
            if member_role and member_role not in member.roles:
                await member.add_roles(member_role, reason="Вериф")
                print(f"VERIFY: выдана m3mbR {member.name}")

            channel = bot.get_channel(VERIFY_CHANNEL_ID)
            if channel:
                try:
                    msg = await channel.fetch_message(VERIFY_MESSAGE_ID)
                    await msg.remove_reaction("✅", member)
                except Exception as e:
                    print(f"VERIFY: не удалось удалить реакцию: {e}")

            log_ch = discord.utils.get(guild.text_channels, name="mod-logs")
            if log_ch:
                await log_ch.send(f"{member.mention} верифицирован.")
            print(f"VERIFY: {member.name} верифицирован")
        except Exception as e:
            print(f"VERIFY ERROR: {e}")

    # GENDERCHECK
    elif payload.channel_id == GENDER_CHANNEL_ID and payload.message_id == GENDER_MESSAGE_ID and str(payload.emoji) == "🔔":
        try:
            member = payload.member
            if not member:
                try:
                    member = await guild.fetch_member(payload.user_id)
                except Exception as e:
                    print(f"GENDER: не удалось получить member {payload.user_id}: {e}")
                    return
            if not member:
                return

            girl_role = discord.utils.get(guild.roles, name="girl")
            if girl_role and girl_role in member.roles:
                return

            channel = bot.get_channel(GENDER_CHANNEL_ID)
            if channel:
                try:
                    msg = await channel.fetch_message(GENDER_MESSAGE_ID)
                    await msg.remove_reaction("🔔", member)
                except Exception as e:
                    print(f"GENDER: не удалось удалить реакцию: {e}")

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

            temp_ch = await guild.create_voice_channel(
                name=f"gender-check-{member.name[:10]}",
                category=mod_cat,
                overwrites=overwrites,
                reason=f"Проверка {member.name}"
            )

            invite = await temp_ch.create_invite(max_age=600, max_uses=5, reason="Проверка")

            ping = f"<@&{mod_role.id}>" if mod_role else "@here"
            await channel.send(
                f"{ping}\n"
                f"{member.mention} запросил проверку.\n"
                f"Канал: {invite.url}\n"
                f"Удалится через 10 минут."
            )

            asyncio.create_task(delete_temp_voice_after(temp_ch, 600))

        except Exception as e:
            print(f"GENDER ERROR: {e}")
            try:
                ch = bot.get_channel(GENDER_CHANNEL_ID)
                if ch:
                    await ch.send(f"Ошибка проверки: {e}")
            except:
                pass

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
                print(f"{member.name} +{coins} coin ({hours:.2f}ч)")
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
            await message.channel.send(f"{message.author.mention} ссылки запрещены. Только @#!.", delete_after=5)
        except:
            pass
        return

    if message.attachments:
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention} файлы запрещены. Только @#!.", delete_after=5)
        except:
            pass
        return

    await bot.process_commands(message)

if __name__ == "__main__":
    if not BOT_TOKEN or BOT_TOKEN == "ВСТАВЬ_ТОКЕН_БОТА_СЮДА":
        print("BOT_TOKEN не задан!")
    elif GUILD_ID == 1234567890123456789:
        print("GUILD_ID не задан!")
    elif VERIFY_CHANNEL_ID == 1234567890123456789:
        print("VERIFY_CHANNEL_ID не задан!")
    else:
        print("Запуск DEGRADECORE...")
        bot.run(BOT_TOKEN)
