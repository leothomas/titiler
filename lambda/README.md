
# Titiler in AWS Lambda

Titiler is built on top of [FastAPI](https://github.com/tiangolo/fastapi) which *is a modern, fast (high-performance), web framework for building APIs*. It doesn't work natively with AWS Lambda and API Gateway because it needs a way to handler `event` and `context` instead of raw HTML requests. This is possible by wrapping the FastAPI app with the awesome [mangum](https://github.com/erm/mangum).

```python
from mangum import Mangum
from titiler.main import app

handler = Mangum(app, enable_lifespan=False)
```

## Deployement

1. Get titiler

```bash
$ git clone https://github.com/developmentseed/titiler.git
```

2. Deploy -- Using serverless


2.1. Build Docker image and save package 

```bash
$ cd titiler/lambda

$ docker build --tag lambda:latest .
$ docker run --name lambda -itd lambda:latest /bin/bash
$ docker cp lambda:/tmp/package.zip package.zip
$ docker stop lambda
$ docker rm lambda
```

2.2. Install serverless and update `serverless.yml`

```bash
$ npm install -g serverless
```

```yml
# serverless.yml
service: titiler

provider:
  name: aws
  runtime: python3.7
  stage: ${opt:stage, 'production'}
  region: ${opt:region, 'us-east-1'}

package:
  artifact: package.zip

functions:
  app:
    handler: handler.handler
    memorySize: 2048
    timeout: 10
    environment:
      CPL_TMPDIR: /tmp
      GDAL_CACHEMAX: 25%
      GDAL_DISABLE_READDIR_ON_OPEN: EMPTY_DIR
      GDAL_HTTP_MERGE_CONSECUTIVE_RANGES: YES
      GDAL_HTTP_MULTIPLEX: YES
      GDAL_HTTP_VERSION: 2
      PYTHONWARNINGS: ignore
      VSI_CACHE: TRUE
      VSI_CACHE_SIZE: 1000000
    events:
      - httpApi:
          path: /{proxy+}
          method: '*'
          cors: true
```

2.3. Deploy 

```bash
$ sls deploy --bucket <my-bucket>
```

3. Deploy -- Using CDK

3.1. Install cdk and set up CDK in your AWS account - Only need once per account

```bash
$ npm install cdk -g

$ cdk bootstrap # Deploys the CDK toolkit stack into an AWS environment
```

3.2. Install dependencies

```bash
# Note: it's recommanded to use virtualenv
$ cd titiler && pip install -e .[deploy]
```

3.3. Pre-Generate CFN template

```bash
$ cdk synth <projectname-stage>  # Synthesizes and prints the CloudFormation template for this stack
```

3.4. Deploy

```bash
$ cdk deploy <projectname-stage>
```

**Note:** The CDK commands build the necessary docker image in the background. This may take several minutes depending on internet connection, etc.

**Note:** Due to [compatibility issues](https://github.com/aws/aws-cdk/issues/5877) between some of the aws_cdk libraries and Node v13.X, it's recommended to use Node v12.X
