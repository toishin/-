import discord
from discord.ext import commands
import asyncio
import os
import re

# ========== 牢屋設定 ==========
JOIN_LOG_CHANNEL = 1540519816719237190
LEAVE_LOG_CHANNEL = 1540519875825631384
INVITE_LINK = "https://discord.gg/SB2hn9eV8"

DM_TEXT = f"""逃げれると思った？www😂
牢屋に戻らない限りスパムするチー！🤓
やめて欲しかったらさっさと牢屋に入れチー！

🔗 ここから戻れ：{INVITE_LINK}
"""

TOKENS_FILE = "dm_tokens.txt"

intents = discord.Intents.all()
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)
bot.remove_command("help")

# ========== 管理データ ==========
dm_clients = {}
active_tasks = {}
spam_interval = 2

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

# ✅ 【究極版】自分にだけ見えるフォームで安全に一括登録
@bot.command(name="add_tokens")
async def add_tokens_cmd(ctx):
    """✅ /add_tokens → 自分にだけ見えるフォームで一括登録"""
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ 管理者専用", ephemeral=True)

    # ✅ 「自分にだけ見える」フォームメッセージを送信
    embed = discord.Embed(
        title="📋 DMトークン 一括登録フォーム",
        description="このメッセージに**返信する形**でトークンを貼り付けてください\n"
                    "⚠️ この表示は**あなたにしか見えません**",
        color=0x2F3136
    )
    embed.add_field(
        name="✅ 入力形式（どれでも自動判別）",
        value="```\n"
              "【改行】1行1トークン\n"
              "token1\n"
              "token2\n\n"
              "【カンマ】token1,token2,token3\n"
              "【スペース】token1 token2 token3\n"
              "```",
        inline=False
    )
    embed.set_footer(text="⏱ 3分以内に返信してください")

    await ctx.send(embed=embed, ephemeral=True)  # ← 本人にだけ表示！

    # 返信を待機（同じ人・同じチャンネル）
    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel

    try:
        reply = await bot.wait_for("message", check=check, timeout=180.0)
    except asyncio.TimeoutError:
        await ctx.send("⏱ タイムアウト。再実行してください", ephemeral=True)
        return

    # トークン抽出
    raw_list = re.split(r"[\n, 　]+", reply.content.strip())
    token_list = [t.strip() for t in raw_list if t.strip()]

    if not token_list:
        return await ctx.send("❌ トークンが検出されません", ephemeral=True)

    # 登録処理中メッセージ
    status_msg = await ctx.send(f"🔍 {len(token_list)}件を検知 → 登録中…", ephemeral=True)

    # 自動採番＆登録
    success = []
    failed = []
    used_names = set(dm_clients.keys())
    idx = 0

    for token in token_list:
        idx += 1
        while True:
            name = f"dm{idx:03d}"
            if name not in used_names:
                used_names.add(name)
                break

        res = await connect_dm_client(name, token)
        save_token_file(name, token)
        if res:
            success.append(f"✅ {name}")
        else:
            failed.append(f"❌ {name}")

    # 結果報告（これも本人にだけ表示）
    result = f"✅ **登録完了！** 計{len(token_list)}件\n"
    result += f"🟢 成功: {len(success)}件\n🔴 失敗: {len(failed)}件\n"
    if success: result += "\n".join(success[:15])
    if failed: result += "\n" + "\n".join(failed[:10])

    await status_msg.edit(content=result)


@bot.command(name="set_token")
async def set_token_cmd(ctx, name: str, token: str):
    """/set_token 名前 トークン → 個別登録（本人だけ表示）"""
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ 管理者専用", ephemeral=True)

    res = await connect_dm_client(name, token)
    save_token_file(name, token)
    msg = f"✅「{name}」登録完了！🟢" if res else f"⚠️「{name}」登録済・ログイン不可 🔴"
    await ctx.send(msg, ephemeral=True)


@bot.command(name="status")
async def status_cmd(ctx):
    """/status → 死活一覧（本人だけ表示）"""
    if not dm_clients:
        return await ctx.send("📋 DM垢 未登録", ephemeral=True)

    lines = ["📋 **DM垢 死活一覧**\n"]
    alive_count = 0
    for name, info in dm_clients.items():
        status = "🟢" if info["alive"] else "🔴"
        if info["alive"]: alive_count += 1
        try: un = str(info["client"].user) or "未ログイン"
        except: un = "エラー"
        lines.append(f"{status} {name} — {un}")
    lines.append(f"\n✅ 生: {alive_count} / 計{len(dm_clients)}")
    await ctx.send("\n".join(lines), ephemeral=True)


