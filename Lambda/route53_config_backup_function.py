import boto3
import json
import os
from datetime import datetime, timezone
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    AWSConfigRuleEvent,
    event_source,
)

# Configure logger
logger = Logger()

# Global variables
aws_route53 = boto3.client("route53")
aws_s3 = boto3.client("s3")
aws_config = boto3.client("config")


@dataclass
class ConfigItem:
    resource_id: str
    resource_type: str
    configuration_item_status: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigItem":
        return cls(
            resource_id=data.get("resourceId", ""),
            resource_type=data.get("resourceType", ""),
            configuration_item_status=data.get("configurationItemStatus", "").lower(),
        )

    @property
    def is_route53_hosted_zone(self) -> bool:
        return self.resource_type == "AWS::Route53::HostedZone"

    @property
    def hosted_zone_id(self) -> str:
        return self.resource_id.split("/")[-1]

    @property
    def trigger_type(self) -> str:
        return (
            "creation"
            if self.configuration_item_status == "resourcediscovered"
            else "change"
        )


@dataclass
class ResourceRecordSet:
    name: str
    type: str
    ttl: Optional[int] = None
    resource_records: list[dict[str, str]] = field(default_factory=list)
    alias_target: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResourceRecordSet":
        return cls(
            name=data.get("Name", ""),
            type=data.get("Type", ""),
            ttl=data.get("TTL"),
            resource_records=data.get("ResourceRecords", []),
            alias_target=data.get("AliasTarget"),
        )


@dataclass
class HostedZoneDetails:
    id: str
    name: str
    config: dict[str, Any]
    resource_record_sets: list[ResourceRecordSet] = field(default_factory=list)

    @property
    def normalized_name(self) -> str:
        return self.name.rstrip(".")


@dataclass
class BackupMetadata:
    account_id: str
    hosted_zone_id: str
    hosted_zone_name: str
    trigger_type: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    backup_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, str]:
        return {
            "accountId": self.account_id,
            "hostedZoneId": self.hosted_zone_id,
            "hostedZoneName": self.hosted_zone_name,
            "triggerType": self.trigger_type,
            "timestamp": self.timestamp,
            "backupId": self.backup_id,
        }


def fetch_hosted_zone_details(zone_id: str) -> HostedZoneDetails:
    """Fetch hosted zone details from Route53."""
    logger.info(f"Fetching hosted zone details for {zone_id}")
    hosted_zone_response = aws_route53.get_hosted_zone(Id=zone_id)
    logger.debug(f"Hosted zone response: {hosted_zone_response}")

    hosted_zone = hosted_zone_response["HostedZone"]
    hosted_zone_details = HostedZoneDetails(
        id=zone_id, name=hosted_zone["Name"], config=hosted_zone
    )

    # Fetch all record sets
    logger.info(f"Fetching resource record sets for zone {zone_id}")
    record_sets = []

    paginator = aws_route53.get_paginator("list_resource_record_sets")
    page_iterator = paginator.paginate(HostedZoneId=zone_id)

    for page in page_iterator:
        logger.debug(f"Retrieved {len(page['ResourceRecordSets'])} record sets")

        for record_set in page["ResourceRecordSets"]:
            record_sets.append(ResourceRecordSet.from_dict(record_set))

    hosted_zone_details.resource_record_sets = record_sets
    logger.info(f"Total record sets retrieved: {len(record_sets)}")

    return hosted_zone_details


def create_backup_data(
    zone_details: HostedZoneDetails, metadata: BackupMetadata
) -> dict[str, Any]:
    """Create the backup data structure."""
    # Convert resource record sets to dicts for JSON serialization
    record_sets_dicts = []
    for rrs in zone_details.resource_record_sets:
        rrs_dict = {"Name": rrs.name, "Type": rrs.type}
        if rrs.ttl:
            rrs_dict["TTL"] = rrs.ttl
        if rrs.resource_records:
            rrs_dict["ResourceRecords"] = rrs.resource_records
        if rrs.alias_target:
            rrs_dict["AliasTarget"] = rrs.alias_target

        record_sets_dicts.append(rrs_dict)

    # Create the backup structure
    backup_data = {
        "metadata": metadata.to_dict(),
        "hostedZone": zone_details.config,
        "resourceRecordSets": record_sets_dicts,
    }

    return backup_data


