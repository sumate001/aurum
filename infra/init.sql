-- AURUM Database Schema

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    broker VARCHAR(20) DEFAULT 'XM',
    action VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10),
    entry DECIMAL(10,2),
    sl DECIMAL(10,2),
    tp1 DECIMAL(10,2),
    tp2 DECIMAL(10,2),
    confidence INTEGER,
    macro_bias VARCHAR(10),
    macro_confidence INTEGER,
    technical_consensus VARCHAR(50),
    reasoning TEXT,
    upcoming_events JSONB,
    status VARCHAR(20) DEFAULT 'PENDING_APPROVAL',
    raw_macro JSONB,
    raw_technical JSONB
);

CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id),
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    mt5_ticket BIGINT,
    lot_size DECIMAL(5,2),
    actual_entry DECIMAL(10,2),
    actual_sl DECIMAL(10,2),
    actual_tp DECIMAL(10,2),
    status VARCHAR(20),
    pnl DECIMAL(10,2),
    close_price DECIMAL(10,2),
    closed_at TIMESTAMPTZ
);

CREATE TABLE seed_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20),
    content TEXT,
    sources JSONB,
    word_count INTEGER
);

CREATE TABLE simulation_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    seed_id UUID REFERENCES seed_documents(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    direction VARCHAR(10),
    confidence INTEGER,
    recommended_tf VARCHAR(10),
    reasoning TEXT,
    raw_output JSONB
);

CREATE TABLE agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES signals(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    agent_name VARCHAR(50),
    signal VARCHAR(10),
    value DECIMAL(10,4),
    metadata JSONB
);

CREATE TABLE calendar_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    event_datetime TIMESTAMPTZ,
    currency VARCHAR(10),
    impact VARCHAR(10),
    event_name VARCHAR(200),
    actual VARCHAR(50),
    forecast VARCHAR(50),
    previous VARCHAR(50),
    surprise_pct DECIMAL(5,2)
);

CREATE INDEX idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_calendar_events_datetime ON calendar_events(event_datetime);
CREATE INDEX idx_agent_logs_signal_id ON agent_logs(signal_id);
