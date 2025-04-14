# Route 53 Backup Solution

This repository contains two solutions for automating backups of AWS Route 53 hosted zones. Both solutions store backups in an Amazon S3 bucket in JSON format but differ in their functionality and triggers. Additionally, a consolidated deployment option is available to choose between AWS Config or EventBridge for scheduled backups.

## Features

### AWS Config-Based Solution
- **Scheduled Backups**: Automatically backup Route 53 hosted zones at regular intervals.
- **Hosted Zone Creation Monitoring**: Detects and triggers backups when new hosted zones are created.
- **Simplified Scope**: Monitors only hosted zone creation and configuration changes.

### EventBridge-Based Solution
- **Change-Driven Backups**: Triggers backups for changes to Route 53 resources, including:
  - Resource record sets
  - CIDR collections
  - Health checks
  - Traffic policies
- **Scheduled Backups**: Supports regular backups at configurable intervals.
- **Comprehensive Resource Coverage**: Captures additional Route 53 resources beyond hosted zones.

### Consolidated Deployment
- **Flexible Configuration**: Use a single CloudFormation template with an optional parameter to select the service (AWS Config or EventBridge) for scheduled backups.
- **Unified Management**: Simplifies deployment and management of the solution.

## Architecture

The solution consists of the following components:
1. **CloudFormation Templates**:
   - Individual templates for AWS Config and EventBridge solutions.
   - A consolidated template with an optional parameter to choose the service for scheduled backups.
2. **Lambda Functions**:
   - `Route53ConfigBackupFunction`: Handles AWS Config-triggered backups for hosted zones.
   - `EventBridgeRoute53BackupLambda`: Handles EventBridge-triggered backups for both scheduled and change-driven events.
3. **S3 Bucket**: Stores the backup files in a structured format.

## Prerequisites

- **AWS Config**:
  - AWS Config must be enabled in the account.
  - The "record resources" feature must be configured to monitor Route 53 hosted zones.
- **CloudTrail**:
  - A CloudTrail trail must be configured to capture API activity for Route 53.
- **Region**:
  - The solution must be deployed in the `us-east-1` (N. Virginia) region because Route 53 is a global service.
- **AWS CLI**:
  - Installed and configured with appropriate permissions.
- **S3 Bucket**:
  - An S3 bucket for storing backups.
- **IAM Permissions**:
  - Permissions to deploy CloudFormation stacks and manage AWS resources.

## Deployment

### Individual Deployment
1. Clone this repository:
   ```bash
   git clone https://github.com/your-repo/route53-backup.git
   cd route53-backup
   ```

2. Deploy the AWS Config-based solution:
   ```bash
   aws cloudformation deploy \
     --template-file CloudFormation/aws-config-backup.yaml \
     --stack-name Route53ConfigBackupStack \
     --parameter-overrides BackupBucketName=<YourS3BucketName> \
     --region us-east-1 \
     --capabilities CAPABILITY_NAMED_IAM
   ```

3. Deploy the EventBridge-based solution:
   ```bash
   aws cloudformation deploy \
     --template-file CloudFormation/eventbridge-backup.yaml \
     --stack-name Route53EventBridgeBackupStack \
     --parameter-overrides BackupBucketName=<YourS3BucketName> \
     --region us-east-1 \
     --capabilities CAPABILITY_NAMED_IAM
   ```

### Consolidated Deployment
1. Deploy the consolidated solution:
   ```bash
   aws cloudformation deploy \
     --template-file CloudFormation/route53-backup.yaml \
     --stack-name Route53BackupStack \
     --parameter-overrides BackupBucketName=<YourS3BucketName> UseConfigScheduledBackup=Yes \
     --region us-east-1 \
     --capabilities CAPABILITY_NAMED_IAM
   ```

   - Set `UseConfigScheduledBackup` to `Yes` for AWS Config or `No` for EventBridge.

2. Verify the deployment:
   - Check the CloudFormation stack outputs for the Lambda function ARNs and IAM role ARN.
   - Ensure the S3 bucket is accessible and has the correct permissions.

## Configuration

The CloudFormation templates include several configurable parameters:
- **BackupBucketName**: Name of the S3 bucket for storing backups.
- **ConfigRuleName**: Name of the AWS Config rule for triggering backups.
- **EventBridgeScheduledBackupFrequency**: Schedule expression for regular backups (e.g., `rate(24 hours)`).
- **LambdaLogRetentionDays**: Number of days to retain CloudWatch logs.
- **UseConfigScheduledBackup** (Consolidated Template Only): Set to `Yes` to use AWS Config for scheduled backups or `No` to use EventBridge.

Refer to the respective template files for the full list of parameters.

## Usage

### AWS Config-Based Solution
- **Scheduled Backups**: AWS Config triggers the `Route53ConfigBackupFunction` based on a configured schedule.
- **Hosted Zone Creation Monitoring**: Backups are triggered when new hosted zones are created.
- **Backup Format**: Files are uploaded to the S3 bucket in the `route53-backup/<AccountID>/<ZoneName>/schedule-<Timestamp>.json` format.

### EventBridge-Based Solution
- **Scheduled Backups**: EventBridge triggers the `EventBridgeRoute53BackupLambda` function at regular intervals.
- **Change-Driven Backups**: EventBridge triggers backups for changes to Route 53 resources, such as record sets, CIDRs, health checks, and traffic policies.
- **Backup Format**: Files are uploaded to the S3 bucket in the `route53-backup/<AccountID>/<ZoneName>/<ChangeType>-<Timestamp>.json` format.
  - **Note**: Backup files will include only the changes themselves, except for API calls like "recordsets" changes, which provide full information.

## Lambda Functions

### `Route53ConfigBackupFunction`
- Triggered by AWS Config.
- Handles backups for hosted zone creation and scheduled events.

### `EventBridgeRoute53BackupLambda`
- Triggered by EventBridge.
- Handles both scheduled backups and change-driven backups for Route 53 resources.

## Backup Data Structure

Each backup file contains:
- **Metadata**: Account ID, hosted zone ID, name, trigger type, timestamp, and backup ID.
- **Hosted Zone Details**: Configuration and resource record sets.
- **Additional Resources** (EventBridge solution only): Health checks, CIDR blocks, and traffic policies.

## Monitoring and Logs

- CloudWatch Logs are used to monitor the execution of Lambda functions.
- Log retention is configurable via the `LambdaLogRetentionDays` parameter.

## Cleanup

To remove the solution, delete the CloudFormation stack:
```bash
aws cloudformation delete-stack --stack-name <StackName> --region us-east-1
```

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.