def upload_to_s3(data: dict[str, Any], bucket_name: str, s3_key: str) -> bool:
    """Upload the backup data to S3."""
    try:
        logger.info(f"Uploading backup to s3://{bucket_name}/{s3_key}")
        aws_s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(data, indent=2),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        logger.info("Upload successful")
        return True
    except Exception as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        return False


def put_evaluations(
    event: AWSConfigRuleEvent, compliance: str = "NON_COMPLIANT", annotation: str = ""
) -> None:
    aws_config.put_evaluations(
        Evaluations=[
            {
                "ComplianceResourceType": event.invoking_event.configuration_item.resource_type,
                "ComplianceResourceId": event.invoking_event.configuration_item.resource_id,
                "ComplianceType": compliance,
                "OrderingTimestamp": event.invoking_event.configuration_item.configuration_item_capture_time,
                "Annotation": annotation,
            },
        ],
        ResultToken=event.result_token,
    )


@logger.inject_lambda_context
@event_source(data_class=AWSConfigRuleEvent)
def handler(event: AWSConfigRuleEvent, context: LambdaContext) -> None:
    """
    Lambda function handler to backup Route 53 hosted zones.
    This function is triggered by AWS Config when a Route 53 hosted zone
    is created or modified.
    """
    try:
        logger.info("Starting Route53 backup process")
        logger.debug(f"Event: {event}")

        compliance = "NON_COMPLIANT"
        annotation = ""
        # Get hosted zone details
        hosted_zone_id = event.invoking_event.configuration_item.resource_id
        account_id = event.invoking_event.configuration_item.accountid
        trigger_type = (
            "change"
            if event.invoking_event.message_type
            == "ConfigurationItemChangeNotification"
            else "creation"
        )

        logger.info(
            {
                "message": "Processing Route53 hosted zone",
                "hosted_zone_id": hosted_zone_id,
                "trigger_type": trigger_type,
            }
        )

        # Fetch hosted zone details
        zone_details = fetch_hosted_zone_details(hosted_zone_id)

        # Create backup metadata
        metadata = BackupMetadata(
            account_id=account_id,
            hosted_zone_id=hosted_zone_id,
            hosted_zone_name=zone_details.normalized_name,
            trigger_type=trigger_type,
        )

        # Create backup data
        backup_data = create_backup_data(zone_details, metadata)

        # Prepare S3 key
        s3_key = f"route53-backup/{account_id}/{zone_details.normalized_name}/{trigger_type}-{metadata.timestamp}.json"

        # Upload to S3
        bucket_name = os.environ["BACKUP_BUCKET_NAME"]
        success = upload_to_s3(backup_data, bucket_name, s3_key)

        if success:
            compliance = "COMPLIANT"
            annotation = f"Successfully backed up hosted zone {hosted_zone_id}"
            logger.info(
                {
                    "message": "Successfully backed up hosted zone",
                    "hosted_zone_id": hosted_zone_id,
                    "s3_location": f"s3://{bucket_name}/{s3_key}",
                }
            )
        else:
            annotation = f"Failed to upload backup for hosted zone {hosted_zone_id}"
            logger.error(
                {"message": "Failed to upload backup", "hosted_zone_id": hosted_zone_id}
            )

    except Exception as e:
        logger.exception("Error in Route53 backup process")
        annotation = f"Error processing hosted zone: {str(e)}"

    put_evaluations(
        event,
        compliance=compliance,
        annotation=annotation,
    )
