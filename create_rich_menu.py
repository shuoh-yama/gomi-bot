import os
import json
import certifi
from dotenv import load_dotenv
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    RichMenuRequest,
    RichMenuArea,
    RichMenuBounds,
    MessageAction
)

def create_rich_menu():
    """
    Creates a rich menu and provides the curl commands to upload the image and set it as default.
    """
    # --- SSL Certificate Workaround for macOS ---
    os.environ['SSL_CERT_FILE'] = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
    # -----------------------------------------

    load_dotenv()
    access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    if not access_token:
        print("Error: LINE_CHANNEL_ACCESS_TOKEN not found in .env file.")
        return

    configuration = Configuration(access_token=access_token)
    
    rich_menu_to_create = RichMenuRequest(
        size={'width': 2500, 'height': 1686},
        selected=False,
        name="Gomi Bot Rich Menu",
        chat_bar_text='メニューを開く',
        areas=[
            RichMenuArea(bounds=RichMenuBounds(x=0, y=0, width=1250, height=843), action=MessageAction(label='Check Day', text='メニュー')),
            RichMenuArea(bounds=RichMenuBounds(x=1251, y=0, width=1250, height=843), action=MessageAction(label='Rules', text='ゴミのルール')),
            RichMenuArea(bounds=RichMenuBounds(x=0, y=844, width=1250, height=843), action=MessageAction(label='Register', text='地域を登録')),
            RichMenuArea(bounds=RichMenuBounds(x=1251, y=844, width=1250, height=843), action=MessageAction(label='PDF', text='PDF'))
        ]
    )

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            
            # 1. Create rich menu object
            print("Creating rich menu object...")
            rich_menu_id_response = line_bot_api.create_rich_menu(rich_menu_request=rich_menu_to_create)
            rich_menu_id = rich_menu_id_response.rich_menu_id
            print(f"Rich menu object created successfully. ID: {rich_menu_id}")

            # 2. Provide the manual curl command for image upload
            print("\n--- STEP 1: Upload Image ---")
            print("First, run this command to upload the image:\n")
            curl_upload_command = f"""curl -v -X POST https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content \
-H \"Authorization: Bearer {access_token}\" \
-H \"Content-Type: image/png\" \
-T richmenu.png"""
            print(curl_upload_command)

            # 3. Provide the manual curl command for setting the menu as default
            print("\n--- STEP 2: Set as Default ---")
            print("AFTER the image upload is successful, run this second command to set the menu as default:\n")
            curl_set_default_command = f"""curl -v -X POST https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id} \
-H \"Authorization: Bearer {access_token}\""""
            print(curl_set_default_command)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    create_rich_menu()
