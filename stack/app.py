"""Construct App."""

from typing import Any, Union

import os

from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_elasticloadbalancingv2 as elbv2,
)

import config

import docker


class titilerLambdaStack(core.Stack):
    """Titiler Lambda Stack"""

    def __init__(
        self, scope: core.Construct, id: str, code_dir: str = "./", **kwargs: Any,
    ) -> None:
        """Define stack."""
        super().__init__(scope, id, *kwargs)

        lambda_function = _lambda.Function(
            self,
            f"{id}-lambda",
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=self.create_package(code_dir),
            handler="handler.handler",
        )

        apigw.LambdaRestApi(self, f"{id}-endpoint", handler=lambda_function)

    def create_package(self, code_dir: str) -> _lambda.Code:
        """Create the lambda deployment package."""
        client = docker.from_env()
        client.images.build(path=code_dir, dockerfile="Dockerfile", tag="lambda:latest")
        client.containers.run(
            image="lambda:latest",
            command="/bin/sh -c 'cp /tmp/package.zip /local/package.zip'",
            remove=True,
            volumes={os.path.abspath(code_dir): {"bind": "/local/", "mode": "rw"}},
            user=0,
        )
        return _lambda.Code.asset(
            os.path.join(code_dir, "package.zip"), exclude=["cdk.out", ".git"]
        )


class titilerStack(core.Stack):
    """Titiler ECS Fargate + Lambda Stack (invoked through application load balancer)"""

    def __init__(
        self,
        scope: core.Construct,
        id: str,
        cpu: Union[int, float] = 256,
        memory: Union[int, float] = 512,
        mincount: int = 1,
        maxcount: int = 50,
        code_dir: str = "./",
        lambda_code_dir: str = "./lambda",
        **kwargs: Any,
    ) -> None:

        """Define stack."""
        super().__init__(scope, id, *kwargs)

        lambda_function = _lambda.Function(
            self,
            f"{id}-lambda",
            runtime=_lambda.Runtime.PYTHON_3_7,
            code=self.create_package(lambda_code_dir),
            handler="handler.handler",
        )

        vpc = ec2.Vpc(self, f"{id}-vpc", max_azs=2)

        security_group = ec2.SecurityGroup(
            self, f"{id}-securitygroup", allow_all_outbound=True, vpc=vpc
        )

        security_group.connections.allow_from_any_ipv4(
            port_range=ec2.Port(
                protocol=ec2.Protocol.ALL,
                string_representation="All port 80",
                from_port=80,
            ),
            # TODO: review this description
            description="Allows traffic on port 80 from NLB",
        )

        fargate_cluster = ecs.Cluster(self, f"{id}-fargate-cluster", vpc=vpc,)

        task_definition = ecs.FargateTaskDefinition(
            self, f"{id}-fargate-task-definition", cpu=cpu, memory_limit_mib=memory
        )

        container = task_definition.add_container(
            f"{id}-fargate-main-container",
            image=ecs.ContainerImage.from_asset(code_dir, exclude=["cdk.out", ".git"]),
            cpu=cpu,
            environment=dict(
                CPL_TMPDIR="/tmp",
                GDAL_CACHEMAX="75%",
                GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
                GDAL_HTTP_MULTIPLEX="YES",
                GDAL_HTTP_VERSION="2",
                MODULE_NAME="titiler.main",
                PYTHONWARNINGS="ignore",
                VARIABLE_NAME="app",
                VSI_CACHE="TRUE",
                VSI_CACHE_SIZE="1000000",
                WORKERS_PER_CORE="1",
                LOG_LEVEL="error",
            ),
        )
        container.add_port_mappings(ecs.PortMapping(container_port=80))
        fargate_service = ecs.FargateService(
            self,
            f"{id}-fargate-service",
            cluster=fargate_cluster,
            desired_count=mincount,
            task_definition=task_definition,
            security_group=security_group,
        )

        alb = elbv2.ApplicationLoadBalancer(
            self,
            f"{id}-loadbalancer",
            vpc=vpc,
            internet_facing=True,
            security_group=security_group,
        )

        listener = alb.add_listener(f"{id}-listener", port=80)

        listener.add_targets(
            f"{id}-listener-ecs-target",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            # health_check = dict(
            #     port= 'traffic-port',
            #     path= '/',
            #     intervalSecs= 30,
            #     timeoutSeconds= 5,
            #     healthyThresholdCount= 5,
            #     unhealthyThresholdCount= 2,
            #     healthyHttpCodes= "200,301,302"
            # ),
            targets=[fargate_service],
            deregistration_delay=core.Duration.seconds(3),
        )

        listener.add_targets(
            f"{id}-listener-lambda-targets",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[lambda_function],
            deregistration_delay=core.Duration.seconds(3),
        )

    def create_package(self, code_dir: str) -> _lambda.Code:
        """Create the lambda deployment package."""
        client = docker.from_env()
        client.images.build(path=code_dir, dockerfile="Dockerfile", tag="lambda:latest")
        client.containers.run(
            image="lambda:latest",
            command="/bin/sh -c 'cp /tmp/package.zip /local/package.zip'",
            remove=True,
            volumes={os.path.abspath(code_dir): {"bind": "/local/", "mode": "rw"}},
            user=0,
        )
        return _lambda.Code.asset(
            os.path.join(code_dir, "package.zip"), exclude=["cdk.out", ".git"]
        )


