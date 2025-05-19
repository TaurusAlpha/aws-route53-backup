# Route 53 EventBridge-Driven Backup Solution

This CloudFormation template ([CloudFormation/eventbridge-backup-solution.yaml](CloudFormation/eventbridge-backup-solution.yaml)) deploys an automated backup solution for AWS Route 53 using EventBridge and Lambda. The solution captures both scheduled and change-driven backups of Route 53 hosted zones and related resources, storing them in a central S3 bucket.

## Features

- **Scheduled Backups:** Periodically backs up all Route 53 hosted zones at a configurable interval.
- **Change-Driven Backups:** Automatically triggers backups when changes are made to Route 53 resources, including:
  - Resource record sets
  - CIDR collections
  - Health checks
  - Traffic policies
- **Centralized Storage:** All backup files are stored in a specified S3 bucket in JSON format.
- **Comprehensive Coverage:** Captures hosted zone configuration, record sets, and additional Route 53 resources.

## Architecture

- **EventBridge Rules:** 
  - One rule triggers scheduled backups.
  - Another rule triggers on Route 53 API changes via CloudTrail.
- **Lambda Function:** 
  - Handles both scheduled and event-driven backups.
  - Gathers Route 53 data and uploads it to S3.
- **IAM Role:** 
  - Grants the Lambda function permissions to read Route 53 data and write to S3.
- **CloudWatch Logs:** 
  - Lambda logs are retained for a configurable number of days.

## Parameters

- `BackupBucketName`: Name of the S3 bucket for storing backups (must exist or be created separately).
- `EventBridgeLambdaFunctionName`: Name for the Lambda function (default: `Route53EventBridgeBackupFunction`).
- `LambdaLogRetentionDays`: CloudWatch log retention (default: 14).
- `EventBridgeScheduledRuleName`: Name for the scheduled EventBridge rule.
- `EventBridgeEventRuleName`: Name for the change-driven EventBridge rule.
- `EventBridgeScheduledBackupFrequency`: Schedule expression for regular backups (default: `rate(24 hours)`).

## Deployment

1. **Prepare an S3 Bucket:**  
   Create or identify an S3 bucket for storing Route 53 backups.

2. **Deploy the Stack:**  
   Use the AWS CLI or AWS Console to deploy the template. Example with AWS CLI:
   ```sh
   aws cloudformation deploy \
     --template-file CloudFormation/eventbridge-backup-solution.yaml \
     --stack-name Route53EventBridgeBackupStack \
     --parameter-overrides BackupBucketName=<YourS3BucketName> \
     --region us-east-1 \
     --capabilities CAPABILITY_NAMED_IAM
   ```
   - Replace `<YourS3BucketName>` with your bucket name.
   - The stack must be deployed in `us-east-1` (Route 53 is a global service).

3. **Verify Outputs:**  
   After deployment, check the stack outputs for:
   - Lambda execution role ARN
   - Lambda function ARN

4. **CloudTrail Requirement:**  
   Ensure CloudTrail is enabled and logging Route 53 API activity for change-driven backups to work.

## Backup File Structure

Each backup file in S3 contains:
- **Metadata:** Account ID, hosted zone ID, name, trigger type, timestamp, backup ID, and event details.
- **Hosted Zone Details:** Configuration and resource record sets.
- **Additional Resources:** Health checks, CIDR blocks, and traffic policies (for scheduled backups).

Files are stored under:
```
route53-backup/<AccountID>/<ZoneName>/<ChangeType>-<Timestamp>.json
```

## Monitoring

- Lambda execution logs are available in CloudWatch Logs under the configured log group.
- Log retention is controlled by the `LambdaLogRetentionDays` parameter.

## Cleanup

To remove the solution, delete the CloudFormation stack:
```sh
aws cloudformation delete-stack --stack-name Route53EventBridgeBackupStack --region us-east-1
```

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.