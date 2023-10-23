from urllib.parse import parse_qs
import json
import requests


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
    print("Updating that meeting started to busy")
    response = requests.post(
        url=response_url,
        json=message
    )
    print(f'response of update:', response.json())
