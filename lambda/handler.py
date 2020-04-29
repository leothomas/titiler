"""AWS Lambda handler."""

from mangum import Mangum
from titiler.main import app

handler = Mangum(
    app, 
    api_gateway_base_path="prod",
    enable_lifespan=False
)