class titilerECSStack(core.Stack):
    """Titiler ECS Fargate Stack."""

    def __init__(
        self,
        scope: core.Construct,
        id: str,
        cpu: Union[int, float] = 256,
        memory: Union[int, float] = 512,
        mincount: int = 1,
        maxcount: int = 50,
        code_dir: str = "./",
        **kwargs: Any,
    ) -> None:
        """Define stack."""
        super().__init__(scope, id, *kwargs)

        vpc = ec2.Vpc(self, f"{id}-vpc", max_azs=2)

        cluster = ecs.Cluster(self, f"{id}-cluster", vpc=vpc)

        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            f"{id}-service",
            cluster=cluster,
            cpu=cpu,
            memory_limit_mib=memory,
            desired_count=mincount,
            public_load_balancer=True,
            listener_port=80,
            # task_image_options=dict(
            #     image=ecs.ContainerImage.from_asset(
            #         code_dir, exclude=["cdk.out", ".git"]
            #     ),
            #     container_port=80,
            #     environment=dict(
            #         CPL_TMPDIR="/tmp",
            #         GDAL_CACHEMAX="75%",
            #         GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
            #         GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
            #         GDAL_HTTP_MULTIPLEX="YES",
            #         GDAL_HTTP_VERSION="2",
            #         MODULE_NAME="titiler.main",
            #         PYTHONWARNINGS="ignore",
            #         VARIABLE_NAME="app",
            #         VSI_CACHE="TRUE",
            #         VSI_CACHE_SIZE="1000000",
            #         WORKERS_PER_CORE="1",
            #         LOG_LEVEL="error",
            #     ),
            # ),
        )

        scalable_target = fargate_service.service.auto_scale_task_count(
            min_capacity=mincount, max_capacity=maxcount
        )

        # https://github.com/awslabs/aws-rails-provisioner/blob/263782a4250ca1820082bfb059b163a0f2130d02/lib/aws-rails-provisioner/scaling.rb#L343-L387
        scalable_target.scale_on_request_count(
            "RequestScaling",
            requests_per_target=50,
            scale_in_cooldown=core.Duration.seconds(240),
            scale_out_cooldown=core.Duration.seconds(30),
            target_group=fargate_service.target_group,
        )

        # scalable_target.scale_on_cpu_utilization(
        #     "CpuScaling", target_utilization_percent=70,
        # )

        fargate_service.service.connections.allow_from_any_ipv4(
            port_range=ec2.Port(
                protocol=ec2.Protocol.ALL,
                string_representation="All port 80",
                from_port=80,
            ),
            description="Allows traffic on port 80 from NLB",
        )


app = core.App()

# Tag infrastructure
for key, value in {
    "Project": config.PROJECT_NAME,
    "Stack": config.STAGE,
    "Owner": os.environ.get("OWNER"),
    "Client": os.environ.get("CLIENT"),
}.items():
    if value:
        core.Tag.add(app, key, value)

ecs_stackname = f"{config.PROJECT_NAME}-ecs-{config.STAGE}"
titilerECSStack(
    app,
    ecs_stackname,
    cpu=config.TASK_CPU,
    memory=config.TASK_MEMORY,
    mincount=config.MIN_ECS_INSTANCES,
    maxcount=config.MAX_ECS_INSTANCES,
)

lambda_stackname = f"{config.PROJECT_NAME}-lambda-{config.STAGE}"
titilerLambdaStack(
    app, lambda_stackname,
)

titiler_stackname = f"{config.PROJECT_NAME}-combined-{config.STAGE}"
titilerStack(
    app,
    titiler_stackname,
    cpu=config.TASK_CPU,
    memory=config.TASK_MEMORY,
    mincount=config.MIN_ECS_INSTANCES,
    maxcount=config.MAX_ECS_INSTANCES,
)

app.synth()
