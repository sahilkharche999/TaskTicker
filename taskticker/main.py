import json


def lambda_handler(event: dict, context):
    print(f'event: {event}')

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": 'Hello World!'
        })
    }
