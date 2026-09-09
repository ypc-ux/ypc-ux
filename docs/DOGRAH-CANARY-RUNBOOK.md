# Dograh Canary Deployment Runbook

Live operational guide for executing Phase B (canary deployment).

---

## Pre-Deployment Checklist (Do This First)

- [ ] Dograh instance running and healthy
- [ ] All Switchboard code built and tested locally
- [ ] Database migrations applied (`0003_dograh_canary.sql`)
- [ ] Environment variables configured
- [ ] Monitoring dashboards created
- [ ] Alerts configured
- [ ] On-call engineer standing by
- [ ] Rollback procedures reviewed
- [ ] Team notified

---

## Step 1: Apply Database Migration

```bash
# Connect to Supabase
supabase link --project-ref <project-id>

# Apply migration
supabase migration up

# Verify tables created
supabase db query "SELECT * FROM feature_flags WHERE name = 'dograh_enabled';"
# Should return: { name: 'dograh_enabled', enabled: false, percentage: 0, ... }

# Test helper functions
supabase db query "SELECT get_dograh_rollout_percentage();"
# Should return: 0

supabase db query "SELECT get_canary_health(1);"
# Should return: { total_calls: 0, dograh_calls: 0, ... }
```

---

## Step 2: Deploy Switchboard (Code)

```bash
# Build and test
npm run typecheck
npm run build

# Deploy to production
# Option A: Vercel
vercel deploy --prod

# Option B: Docker
docker build -t switchboard:canary .
docker push <registry>/switchboard:canary
kubectl apply -f k8s/deployment.yaml  # or equivalent

# Verify deployment
curl https://switchboard.yourdomain.com/api/health
# Should return: { status: "ok", version: "..." }

# Verify endpoints accessible
curl -X POST https://switchboard.yourdomain.com/api/voice/incoming
# Should return: 400 (missing form data, but endpoint is reachable)
```

---

## Step 3: Set Up Monitoring (Before Turning on Canary)

### Datadog Setup (Example)

```bash
# Create dashboards and alerts
# Dashboard: Dograh Canary
# - Graph 1: Call volume by route (dograh vs. textback)
# - Graph 2: Booking rate (goal: >80%)
# - Graph 3: Tool latency (goal: <1s p95)
# - Graph 4: Error rate (goal: <5%)
# - Gauge: Current rollout percentage (updated via API)

# Alerts
# 1. SIP connection down (0 dograh calls for 15min)
# 2. High error rate (>10% of dograh calls)
# 3. Low booking rate (<50% of dograh calls)
# 4. High latency (>2s p95)
```

### CloudWatch Setup (AWS Example)

```bash
# Create metric filters
aws logs put-metric-filter \
  --log-group-name /aws/lambda/switchboard \
  --filter-name DograhErrors \
  --filter-pattern '"dograh" "error"' \
  --metric-transformations metricName=DograhErrors,metricValue=1

# Create alarms
aws cloudwatch put-metric-alarm \
  --alarm-name dograh-error-rate-high \
  --metric-name DograhErrors \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

---

## Step 4: Start Canary at 0% (Dry Run)

This verifies all infrastructure is working without affecting production traffic.

```bash
# Check current rollout
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/status \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Expected response:
# {
#   "percentage": 0,
#   "enabled": false,
#   "updated_at": "2026-09-09T..."
# }

# Check health
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/health \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Expected response:
# {
#   "healthy": true,
#   "issues": ["No calls recorded in last hour"],
#   "metrics": { ... }
# }
```

---

## Step 5: Gradual Traffic Ramp-Up (Phase B)

### Day 1-2: 10% Canary

```bash
# Set rollout to 10%
curl -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 10}'

# Verify
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/status \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Should return: { "percentage": 10, "enabled": true, ... }

# Monitor for 24-48 hours
# Check every 6 hours:
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/health \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Expected metrics (after 24h of calls):
# - total_calls: 10-50 (depending on volume)
# - dograh_calls: 1-5 (10% of total)
# - booking_rate: >60%
# - error_rate: <10%

# Review logs
docker logs switchboard | grep "dograh\|tool\|booking"

# If healthy: proceed to next step
# If issues: stay at 10% and debug
```

### Day 3-4: 25% Canary

```bash
# Increase rollout
curl -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 25}'

