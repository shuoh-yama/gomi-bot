import os
import re
from flask import Blueprint, request, abort, current_app
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    QuickReply,
    QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent
)

from .models import db, User, Schedule

bp = Blueprint('bot', __name__)

# Load environment variables and create API clients
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

# --- Helper Functions for Area Parsing ---

def parse_user_area(text):
    """Parses user input like '東大井2丁目' into a base name and number."""
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    match = re.match(r'(.+?)(\d+)丁目.*', text)
    if match:
        return match.group(1), int(match.group(2))
    return text, None

def is_number_in_range(num, schedule_name):
    """Checks if a number is within the range specified by a schedule name."""
    if num is None:
        return False
    schedule_name = schedule_name.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    match = re.search(r'(\d+)-(\d+)丁目', schedule_name)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return start <= num <= end
    match = re.findall(r'(\d+)・', schedule_name)
    if match:
        nums = [int(n) for n in match]
        last_num_match = re.search(r'・(\d+)丁目', schedule_name)
        if last_num_match:
            nums.append(int(last_num_match.group(1)))
        return num in nums
    match = re.search(r'(\d+)丁目', schedule_name)
    if match:
        if '-' not in schedule_name and '・' not in schedule_name:
            return num == int(match.group(1))
    return False

# --- LINE Bot Webhook Handlers ---

@bp.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    reply_text = ""
    quick_reply = None

    try:
        user = db.session.query(User).filter_by(line_user_id=user_id).first()

        if text.startswith('登録'):
            user_input_area = text.split(maxsplit=1)[1].strip()
            schedule = db.session.query(Schedule).filter_by(name=user_input_area).first()
            if not schedule:
                base_name, num = parse_user_area(user_input_area)
                potential_schedules = db.session.query(Schedule).filter(Schedule.name.like(f"%{base_name}%")).all()
                found_schedules = [s for s in potential_schedules if is_number_in_range(num, s.name)]
                if len(found_schedules) == 1:
                    schedule = found_schedules[0]
            
            if schedule:
                if not user:
                    user = User(line_user_id=user_id)
                user.area_name = schedule.name
                db.session.add(user)
                db.session.commit()
                reply_text = f"「{schedule.name}」を登録しました。\n毎晩20時にお知らせします。"
            else:
                reply_text = f"「{user_input_area}」に一致する地域が見つかりませんでした。"

        elif text in ["メニュー", "確認", "ごみの日", "収集日を確認"]:
            reply_text = "どのごみの日を確認しますか？"
            quick_reply = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="燃やすごみ", text="燃やすごみ")),
                QuickReplyItem(action=MessageAction(label="資源", text="資源")),
                QuickReplyItem(action=MessageAction(label="陶器・ガラス・金属ごみ", text="陶器・ガラス・金属ごみ")),
            ])

        elif text in ["燃やすごみ", "資源", "陶器・ガラス・金属ごみ"]:
            if user and user.schedule:
                if text == "燃やすごみ":
                    reply_text = f"【燃やすごみ】\n収集日は「{user.schedule.burnable}」です。"
                elif text == "資源":
                    reply_text = f"【資源】\n収集日は「{user.schedule.resources}」です。"
                elif text == "陶器・ガラス・金属ごみ":
                    reply_text = f"【陶器・ガラス・金属ごみ】\n収集日は「{user.schedule.ceramic_glass_metal}」です。"
            else:
                reply_text = "地域が登録されていません。\n「登録 〇〇」と送信して、お住まいの地域を登録してください。"

        elif text == "ゴミのルール":
            reply_text = (
                "【主なゴミのルール】\n\n"
                "■燃やすごみ\n生ごみ、汚れの落ちないプラスチック、ゴム・革製品など\n\n"
                "■資源\nプラスチック類、ペットボトル、びん、缶、古紙、乾電池など\n※汚れを落として出してください\n\n"
                "■陶器・ガラス・金属ごみ\n金属類、ガラス類、傘、スプレー缶、電球など\n※スプレー缶は使い切ってから出してください\n\n"
                "詳細は「PDFで確認」ボタンからご確認ください。"
            )

        elif text == "地域を登録":
            reply_text = "地域を登録・変更するには、「登録 〇〇」と送信してください。\n例：登録 大井1丁目"

        elif text == "PDF":
            pdf_url = "https://raw.githubusercontent.com/shuoh-yama/gomi-bot/main/data/sigengomi2024.pdf"
            reply_text = f"ゴミ出しの全体スケジュールはこちらのPDFから確認できます：\n{pdf_url}"
        
        else:
            reply_text = "メニューから操作を選択するか、「登録 〇〇」と送信して地域を登録してください。"

    except Exception as e:
        current_app.logger.error(f"Error handling message: {e}")
        reply_text = "エラーが発生しました。もう一度お試しください。"

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text, quick_reply=quick_reply)]
        )
    )

@handler.add(FollowEvent)
def handle_follow(event):
    """Handles the event when a user adds the bot as a friend."""
    pdf_url = "https://raw.githubusercontent.com/shuoh-yama/gomi-bot/main/data/sigengomi2024.pdf"
    welcome_message = (
        "友だち追加ありがとうございます！\n\n"
        "このBOTは、品川区のゴミ収集日をお知らせします。\n\n"
        "まず、お住まいの地域を登録してください。\n"
        "例：登録 大井1丁目\n\n"
        "登録後は「メニュー」と入力すると、収集日を確認できます。\n\n"
        f"ゴミ出しの全体スケジュールはこちらのPDFから確認できます：\n{pdf_url}"
    )
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=welcome_message)]
        )
    )
