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
    TextMessage
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
    # Normalize numbers (e.g., ２ -> 2)
    text = text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    # Try to find '〇丁目' pattern
    match = re.match(r'(.+?)(\d+)丁目.*', text)
    if match:
        return match.group(1), int(match.group(2))
    # Fallback for names without numbers
    return text, None

def is_number_in_range(num, schedule_name):
    """Checks if a number is within the range specified by a schedule name."""
    if num is None:
        return False
    
    # Normalize schedule name for parsing
    schedule_name = schedule_name.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    
    # Case 1: "1-4丁目"
    match = re.search(r'(\d+)-(\d+)丁目', schedule_name)
    if match:
        start, end = int(match.group(1)), int(match.group(2))
        return start <= num <= end

    # Case 2: "5・6丁目"
    match = re.findall(r'(\d+)・', schedule_name)
    if match:
        nums = [int(n) for n in match]
        # Also get the last number, e.g., the "6" in "5・6丁目"
        last_num_match = re.search(r'・(\d+)丁目', schedule_name)
        if last_num_match:
            nums.append(int(last_num_match.group(1)))
        return num in nums

    # Case 3: "7丁目" (single number)
    match = re.search(r'(\d+)丁目', schedule_name)
    if match:
        # Ensure it's not a range or list, e.g. "1-4丁目" should not match "1丁目"
        if '-' not in schedule_name and '・' not in schedule_name:
            return num == int(match.group(1))

    return False

# --- LINE Bot Webhook Handlers ---

@bp.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    current_app.logger.info("Request body: " + body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        current_app.logger.error("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    reply_text = ""

    try:
        if text.startswith('登録'):
            user_input_area = text.split(maxsplit=1)[1].strip()
            
            # First, try for an exact match
            schedule = db.session.query(Schedule).filter_by(name=user_input_area).first()

            if not schedule:
                # If no exact match, try fuzzy matching
                base_name, num = parse_user_area(user_input_area)
                
                # Find potential schedules
                potential_schedules = db.session.query(Schedule).filter(Schedule.name.like(f"%{base_name}%")).all()
                
                found_schedules = []
                for s in potential_schedules:
                    if num is not None and is_number_in_range(num, s.name):
                        found_schedules.append(s)
                
                if len(found_schedules) == 1:
                    schedule = found_schedules[0]

            # Process the found schedule
            if schedule:
                user = db.session.query(User).filter_by(line_user_id=user_id).first()
                if not user:
                    user = User(line_user_id=user_id)
                
                user.area_name = schedule.name
                db.session.add(user)
                db.session.commit()
                reply_text = f"「{schedule.name}」を登録しました。\nゴミ収集日の前日20時にお知らせします。"
            else:
                reply_text = f"「{user_input_area}」に一致する地域が見つかりませんでした。\nPDFの正式名称をご確認の上、再度お試しください。"

        else:
            reply_text = "お住まいの地域を登録するには、「登録 〇〇」と送信してください。\n例：登録 大井1丁目"

    except Exception as e:
        current_app.logger.error(f"Error handling message: {e}")
        reply_text = "エラーが発生しました。もう一度お試しください。"

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
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
        f"ゴミ出しの全体スケジュールはこちらのPDFから確認できます：\n{pdf_url}"
    )

    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=welcome_message)]
        )
    )
