# AWS Node Reference

Quick-reference for `from diagrams.aws.<category> import <Class>`. Aliases shown in parentheses.

## aws.analytics

```python
from diagrams.aws.analytics import (
    AmazonOpensearchService, Analytics, Athena,
    CloudsearchSearchDocuments, Cloudsearch, DataLakeResource, DataPipeline,
    ElasticsearchService,  # (ES)
    EMRCluster, EMREngineMaprM3, EMREngineMaprM5, EMREngineMaprM7,
    EMREngine, EMRHdfsCluster, EMR,
    GlueCrawlers, GlueDataCatalog, Glue,
    KinesisDataAnalytics, KinesisDataFirehose, KinesisDataStreams,
    KinesisVideoStreams, Kinesis,
    LakeFormation, ManagedStreamingForKafka, Quicksight,
    RedshiftDenseComputeNode, RedshiftDenseStorageNode, Redshift,
)
```

## aws.compute

```python
from diagrams.aws.compute import (
    AppRunner,
    ApplicationAutoScaling,  # (AutoScaling)
    Batch, ComputeOptimizer, Compute,
    EC2Ami,  # (AMI)
    EC2AutoScaling, EC2ContainerRegistryImage, EC2ContainerRegistryRegistry,
    EC2ContainerRegistry,  # (ECR)
    EC2ElasticIpAddress, EC2ImageBuilder, EC2Instance, EC2Instances,
    EC2Rescue, EC2SpotInstance, EC2,
    ElasticBeanstalkApplication, ElasticBeanstalkDeployment,
    ElasticBeanstalk,  # (EB)
    ElasticContainerServiceContainer, ElasticContainerServiceServiceConnect,
    ElasticContainerServiceService, ElasticContainerServiceTask,
    ElasticContainerService,  # (ECS)
    ElasticKubernetesService,  # (EKS)
    Fargate, LambdaFunction, Lambda, Lightsail, LocalZones, Outposts,
    ServerlessApplicationRepository,  # (SAR)
    VmwareCloudOnAWS, Wavelength,
)
```

## aws.database

```python
from diagrams.aws.database import (
    AuroraInstance, Aurora,
    DatabaseMigrationServiceDatabaseMigrationWorkflow,
    DatabaseMigrationService,  # (DMS)
    Database,  # (DB)
    DocumentdbMongodbCompatibility,  # (DocumentDB)
    DynamodbAttribute, DynamodbAttributes,
    DynamodbDax,  # (DAX)
    DynamodbGlobalSecondaryIndex,  # (DynamodbGSI)
    DynamodbItem, DynamodbItems, DynamodbStreams, DynamodbTable,
    Dynamodb,  # (DDB)
    ElasticacheCacheNode, ElasticacheForMemcached, ElasticacheForRedis,
    Elasticache,  # (ElastiCache)
    KeyspacesManagedApacheCassandraService, Neptune,
    QuantumLedgerDatabaseQldb,  # (QLDB)
    RDSInstance, RDSMariadbInstance, RDSMysqlInstance, RDSOnVmware,
    RDSOracleInstance, RDSPostgresqlInstance, RDSSqlServerInstance, RDS,
    RedshiftDenseComputeNode, RedshiftDenseStorageNode, Redshift, Timestream,
)
```

## aws.general

```python
from diagrams.aws.general import (
    Client, Disk, Forums, General, GenericDatabase, GenericFirewall,
    GenericOfficeBuilding,  # (OfficeBuilding)
    GenericSamlToken, GenericSDK,
    InternetAlt1, InternetAlt2, InternetGateway, Marketplace,
    MobileClient, Multimedia, OfficeBuilding, SamlToken, SDK, SslPadlock,
    TapeStorage, Toolkit, TraditionalServer, User, Users,
)
```

## aws.integration

