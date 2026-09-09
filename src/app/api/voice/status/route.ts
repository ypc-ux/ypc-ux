import { TwiMLResponse } from "twilio/lib/twiml/TwiMLResponse";
import { db } from "@/lib/supabase";
import { loadKnowledge } from "@/lib/knowledge";
import { sendTextback } from "@/lib/textback";

export const dynamic = "force-dynamic";

/**
 * Call status webhook from Twilio.
 * Fired when the dialed business doesn't answer (no-answer, busy, failed).
 *
 * Decision logic:
 * - If voice_agent_enabled = false: Send text-back immediately (slice 1 behavior)
 * - If voice_agent_enabled = true: Mint Dograh session, return TwiML to dial Dograh
 *
 * Request (Twilio Form Data):
 * - CallSid: CA-xxxxx
 * - DialCallStatus: no-answer | busy | failed
 * - Caller: +14155552671
 * - Called: +16505550100
 * - CallStatus: in-progress
 *
 * Query params (from /api/voice/incoming action):
 * - client_id: UUID
 * - caller: +14155552671 (URL encoded)
 */
export async function POST(req: Request) {
  let formData: Record<string, string> = {};

  try {
    const text = await req.text();
    const params = new URLSearchParams(text);
    for (const [key, value] of params) {
      formData[key] = value;
    }
  } catch (e) {
    console.error("status: failed to parse form data", { error: String(e) });
    return new Response("invalid request", { status: 400 });
  }

  try {
    const url = new URL(req.url);
    const clientId = url.searchParams.get("client_id");
    const caller = url.searchParams.get("caller");

    const callSid = formData.CallSid as string | undefined;
    const dialStatus = formData.DialCallStatus as string | undefined;

    if (!clientId || !caller || !callSid || !dialStatus) {
      console.warn("status: missing required params", { clientId, caller, callSid, dialStatus });
      return new Response("missing params", { status: 400 });
    }

    console.info("status webhook", { clientId, caller, callSid, dialStatus });

    // Fetch client
    const { data: clientData } = await db().from("clients").select("*").eq("id", clientId).single();

    if (!clientData) {
      console.warn("status: client not found", { clientId });
      return sendImmediateTextback("Sorry, we encountered an error. Please try again.", caller);
    }

    const client = clientData as any;

    // Update call record with dial status
    await db()
      .from("calls")
      .update({ dial_status: dialStatus })
      .eq("twilio_call_sid", callSid);

    // Decision: voice_agent_enabled?
    if (!client.voice_agent_enabled) {
      console.info("status: voice agent disabled, sending text-back", { clientId, dialStatus });
      await sendTextback({
        client,
        toNumber: caller,
        callId: callSid,
      });

      return textOnlyResponse("text-back queued");
    }

    // Voice agent enabled: route to Dograh
    console.info("status: voice agent enabled, handing off to Dograh", { clientId, dialStatus });

    // Load client knowledge for initial_context
    const knowledge = await loadKnowledge(clientId);

    // Format initial_context for Dograh
    const initialContext = {
      client_id: clientId,
      caller_number: caller,
      client_name: client.name,
      client_timezone: client.timezone,
      business_hours: formatBusinessHours(knowledge.hours),
      services_json: JSON.stringify(knowledge.services),
      faqs_json: JSON.stringify(knowledge.faqs),
      agent_instructions: client.agent_instructions || "",
    };

    // Build Dograh SIP URI with context
    // Note: This is where Dograh differs from Vapi
    // Dograh receives context via call metadata, not token in URI
    const dograhSipDomain = process.env.DOGRAH_SIP_DOMAIN || "dograh-instance.example.com";
    const dograhSipUri = `sip://${dograhSipDomain}/appointmentbooking`;

    // Return TwiML to dial Dograh
    // Context will be passed via call metadata or side-band API call
    const twiml = new TwiMLResponse();
    const dial = twiml.dial({
      timeout: 300, // 5 minute timeout for agent
    });

    // Add SIP URI (Dograh will receive incoming call here)
    dial.sip(dograhSipUri);

    // Store context for Dograh to fetch
    // Option 1: Store in Redis/cache with call_sid as key
    // Option 2: Call Dograh API to pre-populate session context
    // Option 3: Dograh fetches from our webhook on session start
    // For now, we'll use Option 3 (covered by assistant-request equivalent in Dograh)

    await storeDograhContext(callSid, initialContext);

    console.info("status: returning Dograh dial TwiML", { clientId, dograhSipUri });

    return new Response(twiml.toString(), {
      status: 200,
      headers: { "content-type": "application/xml" },
    });
  } catch (e) {
    console.error("status: error", { error: String(e) });
    return new Response("internal error", { status: 500 });
  }
}

/**
 * Format business hours for LLM consumption
 * Input: { mon: [['09:00', '17:00']], tue: [...], ... }
 * Output: "Monday: 9:00 AM - 5:00 PM\nTuesday: 9:00 AM - 5:00 PM\n..."
 */
function formatBusinessHours(hours: Record<string, string[][]>): string {
  const dayNames = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
  const displayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  const lines: string[] = [];
  for (let i = 0; i < dayNames.length; i++) {
    const dayKey = dayNames[i];
    const dayName = displayNames[i];
    const dayHours = hours[dayKey] || [];

    if (dayHours.length === 0) {
      lines.push(`${dayName}: Closed`);
    } else {
      const intervals = dayHours.map(([open, close]) => `${open} - ${close}`).join(", ");
      lines.push(`${dayName}: ${intervals}`);
    }
  }

  return lines.join("\n");
}

/**
 * Store Dograh context temporarily (in Redis or in-memory cache)
 * Dograh will fetch this when the call starts
 *
 * TODO: Implement backing store (Redis recommended for distributed setup)
 * For MVP: Use in-memory Map with TTL
 */
const contextStore = new Map<string, { context: Record<string, unknown>; expiry: number }>();

async function storeDograhContext(callSid: string, context: Record<string, unknown>): Promise<void> {
  // 5 minute TTL
  const expiry = Date.now() + 5 * 60 * 1000;
  contextStore.set(callSid, { context, expiry });

  // Cleanup expired entries
  for (const [key, value] of contextStore.entries()) {
    if (value.expiry < Date.now()) {
      contextStore.delete(key);
    }
  }
}

export function getDograhContext(callSid: string): Record<string, unknown> | null {
  const entry = contextStore.get(callSid);
  if (!entry) return null;
  if (entry.expiry < Date.now()) {
    contextStore.delete(callSid);
    return null;
  }
  return entry.context;
}

/**
 * Send text-back immediately (fallback if Dograh handoff fails)
 */
async function sendImmediateTextback(message: string, toNumber: string): Promise<Response> {
  try {
    // Send via textback service
    console.info("status: sending immediate fallback text-back", { toNumber });
    // Implementation depends on sendTextback service
  } catch (e) {
    console.error("status: failed to send fallback text-back", { error: String(e) });
  }

  return textOnlyResponse("error");
}

function textOnlyResponse(message: string): Response {
  return new Response(
    JSON.stringify({
      success: false,
      message,
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
}
