import json


def get_message(channel_id: str) -> dict:
    message = json.load(open('templates/message.json'))
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
