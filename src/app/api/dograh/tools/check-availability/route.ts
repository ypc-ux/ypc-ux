import { db } from "@/lib/supabase";
import { loadKnowledge, resolveSlotMinutes } from "@/lib/knowledge";
import { availableSlots } from "@/lib/availability";

/**
 * HTTP tool endpoint for Dograh's check_availability tool.
 * Dograh's LLM extracts parameters and calls this endpoint.
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
    const preferredDate = body.preferred_date as string | undefined;

    if (!clientId || !serviceName) {
      return new Response(JSON.stringify({ error: "missing client_id or service_name" }), { status: 400 });
    }

    // Load client and knowledge
    const { data: clientData } = await db().from("clients").select("*").eq("id", clientId).single();

    if (!clientData) {
      return new Response(JSON.stringify({ error: "client not found" }), { status: 404 });
    }

    const client = clientData as any;
    const knowledge = await loadKnowledge(clientId);
    const slotMinutes = resolveSlotMinutes(knowledge, serviceName);

    const slots = await availableSlots(
      clientId,
      client.timezone as string,
      knowledge.hours,
      knowledge.booking_rules,
      slotMinutes,
    );

    // Filter by preferred date if provided
    const filtered = preferredDate ? slots.filter((s) => s.start.toISOString().startsWith(preferredDate)) : slots;

    const slotObjects = filtered.slice(0, 5).map((s) => ({
      start: s.start.toISOString(),
      end: s.end.toISOString(),
      label: s.label,
    }));

    return new Response(
      JSON.stringify({
        slots: slotObjects,
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  } catch (e) {
    console.error("dograh check_availability error", { error: String(e) });
    return new Response(JSON.stringify({ error: String(e) }), { status: 500 });
  }
}
