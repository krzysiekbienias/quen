CREATE TABLE universe_instrument (
    instrument_id TEXT PRIMARY KEY,
    provider_symbol TEXT NOT NULL,
    display_name TEXT,
    asset_class TEXT NOT NULL CHECK (
        asset_class IN (
            'EQUITY',
            'INDEX',
            'FX',
            'COMMODITY',
            'RATE',
            'BOND',
            'OTHER'
        )
    ),
    sector TEXT,
    industry TEXT,
    quote_currency TEXT NOT NULL DEFAULT 'USD',
    session_calendar TEXT NOT NULL DEFAULT 'America/New_York',
    country TEXT,
    data_vendor TEXT NOT NULL DEFAULT 'POLYGON',
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    ingest_equity_eod INTEGER NOT NULL DEFAULT 0 CHECK (ingest_equity_eod IN (0, 1)),
    ingest_index_eod INTEGER NOT NULL DEFAULT 0 CHECK (ingest_index_eod IN (0, 1)),
    ingest_priority INTEGER NOT NULL DEFAULT 100,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT, ingest_futures_product INTEGER NOT NULL DEFAULT 0 CHECK (ingest_futures_product IN (0, 1)), ingest_futures_eod INTEGER NOT NULL DEFAULT 0 CHECK (ingest_futures_eod IN (0, 1)),
    UNIQUE (provider_symbol, asset_class)
);
CREATE INDEX idx_universe_instrument_active_equity ON universe_instrument (is_active, ingest_equity_eod);
CREATE INDEX idx_universe_instrument_data_vendor ON universe_instrument (data_vendor, is_active);
CREATE INDEX idx_universe_instrument_active_futures ON universe_instrument (is_active, ingest_futures_eod);
CREATE TABLE equity_daily_eod (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    as_of TEXT NOT NULL,
    session_calendar TEXT NOT NULL DEFAULT 'America/New_York',
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    volume REAL,
    vwap REAL,
    trade_count INTEGER,
    source TEXT NOT NULL,
    timespan TEXT NOT NULL DEFAULT '1d',
    adjusted INTEGER NOT NULL CHECK (adjusted IN (0, 1)) DEFAULT 1,
    provider_timestamp_utc_ms INTEGER,
    ingested_at TEXT NOT NULL,
    UNIQUE (ticker, as_of, timespan, adjusted)
);
CREATE INDEX idx_equity_daily_eod_ticker_as_of ON equity_daily_eod (ticker, as_of);
CREATE TABLE index_daily_eod (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    as_of TEXT NOT NULL,
    session_calendar TEXT NOT NULL DEFAULT 'America/New_York',
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    volume REAL,
    vwap REAL,
    trade_count INTEGER,
    source TEXT NOT NULL,
    timespan TEXT NOT NULL DEFAULT '1d',
    adjusted INTEGER NOT NULL CHECK (adjusted IN (0, 1)) DEFAULT 1,
    provider_timestamp_utc_ms INTEGER,
    ingested_at TEXT NOT NULL,
    UNIQUE (ticker, as_of, timespan, adjusted)
);
CREATE INDEX idx_index_daily_eod_ticker_as_of ON index_daily_eod (ticker, as_of);
CREATE TABLE par_curve_eod (
    curve_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    curve_kind TEXT NOT NULL DEFAULT 'treasury_par_fred',
    source TEXT NOT NULL DEFAULT 'FRED',
    day_count TEXT NOT NULL DEFAULT 'Actual365Fixed',
    session_calendar TEXT NOT NULL DEFAULT 'America/New_York',
    notes TEXT,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (curve_id, as_of)
);
CREATE INDEX idx_par_curve_eod_as_of ON par_curve_eod (as_of);
CREATE TABLE par_curve_point_eod (
    curve_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    tenor TEXT NOT NULL,
    tenor_days INTEGER,
    instrument_type TEXT NOT NULL CHECK (
        instrument_type IN ('deposit', 'fra', 'futures', 'swap', 'other')
    ),
    fred_series_id TEXT NOT NULL,
    quoted_rate REAL NOT NULL CHECK (quoted_rate >= 0.0),
    quote_style TEXT NOT NULL DEFAULT 'annualized_decimal', quoted_price REAL,
    PRIMARY KEY (curve_id, as_of, tenor),
    FOREIGN KEY (curve_id, as_of) REFERENCES par_curve_eod (curve_id, as_of) ON DELETE CASCADE
);
CREATE INDEX idx_par_curve_point_curve_as_of ON par_curve_point_eod (curve_id, as_of);
