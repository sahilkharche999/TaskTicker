import json


def get_message() -> dict:
    return json.load(open('templates/message.json'))


def get_updates_reminder_message():
    return json.load(open('templates/update_reminder.json'))
