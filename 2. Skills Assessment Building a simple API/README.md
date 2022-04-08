# Staircase skills assesment

# Explanation
## How Lambdas works
## **`POST`** /blobs
presigned_and_callback_url -> After a check for content-type JSON request, it generates a blob_id and if callback_url is present inside the request, it creates a new record into DynamoDB table using blob_id like key. It creates a presigned_url using ClientMethod='put_object' and giving a validity time of 1hour
## **`GET`** /blobs/{blobId}
get_labels -> After a check for blobId pathParameters, it retrieves the item from DynamoDB using blob_id like key if it exists and returns the item
## **`PUT`** signedURL
#### Response Body
```json
"body": {
    "blob_id": "<STRING>",
    "upload_url": "<STRING URL>"
}
```
## **`S3`** ObjectCreated Trigger
detect_labels -> It checks if the file is a JPEG or PNG, other image file are not accepted by AWSRekognition, saves labels into DynamoDB using the key retrieved from the event(which corresponds to blob_id), it deletes the object from S3
## **`DYNAMODB`** Stream
make_callback -> When new labels are added into DynamoDB, it makes a POST request to the callback_url saved into the item of the event triggered


#### Possible improvements
- I spent a lot of time to make API gateway works with DynamoDB, but without result, a lot of crashing errors when trying to use serverless-apigateway-service-proxy plugin
