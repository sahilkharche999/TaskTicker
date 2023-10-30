import datetime

from slack_sdk.errors import SlackApiError

from config import SLACK_CLIENT, DB_TABLE_NAME
from helper import create_item_if_not_exists, dynamodb
from messager import get_updates_reminder_message


def send_notifications():
    today = datetime.date.today()
    week_day = today.strftime('%A').upper()
    create_item_if_not_exists(week_day)
    response = dynamodb.Table(DB_TABLE_NAME).get_item(
        Key={
            'week_day': week_day
        }
    )
    print(response)
    projects = response['Item']['projects']
    if len(projects) == 0:
        return
    for project in projects:
        print("project -> ", project)
        try:
            message = get_updates_reminder_message()
            print(message)
            user = SLACK_CLIENT.users_profile_get(user=project['engineer'], include_labels=True)
            print(user)
            res = SLACK_CLIENT.chat_postMessage(channel=project['channel'], **message)
            print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel"]}')
