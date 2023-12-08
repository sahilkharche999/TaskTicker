import json
from datetime import date, datetime
from urllib.parse import parse_qs

import requests
from slack_sdk.errors import SlackApiError

from config import LOG1_URL, LOG1_API_KEY, SLACK_CLIENT, DYNAMO_MAPPING_DB_Table, ADMIN_USERS


def is_from_slack(event: dict) -> bool:
    return event.get('headers', {}).get('User-Agent').startswith('Slackbot 1.0')


def is_from_aws_event_bridge(event: dict) -> bool:
    return event.get('source') == 'aws.events'


def is_slack_command(body: dict) -> bool:
    return "command" in body.keys()


def is_from_admin(body: dict) -> bool:
    return body['user_id'][0] in ADMIN_USERS


def is_slack_submit(slack_payload) -> bool:
    return slack_payload.get('type') == 'view_submission'


def is_button_pressed(payload: dict) -> bool:
    return payload.get('type') == 'block_actions' and payload['actions'][0]['type'] == 'button'


def is_checkboxes_action(payload: dict) -> bool:
    return payload.get('type') == 'block_actions' and payload['actions'][0]['type'] == 'checkboxes'


def get_action_id(payload: dict) -> str:
    return payload['actions'][0]['action_id']


def get_submission(payload: dict) -> str:
    return payload['view']['private_metadata']


def parse_slack_event_body(event: dict) -> dict:
    return parse_qs(event.get('body'))


def get_payload(body: dict):
    return json.loads(body.get('payload')[0])


def update_slack_message(response_url: str, message: dict) -> None:
    """
    Update an existing Slack message
    :param response_url: response url of the message
    :param message: new message
    """
    requests.post(
        url=response_url,
        json=message
    )


def get_setup_modal(channel_id: str) -> dict:
    message = json.load(open('templates/setup_modal.json'))
    message['blocks'].insert(1, {
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": channel_id
        }
    })
    return message


def get_update_modal(channel_id: str, is_blocker: bool = False) -> dict:
    message = json.load(open('templates/update_modal.json'))['with' if is_blocker else 'without']
    message['blocks'].insert(1, {
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": channel_id
        }
    })
    return message


def get_updates_reminder_message(channel_id: str) -> dict:
    message = json.load(open('templates/update_reminder.json'))
    for button in message[2]['elements']:
        button['value'] = channel_id
    return message


def get_channel_from_action_button(payload: dict) -> str:
    return payload['actions'][0]['value']


def retrieve_project_details(payload: dict) -> dict:
    state_values = payload['view']['state']['values'].values()
    values = {key: val for state in state_values for key, val in state.items()}
    return {'project_id': int(values['project_id-action']['value']),
            'engineer': values['user_select-action']['selected_user'],
            'scrum': values['scrum_select-action']['selected_user'],
            'channel': payload['view']['blocks'][1]['text']['text'],
            'frequency': [x['value'] for x in values['frequency_select-action']['selected_options']]
            }


def retrieve_update_details(payload: dict) -> dict:
    state_values = payload['view']['state']['values'].values()
    values = {key: val for state in state_values for key, val in state.items()}
    return {
        'update': values['project-update-action']['value'],
        'blocker': values.get('blocker_input-action', {}).get('value'),
    }


def save_to_db(payload: dict):
    new_project = retrieve_project_details(payload)
    days = new_project.pop('frequency')
    DYNAMO_MAPPING_DB_Table.put_item(
        Item={
            'channel_id': new_project['channel'],
            'project_id': new_project['project_id'],
            'user_id': new_project['engineer'],
            'scrum_id': new_project['scrum'],
            'days': days
        }
    )


def post_updates_to_slack(channel_id: str, user: dict, update: str, blocker: str = None):
    dt = datetime.now().strftime('%m/%d/%Y')
    message_blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Today's Updates ({dt}):*\n{update}"
            }
        }]
    if blocker:
        message_blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Blockers:*:exclamation:\n{blocker}"
                }
            }
        )
    return post_message_as_user(channel_id, message_blocks, user['id'])


