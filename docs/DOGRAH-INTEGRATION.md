# Dograh Integration Guide for Switchboard

This guide details the technical integration between Dograh and Switchboard's voice agent system.

## Architecture Overview

### Call Flow: Twilio → Dograh → Booking → Text-Back

```
[Caller dials Twilio]
        ↓
[/api/voice/incoming] — dial business number
        ↓
[/api/voice/status] — dial status (no-answer/busy/failed)
        ↓
[voice_agent_enabled = true?]
    ├─ NO → Queue text-back (slice 1 behavior, unchanged)
    └─ YES → Mint Dograh session, TwiML <Dial><Sip>
            ↓
[Twilio routes call to Dograh SIP endpoint]
        ↓
[Dograh workflow starts, receives initial_context]
        ↓
[Agent prompt includes {{client_name}}, {{services_json}}, {{business_hours}}]
        ↓
[Agent converses with caller]
        ↓
[LLM calls check_availability → /api/dograh/tools/check-availability]
        ↓
[LLM calls book_appointment → /api/dograh/tools/book-appointment]
        ↓
[Workflow completes, HTTP tools have populated gathered_context]
        ↓
[Dograh fires webhook → /api/dograh/webhook]
        ↓
[Webhook handler checks booking_made flag, sends text-back]
        ↓
[Call ends]
```

## Key Differences from Vapi

| Aspect | Vapi | Dograh |
|--------|------|--------|
| **Tenant Resolution** | Token in SIP URI (`?token=xyz`) | Initial context in call metadata |
| **Assistant Config** | Generated per-call by `/api/vapi` | Pre-built workflow + parameterized prompt |
| **Tool Parameters** | JSON-Schema validation | LLM extraction from prompt instructions |
| **Call Lifecycle** | 3 webhook types (request/calls/report) | 1 webhook at end with all context |
| **Tool Calling** | Request/response in real-time | LLM calls HTTP endpoint directly |
| **Idempotency** | `claimEvent` with messageId | Dograh `workflow_run_id` + webhook deduplication |
| **Cost** | ~$0.30/min (platform fee included) | $0.01/min managed or self-hosted free |

## Implementation Details

### 1. Modified `/api/voice/status` Handler

When a call to the business doesn't get answered, instead of minting a Vapi token and dialing the token URI, we:

1. Fetch client config + `voice_agent_enabled` flag
2. **If enabled**: Prepare initial_context (client_id, caller_number, business knowledge)
3. **Create Dograh session** (via Dograh API or pre-configured workflow)
4. **Return TwiML** to dial Dograh SIP endpoint (no token in URI)

```typescript
// Pseudo-code
if (!client.voice_agent_enabled) {
  // Existing behavior: queue text-back
  await queueTextBack(...);
  return twimlTextResponse();
}

// New behavior: hand off to Dograh
const context = {
  client_id: client.id,
  caller_number: caller,
  client_name: client.name,
  client_timezone: client.timezone,
  business_hours: formatBusinessHours(knowledge.hours),
  services_json: JSON.stringify(knowledge.services),
  faqs_json: JSON.stringify(knowledge.faqs),
  agent_instructions: client.agent_instructions || "",
};

// Dograh receives context via call metadata or API call
const dograhSipUri = `sip://dograh-instance.example.com/appointmentbooking`;
return twimlDialSip(dograhSipUri, context);
```

### 2. Dograh Workflow Configuration

**File:** `scripts/dograh-workflow.json` (provides template)

The workflow is created once in Dograh's UI or imported via API:

- **Start**: Incoming call
- **Agent Node**: Uses `initial_context` variables in system prompt
  - Prompt includes client name, services, business hours, FAQs
  - LLM is gpt-4o-mini (configurable)
  - Voice is OpenAI echo (configurable)
- **HTTP Tool Nodes**: Direct LLM → Tool calls
  - `check_availability`: Dograh LLM extracts `service_name`, `preferred_date`; calls our endpoint
  - `book_appointment`: LLM extracts `service_name`, `start_time`, `contact_name`, `contact_phone`; calls our endpoint
- **Webhook Node**: Fires at end with `booking_made` flag in `gathered_context`
- **End**: Hang up

**Workflow handles all clients**: Same workflow, different `initial_context` per call.

### 3. HTTP Tool Endpoints

#### `POST /api/dograh/tools/check-availability`

**Request** (from Dograh's HTTP tool node):
```json
{
  "client_id": "client-uuid",
  "service_name": "Haircut",
  "preferred_date": "2026-09-15"
}
```

**Response**:
```json
{
  "slots": [
    {
      "start": "2026-09-15T14:00:00Z",
      "end": "2026-09-15T15:00:00Z",
      "label": "Tuesday, September 15, 2:00 PM"
    }
  ]
}
```

**Logic**:
- Load client's timezone, business hours, booking rules from knowledge
- Call `availableSlots()` (same function as Vapi)
- Filter by preferred_date if provided
- Return up to 5 closest slots

#### `POST /api/dograh/tools/book-appointment`

**Request**:
```json
{
  "client_id": "client-uuid",
  "service_name": "Haircut",
  "start_time": "2026-09-15T14:00:00Z",
  "contact_name": "Alice",
  "contact_phone": "+14155552671",
  "notes": "Prefer shorter cut",
  "requested_window": "afternoon"
}
```

**Response**:
```json
{
  "success": true,
  "booking_id": "booking-uuid",
  "message": "Appointment confirmed for Alice on 09/15/2026 at 2:00 PM"
}
```

**Logic**:
- Validate all required fields present
- Load service duration from knowledge
- Insert into `bookings` table with `source: "voice_agent"`
- Return booking confirmation

### 4. Dograh Webhook Handler

**Endpoint:** `POST /api/dograh/webhook`

**Request** (from Dograh at end of call):
```json
{
  "workflow_run_id": "run-12345",
  "initial_context": {
    "client_id": "client-uuid",
    "caller_number": "+14155552671",
    "client_name": "Demo Salon",
    "client_timezone": "America/Los_Angeles"
  },
  "gathered_context": {
    "booking_made": true,
    "appointment": {
      "service": "Haircut",
      "start_time": "2026-09-15T14:00:00Z",
      "contact_name": "Alice"
    }
  }
}
```

**Logic**:
1. Extract `client_id` and `caller_number` from `initial_context`
2. Check `booking_made` flag in `gathered_context`
3. **If booking made**: Send confirmation text with appointment details
4. **If no booking**: Send standard missed-call text-back
5. Upsert caller into `contacts` table
6. Return 200 OK

**Idempotency:**
- Dograh's `workflow_run_id` uniquely identifies each call
- On webhook retry (same `workflow_run_id`), sendTextback is idempotent:
  - Check if message already sent for this run_id (add to DB or use idempotency key)
  - Prevent duplicate texts

### 5. Data Flows and Context Passing

#### How Client Knowledge Reaches Dograh

```
1. Caller dials, reaches /api/voice/status (no-answer)
2. Server loads client + knowledge:
   - Client: id, name, timezone, voice_agent_enabled, agent_instructions
   - Knowledge: services[], hours, booking_rules, faqs
