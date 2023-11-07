from datetime import date
from slack_sdk.errors import SlackApiError
from helper import get_updates_reminder_message
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
        print("project -> ", project)
        try:
            blocks = get_updates_reminder_message()
            res = SLACK_CLIENT.chat_postEphemeral(
                channel=project['channel'],
                user=project['engineer'],
                text="Reminder to update your tasks for today!",
                blocks=blocks)
            print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel"]}')


def schedule_notification(user: str, post_at: int, channel: str):
    try:
        blocks = get_updates_reminder_message()
        blocks[1] = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Hi again, Reminding you to post update in <#{channel}>!",
            }
        }
        res = SLACK_CLIENT.chat_scheduleMessage(
            text="Hi again!",
            blocks=blocks,
            post_at=post_at,
            channel=user
        )
        print(res)

    except SlackApiError as e:
        print(f'Error occurred in sending message : {e}')
