import os
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
    TextMessageContent
)

from .models import db, User, Schedule

bp = Blueprint('bot', __name__)

# Load environment variables and create API clients
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)


@bp.route("/callback", methods=['POST'])
def callback():
    # Log the first 5 chars of the secret to verify it's loaded correctly
    secret = os.getenv('LINE_CHANNEL_SECRET', 'Not Set')
    current_app.logger.warning(f"Using Channel Secret (first 5 chars): {secret[:5]}")

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
        # Handle registration command
        if text.startswith('登録'):
            area_name = text.split(maxsplit=1)[1].strip()
            
            # Check if the area exists in the database
            schedule = db.session.query(Schedule).filter_by(name=area_name).first()

            if schedule:
                # Get user or create a new one
                user = db.session.query(User).filter_by(line_user_id=user_id).first()
                if not user:
                    user = User(line_user_id=user_id)
                
                user.area_name = schedule.name
                db.session.add(user)
                db.session.commit()
                reply_text = f"「{area_name}」を登録しました。\nゴミ収集日の前日20時にお知らせします。"
            else:
                reply_text = f"「{area_name}」が見つかりませんでした。\nPDFに記載されている正式な地域名で登録してください。\n例：登録 大井1丁目"

        # Handle 'help' or other commands
        else:
            reply_text = "お住まいの地域を登録するには、「登録 〇〇」と送信してください。\n例：登録 大井1丁目"

    except Exception as e:
        current_app.logger.error(f"Error handling message: {e}")
        reply_text = "エラーが発生しました。もう一度お試しください。"

    # Send reply message
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
    )
