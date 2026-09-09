-- Dograh Canary Deployment Schema
-- Enables gradual traffic ramp-up with feature flags and metrics

-- Feature flags table
CREATE TABLE IF NOT EXISTS feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL,
  enabled BOOLEAN DEFAULT true,
  percentage INTEGER DEFAULT 0 CHECK (percentage >= 0 AND percentage <= 100),
  rollout_strategy TEXT DEFAULT 'global' CHECK (rollout_strategy IN ('global', 'per_client', 'per_segment')),
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- Initialize Dograh feature flag
INSERT INTO feature_flags (name, enabled, percentage, rollout_strategy)
VALUES ('dograh_enabled', false, 0, 'global')
ON CONFLICT (name) DO NOTHING;

-- Call metrics table for canary monitoring
CREATE TABLE IF NOT EXISTS call_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_id UUID NOT NULL REFERENCES clients(id),
  caller_number TEXT NOT NULL,
  call_sid TEXT NOT NULL,
  routed_to TEXT NOT NULL CHECK (routed_to IN ('dograh', 'textback')),
  timestamp TIMESTAMP DEFAULT now(),
  duration_seconds FLOAT,
  tool_calls INTEGER,
  booking_made BOOLEAN,
  error TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_call_metrics_timestamp ON call_metrics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_call_metrics_client_id ON call_metrics(client_id);
CREATE INDEX IF NOT EXISTS idx_call_metrics_routed_to ON call_metrics(routed_to);

-- Enable RLS
ALTER TABLE feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_metrics ENABLE ROW LEVEL SECURITY;

-- RLS Policies: Nobody can access directly (admin-only via API)
CREATE POLICY rls_feature_flags_none ON feature_flags FOR ALL TO authenticated USING (false);
CREATE POLICY rls_call_metrics_none ON call_metrics FOR ALL TO authenticated USING (false);

-- Service role can access (for API server)
CREATE POLICY rls_feature_flags_service ON feature_flags FOR ALL TO service_role USING (true);
CREATE POLICY rls_call_metrics_service ON call_metrics FOR ALL TO service_role USING (true);

-- Audit logging
CREATE TABLE IF NOT EXISTS canary_audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action TEXT NOT NULL,
  old_value JSONB,
  new_value JSONB,
  changed_by TEXT,
  timestamp TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_canary_audit_timestamp ON canary_audit_log(timestamp DESC);

ALTER TABLE canary_audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_audit_none ON canary_audit_log FOR ALL TO authenticated USING (false);
CREATE POLICY rls_audit_service ON canary_audit_log FOR ALL TO service_role USING (true);

-- Function to log feature flag changes
CREATE OR REPLACE FUNCTION log_feature_flag_change()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO canary_audit_log (action, old_value, new_value, changed_by)
  VALUES (
    'feature_flag_updated',
    to_jsonb(OLD),
    to_jsonb(NEW),
    current_user
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to audit feature flag changes
DROP TRIGGER IF EXISTS trigger_feature_flag_audit ON feature_flags;
CREATE TRIGGER trigger_feature_flag_audit
AFTER UPDATE ON feature_flags
FOR EACH ROW
EXECUTE FUNCTION log_feature_flag_change();

-- Helper function to get current rollout percentage
CREATE OR REPLACE FUNCTION get_dograh_rollout_percentage()
RETURNS INTEGER AS $$
  SELECT COALESCE(percentage, 0)
  FROM feature_flags
  WHERE name = 'dograh_enabled'
  LIMIT 1;
$$ LANGUAGE sql;

-- Helper function to get canary health
CREATE OR REPLACE FUNCTION get_canary_health(hours_back INTEGER DEFAULT 1)
RETURNS JSONB AS $$
WITH recent_calls AS (
  SELECT *
  FROM call_metrics
  WHERE timestamp > now() - (hours_back || ' hours')::INTERVAL
),
stats AS (
  SELECT
    COUNT(*) as total_calls,
    COUNT(CASE WHEN routed_to = 'dograh' THEN 1 END) as dograh_calls,
    COUNT(CASE WHEN routed_to = 'textback' THEN 1 END) as textback_calls,
    COUNT(CASE WHEN booking_made = true THEN 1 END) as bookings,
    COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as errors
  FROM recent_calls
)
SELECT jsonb_build_object(
  'total_calls', total_calls,
  'dograh_calls', dograh_calls,
  'textback_calls', textback_calls,
  'dograh_percentage', ROUND((dograh_calls::FLOAT / NULLIF(total_calls, 0) * 100)::NUMERIC, 2),
  'booking_rate', ROUND((bookings::FLOAT / NULLIF(dograh_calls, 0) * 100)::NUMERIC, 2),
  'error_rate', ROUND((errors::FLOAT / NULLIF(dograh_calls, 0) * 100)::NUMERIC, 2)
)
FROM stats;
$$ LANGUAGE sql;
