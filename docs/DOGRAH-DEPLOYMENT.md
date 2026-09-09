# Dograh Deployment Guide

Complete step-by-step guide to deploy Dograh integration for Switchboard.

## Prerequisites

- Twilio account with phone number and API credentials
- Supabase project for call/booking/message data
- Server infrastructure (Docker-capable for self-hosted, or managed Dograh account)
- Environment variables configured
- Domain with HTTPS (required for webhooks)

---

## Option A: Self-Hosted Dograh (Recommended for Cost)

### 1. Infrastructure Setup

**Recommended spec:**
- 4 vCPU, 8GB RAM minimum
- 50GB SSD storage
- Public IP or reverse proxy
- Docker & Docker Compose

**Deployment platforms:**
- [Railway.app](https://railway.app) (easiest, $5-20/month)
- [Render.com](https://render.com) (simple, $7-12/month)
- AWS EC2 (t3.medium, $30-50/month)
- Self-managed VPS (Linode, Vultr, etc., $5-10/month)

### 2. Deploy Dograh Stack

```bash
# SSH into server (or use deployment dashboard)
cd /opt/dograh

# Download docker-compose configuration
curl -o docker-compose.yaml https://raw.githubusercontent.com/dograh-hq/dograh/main/docker-compose.yaml

# Set environment variables
export REGISTRY=dograhai
export ENABLE_TELEMETRY=true
export DOGRAH_API_KEY=$(openssl rand -hex 32)  # Generate strong key
export DOGRAH_DOMAIN=dograh.yourdomain.com

# Start stack (includes Postgres, Redis, MinIO, API, UI)
docker compose up --pull always -d

# Verify all services are running
docker compose ps

# Check logs
docker compose logs -f api
```

**Expected startup time:** 2-3 minutes

**Access Dograh UI:** https://dograh.yourdomain.com (auto-provisioned HTTPS via Let's Encrypt)

### 3. Configure Dograh

**Step 1: Create Organization**
1. Visit Dograh UI at `https://dograh.yourdomain.com`
2. Create organization (auto-setup on first visit)
3. Note the organization ID

**Step 2: Add Twilio Provider**
1. In Dograh UI → Settings → Providers
2. Click "Add Twilio"
3. Enter:
   - Account SID: (from Twilio console)
   - Auth Token: (from Twilio console)
   - Webhook URL: `https://switchboard.yourdomain.com/api/dograh/webhook`
4. Save and test connection

**Step 3: Assign Phone Number**
1. Dograh → Phone Numbers
2. Select or provision a number
3. Set as "Inbound" (if not already)
4. Configure inbound webhook to `https://switchboard.yourdomain.com/api/dograh/webhook`

**Step 4: Create Workflow**
1. Dograh UI → Workflows → New
2. Manually recreate the workflow from `scripts/dograh-workflow.json`:
   - **Name:** "Appointment Booking Agent"
   - **Start Node:** Incoming Call
   - **Agent Node:**
     - Model: gpt-4o-mini
     - Voice: OpenAI echo
     - System Prompt (from template below)
   - **HTTP Tool Nodes:**
     - check_availability: POST `https://switchboard.yourdomain.com/api/dograh/tools/check-availability`
     - book_appointment: POST `https://switchboard.yourdomain.com/api/dograh/tools/book-appointment`
   - **Webhook Node:** POST `https://switchboard.yourdomain.com/api/dograh/webhook`
   - **End Node:** Hang Up
3. Save workflow

**Workflow Agent System Prompt Template:**
```
You are a professional appointment booking assistant for {{client_name}} in {{client_timezone}}.

BUSINESS HOURS:
{{business_hours}}

SERVICES OFFERED:
{{services_json}}

FREQUENTLY ASKED QUESTIONS:
{{faqs_json}}

SPECIAL INSTRUCTIONS:
{{agent_instructions}}

YOUR RESPONSIBILITIES:
1. Greet the caller warmly with the business name
2. Ask what service or appointment they're interested in
3. If they want to book:
   - Use the 'check_availability' tool to find open times
   - Suggest the best available slots
   - Once they choose a time, use 'book_appointment' to confirm
   - Collect their name and phone number
   - Confirm the full appointment details
4. If they can't find a suitable time or want to speak to someone:
   - Apologize for any inconvenience
   - Offer to take their information for a callback
   - Or escalate gracefully to a human

Be helpful, professional, and concise. Always confirm appointment details before ending the call.
```

### 4. Test the Deployment

```bash
# From your local machine, test the Dograh SIP endpoint
curl -X POST https://dograh.yourdomain.com/api/health

# Should return 200 OK with service status

# Test workflow by calling the provisioned number
# (you'll need a SIP client or use Dograh's test tool)
```

---

## Option B: Managed Dograh Cloud (Easier, Slightly More Expensive)

### 1. Create Account
1. Go to [dograh.com](https://dograh.com)
2. Sign up for managed cloud account
3. Create organization

### 2. Add Twilio Provider
1. Dograh Dashboard → Integrations → Twilio
2. Enter Twilio Account SID and Auth Token
3. Set inbound webhook: `https://switchboard.yourdomain.com/api/dograh/webhook`

### 3. Create Workflow
Same as self-hosted Step 4 above.

### 4. Notes
- **Cost:** $0.01/minute usage-based
- **No maintenance:** Dograh handles infrastructure
- **Regional:** Data stays in Dograh's managed region
- **Support:** Dograh team handles uptime

**Recommendation:** Start with managed cloud for MVP; migrate to self-hosted if usage grows.

---

## Switchboard Configuration

### 1. Environment Variables

Add to `.env.local`:

```env
# Dograh SIP Configuration
DOGRAH_SIP_DOMAIN=dograh-instance.example.com  # For self-hosted: your domain
# For managed: dograh.yourdomain.example.com or their SIP endpoint

# Twilio
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...

# Supabase (existing)
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...

# SMS (existing)
TWILIO_PHONE_NUMBER=+16505550100
SMS_DRY_RUN=false  # Set to true initially for testing

# Switchboard
PUBLIC_BASE_URL=https://switchboard.yourdomain.com
CRON_SECRET=<random-strong-secret>
```

### 2. Database Schema

Ensure these tables exist (from migrations):

- `clients` — with fields: `voice_agent_enabled`, `forward_number`, `agent_instructions`
- `calls` — with fields: `dial_status`, `twilio_call_sid`, `answered_by`
- `bookings` — with fields: `source`, `starts_at`, `ends_at`
- `messages` — for text-back queuing
- `business_knowledge` — for services, hours, FAQs

### 3. API Endpoints Implemented

**Voice Flow:**
- `POST /api/voice/incoming` — Inbound call handler (dials business)
- `POST /api/voice/status` — Status webhook (no-answer → Dograh or text-back)

**Dograh Integration:**
- `GET /api/dograh/context` — Context retrieval (Dograh fetches business info)
- `POST /api/dograh/webhook` — End-of-call webhook (booking confirmation)
- `POST /api/dograh/tools/check-availability` — Availability lookup
- `POST /api/dograh/tools/book-appointment` — Booking insertion

### 4. Build & Deploy Switchboard

```bash
# Build Switchboard app
npm run build

# Deploy to Vercel or your hosting
vercel deploy --prod

# Or use Docker
docker build -t switchboard:latest .
docker push <registry>/switchboard:latest
```

---

## Integration Testing Checklist

### Pre-Flight (Before Live Calls)

- [ ] Dograh instance running and accessible
- [ ] Twilio provider configured in Dograh
- [ ] Workflow created and assigned to phone number
- [ ] Switchboard environment variables set
- [ ] Database migrations applied
- [ ] Test client created with `voice_agent_enabled = true`

### Manual Testing

1. **Call Incoming Flow:**
   ```bash
   curl -X POST http://localhost:3000/api/voice/incoming \
     -d "Caller=+14155552671&Called=+16505550100&CallSid=CA-TEST-123&Direction=inbound&CallStatus=ringing"
   ```
   Expected: TwiML response dialing business number

2. **Status Webhook (No-Answer):**
   ```bash
   curl -X POST "http://localhost:3000/api/voice/status?client_id=<id>&caller=%2B14155552671" \
     -d "CallSid=CA-TEST-123&DialCallStatus=no-answer&CallStatus=in-progress"
   ```
   Expected: TwiML response dialing Dograh (or text-back if disabled)

3. **Tool Endpoint (Check Availability):**
   ```bash
   curl -X POST http://localhost:3000/api/dograh/tools/check-availability \
     -H "Content-Type: application/json" \
     -d '{"client_id":"<id>", "service_name":"Haircut"}'
   ```
   Expected: JSON with slots array

4. **Tool Endpoint (Book Appointment):**
   ```bash
   curl -X POST http://localhost:3000/api/dograh/tools/book-appointment \
     -H "Content-Type: application/json" \
     -d '{
       "client_id": "<id>",
       "service_name": "Haircut",
       "start_time": "2026-09-15T14:00:00Z",
       "contact_name": "Test User",
       "contact_phone": "+14155552671"
     }'
   ```
   Expected: JSON with booking_id and success message

5. **Webhook Handler:**
   ```bash
   curl -X POST http://localhost:3000/api/dograh/webhook \
     -H "Content-Type: application/json" \
     -d '{
       "workflow_run_id": "run-test-123",
       "initial_context": {
         "client_id": "<id>",
         "caller_number": "+14155552671",
         "client_name": "Test Salon"
       },
       "gathered_context": {
         "booking_made": true,
         "appointment": {
           "service": "Haircut",
           "start_time": "2026-09-15T14:00:00Z"
         }
       }
     }'
   ```
   Expected: 200 OK, text-back queued

### With Live Dograh Instance

1. Make real SIP call to Dograh number from test phone
2. Converse with agent
3. Book appointment through agent
4. Verify:
   - Booking created in database
   - Confirmation text-back sent
   - Call transcript stored
   - No duplicate bookings on retry

---

## Monitoring & Observability

### Key Metrics to Track

```typescript
// In logging/monitoring system
{
  "event": "call_incoming",
  "client_id": "...",
  "caller": "...",
  "timestamp": "ISO-8601"
}

{
  "event": "voice_agent_handoff",
  "client_id": "...",
  "target": "dograh",
  "enabled": true,
  "timestamp": "ISO-8601"
}

{
  "event": "booking_created",
  "client_id": "...",
  "source": "voice_agent",
  "duration_minutes": 4,
  "timestamp": "ISO-8601"
}

{
  "event": "textback_sent",
  "client_id": "...",
  "type": "confirmation|missed_call",
  "delivery_status": "sent|failed",
  "timestamp": "ISO-8601"
}
```

### Alerts to Set Up

- **SIP Connection Failure:** Dograh unreachable
- **High Tool Latency:** check_availability taking >2s
- **Booking Failure Rate:** >10% of tool calls failing
- **Text-Back Failure:** >5% of confirmations not sent
- **Cost Anomaly:** Usage 2x expected (detect overages early)

### Logs to Watch

```
// Successful call flow
INFO: incoming call { caller, called, callSid }
INFO: tenant resolved for dograh { clientId }
INFO: voice_agent handoff { clientId, dograhSipUri }
INFO: dograh check_availability { service_name, slots_returned }
INFO: dograh book_appointment { booking_id, service }
INFO: dograh webhook received { workflow_run_id, booking_made }
INFO: confirmation text sent { clientId, callerNumber }

// Error cases
WARN: client not found for number { called }
ERROR: dograh webhook missing client_id
WARN: tool endpoint error { tool_name, error }
ERROR: textback delivery failed { clientId, reason }
```

---

## Troubleshooting

### Dograh SIP Not Receiving Calls

**Symptoms:** Twilio dials Dograh, but call doesn't arrive in workflow

**Check:**
1. Dograh provider configured in UI with correct credentials
2. Twilio webhook URL points to correct Dograh SIP domain
3. Dograh logs show incoming SIP attempts (`docker compose logs api`)
4. Network firewall allows inbound SIP (port 5060/5061)

**Fix:**
```bash
# Verify Dograh is reachable
curl https://dograh.yourdomain.com/api/health

# Check Dograh SIP registration
docker compose exec api sip-status

# Restart Dograh if needed
docker compose restart api
```

### Tools Not Calling Switchboard

**Symptoms:** Dograh agent calls check_availability but it doesn't work

**Check:**
1. Tool URL is correct: `https://switchboard.yourdomain.com/api/dograh/tools/check-availability`
2. HTTPS certificate is valid (not self-signed)
3. Switchboard can reach tool endpoint
4. Tool endpoint logs show incoming requests

**Fix:**
```bash
# Test tool endpoint directly
curl -X POST https://switchboard.yourdomain.com/api/dograh/tools/check-availability \
  -H "Content-Type: application/json" \
  -d '{"client_id":"test","service_name":"Haircut"}'

# Should return 200 with slots array
```

### Bookings Not Created

**Symptoms:** Agent says "booking confirmed" but nothing in database

**Check:**
1. `book_appointment` endpoint returns 200 OK
2. Database inserts have no errors
3. Client ID in tool request matches actual client
4. `source: "voice_agent"` is set on booking

**Fix:**
```sql
-- Check for failed bookings
SELECT * FROM bookings WHERE source = 'voice_agent' ORDER BY created_at DESC;

-- Check for errors in logs
docker compose logs switchboard | grep "book_appointment"
```

### Text-Backs Not Sending

**Symptoms:** Call ends but no confirmation text received

**Check:**
1. `SMS_DRY_RUN` is false in `.env`
2. Twilio SMS credentials are correct
3. Webhook handler receives the webhook (check logs)
4. Phone number is in E.164 format (+1...)

**Fix:**
```bash
# Test SMS directly via Twilio CLI
twilio api:core:messages:create \
  --from +16505550100 \
  --to +14155552671 \
  --body "Test message"
```

---

## Rollback Plan

If Dograh integration fails in production:

### Immediate (Within 5 minutes)
```bash
# Disable voice_agent for all clients
UPDATE clients SET voice_agent_enabled = false;

# All calls now route to text-back only (slice 1 behavior)
# Users see no change; voice agent simply unavailable
```

### Short-term (Within 1 hour)
```bash
# Roll back Switchboard deployment to previous version
vercel rollback

# Or revert commits and re-deploy
git revert <dograh-commits>
git push
```

### Investigation
- Check Dograh logs: `docker compose logs api`
- Check Switchboard logs in hosting dashboard
- Review webhook delivery status
- Verify database constraints

### Long-term
- Fix root cause identified from logs
- Redeploy with fixes
- Canary: 5% traffic to Dograh
- Gradually increase if stable

---

## Cost Tracking

### Monthly Cost Breakdown (500 calls)

**Self-Hosted Dograh:**
- Infrastructure: $20-50 (server rental)
- Deepgram STT: ~$1.50 (300 min × $0.005/min)
- OpenAI LLM: ~$27 (300 min × $0.000150/s)
- OpenAI TTS: ~$1.50
- **Total: $50-80/month**

**Managed Dograh:**
- Dograh usage: $15 (1500 min × $0.01/min)
- **Total: $15/month**

**Vapi (comparison):**
- $450-495/month (same call volume)

**Savings:** 85-90% vs. Vapi

---

## Next: Phase B Canary Deployment

Once Phase A is complete and tested:

1. Route 10% of voice calls to Dograh (90% to fallback/text-back)
2. Monitor for 1 week: latency, booking rate, errors
3. If stable, increase to 50%
4. If still stable, increase to 100%
5. Deprecate Vapi (if running in parallel)

See `DOGRAH-INTEGRATION.md` for full migration path.
