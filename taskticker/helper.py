import ast
import json
from urllib.parse import parse_qs

import boto3
import requests

from config import DB_TABLE_NAME

dynamodb = boto3.resource('dynamodb')


def is_from_slack(event: dict) -> bool:
    return event.get('headers', {}).get('User-Agent').startswith('Slackbot 1.0')


def is_from_aws_event_bridge(event: dict) -> bool:
    return event.get('source') == 'aws.events'


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


def parse_db_response(res: str):
    obj = ast.literal_eval(res)
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return obj


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
    del new_project['frequency']
    db_data = {}
    for i in freq:
        create_item_if_not_exists(i)
        table = boto3.resource('dynamodb').Table(DB_TABLE_NAME)
        res = table.get_item(Key={"week_day": i})['Item']
        val = res['projects']
        val.append(new_project)
        db_data[i] = val
    print(db_data)
    for k, v in db_data.items():
        update_item(key=k, val=v)


def update_item(key, val):
    table = boto3.resource('dynamodb').Table(DB_TABLE_NAME)
    update_expression = "SET projects = :value1"
    response = table.update_item(
        Key={
            'week_day': key
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues={
            ':value1': val,
        },
        ReturnValues="UPDATED_NEW"
    )
    print(response)


def create_item_if_not_exists(item):
    table = boto3.resource('dynamodb').Table(DB_TABLE_NAME)
    res = table.get_item(Key={'week_day': item})
    if 'Item' not in res.keys():
        resp = table.put_item(Item={
            'week_day': item,
            'projects': []
        })
        print(resp)
    else:
        print(res)