```python
from diagrams.aws.integration import (
    ApplicationIntegration, Appsync, ConsoleMobileApplication,
    EventResource, EventbridgeCustomEventBusResource,
    EventbridgeDefaultEventBusResource, EventbridgeEvent,
    EventbridgePipes, EventbridgeRule,
    EventbridgeSaasPartnerEventBusResource, EventbridgeScheduler,
    EventbridgeSchema, Eventbridge, ExpressWorkflows, MQ,
    SimpleNotificationServiceSnsEmailNotification,
    SimpleNotificationServiceSnsHttpNotification,
    SimpleNotificationServiceSnsTopic,
    SimpleNotificationServiceSns,  # (SNS)
    SimpleQueueServiceSqsMessage, SimpleQueueServiceSqsQueue,
    SimpleQueueServiceSqs,  # (SQS)
    StepFunctions,  # (SF)
)
```

## aws.management

```python
from diagrams.aws.management import (
    AmazonDevopsGuru, AmazonManagedGrafana, AmazonManagedPrometheus,
    AmazonManagedWorkflowsApacheAirflow, AutoScaling, Chatbot,
    CloudformationChangeSet, CloudformationStack, CloudformationTemplate,
    Cloudformation, Cloudtrail,
    CloudwatchAlarm, CloudwatchEventEventBased, CloudwatchEventTimeBased,
    CloudwatchLogs, CloudwatchRule, Cloudwatch,
    Codeguru, CommandLineInterface, Config, ControlTower,
    LicenseManager, ManagedServices, ManagementAndGovernance,
    ManagementConsole,
    OpsworksApps, OpsworksDeployments, OpsworksInstances, OpsworksLayers,
    OpsworksMonitoring, OpsworksPermissions, OpsworksResources,
    OpsworksStack, Opsworks,
    OrganizationsAccount, OrganizationsOrganizationalUnit, Organizations,
    PersonalHealthDashboard, Proton, ServiceCatalog,
    SystemsManagerAppConfig, SystemsManagerAutomation,
    SystemsManagerDocuments, SystemsManagerInventory,
    SystemsManagerMaintenanceWindows, SystemsManagerOpscenter,
    SystemsManagerParameterStore,  # (ParameterStore)
    SystemsManagerPatchManager, SystemsManagerRunCommand,
    SystemsManagerStateManager,
    SystemsManager,  # (SSM)
    TrustedAdvisorChecklistCost, TrustedAdvisorChecklistFaultTolerant,
    TrustedAdvisorChecklistPerformance, TrustedAdvisorChecklistSecurity,
    TrustedAdvisorChecklist, TrustedAdvisor,
    UserNotifications, WellArchitectedTool,
)
```

## aws.network

```python
from diagrams.aws.network import (
    APIGatewayEndpoint, APIGateway, AppMesh, ClientVpn, CloudMap,
    CloudFrontDownloadDistribution, CloudFrontEdgeLocation,
    CloudFrontStreamingDistribution,
    CloudFront,  # (CF)
    DirectConnect,
    ElasticLoadBalancing,  # (ELB)
    ElbApplicationLoadBalancer,  # (ALB)
    ElbClassicLoadBalancer,  # (CLB)
    ElbNetworkLoadBalancer,  # (NLB)
    Endpoint,
    GlobalAccelerator,  # (GAX)
    InternetGateway,  # (IGW)
    Nacl, NATGateway, NetworkFirewall, NetworkingAndContentDelivery,
    PrivateSubnet, Privatelink, PublicSubnet,
    Route53HostedZone, Route53, RouteTable, SiteToSiteVpn,
    TransitGatewayAttachment,  # (TGWAttach)
    TransitGateway,  # (TGW)
    VPCCustomerGateway, VPCElasticNetworkAdapter,
    VPCElasticNetworkInterface, VPCFlowLogs, VPCPeering, VPCRouter,
    VPCTrafficMirroring, VPC, VpnConnection, VpnGateway,
)
```

## aws.security

