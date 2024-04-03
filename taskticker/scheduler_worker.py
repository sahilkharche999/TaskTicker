import json
from datetime import date
from slack_sdk.errors import SlackApiError

from config import SLACK_CLIENT, DYNAMO_MAPPING_DB_Table


def get_updates_reminder_message(channel_id: str) -> dict:
    message = json.load(open('templates/update_reminder.json'))
    for button in message[2]['elements']:
        button['value'] = channel_id
    return message


def send_notifications(channel_type: str):
    week_day = date.today().strftime('%A').upper()
    if channel_type == 'standup':
        filter_expression = "contains (days, :week_day) AND channel_type = :channel_type"
    else:
        filter_expression = "contains (days, :week_day) AND channel_type <> :channel_type"
    channels = DYNAMO_MAPPING_DB_Table.scan(
        FilterExpression=filter_expression,
        ExpressionAttributeValues={
            ":week_day": week_day,
            ":channel_type": "standup"
        }
    ).get('Items', [])

    for channel in channels:
        print("channel -> ", channel)
        if channel['channel_type'] == 'standup':
            for user in channel['user_ids']:
                try:
                    blocks = get_updates_reminder_message(channel_id=channel['channel_id'])
                    # post ephemeral message to slack with metadata
                    res = SLACK_CLIENT.chat_postEphemeral(
                        channel=channel['channel_id'],
                        user=user,
                        text="Reminder to post update on your tasks for today!",
                        blocks=blocks)
                    print(res)
                except SlackApiError as e:
                    print(f'Error occurred in sending message : {e} --- channel id : {channel["channel_id"]}')
        else:
            try:
                blocks = get_updates_reminder_message(channel_id=channel['channel_id'])
                # post ephemeral message to slack with metadata
                res = SLACK_CLIENT.chat_postEphemeral(
                    channel=channel['channel_id'],
                    user=channel['user_id'],
                    text="Reminder to post update on your tasks for today!",
                    blocks=blocks)
                print(res)
            except SlackApiError as e:
                print(f'Error occurred in sending message : {e} --- channel id : {channel["channel_id"]}')


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
