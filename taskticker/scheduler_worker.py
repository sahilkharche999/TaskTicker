import datetime
import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from helper import dynamodb, parse_db_response, create_item_if_not_exists
from messager import get_updates_reminder_message

slack_client = WebClient(token=os.environ.get('BOT_TOKEN'))
tbl_name = os.environ.get('DB_TABLE_NAME')


def send_notifications():
    today = datetime.date.today()
    week_day = today.strftime('%A').upper()
    create_item_if_not_exists(week_day)
    response = dynamodb.get_item(
        TableName=tbl_name,
        Key={
            'week_day': {
                'S': week_day
            }
        },
        AttributesToGet=['projects']
    )
    projects_string = response['Item']['projects']['S']
    if projects_string == '[]':
        return
    projects = parse_db_response(projects_string)
    print(projects_string)
    for project in projects:
        try:
            message = get_updates_reminder_message()
            res = slack_client.chat_postMessage(channel=project['channel'], **message)
            print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel"]}')
