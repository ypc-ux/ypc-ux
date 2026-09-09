import { TwiMLResponse } from "twilio/lib/twiml/TwiMLResponse";
import { db } from "@/lib/supabase";
import { clientByInboundNumber } from "@/lib/clients";

export const dynamic = "force-dynamic";

/**
 * Inbound call handler from Twilio.
 * Receives incoming call, looks up client by dialed number,
 * and returns TwiML to dial the business.
 *
 * Request (Twilio Form Data):
 * - Caller: +14155552671
 * - Called: +16505550100 (client's Twilio number)
 * - CallSid: CA-xxxxx
 * - AccountSid: AC-xxxxx
 * - CallStatus: ringing
 * - Direction: inbound
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
    console.error("incoming: failed to parse form data", { error: String(e) });
    return errorTwiml("invalid request");
  }

  try {
    const caller = formData.Caller as string | undefined;
    const called = formData.Called as string | undefined;
    const callSid = formData.CallSid as string | undefined;
    const accountSid = formData.AccountSid as string | undefined;

    if (!caller || !called || !callSid) {
      console.warn("incoming: missing required fields", { caller, called, callSid });
      return errorTwiml("missing fields");
    }

    console.info("incoming call", { caller, called, callSid });

    // Look up client by dialed number
    const client = await clientByInboundNumber(called);
    if (!client) {
      console.warn("incoming: client not found for number", { called });
      return errorTwiml("client not found");
    }

    // Record call initiation
    const { error: callError } = await db().from("calls").insert({
      client_id: client.id,
      caller_number: caller,
      twilio_call_sid: callSid,
      twilio_account_sid: accountSid || null,
      dial_status: "initiated",
      direction: "inbound",
    });

    if (callError) {
      console.error("incoming: failed to record call", { error: callError.message });
      // Continue anyway; don't block the call
    }

    // Dial the business number
    const businessNumber = client.forward_number;
    if (!businessNumber) {
      console.warn("incoming: client has no forward_number", { clientId: client.id });
      return errorTwiml("no forward number configured");
    }

    // Return TwiML to dial business
    const twiml = new TwiMLResponse();
    const dial = twiml.dial({
      timeout: 20,
      action: `${process.env.PUBLIC_BASE_URL}/api/voice/status?client_id=${client.id}&caller=${encodeURIComponent(caller)}`,
      method: "POST",
    });

    dial.number(businessNumber);

    console.info("incoming: dialing business", { clientId: client.id, businessNumber, timeout: 20 });

    return new Response(twiml.toString(), {
      status: 200,
      headers: { "content-type": "application/xml" },
    });
  } catch (e) {
    console.error("incoming: error", { error: String(e) });
    return errorTwiml("internal error");
  }
}

function errorTwiml(message: string): Response {
  const twiml = new TwiMLResponse();
  twiml.say(`Sorry, we encountered an error: ${message}`);
  twiml.hangup();

  return new Response(twiml.toString(), {
    status: 200,
    headers: { "content-type": "application/xml" },
  });
}
