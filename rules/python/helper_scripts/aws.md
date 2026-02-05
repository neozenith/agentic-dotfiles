---
paths:
  - "**/aws_*.py"
  - "infra/**/*.py"
  - "cdk/**/*.py"
---

# AWS Script Conventions

Rules for scripts interacting with AWS services.

## Authentication

- **ASSUME `AWS_PROFILE` is already exported** in the current session
- Never hardcode credentials or prompt for them
- Scripts should fail clearly if credentials are missing

```python
import os
if not os.environ.get("AWS_PROFILE"):
    log.error("AWS_PROFILE not set. Export it before running this script.")
    sys.exit(1)
```

## Infrastructure Management

- **Always prefer AWS CDK** for deployment management
- Use CDK for infrastructure-as-code, not raw CloudFormation or Terraform

## Caching AWS API Responses

Export JSON results to cache directory to reduce API calls and enable offline analysis:

```python
CACHE_DIR = PROJECT_ROOT / "tmp" / "claude_cache" / SCRIPT_NAME

# Cache file definitions at top of script
EC2_INSTANCES_CACHE = CACHE_DIR / "ec2_instances.json"
LAMBDA_FUNCTIONS_CACHE = CACHE_DIR / "lambda_functions.json"
CLOUDWATCH_METRICS_CACHE = CACHE_DIR / "cloudwatch_metrics.json"

# Default cache timeout: 5 minutes (300 seconds)
CACHE_TIMEOUT = 300
```

## Caching Pattern

```python
import boto3
import json

def get_ec2_instances(force: bool = False) -> list[dict]:
    """Fetch EC2 instances with caching."""
    cache_status = check_cache(CACHE_DIR, [], timeout=CACHE_TIMEOUT, force=force)

    if _is_cache_valid(cache_status) and EC2_INSTANCES_CACHE.exists():
        log.debug("Using cached EC2 instances")
        return json.loads(EC2_INSTANCES_CACHE.read_text())

    log.info("Fetching EC2 instances from AWS...")
    ec2 = boto3.client('ec2')
    response = ec2.describe_instances()

    instances = []
    for reservation in response['Reservations']:
        instances.extend(reservation['Instances'])

    # Cache the result
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    EC2_INSTANCES_CACHE.write_text(json.dumps(instances, default=str, indent=2))

    return instances
```

## Rate Limiting Awareness

AWS APIs have rate limits. Caching helps, but also:
- Use pagination for large result sets
- Implement exponential backoff for retries
- Consider longer cache timeouts for stable data (e.g., VPC configs)

```python
from botocore.config import Config

# Configure retries with exponential backoff
boto_config = Config(
    retries={
        'max_attempts': 3,
        'mode': 'exponential'
    }
)

ec2 = boto3.client('ec2', config=boto_config)
```

## Useful for Triage

When triaging AWS issues:
- Cache CloudWatch metrics and logs locally
- Export findings to JSON for cross-referencing
- Include AWS region and account ID in output for context

```python
sts = boto3.client('sts')
identity = sts.get_caller_identity()
log.info(f"AWS Account: {identity['Account']}, Region: {boto3.Session().region_name}")
```
