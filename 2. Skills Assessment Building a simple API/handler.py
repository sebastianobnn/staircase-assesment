import boto3
from decimal import Decimal
import json
import urllib.request
import urllib.parse
import urllib.error
from uuid import uuid4
import os

lambda_client = boto3.client('lambda')
rekognition_client = boto3.client('rekognition')
dynamodb_client = boto3.client("dynamodb")
s3_client = boto3.client("s3")

JPEG_HEADER = b'\xff\xd8\xff'
JPEG_FOOTER = b'\xff\xd9'
PNG_HEADER = b'\x89\x50\x4e\x47'

def find_values(key, response):
    results = []
    for elem in response:
        results.append(elem[key])
    return results

def make_response(code, body):
    return {
        'statusCode': code,
        'headers': {
            'content-type': 'application/json'
        },
        'body': json.dumps(body)
    }

def presigned_and_callback_url(event, context):

    if 'content-type' in event['headers'] and 'body' in event and event['body']:
        if event['headers']['content-type'] != 'application/json':
            return make_response(400, {
                'error': 'Only application/json is accepted'
            })

        try:

            body = json.loads(event['body'])
            blob_id = str(uuid4())

            if 'callback_url' in body:
                callback_url = body['callback_url']
                data = dynamodb_client.update_item(
                TableName=os.environ['DYNAMODB_TABLENAME'],
                Key={
                    "id": {
                        "S": blob_id
                    }
                },
                UpdateExpression="SET callback_url= :c ",
                ExpressionAttributeValues={
                    ":c": {'S': callback_url}
                },
                ReturnValues="UPDATED_NEW",
            )

            presigned_url = s3_client.generate_presigned_url(
                ClientMethod='put_object', 
                Params={
                    "Bucket" : os.environ['S3_BUCKETNAME'],
                    "Key" : blob_id
                },
                ExpiresIn = 3600,
                HttpMethod = 'PUT'
            )

            return make_response(200, {
                'blob_id': blob_id,
                'upload_url': presigned_url
            })

            return data
        except Exception as e:
            return make_response(500, {
                    'error': 'Unexpected error handling request'
                })

    else:
        return make_response(400, {
                'error': 'Missing fields'
            })

def detect_labels(event, context):
    
    try:
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])

        file_header = s3_client(Bucket=bucket, Key=key, Range="bytes=0-3")['Body'].read()
        if file_header[:3] == JPEG_HEADER:
            file_footer = s3_client.get_object(
                Bucket=bucket, Key=key, Range="bytes=-2")['Body'].read()
            if file_footer[-2:] != JPEG_FOOTER:
                raise Exception()
        elif file_header != PNG_HEADER:
            raise Exception()

        response = rekognition_client.detect_labels(Image={"S3Object": {"Bucket": bucket, "Name": key}})
        labels = find_values("Name", response['Labels'])
        dynamodb_client.update_item(
            TableName=os.environ['DYNAMODB_TABLENAME'],
            Key={
                "id": {
                    "S": key
                }
            },
            UpdateExpression="SET labels= :l ",
            ExpressionAttributeValues={
                ":l": {'SS': labels}
            },
            ReturnValues="UPDATED_NEW",
        )
        s3_client.delete_object(Bucket=bucket, Key=key)
        return make_response(200, {
                'key': key
            })
    except Exception as e:
        return make_response(500, {
                'error': 'Unexpected error handling request'
            })

def get_labels(event, context):
    if 'pathParameters' not in event or not event['pathParameters']['blobId']:
        return make_response(400, {
            "error": "blob id is missing"
        })
    blob_id = event['pathParameters']['blobId']
    response = dynamodb_client.get_item(
            TableName=os.environ['DYNAMODB_TABLENAME'],
            Key={
                "id": {
                    "S": blob_id
                }})
    if 'Item' not in response:
        return make_response(404, {
            "error": "Item not found"
        })
    item = response['Item']

    if 'result' in item and isinstance(item['result'], str):
        item['result'] = json.loads(item['result'])

    return make_response(200, item)

def make_callback(event, context):
    try:
        if(event['Records'][0]['eventName']=='MODIFY'):
            data = event['Records'][0]['dynamodb']['NewImage']
            if('callbackURL' in data):
                requests.post(
                    data['callback_url']['S'],
                    json = {
                        'blob_id': data['id']['S'],
                        'result': json.loads(data['labels']['S'])
                    }
                )
        return make_response(200, {'OK': 'Good'})
    except:
        return make_response(500, {'error': 'Unexpected error handling request'})