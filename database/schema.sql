-- ============================================
-- Supabase Database Schema for AI Chat Application
-- ============================================
-- Run this SQL in your Supabase SQL Editor
-- Dashboard > SQL Editor > New Query
-- ============================================

-- Drop existing tables if you want to start fresh (CAREFUL: This deletes data!)
-- DROP TABLE IF EXISTS session_logs CASCADE;
-- DROP TABLE IF EXISTS sessions CASCADE;

-- ============================================
-- 1. SESSIONS TABLE
-- ============================================
-- Stores chat session metadata
CREATE TABLE IF NOT EXISTS sessions (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    summary TEXT,
    topics JSONB DEFAULT '[]'::jsonb,
    sentiment TEXT,
    metrics JSONB DEFAULT '{}'::jsonb,
    user_rating INTEGER CHECK (user_rating >= 1 AND user_rating <= 5),
    rated_at TIMESTAMPTZ,
    key_outcomes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_sessions_session_id ON sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time DESC);

-- ============================================
-- 2. SESSION_LOGS TABLE
-- ============================================
-- Stores individual messages in chat sessions
CREATE TABLE IF NOT EXISTS session_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('user', 'ai', 'system')),
    message TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_session_logs_session_id ON session_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_session_logs_created_at ON session_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_logs_event_type ON session_logs(event_type);

-- ============================================
-- 3. AUTOMATIC UPDATED_AT TRIGGER
-- ============================================
-- Update the updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_sessions_updated_at ON sessions;
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 4. ROW LEVEL SECURITY (RLS) - OPTIONAL
-- ============================================
-- Enable RLS if you want user-level access control
-- Uncomment these lines if you want to enable RLS

-- ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE session_logs ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users
-- CREATE POLICY "Users can view their own sessions"
--     ON sessions FOR SELECT
--     USING (auth.uid()::text = user_id);

-- CREATE POLICY "Users can insert their own sessions"
--     ON sessions FOR INSERT
--     WITH CHECK (auth.uid()::text = user_id);

-- CREATE POLICY "Users can update their own sessions"
--     ON sessions FOR UPDATE
--     USING (auth.uid()::text = user_id);

-- CREATE POLICY "Users can view their own session logs"
--     ON session_logs FOR SELECT
--     USING (EXISTS (
--         SELECT 1 FROM sessions
--         WHERE sessions.session_id = session_logs.session_id
--         AND sessions.user_id = auth.uid()::text
--     ));

-- CREATE POLICY "Users can insert their own session logs"
--     ON session_logs FOR INSERT
--     WITH CHECK (EXISTS (
--         SELECT 1 FROM sessions
--         WHERE sessions.session_id = session_logs.session_id
--         AND sessions.user_id = auth.uid()::text
--     ));

-- ============================================
-- 5. SAMPLE DATA (OPTIONAL FOR TESTING)
-- ============================================
-- Insert a test session (uncomment to use)
-- INSERT INTO sessions (session_id, user_id, status)
-- VALUES ('123e4567-e89b-12d3-a456-426614174000'::uuid, 'test_user', 'active')
-- ON CONFLICT (session_id) DO NOTHING;

-- ============================================
-- 6. VERIFY SCHEMA
-- ============================================
-- Run these queries to verify your tables were created correctly

-- Check sessions table structure
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'sessions'
-- ORDER BY ordinal_position;

-- Check session_logs table structure
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'session_logs'
-- ORDER BY ordinal_position;

-- Count existing records
-- SELECT 
--     (SELECT COUNT(*) FROM sessions) as session_count,
--     (SELECT COUNT(*) FROM session_logs) as log_count;

-- View recent sessions with message counts
-- SELECT 
--     s.session_id,
--     s.status,
--     s.start_time,
--     s.end_time,
--     s.sentiment,
--     COUNT(sl.id) as message_count
-- FROM sessions s
-- LEFT JOIN session_logs sl ON s.session_id = sl.session_id
-- GROUP BY s.session_id, s.status, s.start_time, s.end_time, s.sentiment
-- ORDER BY s.start_time DESC
-- LIMIT 10;

-- ============================================
-- DONE! Your database is ready to use.
-- ============================================