def post_updates_to_log1(
        project_id: int,
        update: str,
        sprint_start: date,
        sprint_end: date,
        update_type: str = "project",
        blocker: str = None
):
    """
    Post updates to log1
    :param project_id: project ID
    :param update: update text
    :param sprint_start: sprint start date
    :param sprint_end: sprint end date
    :param update_type: type of update
    :param blocker: blocker text
    :return: dict with status code and response body
    """
    headers = {
        "Accept": "application/json",
    }
    data = {
        "update": update,
        "blocker": blocker,
        "start": sprint_start.strftime("%Y-%m-%d"),
        "end": sprint_end.strftime("%Y-%m-%d"),
        "type": update_type
    }
    url = f"{LOG1_URL}/engineers/{project_id}/remote_project/update/?api_key={LOG1_API_KEY}"
    response = requests.put(url=url, headers=headers, data=data)
    return {
        "statusCode": response.status_code,
        "body": json.dumps({'text': response.text}),
    }


def fetch_user_details(user_id: str):
    try:
        response = SLACK_CLIENT.users_info(user=user_id)
        if response['ok']:
            return {'ok': True, 'res': response['user']}
    except SlackApiError as e:
        print('Error occurred while fetching user details. : ', e)
        return {'ok': False, 'res': {}}


def post_message_as_user(channel_id: str, message_blocks: list, user_id: str):
    """
    :param channel_id: Channel ID of project channel
    :param message_blocks: The message body
    :param user_id: Engineer's slack user ID
    """
    user_details = fetch_user_details(user_id)
    if user_details['ok']:
        user_details = user_details['res']
        return SLACK_CLIENT.chat_postMessage(
            channel=channel_id,
            text="Update posted!",
            blocks=message_blocks,
            # as_user=False,
            username=user_details['profile']['display_name'],
            icon_url=user_details['profile']['image_original'],
            user=user_id
        )
    else:
        return 'Error occurred, while fetching user details!'


def get_update_channel_settings_modal(channel_id: str):
    query = fetch_channel_details(channel_id)
    if query['Count'] > 0:
        item = query['Items'][0]
        modal = get_setup_modal(channel_id)
        blocks = modal['blocks']
        modal['private_metadata'] = 'update_settings_view'
        # Project ID
        blocks[3]['element']['initial_value'] = str(item['project_id'])
        blocks[3]['block_id'] = 'PID'
        # Engineer
        blocks[5]['element']['initial_user'] = item['user_id']
        blocks[5]['block_id'] = 'UID'
        # Scrum
        blocks[7]['element']['initial_user'] = item['scrum_id']
        blocks[7]['block_id'] = 'SID'
        # Days
        initial_days_options = []
        for day in item['days']:
            initial_days_options.append(
                {'text': {'type': 'plain_text', 'text': day, 'emoji': True},
                 'value': day}
            )
        blocks[9]['accessory']['initial_options'] = initial_days_options
        blocks[9]['block_id'] = 'DAY'
        return modal


def fetch_channel_details(channel_id: str):
    query = DYNAMO_MAPPING_DB_Table.query(
        KeyConditionExpression='#ci = :ci_value',
        ExpressionAttributeNames={'#ci': 'channel_id'},
        ExpressionAttributeValues={':ci_value': channel_id}
    )
    return query


def update_channel_settings(payload: dict):
    chl_details = retrieve_channel_details(payload)
    print('Updating channel : ', chl_details)
    DYNAMO_MAPPING_DB_Table.put_item(
        Item={
            'channel_id': chl_details['channel_id'],
            'project_id': chl_details['project_id'],
            'user_id': chl_details['user_id'],
            'scrum_id': chl_details['scrum_id'],
            'days': chl_details['days']
        }
    )


def retrieve_channel_details(payload: dict):
    values = payload['view']['state']['values']
    days = [day['value'] for day in values['DAY']['frequency_select-action']['selected_options']]
    return {'channel_id': payload['view']['blocks'][1]['text']['text'],
            "project_id": values['PID']['project_id-action']['value'],
            "user_id": values['UID']['user_select-action']['selected_user'],
            "scrum_id": values['SID']['scrum_select-action']['selected_user'],
            "days": days}
