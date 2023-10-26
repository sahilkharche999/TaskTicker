import ast
import json
import os
from urllib.parse import parse_qs

import boto3
import requests

# mndp_client = boto3.session.Session(profile_name='mndp', region_name='ap-south-1')
tbl_name = os.environ.get('DB_TABLE_NAME')
dynamodb = boto3.client('dynamodb')


def is_from_slack(event: dict) -> bool:
    return event.get('headers', {}).get('User-Agent').startswith('Slackbot 1.0')


def is_slack_command(body: dict) -> bool:
    return "command" in body.keys()


def is_slack_submit(slack_payload) -> bool:
    return any(map(lambda x: x['action_id'] == 'setup_submit', slack_payload['actions']))


def parse_slack_event_body(event: dict) -> dict:
    return parse_qs(event.get('body'))


def get_payload(body: dict):
    return json.loads(body.get('payload')[0])


def update_slack_message(response_url: str, message: dict):
    response = requests.post(
        url=response_url,
        json=message
    )


def parse_db_response(res: str) -> list:
    to_list = ast.literal_eval(res)
    if isinstance(to_list, list):
        return to_list


def retrieve_project_details(payload: dict) -> dict:
    data = {'project_id': payload['state']['values']['vG6RL']['plain_text_input-action']['value'],
            'engineer': payload['state']['values']['pfx1W']['user_select-action']['selected_user'],
            'scrum': payload['state']['values']['jdZjD']['user_select-action']['selected_user'],
            'channel': payload['channel']['id']}
    freq = []
    for x in payload['state']['values']['9PkmD']['multi_static_select-action']['selected_options']:
        freq.append(x['value'])
    data['frequency'] = freq
    return data


def save_to_db(payload: dict):
    new_project = retrieve_project_details(payload)
    freq = new_project['frequency']
    freq.append('FRIDAY')
    del new_project['frequency']
    db_data = {}
    for i in freq:
        request_item = {tbl_name: {'Keys': [{'week_day': {'S': i}}]}}
        batch_items = dynamodb.batch_get_item(
            RequestItems=request_item)
        day = batch_items['Responses'][tbl_name][0]['week_day']['S']
        val = parse_db_response(batch_items['Responses'][tbl_name][0]['projects']['S'])
        val.append(new_project)
        db_data[day] = val
    print(db_data)
    for k, v in db_data.items():
        update_item(key=k, val=v)


def update_item(key, val):
    primary_key = {
        'week_day': {'S': key}
    }

    update_expression = "SET projects = :value1"
    expression_attribute_values = {
        ':value1': {'S': str(val)}
    }

    update_params = {
        'TableName': tbl_name,
        'Key': primary_key,
        'UpdateExpression': update_expression,
        'ExpressionAttributeValues': expression_attribute_values,
    }

    response = dynamodb.update_item(**update_params)
    print(response)
