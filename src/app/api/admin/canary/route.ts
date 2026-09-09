import {
  getDograhRolloutPercentage,
  setDograhRolloutPercentage,
  getRolloutStatus,
} from "@/lib/feature-flags";
import { getCanaryMetrics, canaryHealthCheck, getPerClientMetrics } from "@/lib/metrics";

export const dynamic = "force-dynamic";

/**
 * Canary deployment admin API
 *
 * Requires authorization header: Authorization: Bearer CRON_SECRET
 *
 * Endpoints:
 * - GET /api/admin/canary/status — Get current rollout percentage
 * - GET /api/admin/canary/metrics — Get canary performance metrics
 * - GET /api/admin/canary/health — Health check (all green?)
 * - GET /api/admin/canary/per-client — Metrics by client
 * - POST /api/admin/canary/rollout — Set rollout percentage
 */

async function authorize(req: Request): Promise<boolean> {
  const authHeader = req.headers.get("authorization");
  if (!authHeader) return false;

  const [scheme, token] = authHeader.split(" ");
  if (scheme !== "Bearer") return false;

  const expected = process.env.CRON_SECRET || process.env.ADMIN_TOKEN;
  return token === expected;
}

export async function GET(req: Request) {
  if (!(await authorize(req))) {
    return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 });
  }

  const url = new URL(req.url);
  const action = url.pathname.split("/").pop();

  try {
    switch (action) {
      case "status": {
        const status = await getRolloutStatus();
        return new Response(JSON.stringify(status), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      case "metrics": {
        const hoursBack = parseInt(url.searchParams.get("hours") || "24", 10);
        const metrics = await getCanaryMetrics(hoursBack);
        return new Response(JSON.stringify(metrics), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      case "health": {
        const health = await canaryHealthCheck();
        return new Response(JSON.stringify(health), {
          status: health.healthy ? 200 : 503,
          headers: { "content-type": "application/json" },
        });
      }

      case "per-client": {
        const hoursBack = parseInt(url.searchParams.get("hours") || "24", 10);
        const perClientMetrics = await getPerClientMetrics(hoursBack);
        return new Response(JSON.stringify({ metrics: perClientMetrics }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }

      default:
        return new Response(JSON.stringify({ error: "unknown action" }), { status: 400 });
    }
  } catch (e) {
    console.error("canary admin: error", { error: String(e) });
    return new Response(
      JSON.stringify({
        error: "internal error",
        message: String(e),
      }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }
}

export async function POST(req: Request) {
  if (!(await authorize(req))) {
    return new Response(JSON.stringify({ error: "unauthorized" }), { status: 401 });
  }

  try {
    const body = await req.json();
    const { percentage } = body;

    if (typeof percentage !== "number" || percentage < 0 || percentage > 100) {
      return new Response(
        JSON.stringify({
          error: "invalid percentage",
          message: "percentage must be a number between 0 and 100",
        }),
        { status: 400, headers: { "content-type": "application/json" } },
      );
    }

    await setDograhRolloutPercentage(percentage);

    const status = await getRolloutStatus();
    console.info("canary: rollout updated", { percentage });

    return new Response(JSON.stringify({ success: true, status }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  } catch (e) {
    console.error("canary admin: post error", { error: String(e) });
    return new Response(
      JSON.stringify({
        error: "internal error",
        message: String(e),
      }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }
}
