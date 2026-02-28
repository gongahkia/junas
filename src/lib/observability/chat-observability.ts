export type ObservabilityChannel = 'provider' | 'tool';

export interface ChatObservabilityEvent {
  id: string;
  channel: ObservabilityChannel;
  name: string;
  operation: string;
  durationMs: number;
  success: boolean;
  failureRate: number;
  averageDurationMs: number;
  timestamp: string;
  error?: string;
}

interface MetricAccumulator {
  total: number;
  failures: number;
  totalDurationMs: number;
}

const EVENT_NAME = 'junas-observability';
const MAX_RECENT_EVENTS = 200;
const recentEvents: ChatObservabilityEvent[] = [];
const metricAccumulators = new Map<string, MetricAccumulator>();

function createEventId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `obs-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function metricKey(channel: ObservabilityChannel, name: string, operation: string): string {
  return `${channel}:${name}:${operation}`;
}

function updateMetricAccumulator(
  channel: ObservabilityChannel,
  name: string,
  operation: string,
  durationMs: number,
  success: boolean
): { failureRate: number; averageDurationMs: number } {
  const key = metricKey(channel, name, operation);
  const current = metricAccumulators.get(key) || { total: 0, failures: 0, totalDurationMs: 0 };
  const updated: MetricAccumulator = {
    total: current.total + 1,
    failures: current.failures + (success ? 0 : 1),
    totalDurationMs: current.totalDurationMs + durationMs,
  };
  metricAccumulators.set(key, updated);

  return {
    failureRate: updated.failures / updated.total,
    averageDurationMs: updated.totalDurationMs / updated.total,
  };
}

function emitObservabilityEvent(event: ChatObservabilityEvent): void {
  recentEvents.push(event);
  if (recentEvents.length > MAX_RECENT_EVENTS) {
    recentEvents.splice(0, recentEvents.length - MAX_RECENT_EVENTS);
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(EVENT_NAME, {
        detail: event,
      })
    );
  }
}

function recordEvent(
  channel: ObservabilityChannel,
  name: string,
  operation: string,
  durationMs: number,
  success: boolean,
  error?: string
): ChatObservabilityEvent {
  const metrics = updateMetricAccumulator(channel, name, operation, durationMs, success);
  const event: ChatObservabilityEvent = {
    id: createEventId(),
    channel,
    name,
    operation,
    durationMs,
    success,
    failureRate: metrics.failureRate,
    averageDurationMs: metrics.averageDurationMs,
    timestamp: new Date().toISOString(),
    error,
  };
  emitObservabilityEvent(event);
  return event;
}

export function recordProviderObservability(
  provider: string,
  operation: string,
  durationMs: number,
  success: boolean,
  error?: string
): ChatObservabilityEvent {
  return recordEvent('provider', provider, operation, durationMs, success, error);
}

export function recordToolObservability(
  toolId: string,
  durationMs: number,
  success: boolean,
  error?: string
): ChatObservabilityEvent {
  return recordEvent('tool', toolId, 'tool_call', durationMs, success, error);
}

export function getRecentObservabilityEvents(): ChatObservabilityEvent[] {
  return [...recentEvents];
}