# Monitor for 24h
# Same health checks as 10% phase

# Specific things to watch:
# - No SIP connection errors
# - Tool endpoints responding <1s
# - Booking rate stable >60%
# - No duplicate bookings
# - Text-backs sending successfully
```

### Day 5-6: 50% Canary

```bash
# Halfway point - good stopping point for feedback
curl -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 50}'

# Monitor for 24h
# At this point, ~half of calls are using Dograh
# Performance characteristics should be clear

# Metrics to validate:
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/per-client \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Should show per-client metrics:
# [
#   {
#     "client_id": "...",
#     "total_calls": 25,
#     "dograh_routed": 12,
#     "booking_rate": 75,
#     "error_rate": 0
#   },
#   ...
# ]

# If any client has >10% error rate: investigate
# If booking rate < 50%: don't proceed to 100%
```

### Day 7: Full Migration (100%)

```bash
# Only proceed if:
# ✓ No SIP errors
# ✓ Booking rate >= 70%
# ✓ Error rate < 5%
# ✓ Tool latency < 1s p95
# ✓ All metrics stable for 48h

# Go live
curl -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 100}'

# Verify
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/status \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Expected: { "percentage": 100, "enabled": true, ... }

# Final validation:
# - Check all incoming calls are routed to Dograh
# - Monitor SIP connection
# - Watch booking rate for 1 hour
# - Verify text-backs sending
```

---

## Monitoring During Canary

### Hourly Checks

```bash
# Every hour, run health check
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/health \
  -H "Authorization: Bearer ${CRON_SECRET}" | jq

# Expected output:
# {
#   "healthy": true,
#   "issues": [],
#   "metrics": {
#     "total_calls": 42,
#     "dograh_calls": 4,
#     "textback_calls": 38,
#     "dograh_percentage": 9.52,
#     "booking_rate": 75.0,
#     "tool_call_latency_ms": 450,
#     "errors": []
#   }
# }

# If "healthy": false, check "issues" array and investigate
```

### Daily Summary

```bash
#!/bin/bash
# dograh-canary-report.sh

set -e

ADMIN_TOKEN="${CRON_SECRET}"
BASE_URL="https://switchboard.yourdomain.com"

echo "=== Dograh Canary Daily Report ==="
echo "Date: $(date)"
echo ""

echo "1. Status"
curl -s -X GET "$BASE_URL/api/admin/canary/status" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo ""
echo "2. 24h Metrics"
curl -s -X GET "$BASE_URL/api/admin/canary/metrics?hours=24" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo ""
echo "3. Per-Client Metrics"
curl -s -X GET "$BASE_URL/api/admin/canary/per-client?hours=24" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.metrics | sort_by(.error_rate) | reverse'

echo ""
echo "4. Health"
curl -s -X GET "$BASE_URL/api/admin/canary/health" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

# Send summary email
# (configure separately based on your monitoring system)
```

Run this daily:
```bash
chmod +x dograh-canary-report.sh
./dograh-canary-report.sh > canary-report-$(date +%Y%m%d).txt
# Email to stakeholders
```

---

## Rollback Procedures

### If Metrics Look Bad

**Symptoms:**
- Error rate >10%
- Booking rate <50%
- Tool latency >2s
- SIP connection errors

**Immediate Action:**

```bash
# Rollback to previous percentage
curl -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 0}'

# Verify rollback
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/status \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Disable Dograh completely
UPDATE feature_flags SET enabled = false WHERE name = 'dograh_enabled';

# All calls now route to text-back (slice 1 behavior)
```

### Post-Rollback Investigation

1. Check Dograh logs
2. Check Switchboard application logs
3. Verify tool endpoints are responding
4. Check database connectivity
5. Review errors in `call_metrics` table

```sql
-- Find errors
SELECT error, COUNT(*) as count
FROM call_metrics
WHERE error IS NOT NULL
GROUP BY error
ORDER BY count DESC;

-- Find slow calls
SELECT call_sid, duration_seconds, tool_calls
FROM call_metrics
WHERE routed_to = 'dograh'
  AND duration_seconds > 3
ORDER BY duration_seconds DESC;

-- Find problematic clients
SELECT client_id, COUNT(*) as calls, 
       COUNT(CASE WHEN error IS NOT NULL THEN 1 END) as errors
