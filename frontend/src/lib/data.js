import { readFileSync } from 'node:fs'

/**
 * Loads output/data.json — the single contract between the Python data layer
 * and this renderer. Python owns fetching and shape; the frontend owns
 * presentation and never reads anything else.
 */
export function loadDashboardData(dataPath) {
  const raw = JSON.parse(readFileSync(dataPath, 'utf8'))

  const environments = (raw.environments ?? []).map((env) => ({
    id: env.id,
    label: env.label ?? env.id,
    networkId: String(env.network_id ?? ''),
    contractAddress: env.contract_address ?? null,
    eligibilityPeriod: Number(env.eligibility_period) || 0,
    // 0 means the oracle has never posted an update on this network.
    oracleUpdatedAt: Number(env.last_oracle_update_time) || 0,
    indexers: Array.isArray(env.indexers) ? env.indexers : [],
    /**
     * Whether this network has anything the oracle has actually judged.
     *
     * Gated on the oracle having run, NOT on row count. The subgraph lists
     * active indexers regardless, so a network whose oracle has never posted
     * still returns a full roster of addresses whose on-chain eligibility is
     * simply unset. Rendering those as "Unqualified · never renewed" would
     * publish a verdict about named third parties that the oracle never made.
     */
    get available() {
      return this.oracleUpdatedAt > 0 && this.indexers.length > 0
    },
  }))

  return {
    generatedAt: raw.generated_at ?? 'unknown',
    criteria: raw.eligibility_criteria ?? null,
    environments,
  }
}
