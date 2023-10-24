import json


def get_message() -> dict:
    return json.load(open('templates/message.json'))


