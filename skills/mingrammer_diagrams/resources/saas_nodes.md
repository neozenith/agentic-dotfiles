# SaaS Node Reference

Quick-reference for `from diagrams.saas.<category> import <Class>`.

## saas.identity

```python
from diagrams.saas.identity import Auth0, Okta
```

## saas.chat

```python
from diagrams.saas.chat import (
    Discord, Line, Mattermost, Messenger,
    RocketChat, Slack, Teams, Telegram,
)
```

## Other SaaS Categories

| Category | Import | Classes |
|----------|--------|---------|
| `saas.alerting` | `from diagrams.saas.alerting import ...` | `Newrelic`, `Opsgenie`, `Pagerduty`, `Pushover`, `Xmatters` |
| `saas.analytics` | `from diagrams.saas.analytics import ...` | `Dataform`, `Snowflake`, `Stitch` |
| `saas.automation` | `from diagrams.saas.automation import ...` | `N8N` |
| `saas.cdn` | `from diagrams.saas.cdn import ...` | `Akamai`, `Cloudflare`, `Fastly`, `Imperva` |
| `saas.communication` | `from diagrams.saas.communication import ...` | `Twilio` |
| `saas.crm` | `from diagrams.saas.crm import ...` | `Intercom`, `Zendesk` |
| `saas.filesharing` | `from diagrams.saas.filesharing import ...` | `Nextcloud` |
| `saas.logging` | `from diagrams.saas.logging import ...` | `Datadog`, `Newrelic`, `Papertrail` |
| `saas.media` | `from diagrams.saas.media import ...` | `Cloudinary` |
| `saas.payment` | `from diagrams.saas.payment import ...` | `Adyen`, `AmazonPay`, `Paypal`, `Stripe` |
| `saas.recommendation` | `from diagrams.saas.recommendation import ...` | `Recombee` |
| `saas.security` | `from diagrams.saas.security import ...` | `Crowdstrike`, `Sonarqube` |
| `saas.social` | `from diagrams.saas.social import ...` | `Facebook`, `Twitter` |

## Example: Auth0 + Slack Integration Diagram

```python
from diagrams.saas.identity import Auth0
from diagrams.saas.chat import Slack, Teams
from diagrams.aws.compute import Lambda
from diagrams.aws.integration import Eventbridge

auth0 = Auth0("Auth0\nIdP")
notify_lambda = Lambda("Notify")
eb = Eventbridge("Events")
slack = Slack("Slack")
teams = Teams("Teams")

auth0 >> notify_lambda >> eb >> [slack, teams]
```
