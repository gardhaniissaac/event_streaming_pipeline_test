CREATE TABLE IF NOT EXISTS room_funnel (
    room_id VARCHAR PRIMARY KEY,
    channel VARCHAR,
    phone_number VARCHAR,
    leads_date TIMESTAMP,
    booking_date TIMESTAMP,
    transaction_date TIMESTAMP,
    transaction_value DECIMAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);