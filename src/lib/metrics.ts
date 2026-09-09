/**
 * Metrics collection for Dograh canary deployment monitoring.
 * Tracks call routing, tool performance, booking rate, text-back delivery.
 */

import { db } from "./supabase";

export interface CallMetric {
  client_id: string;
  caller_number: string;
  call_sid: string;
  routed_to: "dograh" | "textback"; // Where this call was routed
  timestamp: string;
  duration_seconds?: number;
  tool_calls?: number; // Number of tool calls made
  booking_made?: boolean;
  error?: string;
}

/**
 * Record a call metric for canary monitoring
 */
export async function recordCallMetric(metric: Omit<CallMetric, "timestamp">): Promise<void> {
  try {
    await db().from("call_metrics").insert({
      ...metric,
      timestamp: new Date().toISOString(),
    });
  } catch (e) {
    console.error("metrics: failed to record call metric", { error: String(e) });
    // Don't throw; metrics collection should not block call handling
  }
}

/**
 * Get canary deployment metrics for a time window
 */
export async function getCanaryMetrics(hoursBack: number = 24): Promise<{
  total_calls: number;
  dograh_calls: number;
  textback_calls: number;
  dograh_percentage: number;
  booking_rate: number; // Bookings / dograh_calls
  tool_call_latency_ms: number; // Average
  errors: Array<{ error: string; count: number }>;
}> {
  const startTime = new Date(Date.now() - hoursBack * 60 * 60 * 1000).toISOString();

  const { data: metrics, error } = await db()
    .from("call_metrics")
    .select("*")
    .gte("timestamp", startTime);

  if (error || !metrics) {
    console.error("metrics: failed to fetch canary metrics", { error: error?.message });
    return {
      total_calls: 0,
      dograh_calls: 0,
      textback_calls: 0,
      dograh_percentage: 0,
      booking_rate: 0,
      tool_call_latency_ms: 0,
      errors: [],
    };
  }

  const metricsArray = metrics as Array<CallMetric>;

  const totalCalls = metricsArray.length;
  const dograhCalls = metricsArray.filter((m) => m.routed_to === "dograh").length;
  const textbackCalls = metricsArray.filter((m) => m.routed_to === "textback").length;
  const dograhPercentage = totalCalls > 0 ? (dograhCalls / totalCalls) * 100 : 0;

  const bookings = metricsArray.filter((m) => m.booking_made === true).length;
  const bookingRate = dograhCalls > 0 ? (bookings / dograhCalls) * 100 : 0;

  // Average tool latency (simplistic; real implementation would track per-call)
  const toolLatencies = metricsArray
    .filter((m) => m.tool_calls && m.tool_calls > 0)
    .map((m) => (m.duration_seconds || 0) * 1000);
  const avgLatency =
    toolLatencies.length > 0 ? toolLatencies.reduce((a, b) => a + b, 0) / toolLatencies.length : 0;

  // Error frequency
  const errorMap = new Map<string, number>();
  metricsArray.forEach((m) => {
    if (m.error) {
      errorMap.set(m.error, (errorMap.get(m.error) || 0) + 1);
    }
  });

  const errors = Array.from(errorMap.entries())
    .map(([error, count]) => ({ error, count }))
    .sort((a, b) => b.count - a.count);

  return {
    total_calls: totalCalls,
    dograh_calls: dograhCalls,
    textback_calls: textbackCalls,
    dograh_percentage: parseFloat(dograhPercentage.toFixed(2)),
    booking_rate: parseFloat(bookingRate.toFixed(2)),
    tool_call_latency_ms: parseFloat(avgLatency.toFixed(0)),
    errors,
  };
}

/**
 * Get per-client Dograh performance (to identify problematic clients)
 */
export async function getPerClientMetrics(hoursBack: number = 24): Promise<
  Array<{
    client_id: string;
    total_calls: number;
    dograh_routed: number;
    booking_rate: number;
    error_rate: number;
  }>
> {
  const startTime = new Date(Date.now() - hoursBack * 60 * 60 * 1000).toISOString();

  const { data: metrics, error } = await db()
    .from("call_metrics")
    .select("*")
    .gte("timestamp", startTime);

  if (error || !metrics) return [];

  const metricsArray = metrics as Array<CallMetric>;

  // Group by client
  const clientMap = new Map<
    string,
    {
      total: number;
      dograh: number;
      bookings: number;
      errors: number;
    }
  >();

  metricsArray.forEach((m) => {
    const clientId = m.client_id;
    const current = clientMap.get(clientId) || { total: 0, dograh: 0, bookings: 0, errors: 0 };

    current.total += 1;
    if (m.routed_to === "dograh") {
      current.dograh += 1;
      if (m.booking_made) current.bookings += 1;
    }
    if (m.error) current.errors += 1;

    clientMap.set(clientId, current);
  });

  return Array.from(clientMap.entries()).map(([clientId, stats]) => ({
    client_id: clientId,
    total_calls: stats.total,
    dograh_routed: stats.dograh,
    booking_rate: stats.dograh > 0 ? (stats.bookings / stats.dograh) * 100 : 0,
    error_rate: (stats.errors / stats.total) * 100,
  }));
}

/**
 * Canary health check — all green?
 */
export async function canaryHealthCheck(): Promise<{
  healthy: boolean;
  issues: string[];
  metrics: Awaited<ReturnType<typeof getCanaryMetrics>>;
}> {
  const metrics = await getCanaryMetrics(1); // Last 1 hour

  const issues: string[] = [];

  if (metrics.total_calls === 0) {
    issues.push("No calls recorded in last hour");
  }

  if (metrics.dograh_calls > 0) {
    if (metrics.booking_rate < 60) {
      issues.push(`Low booking rate: ${metrics.booking_rate.toFixed(1)}% (expected >60%)`);
    }

    if (metrics.tool_call_latency_ms > 2000) {
      issues.push(`High tool latency: ${metrics.tool_call_latency_ms.toFixed(0)}ms (expected <2s)`);
    }

    const errorCount = metrics.errors.reduce((sum, e) => sum + e.count, 0);
    const errorRate = (errorCount / metrics.dograh_calls) * 100;
    if (errorRate > 10) {
      issues.push(`High error rate: ${errorRate.toFixed(1)}% (expected <10%)`);
    }
  }

  return {
    healthy: issues.length === 0,
    issues,
    metrics,
  };
}
