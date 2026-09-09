import { db } from "@/lib/supabase";
import { upsertContact } from "@/lib/clients";
import { sendTextback } from "@/lib/textback";

export const dynamic = "force-dynamic";

/**
 * Dograh webhook handler for end-of-call reports.
 * Fires once per call after workflow completes with all context.
 */
export async function POST(req: Request) {
  let payload: any;
  try {
    const body = await req.json();
    payload = body;
  } catch (e) {
    console.error("dograh webhook: invalid json", { error: String(e) });
    return new Response("invalid json", { status: 400 });
  }

  try {
    const workflowRunId = payload.workflow_run_id as string | undefined;
    const initialContext = payload.initial_context as Record<string, unknown> | undefined;
    const gatherContext = payload.gathered_context as Record<string, unknown> | undefined;

    if (!workflowRunId) {
      console.warn("dograh webhook: missing workflow_run_id");
      return new Response("ok", { status: 200 });
    }

    if (!initialContext?.client_id) {
      console.warn("dograh webhook: missing initial_context.client_id", { workflowRunId });
      return new Response("ok", { status: 200 });
    }

    const clientId = initialContext.client_id as string;
    const callerNumber = initialContext.caller_number as string | undefined;

    if (!callerNumber) {
      console.warn("dograh webhook: missing caller_number", { workflowRunId, clientId });
      return new Response("ok", { status: 200 });
    }

    // Check if booking was made (extracted from gathered_context by workflow)
    const bookingMade = gatherContext?.booking_made === true || gatherContext?.booking_made === "true";
    const appointmentDetails = gatherContext?.appointment as Record<string, unknown> | undefined;

    // Fetch client for text-back
    const { data: clientData } = await db()
      .from("clients")
      .select("*")
      .eq("id", clientId)
      .single();

    const client = clientData as any;
    if (!client) {
      console.warn("dograh webhook: client not found", { clientId, workflowRunId });
      return new Response("ok", { status: 200 });
    }

    // Upsert contact
    await upsertContact(clientId, callerNumber);

    // Send appropriate text-back
    if (bookingMade && appointmentDetails) {
      const appointmentTime = appointmentDetails.start_time as string | undefined;
      const appointmentService = appointmentDetails.service as string | undefined;

      let confirmationText =
        appointmentTime && appointmentService
          ? `Great! Your ${appointmentService} is confirmed for ${appointmentTime}. See you soon!`
          : "Great! Your appointment is confirmed. See you soon!";

      await sendTextback({
        client,
        toNumber: callerNumber,
        callId: null,
        bodyOverride: confirmationText,
      });

      console.info("dograh webhook: booking confirmation sent", {
        clientId,
        callerNumber,
        workflowRunId,
      });
    } else {
      // No booking made; send missed-call text-back
      await sendTextback({
        client,
        toNumber: callerNumber,
        callId: null,
      });

      console.info("dograh webhook: missed call text-back sent", { clientId, callerNumber, workflowRunId });
    }

    return new Response(JSON.stringify({ success: true, workflowRunId }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  } catch (e) {
    console.error("dograh webhook error", { error: String(e) });
    return new Response("internal error", { status: 500 });
  }
}
