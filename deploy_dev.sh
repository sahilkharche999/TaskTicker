# Only need to uncomment if deploying first time or added new dep in requirements
#rm -r libs/python
#pip install -r requirements.txt -t libs/python

sam build

sam deploy --stack-name taskticker-dev \
  --capabilities CAPABILITY_IAM \
  --region ap-south-1 \
  --resolve-s3 \
  --confirm-changeset \
  --parameter-overrides \
  Environment='dev' \
  Log1Url='https://staging.log1.com/api'


# to delete stack
# sam delete --stack-name taskticker-dev