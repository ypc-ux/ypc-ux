# Switchboard Voice Agent Platform - Master Project Guide

**Status**: Phase A (Development) complete, ready for Phase A Infrastructure & Testing  
**Last Updated**: 2026-09-10  
**Repository**: ypc-ux/ypc-ux  
**Branch**: `claude/brand-vault-content-calendar-kk5rv1`

---

## 🎯 Project Overview

This is the central hub for **Switchboard** - a voice-first business automation platform combining:
1. **Voice Call Routing** (Twilio integration)
2. **Dograh AI Voice Agent** for intelligent call handling and appointment booking
3. **Premium Marketing Sites** (Switchboard Premium & Agent Ad Spend Premium)
4. **Brand Vault & Content Management** (in development)
5. **Business Integration Protocol** (Supabase-backed backend)

---

## 📂 Project Structure

### Core Platform (This Repo)
- **Branch**: `claude/brand-vault-content-calendar-kk5rv1`
- **Location**: `/home/user/ypc-ux/`
- **Status**: ✅ Phase A3 (Code) complete, awaiting Phase A1-A2 (Infrastructure)

#### Key Directories:
- `src/app/api/` - All API endpoints (voice call handling, Dograh integration)
- `src/lib/` - Business logic (availability calculation, knowledge management, handoff tokens)
- `docs/` - Complete technical documentation
- `scripts/` - Integration tests and deployment utilities
- `supabase/` - Database migrations and RLS policies

### Premium Marketing Sites (Separate Repos)
1. **Switchboard Premium**
   - **Repository**: `ypc-ux/switchboard-premium`
   - **Location**: `/home/user/switchboard-premium/`
   - **Status**: Deployed to Vercel, ready for image integration
   - **Theme**: Blue/cyan gradient, enterprise aesthetic
   - **Message**: "Enterprise-Grade Call Management"

2. **Agent Ad Spend Premium**
   - **Repository**: `ypc-ux/agent-adspend-premium`
   - **Location**: `/home/user/agent-adspend-premium/`
   - **Status**: Deployed to Vercel, ready for image integration
   - **Theme**: Red/amber gradient, performance-focused
   - **Message**: "Cut Ad Spend In Half"

---

## 🚀 What's Implemented (Phase A3 - COMPLETE)

### All API Endpoints (Ready to Deploy)
```
POST /api/voice/incoming              - Accept inbound calls from Twilio
POST /api/voice/status                - Route missed calls to Dograh AI agent
POST /api/dograh/webhook              - Receive end-of-call events from Dograh
POST /api/dograh/tools/check-availability  - List available booking slots
POST /api/dograh/tools/book-appointment    - Create appointment bookings
GET  /api/dograh/context              - Fetch call context for Dograh agent
```

### Database Schema (Applied)
- `voice_handoffs` - Track Dograh handoff attempts with idempotency
- `bookings` - Appointment bookings from voice agent (source: "voice_agent")
- `calls` - Call history and transcripts
- `clients` - Enhanced with `voice_agent_enabled`, `agent_instructions`, `dograh_sip_domain`

### Integration Test
- **File**: `scripts/dograh-integration-test.ts`
- **Tests**: 4 scenarios (happy path, no booking, idempotency, fallback)
- **Status**: Ready to run once infrastructure deployed

### Documentation
- `docs/DOGRAH-INTEGRATION.md` - Complete technical architecture
- `docs/DOGRAH-MIGRATION-CHECKLIST.md` - Phase-by-phase implementation checklist
- `DOGRAH-IMPLEMENTATION-STATUS.md` - Current status report (in scratchpad)

---

## ⚙️ Next Steps by Phase

### Phase A1: Infrastructure Setup (NOT STARTED)
**Owner**: DevOps/Infrastructure  
**Blocker**: None - ready to start anytime  

```bash
# Decision needed:
# Option A: Deploy self-hosted Dograh on Kubernetes
# Option B: Use managed Dograh Cloud service

# Then:
1. Reserve resources / sign up for managed service
2. Deploy Dograh stack
3. Verify Dograh UI is accessible
4. Get SIP domain (e.g., dograh-instance.example.com)
```

### Phase A2: Dograh Configuration (Waiting on A1)
**Owner**: DevOps/Dograh team  

