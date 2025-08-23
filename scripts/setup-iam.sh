#!/bin/bash
# IAM Role Setup Script for Quitemailingyourself
# Run this script to create the necessary IAM role and policies

set -e

ROLE_NAME="QuitemailingyourselfEC2Role"
POLICY_NAME="QuitemailingyourselfS3Policy"
INSTANCE_PROFILE_NAME="QuitemailingyourselfInstanceProfile"

echo "🚀 Setting up IAM role for Quitemailingyourself..."

# Create trust policy for EC2
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create S3 permissions policy
cat > s3-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::quitemailingmyself",
        "arn:aws:s3:::quitemailingmyself/*"
      ]
    }
  ]
}
EOF

echo "📋 Creating IAM role: $ROLE_NAME"
# Create IAM role
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document file://trust-policy.json \
  --description "Role for Quitemailingyourself EC2 instance to access S3" \
  --output text

echo "📋 Creating S3 policy: $POLICY_NAME"
# Create and attach S3 policy
POLICY_ARN=$(aws iam create-policy \
  --policy-name $POLICY_NAME \
  --policy-document file://s3-policy.json \
  --description "S3 permissions for Quitemailingyourself" \
  --output text --query 'Policy.Arn')

echo "🔗 Attaching policy to role"
aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn $POLICY_ARN

echo "📋 Creating instance profile: $INSTANCE_PROFILE_NAME"
# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME \
  --output text

echo "🔗 Adding role to instance profile"
aws iam add-role-to-instance-profile \
  --instance-profile-name $INSTANCE_PROFILE_NAME \
  --role-name $ROLE_NAME

# Clean up temporary files
rm -f trust-policy.json s3-policy.json

echo ""
echo "✅ IAM setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. When launching your EC2 instance, attach the IAM instance profile:"
echo "   Instance Profile: $INSTANCE_PROFILE_NAME"
echo ""
echo "2. Or attach to existing instance:"
echo "   aws ec2 associate-iam-instance-profile \\"
echo "     --instance-id i-1234567890abcdef0 \\"
echo "     --iam-instance-profile Name=$INSTANCE_PROFILE_NAME"
echo ""
echo "3. Your app will now use IAM role instead of hardcoded credentials!"