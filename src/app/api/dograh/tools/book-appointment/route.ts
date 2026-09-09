import { db } from "@/lib/supabase";
import { loadKnowledge, resolveSlotMinutes } from "@/lib/knowledge";

/**
 * HTTP tool endpoint for Dograh's book_appointment tool.
 * Dograh's LLM extracts appointment details and calls this endpoint.
 */
export async function POST(req: Request) {
  let body: any;
  try {
    body = await req.json();
  } catch (e) {
    return new Response(JSON.stringify({ error: "invalid json" }), { status: 400 });
  }

  try {
    const clientId = body.client_id as string | undefined;
    const serviceName = body.service_name as string | undefined;
    const startTimeStr = body.start_time as string | undefined;
    const contactName = body.contact_name as string | undefined;
    const contactPhone = body.contact_phone as string | undefined;
    const notes = body.notes as string | undefined;
    const requestedWindow = body.requested_window as string | undefined;

    if (!clientId || !serviceName || !startTimeStr || !contactName || !contactPhone) {
      return new Response(
        JSON.stringify({
          error: "missing required fields: client_id, service_name, start_time, contact_name, contact_phone",
        }),
        { status: 400 },
      );
    }

    const startTime = new Date(startTimeStr);
    const knowledge = await loadKnowledge(clientId);
    const slotMinutes = resolveSlotMinutes(knowledge, serviceName);
    const endTime = new Date(startTime.getTime() + slotMinutes * 60000);

    // Insert booking
    const { error, data } = await db()
      .from("bookings")
      .insert({
        client_id: clientId,
        service: serviceName,
        starts_at: startTime.toISOString(),
        ends_at: endTime.toISOString(),
        contact_name: contactName,
        contact_phone: contactPhone,
        notes: notes || null,
        requested_window: requestedWindow || null,
        source: "voice_agent",
      })
      .select("id");

    if (error) {
      console.error("dograh book_appointment insert error", { error: error.message, clientId, serviceName });
      return new Response(
        JSON.stringify({
          error: `booking failed: ${error.message}`,
        }),
        { status: 500 },
      );
    }

    const bookingId = data?.[0]?.id;

    return new Response(
      JSON.stringify({
        success: true,
        booking_id: bookingId,
        message: `Appointment confirmed for ${contactName} on ${startTime.toLocaleDateString()} at ${startTime.toLocaleTimeString()}`,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  } catch (e) {
    console.error("dograh book_appointment error", { error: String(e) });
    return new Response(JSON.stringify({ error: String(e) }), { status: 500 });
  }
}
