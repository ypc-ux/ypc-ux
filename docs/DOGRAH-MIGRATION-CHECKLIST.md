# Dograh Migration Checklist

Complete task list for migrating from Vapi to Dograh.

---

## Phase A: Development & Setup (1-2 Days)

### A1: Infrastructure ☐
- [ ] Choose deployment option: Self-hosted vs. Managed
- [ ] Reserve server resources if self-hosted
- [ ] Deploy Dograh stack
- [ ] Verify Dograh UI is accessible and healthy
- [ ] Generate Dograh API key for future API calls

### A2: Dograh Configuration ☐
- [ ] Add Twilio provider to Dograh with credentials
- [ ] Provision or assign phone number to Dograh
- [ ] Set webhook URLs in Dograh:
  - [ ] Inbound webhook: `https://switchboard.yourdomain.com/api/dograh/webhook`
  - [ ] Tool callback (optional): `https://switchboard.yourdomain.com/api/dograh/tools/*`
- [ ] Create "Appointment Booking Agent" workflow manually
- [ ] Add HTTP tool nodes with correct endpoints
- [ ] Test workflow with mock call

### A3: Switchboard Code ☐
- [ ] Implement `/api/voice/incoming/route.ts` ✓ (Done)
- [ ] Implement `/api/voice/status/route.ts` ✓ (Done)
- [ ] Implement `/api/dograh/webhook/route.ts` ✓ (Done)
- [ ] Implement `/api/dograh/tools/check-availability/route.ts` ✓ (Done)
- [ ] Implement `/api/dograh/tools/book-appointment/route.ts` ✓ (Done)
- [ ] Implement `/api/dograh/context/route.ts` ✓ (Done)
- [ ] Update environment variables
- [ ] Run TypeScript type check: `npm run typecheck`
- [ ] Run build: `npm run build`

### A4: Testing (Local/Staging) ☐
- [ ] Unit tests for tool endpoints pass
- [ ] Integration test simulation passes
- [ ] Mock Dograh server test (if available)
- [ ] Create test client with `voice_agent_enabled = true`
- [ ] Test inbound call flow manually:
  - [ ] POST to `/api/voice/incoming` → TwiML response
  - [ ] POST to `/api/voice/status` → TwiML to Dograh
- [ ] Test tool endpoints:
  - [ ] `/api/dograh/tools/check-availability` returns slots
  - [ ] `/api/dograh/tools/book-appointment` creates booking
- [ ] Test webhook:
  - [ ] `/api/dograh/webhook` sends text-back
  - [ ] Idempotency: duplicate webhook doesn't create duplicate message

### A5: Documentation ☐
- [ ] Review DOGRAH-INTEGRATION.md
- [ ] Review DOGRAH-DEPLOYMENT.md
- [ ] Create runbook for production incident response
- [ ] Document Dograh workflow configuration (screenshots/steps)
- [ ] Document Twilio configuration changes

---

## Phase B: Canary Deployment (1 Week)

### B1: Production Setup ☐
- [ ] Deploy Switchboard changes to staging
- [ ] Deploy Switchboard changes to production
- [ ] Verify all API endpoints accessible
- [ ] Verify database tables and schema
- [ ] Test database connectivity

### B2: Configuration ☐
- [ ] Set environment variables in production
- [ ] Verify `DOGRAH_SIP_DOMAIN` is correct
- [ ] Verify Twilio webhooks point to production URLs
- [ ] Test SMS_DRY_RUN=true (no real SMS yet)

### B3: Canary Traffic (10%) ☐
- [ ] Create feature flag: `DOGRAH_ENABLED` (default false)
- [ ] Set flag to enable Dograh for 10% of calls
- [ ] Deploy feature flag code
- [ ] Route 10% of test clients to Dograh
- [ ] Monitor for 24 hours:
  - [ ] No SIP errors
  - [ ] Tool endpoints responding
  - [ ] Bookings created successfully
  - [ ] Text-backs sent (in dry-run mode)

### B4: Metrics & Monitoring ☐
- [ ] Set up Datadog/CloudWatch dashboards
- [ ] Create alerts:
  - [ ] Dograh SIP unreachable
  - [ ] Tool latency >2s
  - [ ] Booking failure rate >5%
  - [ ] SMS delivery failure >5%
- [ ] Review metrics daily
- [ ] Document baseline metrics

### B5: Gradual Traffic Increase ☐
- [ ] Day 1-2: 10% traffic, all green? → proceed
- [ ] Day 3-4: Increase to 25% traffic
- [ ] Day 5-6: Increase to 50% traffic
- [ ] Day 7: Ready for full migration?
  - [ ] No critical errors?
  - [ ] Booking rate > 90% of expected?
  - [ ] No duplicate bookings?
  - [ ] Text-backs delivering?
  - [ ] → YES: Proceed to Phase C
  - [ ] → NO: Rollback and debug

