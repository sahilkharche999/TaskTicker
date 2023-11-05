from datetime import date
from slack_sdk.errors import SlackApiError
from messager import get_updates_reminder_message
from config import DYNAMO_DB_Table, SLACK_CLIENT


def send_notifications():
    week_day = date.today().strftime('%A').upper()
    projects = DYNAMO_DB_Table.get_item(
        Key={
            'week_day': week_day
        },
        ProjectionExpression='projects'
    ).get('Item', {}).get('projects', [])
    for project in projects:
        try:
            message = get_updates_reminder_message()
            res = SLACK_CLIENT.chat_postEphemeral(
                channel=project['channel'],
                user=project['engineer'],
                message=message)
            print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel"]}')
