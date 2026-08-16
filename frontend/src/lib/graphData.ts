import { METRIC_DEFINITIONS, type MetricKey } from "./metricDefinitions";
import type { AdvancedTrendPoint } from "./types";

export function computeChartData(
  trend: AdvancedTrendPoint[],
  primaryMetricKey: MetricKey,
  strengthState: string
): AdvancedTrendPoint[] {
  const graphStrengthState = METRIC_DEFINITIONS[primaryMetricKey].strengthAware
    ? strengthState
    : "5v5";
  return trend.filter((row) => row.strength_state === graphStrengthState);
}