3. Format knowledge into strings for initial_context:
   - services_json = JSON.stringify(services)
   - business_hours = formatBusinessHours(hours)
   - faqs_json = JSON.stringify(faqs)
4. Pass to Dograh via initial_context
5. Dograh's workflow substitutes {{variables}} in agent prompt
6. Agent has full context without per-call code generation
```

#### How Tool Calls Extract Parameters

```
Agent prompt says:
"When user wants to book, call the book_appointment tool with:
- service_name: the service they chose
- start_time: ISO 8601 of the slot
- contact_name: their name
- contact_phone: their number"

LLM conversation:
Caller: "I'd like a haircut on Tuesday at 2pm"
Agent: "Great! Let me book that for you."
[LLM reasons: service_name=Haircut, start_time=2026-09-15T14:00:00Z, contact_name=?, contact_phone=?]
[LLM: "Can I get your name and phone number?"]
Caller: "It's Alice, 415-555-2671"
[LLM reasons: contact_name=Alice, contact_phone=+14155552671]
[LLM calls book_appointment with extracted values]
→ /api/dograh/tools/book-appointment
← Returns success

Agent: "Alice, your haircut is booked for Tuesday at 2pm!"
Call ends.

Workflow fires webhook with:
gathered_context: {
  booking_made: true,
  appointment: { service: "Haircut", start_time: "...", contact_name: "Alice" }
}
```

## Configuration Steps

### 1. Set Up Dograh Instance

**Option A: Self-Hosted Docker**
```bash
curl -o docker-compose.yaml https://raw.githubusercontent.com/dograh-hq/dograh/main/docker-compose.yaml
REGISTRY=dograhai ENABLE_TELEMETRY=true docker compose up --pull always
# Access at http://localhost:3000
```

**Option B: Managed Dograh Cloud**
- Sign up at dograh.com
- No self-hosting required

### 2. Create Dograh Organization & Twilio Config

1. In Dograh UI, create organization
2. Add Twilio telephony configuration:
   - Twilio Account SID, Auth Token
   - Inbound webhook URL: `{PUBLIC_BASE_URL}/api/dograh/webhook`
3. Provision or assign a phone number to Dograh

### 3. Import Workflow

1. In Dograh UI, create new workflow
2. Manually recreate nodes from `scripts/dograh-workflow.json` or import via API
3. Configure HTTP tool URLs:
   - `check_availability`: `{PUBLIC_BASE_URL}/api/dograh/tools/check-availability`
   - `book_appointment`: `{PUBLIC_BASE_URL}/api/dograh/tools/book-appointment`
4. Set webhook URL: `{PUBLIC_BASE_URL}/api/dograh/webhook`
5. Assign workflow to the provisioned phone number (inbound routing)

### 4. Update Switchboard Config

Add to `.env.local`:
```env
DOGRAH_INSTANCE_URL=https://dograh-instance.example.com  # or managed cloud
DOGRAH_PHONE_NUMBER=+16505550100  # Dograh's phone number
PUBLIC_BASE_URL=https://switchboard.example.com
```

### 5. Modify Voice Status Handler

Update `/api/voice/status` to:
- Check `voice_agent_enabled`
- Load client knowledge
- Format initial_context
- Return TwiML `<Dial><Sip>` to Dograh (instead of Vapi)

## Testing Strategy

### Unit Test: Tool Endpoints

```typescript
// POST /api/dograh/tools/check-availability
const res = await fetch("http://localhost:3000/api/dograh/tools/check-availability", {
  method: "POST",
  body: JSON.stringify({
    client_id: "test-client",
    service_name: "Haircut",
  }),
});
// Expect: 200, slots array with 5 or fewer items

