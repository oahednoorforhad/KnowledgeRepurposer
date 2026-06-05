CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    name TEXT,
    job_title TEXT,
    niche TEXT,
    tone TEXT,
    linkedin_headline TEXT,
    bio TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_url TEXT,
    source_type TEXT NOT NULL,
    raw_content TEXT,
    creative_direction TEXT,
    generated_post TEXT NOT NULL,
    model_used TEXT,
    input_tokens        INT,
    output_tokens       INT,
    estimated_cost_usd  NUMERIC(10,6),
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migration (run if upgrading existing DB):
-- ALTER TABLE generations ADD COLUMN IF NOT EXISTS input_tokens INT;
-- ALTER TABLE generations ADD COLUMN IF NOT EXISTS output_tokens INT;
-- ALTER TABLE generations ADD COLUMN IF NOT EXISTS estimated_cost_usd NUMERIC(10,6);

CREATE INDEX IF NOT EXISTS idx_generations_user_id ON generations(user_id);
CREATE INDEX IF NOT EXISTS idx_generations_created_at ON generations(created_at DESC);

-- +goose Up
-- +goose StatementBegin
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ
);
-- +goose StatementEnd

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id    ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);

-- Migration (run if upgrading existing DB):
-- CREATE TABLE IF NOT EXISTS refresh_tokens (
--     id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
--     user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
--     token_hash TEXT NOT NULL,
--     expires_at TIMESTAMPTZ NOT NULL,
--     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
--     revoked_at TIMESTAMPTZ
-- );
-- CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id    ON refresh_tokens(user_id);
-- CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
-- CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
