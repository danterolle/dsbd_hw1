import os

KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL", "kafka:9092")
CONSUMER_TOPIC = "to-alert-system"
PRODUCER_TOPIC = "to-notifier"