@bot.command(name="remove_dm")
async def remove_dm_cmd(ctx, name: str):
    """/remove_dm 名前 → 削除（本人だけ表示）"""
    if name in dm_clients:
        try: await dm_clients[name]["client"].close()
        except: pass
        del dm_clients[name]
        remove_token_file(name)
        await ctx.send(f"✅「{name}」削除", ephemeral=True)
    else:
        await ctx.send("❌ 存在しません", ephemeral=True)


@bot.command(name="join_all")
async def join_all_cmd(ctx):
    """/join_all → このサーバーに一斉入室（本人だけ表示）"""
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ 管理者専用", ephemeral=True)

    guild = ctx.guild
    if not guild:
        return await ctx.send("❌ サーバー取得不可", ephemeral=True)

    invite_code = INVITE_LINK.split("/")[-1]
    progress = await ctx.send(f"🚀 {len(dm_clients)}体 入室処理中…", ephemeral=True)

    success = []
    failed = []
    for name, info in dm_clients.items():
        if not info["alive"]:
            failed.append(f"🔴 {name}: 未ログイン")
            continue
        try:
            invite = await info["client"].fetch_invite(invite_code)
            await info["client"].accept_invite(invite)
            success.append(f"🟢 {name}")
            await asyncio.sleep(1.5)
        except Exception as e:
            failed.append(f"⚠️ {name}: {type(e).__name__}")

    res = f"📍 {guild.name}\n✅ {len(success)}体 / ❌ {len(failed)}体"
    if success: res += "\n" + "\n".join(success)
    if failed: res += "\n" + "\n".join(failed)
    await progress.edit(content=res)


# ========== 😈 脱走検知 → BAN→解除→スパム ==========
async def spam_worker(user, client, name):
    count = 0
    while True:
        try:
            await user.send(DM_TEXT)
            count += 1
            print(f"✅ [{name}] → {user.name} ({count}通目)")
        except Exception as e:
            dm_clients[name]["alive"] = False
            print(f"🔴 [{name}] 送信失敗: {type(e).__name__}")
            await asyncio.sleep(5)
            continue
        if not dm_clients[name]["alive"]:
            dm_clients[name]["alive"] = True
        await asyncio.sleep(spam_interval)

        log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
        if log_ch and log_ch.guild.get_member(user.id):
            print(f"✅ {user.name} 収容 → 停止")
            return


async def spam_loop(user_id: int):
    log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
    target_guild = log_ch.guild if log_ch else None
    if not target_guild: return

    try:
        await target_guild.ban(discord.Object(id=user_id), reason="脱走試行", delete_message_days=0)
        await asyncio.sleep(0.5)
        await target_guild.unban(discord.Object(id=user_id))
    except Exception as e:
        print(f"⚠️ BAN/解除: {e}")

    leave_ch = bot.get_channel(LEAVE_LOG_CHANNEL)
    alive_list = [n for n, i in dm_clients.items() if i["alive"]]
    if leave_ch:
        await leave_ch.send(
            f"🚨 **脱走検知** <@{user_id}>\n"
            f"🏠 {target_guild.name}\n🟢 {len(alive_list)}体から送信中…"
        )

    user = await bot.fetch_user(user_id)
    if not user: return

    tasks = [asyncio.create_task(spam_worker(user, i["client"], n))
             for n, i in dm_clients.items() if i["alive"]]
    if not tasks:
        if leave_ch: await leave_ch.send("⚠️ DM垢0件")
        return

    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in tasks: t.cancel()
    if leave_ch: await leave_ch.send(f"✅ <@{user_id}> 収容 → 停止")


@bot.event
async def on_member_remove(member):
    if member.id in active_tasks: return
    active_tasks[member.id] = asyncio.create_task(spam_loop(member.id))

@bot.event
async def on_member_join(member):
    if member.id in active_tasks:
        active_tasks.pop(member.id).cancel()
    log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
    alive = sum(1 for i in dm_clients.values() if i["alive"])
    if log_ch and log_ch.guild == member.guild:
        await log_ch.send(
            f"🔒 **収容** {member.mention}\n"
            f"🏠 {member.guild.name}\n💀 脱走時は{alive}体で迎撃"
        )

@bot.event
async def on_ready():
    for n, t in load_tokens().items():
        await connect_dm_client(n, t); await asyncio.sleep(1)
    alive = sum(1 for i in dm_clients.values() if i["alive"])
    print("="*60)
    print(f"🔒 牢屋Bot: {bot.user}｜登録{len(dm_clients)}体｜生{alive}体")
    print("📌 全コマンドは本人にだけ表示（非公開）")
    print("="*60)
    await bot.change_presence(activity=discord.Game(name=f"😈 {alive}体｜/add_tokensで安全登録"))

def get_bot_token():
    t = os.getenv("LOOP_BOT_TOKEN")
    if not t: raise RuntimeError("LOOP_BOT_TOKEN 未設定")
    return t

if __name__ == "__main__":
    bot.run(get_bot_token())