import json
from datetime import date, datetime

from slack_sdk.errors import SlackApiError

from config import SLACK_CLIENT, DYNAMO_MAPPING_DB_Table, UPDATE_LOG_Table


def get_updates_reminder_message(channel_id: str) -> dict:
    message = json.load(open('templates/update_reminder.json'))
    for button in message[2]['elements']:
        button['value'] = channel_id
    return message


def send_notifications():
    week_day = date.today().strftime('%A').upper()
    projects = DYNAMO_MAPPING_DB_Table.scan(
        FilterExpression="contains (days, :week_day)",
        ExpressionAttributeValues={
            ":week_day": week_day
        }
    ).get('Items', [])
    print("Retrieved Projects : ", projects)
    save_to_update_log_table(projects)
    for project in projects:
        try:
            blocks = get_updates_reminder_message(channel_id=project['channel_id'])
            # post ephemeral message to slack with metadata
            # res = SLACK_CLIENT.chat_postEphemeral(
            #     channel=project['channel_id'],
            #     user=project['user_id'],
            #     text="Reminder to update your tasks for today!",
            #     blocks=blocks)
            # print(res)
        except SlackApiError as e:
            print(f'Error occurred in sending message : {e} --- channel id : {project["channel_id"]}')


# todo : Check if :post_at: is after work hours, if so - don't snooze reminder, rather inform scrum and respond
# with 'snooze limit' reached
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


def clean_up_update_log_table():
    pending_updates_projects = UPDATE_LOG_Table.scan().get('Items', [])
    print(pending_updates_projects)
    for project in pending_updates_projects:
        res = SLACK_CLIENT.conversations_open(users=project['scrum_id'])
        id = res['channel']['id']
        print(project['scrum_id'])
        SLACK_CLIENT.chat_postMessage(
            channel=id,
            text=f"Hi <@{project['scrum_id']}>, This message is to inform you that <@{project['user_id']}> did not "
                 f"posted updates for {project['date']} in channel <#{project['channel_id']}>."
        )

    # for project in pending_updates_projects:
    #     UPDATE_LOG_Table.delete_item(
    #         Key=project['channel_id']
    #     )
    print('Finished clean up')


def save_to_update_log_table(projects: list):
    records = []
    current_date = datetime.now().strftime("%d-%m-%Y")
    for project in projects:
        records.append({
            'channel_id': project['channel_id'],
            'project_id': project['project_id'],
            'scrum_id': project['scrum_id'],
            'user_id': project['user_id'],
            'date': current_date,
        })

    with UPDATE_LOG_Table.batch_writer() as batch:
        for record in records:
            batch.put_item(Item=record)

    print(f"Successfully created {len(projects)} items in the UpdateLogTable table.")
