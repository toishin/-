import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os

# ========== 牢屋設定 ==========
GUILD_ID = 1540514292770545746
JOIN_LOG_CHANNEL = 1540519816719237190
LEAVE_LOG_CHANNEL = 1540519875825631384
INVITE_LINK = "https://discord.gg/SB2hn9eV8"

DM_TEXT = f"""😈 逃げようなんて100年早いよ？
おとなしく牢屋に戻りなさい。
何度でも送り続けるからね。

🔗 ここから戻れ：{INVITE_LINK}
"""

TOKENS_FILE = "dm_tokens.txt"

intents = discord.Intents.all()
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)
bot.remove_command("help")

# ========== 管理データ ==========
dm_clients = {}       # {名前: {client, token, alive}}
active_tasks = {}
spam_interval = 2     # 各垢の送信間隔（秒）

# ========== ファイル入出力 ==========
def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        return {}
    tokens = {}
    with open(TOKENS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                name, token = line.split("=", 1)
                tokens[name.strip()] = token.strip()
    return tokens

def save_token_file(name, token):
    tokens = load_tokens()
    tokens[name] = token
    with open(TOKENS_FILE, "w", encoding="utf-8") as f:
        for n, t in tokens.items():
            f.write(f"{n}={t}\n")

def remove_token_file(name):
    tokens = load_tokens()
    if name in tokens:
        del tokens[name]
        with open(TOKENS_FILE, "w", encoding="utf-8") as f:
            for n, t in tokens.items():
                f.write(f"{n}={t}\n")
        return True
    return False

# ========== DM垢接続管理 ==========
async def connect_dm_client(name: str, token: str):
    """DM垢を接続し死活状態を管理"""
    if name in dm_clients:
        try: await dm_clients[name]["client"].close()
        except: pass

    client = discord.Client(intents=discord.Intents.default())
    dm_clients[name] = {"client": client, "token": token, "alive": False}

    @client.event
    async def on_ready():
        dm_clients[name]["alive"] = True
        print(f"🟢 DM垢ログイン成功: {client.user} (@{name})")

    try:
        await client.login(token)
        asyncio.create_task(client.connect())
        await asyncio.sleep(2)
        return dm_clients[name]["alive"]
    except Exception as e:
        dm_clients[name]["alive"] = False
        print(f"🔴 DM垢ログイン失敗 [{name}]: {e}")
        return False

# ========== 🛠 管理コマンド ==========
@bot.command(name="set_token")
async def set_token_cmd(ctx, name: str, token: str):
    """/set_token 名前 トークン → DM垢を追加"""
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ 管理者専用コマンド")
    
    res = await connect_dm_client(name, token)
    save_token_file(name, token)
    if res:
        await ctx.send(f"✅ DM垢「{name}」登録完了！🟢 生きてます")
    else:
        await ctx.send(f"⚠️ DM垢「{name}」登録しましたがログイン不可 🔴 トークン確認")

@bot.command(name="status")
async def status_cmd(ctx):
    """/status → 全DM垢の死活状態を一覧表示"""
    if not dm_clients:
        return await ctx.send("📋 DM垢 未登録")
    
    lines = ["📋 **DM垢 死活一覧**"]
    alive_count = 0
    for name, info in dm_clients.items():
        status = "🟢 生" if info["alive"] else "🔴 死"
        if info["alive"]: alive_count += 1
        try:
            username = info["client"].user or "未ログイン"
        except:
            username = "エラー"
        lines.append(f"{status} **{name}** — {username}")
    
    lines.append(f"\n✅ 生きてる: {alive_count} / 計{len(dm_clients)}")
    await ctx.send("\n".join(lines))

@bot.command(name="remove_dm")
async def remove_dm_cmd(ctx, name: str):
    """/remove_dm 名前 → DM垢を削除"""
    if name in dm_clients:
        try: await dm_clients[name]["client"].close()
        except: pass
        del dm_clients[name]
        remove_token_file(name)
        await ctx.send(f"✅ DM垢「{name}」削除")
    else:
        await ctx.send("❌ その名前は存在しません")

# ========== 😈 同時並行スパム ==========
async def spam_worker(user, client, name):
    """1垢分の送信タスク：永遠に送り続ける"""
    count = 0
    while True:
        # 再接続されてない限りループ
        try:
            await user.send(DM_TEXT)
            count += 1
            print(f"✅ [{name}] → {user.name} ({count}通目)")
        except Exception as e:
            dm_clients[name]["alive"] = False
            print(f"🔴 [{name}] 送信失敗: {type(e).__name__} → 一時停止")
            await asyncio.sleep(5)
            continue

        # 生きてる状態を更新
        if not dm_clients[name]["alive"]:
            dm_clients[name]["alive"] = True

        await asyncio.sleep(spam_interval)

        # 再入室確認
        guild = bot.get_guild(GUILD_ID)
        if guild and guild.get_member(user.id):
            print(f"✅ {user.name} 収容 → 全スパム停止")
            return

async def spam_loop(user_id: int):
    """全垢を同時に起動して並行送信"""
    guild = bot.get_guild(GUILD_ID)
    user = await bot.fetch_user(user_id)
    if not guild or not user:
        return

    # ✅ BAN→即解除
    try:
        await guild.ban(user, reason="脱走試行", delete_message_days=0)
        await asyncio.sleep(0.5)
        await guild.unban(user)
        print(f"⚡ BAN→解除実行: {user.name}")
    except Exception as e:
        print(f"⚠️ BAN/解除エラー: {e}")

    # ✅ ログ通知
    log_ch = bot.get_channel(LEAVE_LOG_CHANNEL)
    alive_list = [n for n, i in dm_clients.items() if i["alive"]]
    if log_ch:
        await log_ch.send(
            f"🚨 **脱走検知 → BAN→解除＋同時スパム起動**\n"
            f"👤 {user.mention} (`{user_id}`)\n"
            f"🟢 生きてる垢: {len(alive_list)}体\n"
            f"📨 同時並行送信中…"
        )

    # ✅ 全垢を同時に起動
    tasks = []
    for name, info in dm_clients.items():
        if info["alive"]:
            t = asyncio.create_task(spam_worker(user, info["client"], name))
            tasks.append(t)
    
    if not tasks:
        if log_ch:
            await log_ch.send("⚠️ **生きてるDM垢が0体です！`/set_token` で追加してください**")
        return

    # ✅ どれか1つが終了（=収容）したら全部止める
    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in tasks:
        t.cancel()

    if log_ch:
        await log_ch.send(f"✅ {user.mention} が収容されました。スパム停止。")


@bot.event
async def on_member_remove(member):
    if member.id in active_tasks:
        return
    task = asyncio.create_task(spam_loop(member.id))
    active_tasks[member.id] = task

@bot.event
async def on_member_join(member):
    """再入室時：スパム停止"""
    if member.id in active_tasks:
        active_tasks.pop(member.id).cancel()

    log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
    alive_count = sum(1 for i in dm_clients.values() if i["alive"])
    if log_ch:
        await log_ch.send(
            f"🔒 **収容** {member.mention}\n"
            f"💀 再脱走時は{alive_count}体同時で迎撃"
        )

# ========== 起動 ==========
@bot.event
async def on_ready():
    saved = load_tokens()
    for name, token in saved.items():
        await connect_dm_client(name, token)
        await asyncio.sleep(1)

    alive_count = sum(1 for i in dm_clients.values() if i["alive"])
    print("="*70)
    print(f"🔒 牢屋Bot起動: {bot.user}")
    print(f"📋 登録: {len(dm_clients)}体 / 🟢生: {alive_count}体")
    print(f"⚡ 脱走時: BAN→解除＋全垢同時スパム")
    print("="*70)
    await bot.change_presence(activity=discord.Game(name=f"😈 {alive_count}体同時 / 脱走即スパム"))


def get_bot_token():
    token = os.getenv("PRISON_BOT_TOKEN")
    if not token: raise RuntimeError("PRISON_BOT_TOKEN 未設定")
    return token


if __name__ == "__main__":
    bot.run(get_bot_token())