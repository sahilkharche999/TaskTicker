import json
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs

import requests
from slack_sdk.errors import SlackApiError

from config import LOG1_URL, LOG1_API_KEY, SLACK_CLIENT, DYNAMO_MAPPING_DB_Table, ADMIN_USERS, DEFAULT_SNOOZE_DELAY, \
    PROJECT_UPDATE_FUNCTION_NAME
from scheduler_worker import schedule_notification

import boto3

from ui_tools import create_setup_complete_message

lambda_client = boto3.client('lambda')


def is_from_slack(event: dict) -> bool:
    return event.get('headers', {}).get('User-Agent').startswith('Slackbot 1.0')


def is_from_aws_event_bridge(event: dict) -> bool:
    return event.get('source') == 'aws.events'


def is_slack_command(body: dict) -> bool:
    return "command" in body.keys()


def is_from_admin(body: dict) -> bool:
    return body['user_id'][0] in ADMIN_USERS


def get_submission_type(payload: dict) -> str:
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


def get_setup_modal(channel_id: str, channel_type: str = 'project', is_update_view: bool = False) -> dict:
    channel_details = fetch_channel_details(channel_id)
    final_channel_type = channel_type if is_update_view else channel_details.get('channel_type', channel_type)

    if final_channel_type == 'standup':
        message = json.load(open('templates/setup_standup_modal.json'))
        # message = json.load(open('taskticker/templates/setup_standup_modal.json'))
        blocks = message['blocks']
        message['blocks'].insert(1, {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": channel_id
            }
        })
        if channel_details and channel_details.get('channel_type') == 'standup':
            # users
            blocks[5]['element']['initial_users'] = channel_details['user_ids']
            # Scrum
            blocks[7]['element']['initial_user'] = channel_details['scrum_id']
            # Days
            if channel_details['days']:
                blocks[9]['accessory']['initial_options'] = [
                    {'text': {'type': 'plain_text', 'text': day}, 'value': day}
                    for day in channel_details['days']]
    else:
        message = json.load(open('templates/setup_modal.json'))
        # message = json.load(open('taskticker/templates/setup_modal.json'))
        blocks = message['blocks']
        message['blocks'].insert(1, {
            "type": "section",
            "text": {
                "type": "plain_text",
                "text": channel_id
            }
        })
        if channel_details and channel_details.get('channel_type') == 'project':
            # Project ID
            if channel_details.get('project_id'):
                blocks[4]['element']['initial_value'] = str(channel_details['project_id'])
            # Engineer
            blocks[6]['element']['initial_user'] = channel_details['user_id']
            # Scrum
            blocks[8]['element']['initial_user'] = channel_details['scrum_id']
            # Days
            if channel_details['days']:
                blocks[10]['accessory']['initial_options'] = [
                    {'text': {'type': 'plain_text', 'text': day}, 'value': day}
                    for day in channel_details['days']]

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


def get_channel_from_action_button(payload: dict) -> str:
    return payload['actions'][0]['value']


def retrieve_setup_details(payload: dict) -> dict:
    state_values = payload['view']['state']['values'].values()
    values = {key: val for state in state_values for key, val in state.items()}
    channel_type = values['channel_type_select-action']['selected_option']['value']

    if channel_type == 'project':
        return {
            'channel_type': channel_type,
            'channel_id': payload['view']['blocks'][1]['text']['text'],
            'project_id': int(values['project_id-action']['value']),
            'user_id': values['user_select-action']['selected_user'],
            'scrum_id': values['scrum_select-action']['selected_user'],
            'days': [x['value'] for x in values['frequency_select-action']['selected_options']]
        }
    return {
        'channel_type': channel_type,
        'channel_id': payload['view']['blocks'][1]['text']['text'],
        'user_ids': values['users_select-action']['selected_users'],
        'scrum_id': values['scrum_select-action']['selected_user'],
        'days': [x['value'] for x in values['frequency_select-action']['selected_options']]
    }


