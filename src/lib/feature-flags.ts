import { db } from "./supabase";

/**
 * Feature flag system for Dograh canary deployment.
 * Controls what percentage of traffic routes to Dograh vs. fallback.
 */

export interface FeatureFlag {
  name: string;
  enabled: boolean;
  percentage: number; // 0-100
  rollout_strategy: "global" | "per_client" | "per_segment";
  created_at: string;
  updated_at: string;
}

/**
 * Get current Dograh rollout percentage
 * Returns: 0-100 (0 = disabled, 100 = all traffic)
 */
export async function getDograhRolloutPercentage(): Promise<number> {
  try {
    const { data, error } = await db()
      .from("feature_flags")
      .select("percentage")
      .eq("name", "dograh_enabled")
      .single();

    if (error) {
      console.warn("feature_flags: failed to fetch rollout percentage", { error: error.message });
      return 0; // Default to disabled on error
    }

    return (data?.percentage as number) || 0;
  } catch (e) {
    console.error("feature_flags: error fetching rollout", { error: String(e) });
    return 0;
  }
}

/**
 * Determine if a caller should be routed to Dograh
 * Uses hash-based consistent distribution for canary rollout
 */
export async function shouldRouteToDograh(callerNumber: string): Promise<boolean> {
  const rolloutPercentage = await getDograhRolloutPercentage();

  if (rolloutPercentage <= 0) return false;
  if (rolloutPercentage >= 100) return true;

  // Hash caller number to get consistent routing
  // Same caller always gets same decision (consistent canary assignment)
  const hash = hashCallerNumber(callerNumber);
  const bucketNumber = hash % 100;

  return bucketNumber < rolloutPercentage;
}

/**
 * Simple hash function for caller number
 * Produces consistent results for same input
 */
function hashCallerNumber(callerNumber: string): number {
  let hash = 0;
  for (let i = 0; i < callerNumber.length; i++) {
    const char = callerNumber.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}

/**
 * Update Dograh rollout percentage
 * Called by ops/admin to gradually increase traffic
 */
export async function setDograhRolloutPercentage(percentage: number): Promise<void> {
  if (percentage < 0 || percentage > 100) {
    throw new Error("Rollout percentage must be between 0 and 100");
  }

  const { error } = await db()
    .from("feature_flags")
    .update({
      percentage,
      updated_at: new Date().toISOString(),
    })
    .eq("name", "dograh_enabled");

  if (error) {
    throw new Error(`Failed to update rollout percentage: ${error.message}`);
  }

  console.info("feature_flags: dograh rollout updated", { percentage });
}

/**
 * Get rollout status for monitoring
 */
export async function getRolloutStatus(): Promise<{
  percentage: number;
  enabled: boolean;
  updated_at: string;
}> {
  const { data, error } = await db()
    .from("feature_flags")
    .select("percentage, enabled, updated_at")
    .eq("name", "dograh_enabled")
    .single();

  if (error) {
    throw new Error(`Failed to fetch rollout status: ${error.message}`);
  }

  return {
    percentage: (data?.percentage as number) || 0,
    enabled: (data?.enabled as boolean) || false,
    updated_at: (data?.updated_at as string) || new Date().toISOString(),
  };
}
