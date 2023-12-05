from datetime import date

from slack_sdk.errors import SlackApiError

from config import SLACK_CLIENT, DYNAMO_MAPPING_DB_Table
from helper import get_updates_reminder_message


def send_notifications():
    week_day = date.today().strftime('%A').upper()
    projects = DYNAMO_MAPPING_DB_Table.scan(
        FilterExpression="contains (days, :week_day)",
        ExpressionAttributeValues={
            ":week_day": week_day
        }
    ).get('Items', [])

    for project in projects:
        print("project -> ", project)
        try:
            blocks = get_updates_reminder_message(channel_id=project['channel_id'])
            # post ephemeral message to slack with metadata
            res = SLACK_CLIENT.chat_postEphemeral(
                channel=project['channel_id'],
                user=project['user_id'],
                text="Reminder to update your tasks for today!",
                blocks=blocks)
            print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel_id"]}')


def schedule_notification(user: str, post_at: int, channel_id: str):
    try:
        blocks = get_updates_reminder_message(channel_id=channel_id)
        blocks[1] = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Hi again, Reminding you to post update in <#{channel_id}>!",
            }
        }
        res = SLACK_CLIENT.chat_scheduleMessage(
            text="Hi again!",
            blocks=blocks,
            post_at=post_at,
            channel=user
        )
        print('scheduleMessage response: ', res)

    except SlackApiError as e:
        print(f'Error occurred in sending message : {e}')
