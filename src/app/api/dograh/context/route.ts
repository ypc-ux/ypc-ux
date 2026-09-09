import { getDograhContext } from "@/app/api/voice/status/route";

export const dynamic = "force-dynamic";

/**
 * Dograh context retrieval endpoint
 * Called by Dograh when a SIP call arrives to fetch the initial_context
 *
 * Query params:
 * - call_sid: Twilio call SID (key for context lookup)
 *
 * Response:
 * {
 *   "client_id": "...",
 *   "caller_number": "...",
 *   "client_name": "...",
 *   "business_hours": "...",
 *   ...
 * }
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const callSid = url.searchParams.get("call_sid");

  if (!callSid) {
    return new Response(
      JSON.stringify({ error: "missing call_sid" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  const context = getDograhContext(callSid);

  if (!context) {
    return new Response(
      JSON.stringify({
        error: "context not found or expired",
        call_sid: callSid,
      }),
      { status: 404, headers: { "content-type": "application/json" } },
    );
  }

  console.info("dograh context retrieved", { callSid });

  return new Response(JSON.stringify(context), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
