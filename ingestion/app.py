from fastapi import FastAPI
from kafka import KafkaProducer
import json
from datetime import datetime

app = FastAPI()

producer = KafkaProducer(
    bootstrap_servers='kafka:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# ----------------------------
# CREATE ROOM WEBHOOK
# ----------------------------
@app.post("/webhook/create_room")
async def create_room(payload: dict):

    internal_event = {
        "event_type": "ROOM_CREATED",
        "room_id": payload.get("room_id"),  # optional if available
        "room_name": payload.get("room_name"),
        "channel": payload.get("channel"),
        "creator": payload.get("creator"),
        "participants": payload.get("participants"),
        "timestamp": datetime.utcnow().isoformat()
    }

    print(internal_event)

    producer.send("crm_messages", internal_event)

    return {"status": "room created event published"}


# ----------------------------
# POST COMMENT WEBHOOK
# ----------------------------
@app.post("/webhook/post_comment")
async def post_comment(payload: dict):

    internal_event = {
        "event_type": "MESSAGE_POSTED",
        "room_id": payload["room_id"],
        "sender_id": payload["user_id"],
        "message": payload["message"],
        "timestamp": datetime.utcnow().isoformat()
    }

    print(internal_event)

    producer.send("crm_messages", internal_event)

    return {"status": "message event published"}