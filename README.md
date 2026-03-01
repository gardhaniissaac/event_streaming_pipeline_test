# event_streaming_pipeline_test
# CRM Funnel Event Processor

## Overview

This project simulates an end-to-end CRM funnel pipeline fully locally using:

- FastAPI (Ingestion Service)
- Apache Kafka (Event Streaming)
- Python Kafka Consumer (Funnel Processor)
- PostgreSQL (Funnel Database)
- Docker Compose (Orchestration)

The system captures structured chat events and builds a CRM funnel table with the following fields:

- leads_date
- channel
- phone_number
- booking_date
- transaction_date
- transaction_value

---

# Architecture

Client → Ingestion API → Kafka Topic (`crm_messages`) → Funnel Processor → PostgreSQL (`room_funnel`)

---

# 1️⃣ Step-by-Step Deployment Guide

## Prerequisites

- Docker
- Docker Compose

---

## Step 1 — Clone Repository

```bash
git clone <your-repo-url>
cd <your-project-folder>
```

---

## Step 2 — Start All Services

```bash
docker-compose up --build
```

Wait until you see:

```
Connected to Kafka
CRM Funnel Processor Started...
```

---

## Step 3 — Verify Containers

```bash
docker ps
```

You should see:

- kafka
- zookeeper (if using ZK mode)
- postgres
- ingestion
- processor

---

## Step 4 — Test the Pipeline

Use curl to send events (examples below).

---

# 2️⃣ Payload Examples

All events are sent to the ingestion service.

Assume ingestion runs at:

```
http://localhost:8000
```

---

## A. Create Room (Lead Stage)

```bash
curl -X POST http://localhost:8000/webhook/create_room \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "1375619",
    "room_name": "Instagram Room",
    "creator": "guest@qiscus.com",
    "channel": "instagram"
}'

```

Effect:
- Creates room in DB
- Sets leads_date
- Sets channel

---

## B. Booking Form Message

```bash
curl -X POST http://localhost:8000/webhook/post_comment \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "1375619",
    "user_id": "guest@qiscus.com",
    "message": "booking form:\nphone_number: +628123456789\nbooking date: 2026-01-01"
}'
```

Effect:
- Extracts phone_number
- Extracts booking_date

---

## C. Admin Confirmation With Price

```bash
curl -X POST http://localhost:8000/webhook/post_comment \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "1375619",
    "user_id": "admin@company.com",
    "message": "Confirmation\nbooking form:\nphone_number: +628123456789\nbooking date: 2026-01-01\n\nThe price would be Rp 500.000"
}'
```

Effect:
- Extracts transaction_value

---

## D. Payment Received

```bash
curl -X POST http://localhost:8000/webhook/post_comment \
  -H "Content-Type: application/json" \
  -d '{
    "room_id": "1375619",
    "user_id": "admin@company.com",
    "message": "Payment received Rp 500.000"
}'
```

Effect:
- Sets transaction_date
- Sets transaction_value (if not already set)

---

# 3️⃣ Accessing the Database

## Option A — Using Docker Exec

Enter PostgreSQL container:

```bash
docker exec -it postgres psql -U admin -d crm
```

List tables:

```sql
\dt
```

Query funnel table:

```sql
SELECT * FROM room_funnel;
```

---

## Option B — From Host (If Port Exposed)

If docker-compose exposes:

```
5432:5432
```

Connect via:

```bash
psql -h localhost -U admin -d crm
```

Password:

```
admin
```

Then run:

```sql
SELECT * FROM room_funnel;
```

---

# Database Schema

```sql
CREATE TABLE room_funnel (
    room_id TEXT PRIMARY KEY,
    channel TEXT,
    phone_number TEXT,
    leads_date TIMESTAMP,
    booking_date TIMESTAMP,
    transaction_date TIMESTAMP,
    transaction_value NUMERIC
);
```

---

# Funnel Logic

| Stage | Trigger | Fields Updated |
|--------|----------|---------------|
| Lead | ROOM_CREATED | leads_date, channel |
| Booking | booking form message | phone_number, booking_date |
| Transaction | price message | transaction_value |
| Payment | payment received | transaction_date |

Updates are idempotent:
- Existing non-null values are not overwritten.

---

# Restarting Clean Environment

To reset everything:

```bash
docker-compose down -v
docker-compose up --build
```

`-v` removes volumes (database reset).

---

# Logs

View processor logs:

```bash
docker logs -f processor
```

View ingestion logs:

```bash
docker logs -f ingestion
```

---