# Dograh Integration Spike

## Phase 1: Architecture Assessment (COMPLETE)

### What We Learned

#### 1. Twilio SIP Integration ✅ COMPATIBLE
- Dograh supports SIP-based telephony with [flexible trunk configuration](https://docs.dograh.com/integrations/telephony/inbound)
- Supports Twilio, Vonage, Plivo, Telnyx, Cloudonix, Vobiz, and Asterisk ARI
- Dograh exposes a **single inbound webhook URL** for the whole organization
- **Routing by called number**: Each phone number is assigned an "Inbound workflow" in Dograh
- **Key difference from Vapi**: Dograh doesn't mint per-call tokens; it routes by dialed number → workflow assignment

**Implication for Switchboard:**
- Can't use the same Dograh webhook for all clients like we do with Vapi
- Each client needs a dedicated phone number → workflow pairing in Dograh
- Or: Single workflow that accepts `initial_context` (caller info, dialed number) and picks the right client dynamically

---

#### 2. Tool Calling / Custom Functions ✅ COMPATIBLE
- Dograh supports [HTTP API tools](https://docs.dograh.com/voice-agent/tools/http-api) for custom function calling
- Tools are configured with target URL, HTTP method, headers, payload template
- **Instructions live in the workflow node prompt** (not as a separate config)
- Example: "if user provides an order ID, call the search_order_id tool to retrieve details"
- Tool parameters are extracted by the LLM based on the prompt instruction

**Implication for Switchboard:**
- We'd configure three HTTP API tools in the Dograh workflow:
  - `POST /api/dograh/check_availability` 
  - `POST /api/dograh/book_appointment`
  - `POST /api/dograh/escalate`
- The prompt tells the agent when to use each tool
- **Differences from Vapi**:
  - Vapi: tools are pre-defined with JSON-Schema parameters; LLM calls them by name
  - Dograh: tools are HTTP endpoints; LLM extracts parameters from its own reasoning

---

#### 3. Dynamic Assistant Configuration ✅ PARTIALLY COMPATIBLE
- Dograh workflows accept [initial_context](https://docs.dograh.com/core-concepts/context-and-variables) at runtime
- `initial_context` values are available in the prompt using `{{variable_name}}` syntax
- Example workflow: "You are helping {{customer_name}} with a {{service_type}} appointment"
- LLM substitutes values before sending prompt to model

**Implication for Switchboard:**
- When Twilio hands off to Dograh, we can pass `initial_context` with:
  - `client_id`
  - `client_name` (salon name, etc.)
  - `client_timezone`
  - Potentially the whole business knowledge object as JSON
- Single Dograh workflow template reused for all clients
- **Challenge**: Dograh workflows are edited in the visual builder, not generated at runtime like Vapi's `buildAssistant()`
- **Solution**: Use a generic workflow + heavy `initial_context` payload to parameterize

---

#### 4. Webhook Format & Call Lifecycle ✅ DIFFERENT FROM VAPI
- Dograh webhooks fire **asynchronously after a call completes**
- Webhook nodes are configured in the workflow graph itself
- Payload template uses `{{workflow_run_id}}`, `{{initial_context.*}}`, `{{gathered_context.*}}`
- Available variables in webhook: extracted data from the call (e.g., appointment details, booking confirmation)

**Implication for Switchboard:**
- No in-call tool response pattern like Vapi's `assistant-request` → `tool-calls` → `end-of-call-report`
- Instead: Call → Workflow executes → Webhook fires once with all context from the call
- **Difference**: Tool results are captured in `gathered_context` during the call, then sent in one webhook at the end
- Text-back logic would be: webhook receives booking confirmation status, triggers immediate SMS

---

#### 5. Self-Hosted Deployment ✅ FEASIBLE
- [Docker Compose deployment](https://docs.dograh.com/deployment/docker) with Postgres, Redis, MinIO, API, UI
- Requires: 8GB RAM, 4 vCPU minimum, root access
- Setup command: `curl -o docker-compose.yaml https://raw.githubusercontent.com/dograh-hq/dograh/main/docker-compose.yaml && REGISTRY=dograhai ENABLE_TELEMETRY=true docker compose up --pull always`
- Includes free HTTPS certificate via sslip.io + Let's Encrypt
- No API keys required; auto-provisions defaults

**Implication for Switchboard:**
- Can self-host Dograh on a dedicated server or Render/Railway
- Free forever (no per-minute platform fee)
- Control over data, compliance, outages

---

#### 6. Pricing ✅ MASSIVE COST SAVINGS
- **Managed Dograh (cloud)**: $0.01/minute starting rate
- **Self-hosted Dograh**: No per-minute platform fee (only pay vendors)
- **Vendor cost at self-hosted scale (100k min/month)**: ~$0.035/min
  - Deepgram STT: $0.005/min
  - OpenAI gpt-4o-mini: $0.025/min  
  - OpenAI TTS: ~$0.005/min
- **Vapi**: $0.30-0.33/min

**Comparison (100,000 minutes/month):**
- Vapi: $3,000-3,300/month
- Managed Dograh: $1,000/month
- Self-hosted Dograh: ~$350/month
- **Savings**: 65-88%

---

### Architecture Comparison: Vapi vs Dograh

| Aspect | Vapi | Dograh |
|--------|------|--------|
| **Call Routing** | Per-call token in SIP URI | Per-number workflow assignment |
| **Tenant Resolution** | Token lookup in handoff table | Dialed number → workflow config |
| **Assistant Config** | Generated at runtime via webhook | Pre-built workflow + initial_context |
| **Tool Definition** | JSON-Schema via POST /api/vapi | HTTP endpoints in workflow config |
| **Tool Calling** | Request/response in real-time | LLM extracts params, calls endpoint |
| **Call Lifecycle** | 3 webhook types (req/calls/report) | 1 webhook at end with all context |
| **Data Access** | Token expiration/consumption | Workflow run context stored |
| **Cost Model** | Per-minute platform fee | No platform fee (BYOK) |
| **Self-Hosting** | Not possible | Full Docker stack available |

---

## Phase 2: Integration Path Analysis

### Current Switchboard Flow
```
Caller → Twilio → /api/voice/incoming (dial business)
              ↓
         /api/voice/status (no-answer)
              ↓
         [voice_agent_enabled?]
              ├─ yes → mint token, TwiML <Dial><Sip> to Vapi
              └─ no  → queue text-back
              
         → Vapi SIP receives token in URI
         → /api/vapi webhook (3 message types)
         → claimEvent for idempotency
         → buildAssistant(client, knowledge)
         → Handle tool-calls
         → end-of-call-report → text-back
```

### Dograh Integration Flow (Option A: Per-Number Workflows)
```
Caller → Twilio → /api/voice/incoming (dial business)
              ↓
         /api/voice/status (no-answer)
              ↓
         [voice_agent_enabled?]
              ├─ yes → TwiML <Dial><Sip> to Dograh (no token needed)
              └─ no  → queue text-back
              
         → Dograh SIP (routed by dialed number)
         → Finds workflow assigned to dialed number
         → Workflow starts with initial_context={client_id, caller_number, knowledge_json}
         → Agent runs, calls HTTP tools
         → Workflow completes
         → /api/dograh/webhook fires with booking status
         → Send text-back
```

**Challenges:**
- Each client needs a Dograh phone number config + workflow
- Can't reuse one workflow for all clients without complex initial_context
- Workflow is visual, not code-generated
- Tool parameters extracted by LLM, not strict schema validation

### Dograh Integration Flow (Option B: Single Workflow + Smart Routing)
```
Single Dograh phone number
    ↓
Incoming call → Workflow start
    ↓
initial_context={caller_number, dialed_number, client_id} fetched from /api/dograh/resolve-tenant
    ↓
Agent prompt: "You're helping {{client_name}} at {{client_timezone}}.
Use these services: {{services_json}}. Available slots: {{business_hours_json}}"
    ↓
Tool: /api/dograh/check_availability (extracts service_name, preferred_date from LLM reasoning)
Tool: /api/dograh/book_appointment (extracts service, time, contact from LLM reasoning)
    ↓
Workflow ends → webhook to /api/dograh/webhook with booking confirmation
    ↓
Send text-back
```

**Advantages:**
- Single Dograh number and workflow
- Reuses switchboard's business logic (availability, booking, textback)
- Similar to Vapi's per-call assistant generation
- Can load client knowledge on-demand

**Challenges:**
- Dograh workflows aren't generated at runtime; workflow is static
- Initial_context payload could get large (full knowledge JSON)
- LLM parameter extraction less precise than JSON-Schema
- No idempotency key like Vapi's claimEvent (Dograh workflow_run_id serves this role)

---

## Phase 3: Cost Calculation

### Assumptions (Switchboard)
- **Call volume**: Unknown; estimate 100-500 calls/month for initial spike
- **Average call duration**: 3 minutes (includes business dialing + no-answer + agent conversation)
- **Agent enabled on**: 100% of missed calls
- **LLM**: gpt-4o-mini (switchboard's current model)
- **STT/TTS**: Deepgram + OpenAI (switchboard's current choice)

### Vapi Cost (Current)
- **Per-call**: $0.30-0.33/min
- **100 calls × 3 min**: 300 minutes
- **Cost**: $90-99/month
- **500 calls × 3 min**: 1500 minutes
- **Cost**: $450-495/month

### Self-Hosted Dograh Cost (Proposed)
- **Infrastructure**: $20-50/month (Render/Railway t3.medium)
- **STT (Deepgram)**: ~300-1500 min × $0.005 = $1.50-7.50/month
- **LLM (gpt-4o-mini)**: ~300-1500 min × $0.000150/s ≈ $27-135/month
- **TTS (OpenAI)**: ~300-1500 min × $0.005 = $1.50-7.50/month
- **Total**: $50-200/month (vs $90-495 on Vapi)

### Managed Dograh Cost
- **Per-minute**: $0.01/min
- **300-1500 min**: $3-15/month
- **Total**: $23-65/month (but less control, still cheaper than Vapi)

**Break-even**: Self-hosted Dograh pays for itself after 1-2 months of production call volume.

---

## Phase 4: Proof-of-Concept Plan

### Minimal Implementation Path

**Goal**: One complete call end-to-end: inbound → Dograh → booking → text-back

**Step 1: Set up Dograh locally** (30 min)
- `docker compose up` with Dograh stack
- Create organization + Twilio telephony config
- Create single "Appointment Booking" workflow (visual builder)

**Step 2: Adapt webhook handler** (1-2 hours)
- Create `src/app/api/dograh/webhook/route.ts`
- Copy logic from `/api/vapi` but adapt to Dograh's single webhook + initial_context model
- Parse `gathered_context` for booking confirmation + extracted contact details
- Reuse `sendTextback()` to send confirmation

**Step 3: Adapt Twilio handoff** (1 hour)
- Modify `/api/voice/status` to dial Dograh instead of Vapi when `voice_agent_enabled = true`
- Remove token minting; pass Dograh phone number in TwiML `<Dial><Sip>`
- Keep text-back fallback for handoff failures

**Step 4: Create Dograh workflow** (1-2 hours)
- Visual workflow in Dograh builder:
  - Start node: receive incoming call
  - Agent node: "Book appointments for {{client_name}} ({{client_timezone}})"
  - Tool node: POST to `/api/dograh/check_availability` 
  - Tool node: POST to `/api/dograh/book_appointment`
  - Webhook node: POST to `/api/dograh/webhook` with booking status
  - End call

**Step 5: Test** (1 hour)
- Curl mock incoming call to Dograh SIP
- Simulate no-answer → handoff
- Verify booking created
- Verify text-back sent
- Check idempotency (replay webhook)

**Total estimated time**: 4-6 hours

---

## Risk Assessment

### Low Risk (Proceed)
- ✅ Dograh Twilio integration is documented and proven
- ✅ Docker deployment is straightforward
- ✅ Cost savings are dramatic and verifiable
- ✅ Webhook at end of call simplifies some logic (no in-call state)

### Medium Risk (Manageable)
- ⚠️ Workflow is visual, not code-generated (requires UI interaction or API-driven workflow creation)
- ⚠️ LLM parameter extraction less strict than JSON-Schema (may need prompt tuning)
- ⚠️ Dograh is younger codebase than Vapi (community vs. commercial support)
- **Mitigation**: Thorough testing with edge cases; keep Vapi config live as fallback

### High Risk (Showstoppers)
- ❌ Initial_context not available during call (GitHub issue #131) — **BUT**: marked as bug, likely fixed in recent versions
- ❌ Workflow graph must be pre-configured (can't generate per-client)
- **Mitigation**: Use single workflow + large initial_context JSON; test with current Dograh release

---

## Recommendation

### Status: **PROCEED TO PHASE 4 (POC)**

**Reasoning:**
1. Dograh is architecturally compatible with switchboard's needs (Twilio SIP + tool calling + webhooks)
2. Cost savings are 65-88% compared to Vapi (self-hosted) or 40-70% (managed)
3. Self-hosted deployment is low-friction (Docker Compose)
4. Risk is manageable with thorough testing
5. Fallback to Vapi remains available if issues arise

**Next Steps:**
1. Spin up local Dograh via Docker Compose (30 min)
2. Build minimal workflow in visual builder (1-2 hours)
3. Implement `/api/dograh/webhook` adapter (1-2 hours)
4. Test one happy-path call end-to-end (1 hour)
5. Document findings in `DOGRAH-POC.md` with:
   - What worked smoothly
   - What required workarounds
   - Revised timeline for full migration
   - Recommendation: merge into switchboard or defer to v2

**Go/No-Go Criteria:**
- ✅ One booking made via Dograh end-to-end
- ✅ Idempotency check passed (duplicate webhook doesn't double-book)
- ✅ Text-back delivery works
- ✅ No critical infrastructure issues
- ✅ Self-hosted Dograh stays running for 1 hour without errors

If all five criteria pass → **RECOMMEND MIGRATION**; plan 1-week refactor to replace Vapi with Dograh.

If any criterion fails → **DOCUMENT BLOCKER**; add to decision log; consider managed Dograh as intermediate step.

---

## References

- [Dograh Telephony Integration](https://docs.dograh.com/integrations/telephony/overview)
- [Dograh Inbound Workflow Configuration](https://docs.dograh.com/integrations/telephony/inbound)
- [Dograh HTTP API Tools](https://docs.dograh.com/voice-agent/tools/http-api)
- [Dograh Context & Variables](https://docs.dograh.com/core-concepts/context-and-variables)
- [Dograh Docker Deployment](https://docs.dograh.com/deployment/docker)
- [Dograh Webhook Payloads](https://dograhai.mintlify.app/developer/webhooks)
- [Dograh GitHub Repository](https://github.com/dograh-hq/dograh)
- [Cost Analysis: Self-Hosted vs. Vapi](https://blog.dograh.com/self-hosted-voice-agents-vs-bland-real-cost-analysis-100k-minute-tco/)