// POST /api/dograh/tools/book-appointment
const res2 = await fetch("http://localhost:3000/api/dograh/tools/book-appointment", {
  method: "POST",
  body: JSON.stringify({
    client_id: "test-client",
    service_name: "Haircut",
    start_time: new Date().toISOString(),
    contact_name: "Test User",
    contact_phone: "+14155552671",
  }),
});
// Expect: 200, booking_id in response, booking created in DB
```

### Integration Test: Webhook Handler

```typescript
// POST /api/dograh/webhook
const res = await fetch("http://localhost:3000/api/dograh/webhook", {
  method: "POST",
  body: JSON.stringify({
    workflow_run_id: "test-run-123",
    initial_context: {
      client_id: "test-client",
      caller_number: "+14155552671",
    },
    gathered_context: {
      booking_made: true,
      appointment: {
        service: "Haircut",
        start_time: new Date().toISOString(),
      },
    },
  }),
});
// Expect: 200, text-back message created in DB
```

### End-to-End Test: Full Call Flow

1. Start Dograh instance (local or managed)
2. Configure workflow + inbound routing
3. Call Dograh's phone number from test SIP client
4. Converse with agent, book appointment
5. Verify:
   - Booking created in DB with `source: "voice_agent"`
   - Text-back message sent
   - No duplicate messages on webhook retry

## Rollback Plan

If Dograh integration has issues:

1. **Immediate**: Revert `/api/voice/status` to original behavior (no Dograh handoff)
2. **Set** `voice_agent_enabled = false` for all clients in database
3. **All calls** route to slice 1 behavior (text-back only, no voice agent)
4. **Decision**: Fix Dograh issues or roll back to Vapi

## Cost Comparison (Updated)

### For 100 calls/month × 3 min = 300 minutes

| Platform | Cost | Notes |
|----------|------|-------|
| **Vapi Cloud** | $90-99 | $0.30-0.33/min |
| **Dograh Managed** | $30 | $0.01/min |
| **Dograh Self-Hosted** | ~$30-50 | Infrastructure + $0.035/min vendor costs |

**ROI**: Self-hosted Dograh pays for itself in 1 month vs. Vapi.

## Monitoring & Observability

Add logging to track:

```typescript
// /api/voice/status
console.info("voice_status handoff", {
  client_id,
  voice_agent_enabled,
  target: "dograh",
});

// /api/dograh/tools/check-availability
console.info("dograh check_availability", {
  client_id,
  service_name,
  slots_returned: slots.length,
});

// /api/dograh/tools/book-appointment
console.info("dograh book_appointment", {
  client_id,
  booking_id,
  service_name,
});

// /api/dograh/webhook
console.info("dograh webhook received", {
  workflow_run_id,
  client_id,
  booking_made,
});
```

Key metrics to track:
- Call completion rate (calls that reach Dograh vs. fail)
- Booking success rate (booked / calls that reached Dograh)
- Tool call latency (check_availability response time)
- Webhook latency (Dograh call end to webhook delivery)
- Text-back delivery rate

## Migration Path (Future)

Once Dograh is stable in production:

1. **Phase 1**: Run Dograh + Vapi in parallel; route subset of calls to Dograh
2. **Phase 2**: Monitor metrics; increase Dograh traffic to 50%
3. **Phase 3**: Switch remaining traffic to Dograh; deprecate Vapi
4. **Phase 4**: Remove Vapi integration code, simplify codebase

---

## References

- [Dograh Telephony Integration](https://docs.dograh.com/integrations/telephony/overview)
- [Dograh Inbound Workflows](https://docs.dograh.com/integrations/telephony/inbound)
- [Dograh HTTP Tools](https://docs.dograh.com/voice-agent/tools/http-api)
- [Dograh Context & Variables](https://docs.dograh.com/core-concepts/context-and-variables)
- [Dograh Webhook Payloads](https://dograhai.mintlify.app/developer/webhooks)