```python
from diagrams.aws.security import (
    AdConnector, Artifact, CertificateAuthority,
    CertificateManager,  # (ACM)
    CloudDirectory,
    Cloudhsm,  # (CloudHSM)
    Cognito, Detective,
    DirectoryService,  # (DS)
    FirewallManager,  # (FMS)
    Guardduty,
    IdentityAndAccessManagementIamAccessAnalyzer,  # (IAMAccessAnalyzer)
    IdentityAndAccessManagementIamAddOn,
    IdentityAndAccessManagementIamAWSStsAlternate,
    IdentityAndAccessManagementIamAWSSts,  # (IAMAWSSts)
    IdentityAndAccessManagementIamDataEncryptionKey,
    IdentityAndAccessManagementIamEncryptedData,
    IdentityAndAccessManagementIamLongTermSecurityCredential,
    IdentityAndAccessManagementIamMfaToken,
    IdentityAndAccessManagementIamPermissions,  # (IAMPermissions)
    IdentityAndAccessManagementIamRole,  # (IAMRole)
    IdentityAndAccessManagementIamTemporarySecurityCredential,
    IdentityAndAccessManagementIam,  # (IAM)
    InspectorAgent, Inspector,
    KeyManagementService,  # (KMS)
    Macie, ManagedMicrosoftAd,
    ResourceAccessManager,  # (RAM)
    SecretsManager, SecurityHubFinding, SecurityHub,
    SecurityIdentityAndCompliance, SecurityLake,
    ShieldAdvanced, Shield, SimpleAd, SingleSignOn,
    WAFFilteringRule, WAF,
)
```

## aws.storage

```python
from diagrams.aws.storage import (
    Backup,
    CloudendureDisasterRecovery,  # (CDR)
    EFSInfrequentaccessPrimaryBg, EFSStandardPrimaryBg,
    ElasticBlockStoreEBSSnapshot, ElasticBlockStoreEBSVolume,
    ElasticBlockStoreEBS,  # (EBS)
    ElasticFileSystemEFSFileSystem,
    ElasticFileSystemEFS,  # (EFS)
    FsxForLustre, FsxForWindowsFileServer,
    Fsx,  # (FSx)
    MultipleVolumesResource,
    S3AccessPoints, S3GlacierArchive, S3GlacierVault, S3Glacier,
    S3ObjectLambdaAccessPoints,
    SimpleStorageServiceS3BucketWithObjects, SimpleStorageServiceS3Bucket,
    SimpleStorageServiceS3Object,
    SimpleStorageServiceS3,  # (S3)
    SnowFamilySnowballImportExport, SnowballEdge, Snowball, Snowmobile,
    StorageGatewayCachedVolume, StorageGatewayNonCachedVolume,
    StorageGatewayVirtualTapeLibrary, StorageGateway, Storage,
)
```

## Common Aliases Cheat Sheet

| Alias | Full Class | Category |
|-------|-----------|----------|
| `S3` | `SimpleStorageServiceS3` | storage |
| `DDB` | `Dynamodb` | database |
| `DynamodbGSI` | `DynamodbGlobalSecondaryIndex` | database |
| `ECS` | `ElasticContainerService` | compute |
| `EKS` | `ElasticKubernetesService` | compute |
| `ECR` | `EC2ContainerRegistry` | compute |
| `ALB` | `ElbApplicationLoadBalancer` | network |
| `NLB` | `ElbNetworkLoadBalancer` | network |
| `CF` | `CloudFront` | network |
| `IGW` | `InternetGateway` | network |
| `SNS` | `SimpleNotificationServiceSns` | integration |
| `SQS` | `SimpleQueueServiceSqs` | integration |
| `SF` | `StepFunctions` | integration |
| `IAM` | `IdentityAndAccessManagementIam` | security |
| `IAMRole` | `IdentityAndAccessManagementIamRole` | security |
| `KMS` | `KeyManagementService` | security |
| `ACM` | `CertificateManager` | security |
| `SSM` | `SystemsManager` | management |
| `ParameterStore` | `SystemsManagerParameterStore` | management |
| `ES` | `ElasticsearchService` | analytics |
| `EBS` | `ElasticBlockStoreEBS` | storage |
| `EFS` | `ElasticFileSystemEFS` | storage |