def retrieve_update_details(payload: dict) -> dict:
    state_values = payload['view']['state']['values'].values()
    update_type = payload['view']['private_metadata']
    values = {key: val for state in state_values for key, val in state.items()}
    return {
        'update_type': update_type,
        'update': values['project-update-action']['value'],
        'blocker': values.get('blocker_input-action', {}).get('value'),
    }


def validate_channel_details(details: dict):
    errors = {}
    if not details['project_id']:
        errors['project_id_input'] = "Project ID is required"
    if not details['days']:
        errors['frequency_select_input'] = "Frequency is required"
    return {
        "statusCode": 200,
        "body": json.dumps({
            "response_action": "errors",
            "errors": errors
        })
    } if errors else None


def save_to_db(payload: dict):
    details = retrieve_setup_details(payload)
    # input validations
    # if errors := validate_channel_details(details):
    #     return errors
    res = DYNAMO_MAPPING_DB_Table.put_item(
        Item=details
    )
    if res.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
        SLACK_CLIENT.chat_postEphemeral(
            channel=details['channel_id'],
            user=payload['user']['id'],
            text="Channel setup complete!",
            blocks=create_setup_complete_message(details)
        )
    else:
        SLACK_CLIENT.chat_postEphemeral(
            channel=details['channel_id'],
            user=payload['user']['id'],
            text="Something went wrong. Please try again."
        )
    return {
        "statusCode": 200
    }


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
            username=user_details['profile'].get('real_name'),
            icon_url=user_details['profile'].get('image_original'),
        )
    else:
        return 'Error occurred, while fetching user details!'


def fetch_channel_details(channel_id: str):
    return DYNAMO_MAPPING_DB_Table.get_item(
        Key={
            'channel_id': channel_id
        }
    ).get('Item', {})


def retrieve_channel_details(payload: dict):
    values = payload['view']['state']['values']
    days = [day['value'] for day in values['DAY']['frequency_select-action']['selected_options']]
    return {'channel_id': payload['view']['blocks'][1]['text']['text'],
            "project_id": values['PID']['project_id-action']['value'],
            "user_id": values['UID']['user_select-action']['selected_user'],
            "scrum_id": values['SID']['scrum_select-action']['selected_user'],
            "days": days}


def post_project_update(payload):
    update = retrieve_update_details(payload)
    details = DYNAMO_MAPPING_DB_Table.get_item(
        Key={
            'channel_id': payload['view']['blocks'][1]['text']['text']
        }
    ).get('Item', {})
    print('details', details)
    res = post_updates_to_log1(
        project_id=details['project_id'],
        update=update['update'],
        sprint_start=date.today(),
        sprint_end=date.today(),
        blocker=update['blocker']
    )
    print('log1 response', res)
    res = post_updates_to_slack(
        channel_id=payload['view']['blocks'][1]['text']['text'],
        user={'id': payload['user']['id'], 'username': payload['user']['username']},
        update=update['update'],
        blocker=update['blocker']
    )
    print('slack response', res)
    return {
        "statusCode": 204
    }


def validate_command(body: dict) -> bool:
    return body['user_id'][0] in ADMIN_USERS \
        if body['command'][0] in ['/setup'] \
        else body['command'][0] in ['/update']


def slack_command_handler(body: dict):
    if validate_command(body):
        models = {
            '/setup': get_setup_modal,
            '/update': get_update_modal
        }
        trigger_id = body['trigger_id'][0]
        command = body['command'][0]
        channel_id = body['channel_id'][0]
        res = SLACK_CLIENT.views_open(
            trigger_id=trigger_id,
            view=models[command](channel_id)
        )
        return {"statusCode": 204} \
            if res.status_code == 200 and res.get('ok') \
            else {
            "statusCode": 200,
            "body": json.dumps({"text": "Something went wrong. Please try again."})
        }
    else:
        return {
            "statusCode": 200,
            "body": json.dumps({"text": "You are not authorized to use this command. Please contact admin."})
        }


