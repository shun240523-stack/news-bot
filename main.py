import os
import random
import re
import threading
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask


# ==========================================
# 🌐 Renderの強制終了（タイムアウト）を防ぐためのダミーサーバー
# ==========================================

app = Flask("")


@app.route("/")
def home():
    return "NewsBotは正常に稼働しています。"


def run_web_server():
    # Renderが自動で割り当てるPORTを使用します。
    # PORTが存在しない場合は10000番を使用します。
    port = int(os.getenv("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True
    )


# Bot起動前にWebサーバーを別スレッドで起動
web_thread = threading.Thread(
    target=run_web_server,
    daemon=True
)

web_thread.start()


# ==========================================
# ⚙️ 設定エリア
# ==========================================

COMMAND_PREFIX = "!"


# ニュースカテゴリー
CATEGORIES = {
    "SOCIAL": {
        "label": "社会",
        "color": discord.Color.red()
    },
    "ENTERTAINMENT": {
        "label": "エンタメ",
        "color": discord.Color.magenta()
    },
    "ECONOMY": {
        "label": "経済",
        "color": discord.Color.green()
    },
    "SPORTS": {
        "label": "スポーツ",
        "color": discord.Color.blue()
    },
    "SPECIAL": {
        "label": "特報",
        "color": discord.Color.gold()
    }
}


# ==========================================
# 🗣️ 街の声（サブコメント）
# ==========================================

STREET_VOICES = [
    "近所の住民「普段は大人しい方だと思っていたのですが…」",
    "同僚のAさん「やはり、という感じですね。予兆はありました」",
    "通りすがりのBさん「信じられません。明日からどうすればいいのか」",
    "ネット上の反応「これは伝説になる」「天才現る」",
    "専門家「今後のサーバー経済に多大な影響を及ぼす一言です」"
]


# ==========================================
# 📰 ニューステンプレート
# ==========================================

NEWS_TEMPLATES = [
    "【速報】{name}氏、「{content}」と発言。周囲に衝撃が走る。",
    "【独自】{name}氏の目撃情報。「{content}」との供述を得ました。",
    "【世論】「{content}」という{name}氏の主張に対し、波紋が広がっています。",
    "【迷言】本日未明、{name}氏が放った一言が話題です。「{content}」",
    "【経済】{name}氏が「{content}」と発言した影響で、サーバーの株価が変動。",
    "【事件】「{content}」――。{name}氏のこの発言の真意を、警察は慎重に調査中。",
    "【感動】全サーバーが泣いた、{name}氏の至高の一言。「{content}」",
    "【速報】{name}氏、突如として「{content}」と宣言。革命の予感。"
]


# ==========================================
# 🤖 Discord Bot 初期化
# ==========================================

intents = discord.Intents.default()

# メッセージ本文を取得するために必要
intents.message_content = True

# メンバー情報を取得するために必要
intents.members = True


bot = commands.Bot(
    command_prefix=COMMAND_PREFIX,
    intents=intents
)


# ==========================================
# 🧹 メッセージの掃除
# ==========================================

def clean_content(content):
    """
    ニュース生成に使用するメッセージを整理する関数。

    ・空メッセージを除外
    ・URLを含むメッセージを除外
    ・メンションを除去
    ・前後の空白を除去
    """

    if not content:
        return None

    # URLを含むメッセージはニュース候補から除外
    if re.search(r"https?://", content):
        return None

    # Discordメンションを除去
    content = re.sub(r"<@!?\d+>", "", content).strip()

    return content if content else None


# ==========================================
# 📰 ニュース生成
# ==========================================

async def generate_news_embed(
    ctx_or_interaction,
    manual_content: str = None
):
    """
    チャンネルの過去ログからランダムにニュースを生成します。

    manual_contentが指定されている場合は、
    過去ログではなく指定された内容をニュース化します。
    """

    is_interaction = isinstance(
        ctx_or_interaction,
        discord.Interaction
    )

    channel = ctx_or_interaction.channel

    requester = (
        ctx_or_interaction.user
        if is_interaction
        else ctx_or_interaction.author
    )

    guild = ctx_or_interaction.guild

    # ==========================================
    # 手動ニュース
    # ==========================================

    if manual_content:
        cleaned_manual = clean_content(manual_content)

        if not cleaned_manual:
            return None, "【案内】有効なニュース内容を入力してください。"

        author = requester
        timestamp = datetime.now()
        main_text = cleaned_manual

        target_msg = None

    # ==========================================
    # 過去ログからニュース生成
    # ==========================================

    else:
        messages = []

        try:
            async for msg in channel.history(limit=300):

                # Botの発言を除外
                if msg.author.bot:
                    continue

                # コマンドそのものを除外
                if (
                    msg.content.startswith(COMMAND_PREFIX)
                    or msg.content.startswith("/")
                ):
                    continue

                cleaned = clean_content(msg.content)

                # 十分な文章、または画像添付がある場合のみ候補にする
                if (
                    (cleaned and len(cleaned) >= 3)
                    or msg.attachments
                ):
                    messages.append(msg)

        except Exception as e:
            return (
                None,
                f"【システム障害】データ取得に失敗しました: {e}"
            )

        # ネタ不足
        if len(messages) < 1:
            return (
                None,
                "【案内】ニュースのネタ（発言）が足りません。"
                "もっと会話を積み上げてください！"
            )

        if len(messages) < 2:
            return (
                None,
                "【案内】過去ログからネタを拾うには、"
                "少なくとも2件以上の発言が必要です。"
            )

        # ランダムな発言を選択
        target_msg = random.choice(messages)

        author = target_msg.author
        timestamp = target_msg.created_at

        main_text = (
            clean_content(target_msg.content)
            or "（静寂を破る沈黙）"
        )

    # ==========================================
    # 見出し生成
    # ==========================================

    if len(main_text) > 60:
        headline_content = main_text[:57] + "..."
    else:
        headline_content = main_text

    headline = random.choice(
        NEWS_TEMPLATES
    ).format(
        name=author.display_name,
        content=headline_content
    )

    # カテゴリーをランダム選択
    category_id = random.choice(
        list(CATEGORIES.keys())
    )

    category = CATEGORIES[category_id]

    # 画像
    main_image_url = None

    if target_msg and target_msg.attachments:
        main_image_url = target_msg.attachments[0].url

    # ==========================================
    # サブコメント用メッセージ
    # ==========================================

    sub_msg = None

    if target_msg:
        other_messages = [
            message
            for message in messages
            if message.author.id != author.id
        ]

        if other_messages:
            sub_msg = random.choice(other_messages)

    # ==========================================
    # Embed本体
    # ==========================================

    embed = discord.Embed(
        title=f"📺 サーバー報道ステーション "
              f"[{category['label']}]",
        description=f"## {headline}",
        color=category["color"],
        timestamp=timestamp
    )

    # 発言者
    embed.set_author(
        name=f"現場の {author.display_name} 氏",
        icon_url=author.display_avatar.url
        if author.display_avatar
        else None
    )

    # ==========================================
    # 現場写真
    # ==========================================

    if main_image_url:
        embed.set_image(url=main_image_url)

        embed.add_field(
            name="【現場写真】",
            value="決定的瞬間を捉えた一枚。",
            inline=False
        )

    # ==========================================
    # 街の声
    # ==========================================

    if sub_msg:
        sub_text = (
            clean_content(sub_msg.content)
            or "「ノーコメントです」"
        )

        voice_label = random.choice(
            STREET_VOICES
        )

        if len(sub_text) > 40:
            sub_text = sub_text[:37] + "..."

        embed.add_field(
            name=f"🗣️ {voice_label}",
            value=f'> 「{sub_text}」',
            inline=False
        )

    # ==========================================
    # L字テロップ
    # ==========================================

    ticker = random.choice([
        "【L字テロップ】サーバー内の室温は現在適温です。",
        "【CM】新発売！ボット専用オイル「デジタル・スムーズ」好評発売中。",
        "【占い】今日のラッキー絵文字は 💎 です。",
        f"【天気】{guild.name if guild else 'サーバー'}地方は概ね晴れでしょう。"
    ])

    embed.set_footer(
        text=f"{ticker} | 記録日時"
    )

    return embed, None


# ==========================================
# 🚨 緊急速報
# ==========================================

def generate_breaking_embed(
    ctx_or_interaction,
    content: str
):
    guild = ctx_or_interaction.guild

    embed = discord.Embed(
        title="🚨 報道特別番組 【号外】",
        description=(
            "# ーー 💻 緊 急 速 報 ーー\n\n"
            f"**{content}**"
        ),
        color=discord.Color.dark_red(),
        timestamp=datetime.now()
    )

    embed.set_footer(
        text=(
            f"【提供】"
            f"{guild.name if guild else 'サーバー'}報道局"
        )
    )

    return embed


# ==========================================
# 📊 世論調査
# ==========================================

def generate_opinion_embed(
    ctx_or_interaction,
    question: str,
    option_a: str,
    option_b: str
):
    is_interaction = isinstance(
        ctx_or_interaction,
        discord.Interaction
    )

    author = (
        ctx_or_interaction.user
        if is_interaction
        else ctx_or_interaction.author
    )

    embed = discord.Embed(
        title="📊 サーバー世論調査特報",
        description=(
            "### 【お題】\n"
            f"## {question}"
        ),
        color=discord.Color.dark_teal(),
        timestamp=datetime.now()
    )

    embed.add_field(
        name="⭕ 選択肢 A",
        value=f"**{option_a}**",
        inline=True
    )

    embed.add_field(
        name="❌ 選択肢 B",
        value=f"**{option_b}**",
        inline=True
    )

    embed.set_footer(
        text=(
            f"有権者：サーバーの皆様 | "
            f"調査担当：{author.display_name}"
        )
    )

    return embed


# ==========================================
# 🚨 指名手配
# ==========================================

def generate_suspect_embed(
    ctx_or_interaction
):
    is_interaction = isinstance(
        ctx_or_interaction,
        discord.Interaction
    )

    author = (
        ctx_or_interaction.user
        if is_interaction
        else ctx_or_interaction.author
    )

    guild = ctx_or_interaction.guild

    # ==========================================
    # 容疑一覧
    # ==========================================

    crimes = [
        "深夜にタイムラインに美味しそうなラーメンの画像を投下し、重大な飯テロを引き起こした容疑",

        "ボットに対して無茶な命令を繰り返し、CPUに過度な労働を強いた労働基準法違反の容疑",

        "チャット欄で『草』を大量に生やしすぎ、サーバーの緑地化を勝手に進めた容疑",

        "『布団から出たくない』という強い執念により、午前中の生産性を著しく低下させた容疑",

        "通話に参加しているにもかかわらず、完全に気配を消して壁と同化していた容疑",

        "タイピング速度が早すぎて、キーボードの『Enterキー』を過剰に痛めつけた容疑"
    ]

    # ==========================================
    # 懸賞金一覧
    # ==========================================

    bounties = [
        "5,000兆 サーバーコイン",
        "うまい棒めんたい味 3本",
        "徳用高級ボット専用オイル 1リットル",
        "サーバー管理者からの温かい眼差し",
        "2 億ゴールド（ただしゲーム内通貨に限る）"
    ]

    chosen_crime = random.choice(crimes)
    chosen_bounty = random.choice(bounties)

    # ==========================================
    # Embed
    # ==========================================

    embed = discord.Embed(
        title="🚨 【指名手配】 サーバー指名手配犯・即時確保令",
        description=(
            "# ーー WANTED ーー\n\n"
            "当サーバーの治安を揺るがす重要容疑者として、"
            "本日の chief（実行者）をここに指名手配します。"
        ),
        color=discord.Color.from_rgb(139, 0, 0),
        timestamp=datetime.now()
    )

    embed.add_field(
        name="👤 容疑者名",
        value=(
            f"**{author.display_name}** "
            f"（@{author.name}）"
        ),
        inline=False
    )

    embed.add_field(
        name="📜 主な容疑",
        value=f"```\n{chosen_crime}\n```",
        inline=False
    )

    embed.add_field(
        name="💰 懸賞金",
        value=f"🏆 **{chosen_bounty}**",
        inline=True
    )

    embed.add_field(
        name="⚠️ 特徴",
        value=(
            "現在もサーバー内を潜伏・徘徊中。"
            "発見しても刺激せず、生温かく見守ってください。"
        ),
        inline=False
    )

    if author.display_avatar:
        embed.set_image(
            url=author.display_avatar.url
        )

    embed.set_footer(
        text=(
            f"【発行元】"
            f"{guild.name if guild else 'サーバー'}"
            "秘密警察広報局"
        )
    )

    return embed


# ==========================================
# 🟢 Bot起動時
# ==========================================

@bot.event
async def on_ready():

    print(
        f"放送開始: {bot.user.name} がオンラインになりました。"
    )

    try:
        # スラッシュコマンドをDiscordへ同期
        synced = await bot.tree.sync()

        print(
            f"スラッシュコマンドを "
            f"{len(synced)} 件同期しました。"
        )

    except Exception as e:

        print(
            f"コマンドの同期に失敗しました: {e}"
        )

    print("------")


# ==========================================
# 💬 メッセージ監視
# ==========================================

@bot.event
async def on_message(message):

    if not message.author.bot:

        timestamp = datetime.now().strftime(
            "%H:%M:%S"
        )

        print(
            f"[{timestamp}] "
            f"{message.author.name}: "
            f"{message.content[:20]}"
        )

    # 通常のprefixコマンドを処理
    await bot.process_commands(message)


# ==========================================
# 📺 1. NEWS
# ==========================================

# ------------------------------------------
# Prefix版
# 例：
# !news
# !news 今日サーバーに異変が起きました
# ------------------------------------------

@bot.command(name="news")
async def server_news_text(
    ctx,
    *,
    manual_content: str = None
):

    try:
        await ctx.message.add_reaction("🎬")
    except Exception:
        pass

    embed, error_msg = await generate_news_embed(
        ctx,
        manual_content
    )

    if error_msg:
        await ctx.send(error_msg)
    else:
        await ctx.send(embed=embed)


# ------------------------------------------
# Slash版
# /news
# ------------------------------------------

@bot.tree.command(
    name="news",
    description="サーバー内の過去ログから豪華なニュースを生成します"
)
@app_commands.describe(
    manual_content="特定のニュース内容を直接入力して速報を流します（任意）"
)
async def server_news_slash(
    interaction: discord.Interaction,
    manual_content: str = None
):

    await interaction.response.defer()

    embed, error_msg = await generate_news_embed(
        interaction,
        manual_content
    )

    if error_msg:
        await interaction.followup.send(
            error_msg
        )
    else:
        await interaction.followup.send(
            embed=embed
        )


# ==========================================
# 🚨 2. BREAKING
# ==========================================

# ------------------------------------------
# Prefix版
# !breaking 重大なニュースです
# ------------------------------------------

@bot.command(name="breaking")
async def server_breaking_text(
    ctx,
    *,
    content: str
):

    embed = generate_breaking_embed(
        ctx,
        content
    )

    await ctx.send(
        embed=embed
    )


# ------------------------------------------
# Slash版
# /breaking
# ------------------------------------------

@bot.tree.command(
    name="breaking",
    description="緊迫した号外・緊急速報を流します"
)
@app_commands.describe(
    content="速報として流したい重大な内容を入力してください"
)
async def server_breaking_slash(
    interaction: discord.Interaction,
    content: str
):

    embed = generate_breaking_embed(
        interaction,
        content
    )

    await interaction.response.send_message(
        embed=embed
    )


# ==========================================
# 📊 3. OPINION
# ==========================================

# ------------------------------------------
# Prefix版
#
# !opinion 質問
# !opinion 質問 賛成 反対
# ------------------------------------------

@bot.command(name="opinion")
async def server_opinion_text(
    ctx,
    question: str,
    option_a: str = "賛成",
    option_b: str = "反対"
):

    embed = generate_opinion_embed(
        ctx,
        question,
        option_a,
        option_b
    )

    msg = await ctx.send(
        embed=embed
    )

    await msg.add_reaction("⭕")
    await msg.add_reaction("❌")


# ------------------------------------------
# Slash版
# /opinion
# ------------------------------------------

@bot.tree.command(
    name="opinion",
    description="ニュース風の2択アンケート（世論調査）を設置します"
)
@app_commands.describe(
    question="調査したいお題や質問",
    option_a="選択肢Aのテキスト",
    option_b="選択肢Bのテキスト"
)
async def server_opinion_slash(
    interaction: discord.Interaction,
    question: str,
    option_a: str = "賛成",
    option_b: str = "反対"
):

    embed = generate_opinion_embed(
        interaction,
        question,
        option_a,
        option_b
    )

    await interaction.response.send_message(
        embed=embed
    )

    msg = await interaction.original_response()

    await msg.add_reaction("⭕")
    await msg.add_reaction("❌")


# ==========================================
# 🚨 4. SUSPECT
# ==========================================

# ------------------------------------------
# Prefix版
# !suspect
# ------------------------------------------

@bot.command(name="suspect")
async def server_suspect_text(ctx):

    embed = generate_suspect_embed(
        ctx
    )

    await ctx.send(
        embed=embed
    )


# ------------------------------------------
# Slash版
# /suspect
# ------------------------------------------

@bot.tree.command(
    name="suspect",
    description="【ジョーク機能】あなた自身にかけられた指名手配の容疑を診断します"
)
async def server_suspect_slash(
    interaction: discord.Interaction
):

    embed = generate_suspect_embed(
        interaction
    )

    await interaction.response.send_message(
        embed=embed
    )


# ==========================================
# 🚀 Bot起動処理
# ==========================================

if __name__ == "__main__":

    TOKEN = os.getenv(
        "DISCORD_BOT_TOKEN"
    )

    if not TOKEN:

        print(
            "エラー: 環境変数 "
            "'DISCORD_BOT_TOKEN' が設定されていません。"
        )

    else:

        try:

            bot.run(TOKEN)

        except Exception as e:

            print(
                f"エラーが発生しました: {e}"
            )
