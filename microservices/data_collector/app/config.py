"""
Configuration variables for the Data Collector microservice.
"""

import os

OPENSKY_API_URL: str = "https://opensky-network.org/api"
USER_MANAGER_GRPC_HOST: str = os.environ.get(
    "USER_MANAGER_GRPC_HOST", "user-manager:50051"
)
TOKEN_URL: str = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
DATABASE_URL: str = os.environ.get("DATABASE_URL")
KAFKA_BROKER_URL: str = os.environ.get("KAFKA_BROKER_URL", "kafka:9092")
KAFKA_TOPIC: str = os.environ.get("KAFKA_TOPIC", "to-alert-system")
