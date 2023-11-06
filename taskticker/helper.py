import json
import requests
from datetime import date
from urllib.parse import parse_qs
from config import DYNAMO_DB_Table, LOG1_URL



def is_from_slack(event: dict) -> bool:
    return event.get('headers', {}).get('User-Agent').startswith('Slackbot 1.0')


def is_from_aws_event_bridge(event: dict) -> bool:
    return event.get('source') == 'aws.events'


def is_slack_command(body: dict) -> bool:
    return "command" in body.keys()


def is_slack_submit(slack_payload) -> bool:
    return slack_payload.get('type') == 'view_submission'


def is_button_pressed(payload: dict) -> bool:
    return payload.get('type') == 'block_actions' and payload['actions'][0]['type'] == 'button'


def get_button_action_id(payload: dict) -> str:
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


def get_update_modal(channel_id: str) -> dict:
    message = json.load(open('templates/update_modal.json'))['without']
    message['blocks'].insert(1, {
        "type": "section",
        "text": {
            "type": "plain_text",
            "text": channel_id
        }
    })
    return message


def get_updates_reminder_message():
    return json.load(open('templates/update_reminder.json'))


def retrieve_project_details(payload: dict) -> dict:
    state_values = payload['view']['state']['values'].values()
    values = {key: val for state in state_values for key, val in state.items()}
    return {'project_id': values['project_id-action']['value'],
            'engineer': values['user_select-action']['selected_user'],
            'scrum': values['scrum_select-action']['selected_user'],
            'channel': payload['view']['blocks'][1]['text']['text'],
            'frequency': [x['value'] for x in values['frequency_select-action']['selected_options']]
            }


def save_to_db(payload: dict):
    new_project = retrieve_project_details(payload)
    days = new_project.pop('frequency')
    db_data = {}
    for day in days:
        existing_projects = DYNAMO_DB_Table.get_item(Key={'week_day': day}).get('Item', {}).get('projects', [])
        existing_projects.append(new_project)
        db_data[day] = existing_projects
    print(db_data)
    with DYNAMO_DB_Table.batch_writer() as batch:
        for k, v in db_data.items():
            batch.put_item(Item={'week_day': k, 'projects': v})

def post_updates_to_log1(
        update: str,
        sprint_start: date,
        sprint_end: date,
        update_type: str = "project"
):
    """
    Post updates to log1
    :param update: update text
    :param sprint_start: sprint start date
    :param sprint_end: sprint end date
    :param update_type: type of update
    :return: dict with status code and response body
    """
    headers = {
        "Accept": "application/json",
        "authorization": f"Token **********"
    }
    data = {
        "update": "Project update bot test2",
        "start": date.today().strftime("%Y-%m-%d"),
        "end": date.today().strftime("%Y-%m-%d"),
        "type": 'project'
    }
    response = requests.post(url=LOG1_URL, headers=headers, data=data)
    return {
        "statusCode": response.status_code,
        "body": response.text,
    }