---

## Phase C: Full Migration (1 Day)

### C1: Pre-Migration ☐
- [ ] Backup database
- [ ] Notify team/stakeholders
- [ ] Have rollback plan ready
- [ ] All monitoring dashboards up
- [ ] On-call engineer standing by

### C2: Switch to 100% Dograh ☐
- [ ] Set feature flag: `DOGRAH_ENABLED = true` (100% traffic)
- [ ] Deploy
- [ ] Monitor first hour closely:
  - [ ] Incoming call rate normal?
  - [ ] Dograh SIP healthy?
  - [ ] Bookings being created?
  - [ ] Text-backs sending (switch SMS_DRY_RUN=false)?

### C3: Disable Fallbacks ☐
- [ ] After 24 hours of 100% Dograh traffic:
- [ ] Remove Vapi integration code (if present)
- [ ] Remove `voice_agent_enabled` toggle (assume true)
- [ ] Clean up Vapi environment variables
- [ ] Deploy cleanup

### C4: Decommission Vapi ☐
- [ ] Cancel Vapi account (or keep as backup for 30 days)
- [ ] Update billing records
- [ ] Document cost savings achieved
- [ ] Archive Vapi integration code to git history

---

## Phase D: Optimization & Hardening (Ongoing)

### D1: Performance Tuning ☐
- [ ] Analyze slow tool calls (>1s latency)
- [ ] Optimize availability query
- [ ] Optimize booking insertion
- [ ] Cache business knowledge (if accessed frequently)
- [ ] Consider connection pooling for Supabase

### D2: Prompt Engineering ☐
- [ ] Collect examples of bad parameter extraction
- [ ] Refine agent prompt to be more explicit
- [ ] Add examples to prompt (few-shot learning)
- [ ] Test revised prompt with mock calls
- [ ] A/B test prompt variations

### D3: Infrastructure ☐
- [ ] If self-hosted: Optimize server size (right-size resources)
- [ ] Monitor Dograh CPU/memory usage
- [ ] Configure auto-scaling if needed
- [ ] Set up database backups
- [ ] Test disaster recovery (restore from backup)

### D4: Reliability ☐
- [ ] Implement retry logic for tool failures
- [ ] Add circuit breaker for Dograh SIP
- [ ] Set up graceful degradation (fallback to text-back)
- [ ] Monitor MTTR (mean time to recovery) for incidents
- [ ] Post-mortems on any outages

---

## Rollback Triggers

**IMMEDIATE ROLLBACK if:**
- [ ] SIP connection completely down for >5 minutes
- [ ] Tool endpoints unreachable (>10% errors)
- [ ] Duplicate bookings created (idempotency failing)
- [ ] SMS delivery rate drops below 80%
- [ ] Cost exceeds budget by >50%

**Quick Rollback Steps:**
```bash
# 1. Disable Dograh (all calls to text-back)
UPDATE clients SET voice_agent_enabled = false;

# 2. Roll back code
git revert <commit-hash>
git push

# 3. Investigate root cause
docker compose logs dograh api  # if self-hosted
# or check Dograh dashboard if managed

# 4. Fix issue
# 5. Re-enable gradually
```

---

## Success Criteria

**Phase A Success:**
- ✓ All code implemented and tested
- ✓ Staging deployment green
- ✓ No TypeScript errors

**Phase B Success:**
- ✓ 10% traffic running stable for 24h
- ✓ Booking rate ≥ 90% vs. baseline
- ✓ No duplicate bookings
- ✓ Tool latency < 1s p95
- ✓ Can scale to 25% and beyond

**Phase C Success:**
- ✓ 100% traffic stable for 24h
- ✓ No increase in error rate
- ✓ SMS delivery ≥ 95%
- ✓ Cost confirmed lower than Vapi

**Phase D Success:**
- ✓ Prompts tuned (parameter extraction >95% success)
- ✓ Infrastructure optimized (right-sized)
- ✓ Runbooks documented
- ✓ Team trained on incident response
- ✓ Cost savings documented ($X/month saved)

---

## Sign-Off

- [ ] PM approves migration plan
- [ ] Eng lead approves code review
- [ ] Ops approves infrastructure
- [ ] QA completes test plan
- [ ] On-call engineer briefed

**Ready to start Phase A:** _______________  (date)  
**Ready to start Phase B:** _______________  (date)  
**Ready to start Phase C:** _______________  (date)  
**Migration complete:** _______________  (date)

---

## Appendix: Key Contacts & Escalation

**For issues:**
- Dograh support: https://github.com/dograh-hq/dograh/issues
- Twilio support: https://www.twilio.com/help
- Infrastructure provider: [your host] support

**On-call engineer:** _______________  
**Backup:** _______________  
**PM:** _______________  

**Incident bridge:** _______________  (Zoom/Slack channel)
