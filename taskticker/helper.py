import os
import json
import boto3
import requests
from urllib.parse import parse_qs
from config import DYNAMO_DB_Table

tbl_name = os.environ.get('DB_TABLE_NAME')
dynamodb = boto3.client('dynamodb')


def is_from_slack(event: dict) -> bool:
    return event.get('headers', {}).get('User-Agent').startswith('Slackbot 1.0')


def is_from_aws_event_bridge(event: dict) -> bool:
    return event.get('source') == 'aws.events'


def is_slack_command(body: dict) -> bool:
    return "command" in body.keys()


def is_slack_submit(slack_payload) -> bool:
    return slack_payload.get('type') == 'view_submission'


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
