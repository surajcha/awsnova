#!/bin/bash
# ─── Nova MKG Lambda Deployment Script ─────────────────────────────────────
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Python 3.11 installed
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
#
# ───────────────────────────────────────────────────────────────────────────

set -e

FUNCTION_NAME="nova-mkg-handler"
REGION="us-east-1"
ROLE_NAME="nova-mkg-lambda-role"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"

echo "=== Step 1: Create deployment package ==="
rm -rf package lambda-package.zip
mkdir package

# Install dependencies
pip install -r requirements.txt -t package/ --platform manylinux2014_x86_64 --only-binary=:all: --python-version 3.11

# Copy lambda code
cp lambda_function.py package/

# Create zip
cd package
zip -r ../lambda-package.zip .
cd ..

echo "=== Step 2: Create IAM Role (if not exists) ==="
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "Role already exists"

# Attach policies
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

# Create inline policy for S3 + Bedrock access
aws iam put-role-policy \
  --role-name $ROLE_NAME \
  --policy-name nova-mkg-s3-bedrock \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:GetObject", "s3:ListBucket"],
        "Resource": ["arn:aws:s3:::*"]
      },
      {
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel"],
        "Resource": ["arn:aws:bedrock:*::foundation-model/*"]
      }
    ]
  }'

echo "Waiting for role to propagate..."
sleep 10

echo "=== Step 3: Create/Update Lambda Function ==="
aws lambda create-function \
  --function-name $FUNCTION_NAME \
  --runtime python3.11 \
  --handler lambda_function.lambda_handler \
  --role $ROLE_ARN \
  --zip-file fileb://lambda-package.zip \
  --timeout 900 \
  --memory-size 2048 \
  --region $REGION \
  --environment "Variables={AWS_REGION=$REGION,NOVA_TEXT_MODEL_ID=amazon.nova-pro-v1:0,NOVA_LITE_MODEL_ID=amazon.nova-lite-v1:0,NOVA_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0,SIMILARITY_THRESHOLD=0.85}" \
  2>/dev/null || \
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://lambda-package.zip \
  --region $REGION

echo "=== Step 4: Create Function URL ==="
aws lambda create-function-url-config \
  --function-name $FUNCTION_NAME \
  --auth-type NONE \
  --cors '{
    "AllowOrigins": ["*"],
    "AllowMethods": ["POST", "OPTIONS"],
    "AllowHeaders": ["Content-Type"]
  }' \
  --region $REGION 2>/dev/null || echo "Function URL already exists"

# Grant public access
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id FunctionURLAllowPublicAccess \
  --action lambda:InvokeFunctionUrl \
  --principal "*" \
  --function-url-auth-type NONE \
  --region $REGION 2>/dev/null || true

# Get the Function URL
FUNCTION_URL=$(aws lambda get-function-url-config \
  --function-name $FUNCTION_NAME \
  --region $REGION \
  --query 'FunctionUrl' --output text)

echo ""
echo "=========================================="
echo "  Deployment complete!"
echo "=========================================="
echo ""
echo "  Lambda Function URL: $FUNCTION_URL"
echo ""
echo "  Paste this URL into the Nova MKG frontend"
echo "  'Lambda Function URL' input field."
echo ""
echo "=========================================="

# Cleanup
rm -rf package lambda-package.zip
