import datetime

from slack_sdk.errors import SlackApiError

from config import SLACK_CLIENT, DB_TABLE_NAME
from helper import dynamodb, parse_db_response, create_item_if_not_exists
from messager import get_updates_reminder_message



def send_notifications():
    today = datetime.date.today()
    week_day = today.strftime('%A').upper()
    create_item_if_not_exists(week_day)
    response = dynamodb.get_item(
        TableName=DB_TABLE_NAME,
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
            res = SLACK_CLIENT.chat_postMessage(channel=project['channel'], **message)
            print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel"]}')
