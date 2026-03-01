import json
import re
import time
import logging
from datetime import datetime

import psycopg2
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable


# ==========================================================
# Logging Configuration
# ==========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ==========================================================
# Kafka Consumer Initialization (Retry Until Ready)
# ==========================================================
def create_consumer():
    """
    Create Kafka consumer and retry until broker is available.
    """
    while True:
        try:
            consumer = KafkaConsumer(
                "crm_messages",
                bootstrap_servers="kafka:9092",
                group_id="crm_funnel_processor",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode("utf-8"))
            )
            logger.info("Connected to Kafka")
            return consumer
        except NoBrokersAvailable:
            logger.warning("Kafka not ready, retrying in 5 seconds...")
            time.sleep(5)


consumer = create_consumer()


# ==========================================================
# Postgres Connection
# ==========================================================
conn = psycopg2.connect(
    host="postgres",
    database="crm",
    user="admin",
    password="admin"
)
cur = conn.cursor()


# ==========================================================
# Helper Functions
# ==========================================================

def parse_booking_form(text: str):
    """
    Extract phone number and booking date from structured booking form.

    Expected format:
        booking form:
        phone_number: +62812345678
        booking date: 2026-01-01
    """
    phone_match = re.search(r'phone_number:\s*(\+?\d+)', text)
    booking_match = re.search(r'booking date:\s*([\d\-]+)', text)

    phone = phone_match.group(1) if phone_match else None
    booking_date = None

    if booking_match:
        booking_date = datetime.strptime(booking_match.group(1), "%Y-%m-%d")

    return phone, booking_date


def extract_price(text: str):
    """
    Extract price from message:
        'The price would be Rp 500.000'
    """
    match = re.search(r'Rp\s*([\d\.]+)', text)
    if match:
        return float(match.group(1).replace(".", ""))
    return None


def get_room_state(room_id):
    """
    Retrieve current funnel state from DB.
    Returns dict with nullable fields.
    """
    cur.execute("""
        SELECT channel, phone_number, leads_date,
               booking_date, transaction_date, transaction_value
        FROM room_funnel
        WHERE room_id = %s
    """, (room_id,))

    row = cur.fetchone()

    if row is None:
        return {
            "channel": None,
            "phone_number": None,
            "leads_date": None,
            "booking_date": None,
            "transaction_date": None,
            "transaction_value": None
        }

    return {
        "channel": row[0],
        "phone_number": row[1],
        "leads_date": row[2],
        "booking_date": row[3],
        "transaction_date": row[4],
        "transaction_value": row[5]
    }


def initialize_room_if_not_exists(room_id):
    """
    Ensure room exists in funnel table.
    """
    cur.execute("""
        INSERT INTO room_funnel (room_id)
        VALUES (%s)
        ON CONFLICT (room_id) DO NOTHING
    """, (room_id,))
    conn.commit()


def update_room(room_id, fields: dict):
    """
    Dynamically update only non-null fields safely using parameterized query.
    """
    update_fields = []
    update_values = []

    for column, value in fields.items():
        if value is not None:
            update_fields.append(f"{column} = %s")
            update_values.append(value)

    if not update_fields:
        return

    query = f"""
        UPDATE room_funnel
        SET {", ".join(update_fields)}
        WHERE room_id = %s
    """

    update_values.append(room_id)

    logger.info(f"Executing update: {query}")
    logger.info(f"With values: {update_values}")

    cur.execute(query, update_values)
    conn.commit()


# ==========================================================
# Main Consumer Loop
# ==========================================================
logger.info("CRM Funnel Processor Started...")

for record in consumer:
    event = record.value
    room_id = event["room_id"]
    event_type = event["event_type"]
    now = datetime.now()

    logger.info(f"Processing event: {event}")

    # Ensure room exists
    initialize_room_if_not_exists(room_id)

    # Load current state
    state = get_room_state(room_id)

    updates = {}

    # ======================================================
    # 1️⃣ ROOM_CREATED → Lead Stage
    # ======================================================
    if event_type == "ROOM_CREATED":

        if state["leads_date"] is None:
            updates["leads_date"] = now

        if not state["channel"]:
            updates["channel"] = event.get("channel")

    # ======================================================
    # 2️⃣ MESSAGE_POSTED → Booking / Payment Stage
    # ======================================================
    elif event_type == "MESSAGE_POSTED":

        message = event["message"]

        # -------- Booking Form --------
        if "booking form:" in message:
            phone, booking = parse_booking_form(message.lower())

            if phone and not state["phone_number"]:
                updates["phone_number"] = phone

            if booking and not state["booking_date"]:
                updates["booking_date"] = booking

        # -------- Payment Confirmation --------
        if "payment received" in message.lower():
            if not state["transaction_date"]:
                updates["transaction_date"] = now

        price = extract_price(message)
        if price and not state["transaction_value"]:
            updates["transaction_value"] = price

    # ======================================================
    # 3️⃣ Update DB
    # ======================================================
    logger.info(f"Updating values in {updates}")
    if updates:
        update_room(room_id, updates)

    logger.info(f"[Processed] Room {room_id}")