```bash
1. Add Twilio provider credentials to Dograh dashboard
2. Provision/assign phone number to Dograh
3. Set webhook URLs in Dograh:
   - POST https://switchboard.yourdomain.com/api/dograh/webhook (end-of-call)
   - POST https://switchboard.yourdomain.com/api/dograh/tools/* (tool callbacks)
4. Create "Appointment Booking Agent" workflow in Dograh UI
5. Test with mock call
```

### Phase A4: Testing & Validation (Ready after A1-A2)
**Owner**: QA/Engineering  

```bash
# Set environment variables
export DOGRAH_SIP_DOMAIN=your-dograh-domain.com
export SUPABASE_URL=https://xxx.supabase.co
export SUPABASE_ANON_KEY=xxx
export TWILIO_ACCOUNT_SID=xxx
export TWILIO_AUTH_TOKEN=xxx
export SMS_DRY_RUN=true

# Run integration test
npx ts-node scripts/dograh-integration-test.ts

# Success criteria:
# ✅ Tool endpoints return 200 OK
# ✅ Bookings created in database
# ✅ Text messages queued
# ✅ Duplicate webhooks don't create duplicates (idempotency)
# ✅ Fallback text-back fires when no booking made
```

### Phase B: Canary Deployment (1 week after A4)
- Feature flag: Route 10% of traffic to Dograh
- Monitor SIP health, tool latency, booking rate
- Gradual increase: 10% → 25% → 50% → 100%

### Phase C: Full Migration (1 day after B)
- Switch 100% traffic to Dograh
- Disable fallbacks after 24h
- Monitor for 72h

### Phase D: Optimization (Ongoing)
- Prompt tuning for parameter extraction
- Performance optimization
- Infrastructure scaling

---

## 🎨 Premium Sites Handoff

Both premium sites are deployed to Vercel and ready for:
1. **Image Integration** (Open-Higgsfield-AI)
2. **Animation Polish** (GSAP scroll triggers, parallax, pin animations)
3. **Performance Optimization** (image optimization, CDN caching)
4. **Final Push** (commit to GitHub)

### Setup for Cline:
```bash
# Clone premium sites
git clone https://github.com/ypc-ux/switchboard-premium.git
git clone https://github.com/ypc-ux/agent-adspend-premium.git

# Install and develop
cd switchboard-premium
npm install
npm run dev  # runs on http://localhost:3000

# Monitor Vercel deployments
# https://vercel.com/ypc-ux/switchboard-premium
# https://vercel.com/ypc-ux/agent-adspend-premium
```

---

## 📋 Environment Variables Required

### For Voice Agent Platform (ypc-ux repo)
```
# Dograh configuration
DOGRAH_SIP_DOMAIN=dograh-instance.example.com

# Supabase (database)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx

# Twilio (voice)
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# SMS Configuration
SMS_DRY_RUN=true  # Set to false only after team approval

# Optional monitoring
DATADOG_API_KEY=xxx  # For production metrics
```

### For Premium Sites (separate repos)
```
# No env vars needed for basic development
# Optional: Add Open-Higgsfield-AI credentials for image generation
HIGGSFIELD_API_KEY=xxx
```

---

## 🧪 Testing Before Handoff

### Code Quality Checks
```bash
npm run typecheck      # TypeScript validation
npm run build          # Next.js build
npm run lint          # ESLint (if configured)
```

### Integration Test
```bash
# From ypc-ux repo root
npx ts-node scripts/dograh-integration-test.ts
```

### Manual Testing Checklist
- [ ] Voice incoming call handler accepts Twilio TwiML request
- [ ] Missed call detection routes to Dograh SIP correctly
- [ ] Check-availability returns proper slot format
- [ ] Book-appointment creates booking with correct fields
- [ ] Webhook handler sends SMS with booking confirmation
- [ ] Duplicate webhooks don't create duplicate SMS (idempotency)
- [ ] Feature flag `voice_agent_enabled` correctly gates behavior
- [ ] RLS policies protect multi-tenant data

---

## 🔄 Handoff Instructions for Cline