FROM call_metrics
WHERE routed_to = 'dograh'
GROUP BY client_id
HAVING COUNT(CASE WHEN error IS NOT NULL THEN 1 END) > 0
ORDER BY errors DESC;
```

---

## Escalation Path

**Problem → Action:**

| Issue | Check | Action | Escalate To |
|-------|-------|--------|------------|
| SIP connection down | Dograh API health | Restart Dograh container | Ops/Infrastructure |
| Tool latency high | Tool endpoint logs | Check database, add connection pool | Backend Lead |
| Booking rate low | Tool call responses | Review LLM parameter extraction | ML/Prompt Engineer |
| Unexpected rollback | Metrics anomaly | Investigate error patterns | On-call Engineer |

**Escalation Contact Chain:**
1. On-call engineer
2. Backend lead
3. Ops lead
4. Engineering manager (if 1+ hour impact)

---

## Success Criteria for Phase B → Phase C

Before proceeding to 100%, ALL of these must be true:

- [ ] 48+ hours at current percentage with no issues
- [ ] Booking rate ≥ 70% (of routed calls)
- [ ] Error rate < 5% (of routed calls)
- [ ] Tool latency < 1s p95
- [ ] No duplicate bookings
- [ ] SIP connection stable (no connection errors)
- [ ] Text-backs sending 100% (for non-booking calls)
- [ ] Team consensus to proceed

---

## Phase B → Phase C Transition (Full 100%)

Once all criteria met:

```bash
# Final check
curl -X GET https://switchboard.yourdomain.com/api/admin/canary/health \
  -H "Authorization: Bearer ${CRON_SECRET}"

# Should be: { "healthy": true, "issues": [], ... }

# Go to 100%
curl -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout \
  -H "Authorization: Bearer ${CRON_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 100}'

# Monitor closely for next 2 hours
# Then hand off to Phase C ops team
```

---

## Logging & Audit Trail

All rollout changes are automatically logged:

```sql
SELECT * FROM canary_audit_log ORDER BY timestamp DESC;

-- Shows:
-- action: 'feature_flag_updated'
-- old_value: { percentage: 0, ... }
-- new_value: { percentage: 10, ... }
-- changed_by: 'canary-admin'
-- timestamp: '2026-09-09T...'
```

---

## Cost Monitoring During Canary

Track actual costs to validate $X savings prediction:

```bash
# Query Supabase usage
curl -s https://api.supabase.com/platform/projects/<project-id>/usage \
  -H "Authorization: Bearer ${SUPABASE_API_TOKEN}" | jq '.usage'

# Query Dograh usage (if using managed cloud)
# Contact Dograh for usage dashboard link

# Compare vs. Vapi:
# Expected: $X/month (Dograh) vs. $Y/month (Vapi)
```

---

## Quick Reference

**Useful Commands:**

```bash
# Get status
STATUS_CMD='curl -s -X GET https://switchboard.yourdomain.com/api/admin/canary/status -H "Authorization: Bearer ${CRON_SECRET}"'

# Get metrics (last 24h)
METRICS_CMD='curl -s -X GET https://switchboard.yourdomain.com/api/admin/canary/metrics?hours=24 -H "Authorization: Bearer ${CRON_SECRET}"'

# Set rollout (example: 25%)
ROLLOUT_CMD='curl -s -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout -H "Authorization: Bearer ${CRON_SECRET}" -H "Content-Type: application/json" -d "{\"percentage\": 25}"'

# Health check
HEALTH_CMD='curl -s -X GET https://switchboard.yourdomain.com/api/admin/canary/health -H "Authorization: Bearer ${CRON_SECRET}"'

# Full rollback
ROLLBACK_CMD='curl -s -X POST https://switchboard.yourdomain.com/api/admin/canary/rollout -H "Authorization: Bearer ${CRON_SECRET}" -H "Content-Type: application/json" -d "{\"percentage\": 0}"'
```

---

## Next Steps After Phase B Success

Once canary is stable at 100%:

1. Run Phase C: Full Migration checklist
2. Decommission Vapi integration (if running in parallel)
3. Archive Vapi configuration
4. Document actual cost savings
5. Plan Phase D: Optimization work