def slack_view_submit_handler(payload):
    """
    Handler for slack view submission
    :param payload: payload
    :return: response dict
    """
    submission = get_submission_type(payload)
    actions = {
        'project_setup_view': save_to_db,
        'project_update_view': initiate_project_update
    }
    return actions[submission](payload) \
        if submission in actions.keys() \
        else {
        "statusCode": 400,
        "body": json.dumps({"text": "Something went wrong. Contest admin."})
    }


def slack_button_pressed_handler(payload):
    action_id = payload['actions'][0]['action_id']
    print('action id:', action_id)
    if action_id == 'update_now_action':
        channel_id = get_channel_from_action_button(payload)
        print('update now action')
        SLACK_CLIENT.views_open(
            trigger_id=payload['trigger_id'],
            view=get_update_modal(channel_id=channel_id)
        )
        update_slack_message(payload['response_url'], {'text': 'Thanks for updating!'})
    if action_id == 'snooze_action':
        print('update later action')
        channel_id = get_channel_from_action_button(payload)
        schedule_notification(
            user=payload['user']['id'],
            channel_id=channel_id,
            post_at=int(payload['actions'][0]['action_ts'].split('.')[0]) + DEFAULT_SNOOZE_DELAY
        )
        update_slack_message(
            response_url=payload['response_url'],
            message={
                "text": "Okay will remind you in an hour.",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Okay will remind you in an hour.\n"
                                    "Or you can post update anytime with `/update` command"
                        }
                    }
                ]
            })
    return {
        "statusCode": 204
    }


def slack_checkboxes_action_handler(payload):
    action_id = payload['actions'][0]['action_id']
    if action_id == 'blocker-checkbox-action':
        print('blocker checkbox action')
        is_blocker = bool(payload['actions'][0]['selected_options'])
        res = SLACK_CLIENT.views_update(
            view_id=payload['view']['id'],
            hash=payload['view']['hash'],
            view=get_update_modal(
                channel_id=payload['view']['blocks'][1]['text']['text'],
                is_blocker=is_blocker
            )
        )
        print('update view response', res)
    return {
        "statusCode": 204
    }


def switch_channel_type(payload):
    action_id = payload['actions'][0]['action_id']
    if action_id == 'channel_type_select-action':
        selected_option = payload['actions'][0]['selected_option']['value']
        print('switching view to', selected_option)
        res = SLACK_CLIENT.views_update(
            view_id=payload['view']['id'],
            hash=payload['view']['hash'],
            view=get_setup_modal(
                channel_id=payload['view']['blocks'][1]['text']['text'],
                channel_type=selected_option,
                is_update_view=True
            )
        )
        print('update view response', res)
    return {
        "statusCode": 204
    }


def slack_block_actions_handler(payload):
    action_type = payload['actions'][0]['type']
    actions = {
        'button': slack_button_pressed_handler,
        'checkboxes': slack_checkboxes_action_handler,
        'number_input': check_project_id,
        'static_select': switch_channel_type,
        'multi_static_select': lambda x: {"statusCode": 200},
    }
    return actions.get(action_type, lambda x: {"statusCode": 400})(payload)


def check_project_id(payload):
    project_id = payload['actions'][0]['value']
    url = f"{LOG1_URL}/engineering/{project_id}/?api_key={LOG1_API_KEY}"
    res = requests.head(url=url)
    print(res, res.status_code)
    print(res.json())


def initiate_project_update(payload):
    print('initiating project update', payload)
    details = retrieve_update_details(payload)
    channel_id = payload['view']['blocks'][1]['text']['text']
    channel_details = fetch_channel_details(channel_id)
    if channel_details['channel_type'] == 'project':
        lambda_client.invoke(
            FunctionName=PROJECT_UPDATE_FUNCTION_NAME,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )
        return {
            "statusCode": 204
        }
    else:
        print('posting update to slack')
        post_updates_to_slack(
            channel_id=channel_id,
            user={'id': payload['user']['id'], 'username': payload['user']['username']},
            update=details['update'],
            blocker=details['blocker']
        )
        return {
            "statusCode": 204
        }