### When Cline clones this repo:
1. **Read this CLAUDE.md** ← You are here
2. **Check current branch**: Should be `claude/brand-vault-content-calendar-kk5rv1`
3. **Install dependencies**: `npm install`
4. **Run checks**: `npm run typecheck && npm run build`
5. **Review docs**: Start with `docs/DOGRAH-IMPLEMENTATION-STATUS.md`
6. **Next task**:
   - If A1 infrastructure not started: Begin infrastructure deployment
   - If A1 complete: Proceed with A2 configuration
   - If A2 complete: Run integration tests (Phase A4)
   - If all complete: Begin canary deployment (Phase B)

### For Premium Sites (separate repos):
1. Clone from GitHub: `git@github.com:ypc-ux/switchboard-premium.git`
2. Check Vercel deployment status
3. Integrate images from Open-Higgsfield-AI
4. Test animations and responsiveness
5. Push final code to GitHub
6. Verify both sites are live

---

## 📚 Documentation Map

### Core Architecture
- `docs/DOGRAH-INTEGRATION.md` - Technical deep-dive, call flow, database schema
- `docs/DOGRAH-DEPLOYMENT.md` - Deployment playbook (if exists)
- `docs/VOICE-AGENT.md` - Voice agent specific setup (if exists)

### Checklists & Plans
- `docs/DOGRAH-MIGRATION-CHECKLIST.md` - Phase-by-phase checklist (A through D)
- Scratchpad: `DOGRAH-IMPLEMENTATION-STATUS.md` - Current status report

### Related Projects
- Brand Vault (content management) - In development
- Portfolio notification system - In development
- Business Integration Protocol - Supabase backend

---

## 🛑 Known Limitations & Blockers

1. **Infrastructure Not Deployed**: Dograh instance not yet provisioned (Phase A1)
2. **Network Proxy**: External image downloads restricted (use local CDN or Open-Higgsfield-AI)
3. **Google Fonts**: Blocked by proxy, using system fonts instead
4. **SMS Dry-Run**: Active by default, must be explicitly disabled

---

## 🎯 Success Criteria

### Phase A (This Phase)
- [x] All endpoints implemented (6/6)
- [x] Database schema applied
- [x] Integration test written and ready
- [ ] Infrastructure deployed (waiting)
- [ ] Dograh configured (waiting)
- [ ] All tests passing (waiting on infrastructure)

### Phase B & Beyond
- Dograh handling 10%+ of missed call volume
- Booking rate ≥90% of baseline expectations
- Zero duplicate bookings (idempotency working)
- SMS delivery ≥95% success rate

---

## 👥 Quick Reference

### Key Files by Role
**DevOps/Infrastructure** (Phase A1):
- `supabase/migrations/0003_dograh_canary.sql` - Database schema
- `docs/DOGRAH-IMPLEMENTATION-STATUS.md` - Infrastructure requirements

**Backend Engineers** (Phase A2-A4):
- `src/app/api/` - All endpoint implementations
- `src/lib/` - Business logic (availability, knowledge, handoff)
- `scripts/dograh-integration-test.ts` - Integration test

**QA/Testing** (Phase A4):
- `scripts/dograh-integration-test.ts` - Run this first
- `docs/DOGRAH-MIGRATION-CHECKLIST.md` - Test scenarios

**DevOps/Monitoring** (Phase B onwards):
- Datadog/CloudWatch configuration for SIP health
- Alert thresholds: SIP errors, tool latency >2s, booking failures >5%

---

## 🔗 Useful Links

- **Main Repo**: https://github.com/ypc-ux/ypc-ux
- **Switchboard Premium**: https://github.com/ypc-ux/switchboard-premium
- **Agent Ad Spend Premium**: https://github.com/ypc-ux/agent-adspend-premium
- **Vercel Deployments**:
  - https://switchboard-premium.vercel.app
  - https://agent-adspend-premium.vercel.app
- **Dograh Docs**: https://github.com/dograh-hq/dograh
- **Twilio Voice API**: https://www.twilio.com/docs/voice

---

## 📝 Last Updated

- **Date**: 2026-09-10
- **By**: Claude Haiku 4.5 (Claude Code)
- **Session**: https://claude.ai/code/session_01Y4bWVGbxU5ttzyiYwQe6PN

**Next reviewer should:**
1. Verify Dograh infrastructure deployment status (Phase A1)
2. Confirm environment variables are set correctly
3. Run integration test and verify all 4 scenarios pass
4. Check SMS dry-run flag before enabling real messages
