import { requestJson } from './http';

export interface PromptTraceItem {
  id: string;
  user_id: string;
  conversation_id: string;
  message_id: string;
  route_mode: string;
  conversation_mode: string;
  pinned_prefix_sha: string;
  character_card_sha: string;
  tool_catalog_sha: string;
  skill_catalog_sha: string;
  memory_ids: string[];
  activated_skill_names: string[];
  tool_names_available: string[];
  vision_context_used: boolean;
  persona_context_used: boolean;
  emotion_context_used: boolean;
  browser_context_used: boolean;
  mcp_context_used: boolean;
  router_reason: string;
  context_summary: Record<string, unknown>;
  created_at: string;
}

export interface ActionAuditItem {
  id: string;
  user_id: string | null;
  conversation_id: string | null;
  message_id: string | null;
  source: string;
  action_type: string;
  target: string;
  status: string;
  risk_level: string;
  requires_confirmation: boolean;
  policy_allowed: boolean;
  verified: boolean;
  arguments_redacted: Record<string, unknown>;
  result_summary: string;
  reasons: string[];
  checked_fields: Record<string, unknown>;
  created_at: string;
  finished_at: string | null;
}

export function listPromptTraces(
  accessToken: string,
  conversationId: string,
): Promise<PromptTraceItem[]> {
  return requestJson<PromptTraceItem[]>(
    `/debug/prompt-traces/conversations/${encodeURIComponent(conversationId)}`,
    { accessToken },
  );
}

export function getPromptTrace(
  accessToken: string,
  messageId: string,
): Promise<PromptTraceItem | null> {
  return requestJson<PromptTraceItem | null>(
    `/debug/prompt-traces/messages/${encodeURIComponent(messageId)}`,
    { accessToken },
  );
}

export function listActionAudits(
  accessToken: string,
  source?: string,
  limit = 50,
  offset = 0,
): Promise<{ items: ActionAuditItem[] }> {
  const query: Record<string, string> = { limit: String(limit), offset: String(offset) };
  if (source) query.source = source;
  return requestJson<{ items: ActionAuditItem[] }>('/debug/action-audits', {
    accessToken,
    query,
  });
}
