export type RouteMode = 'auto' | 'chat' | 'agent';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ReminderMode = 'none' | 'toast' | 'sound';
export type AvatarTool = 'lollipop' | 'fist' | 'hammer';

export type Live2DEmotionMappingItem = {
  expression?: string;
  motion?: string;
};

export type Live2DEmotionMapping = Record<string, Live2DEmotionMappingItem>;

export type ToneSettings = {
  warmth: number;
  sharpness: number;
  formality: number;
};

export type CharacterCard = {
  name: string;
  persona: string;
  tone: ToneSettings;
  example_dialogue: string[];
  visual: Record<string, string>;
  system_prompt_extra: string;
};

export type CharacterCardOverride = {
  tone?: ToneSettings;
  system_prompt_extra?: string;
};

export type AuthSession = {
  accessToken: string;
  userId: string;
  email: string;
  displayName?: string | null;
};

export type Conversation = {
  id: string;
  user_id: string;
  title: string;
  summary?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiMessage = {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  route_mode?: RouteMode | null;
  emotion?: string | null;
  created_at: string;
};

export type MessageOut = ApiMessage;

export type ChatMessage = ApiMessage & {
  status?: 'sending' | 'streaming' | 'sent' | 'failed' | 'vision-loading' | 'vision-error';
  local?: boolean;
  image_preview_url?: string | null;
  character_name?: string | null;
  character_color?: string | null;
  is_auxiliary?: boolean;
};

// ── Local Agent: Local Apps ──

export type IntentType =
  | 'open_music'
  | 'open_browser'
  | 'open_ide'
  | 'open_file_explorer'
  | 'open_terminal'
  | 'open_note_app'
  | 'open_design_app'
  | 'open_chat_app'
  | 'open_custom';

export const INTENT_TYPE_LABELS: Record<IntentType, string> = {
  open_music: '打开音乐',
  open_browser: '打开浏览器',
  open_ide: '打开 IDE',
  open_file_explorer: '打开文件管理器',
  open_terminal: '打开终端',
  open_note_app: '打开笔记应用',
  open_design_app: '打开设计软件',
  open_chat_app: '打开聊天软件',
  open_custom: '自定义（仅手动打开）',
};

export type LocalApp = {
  id: string;
  user_id: string;
  app_key: string;
  intent_type: IntentType;
  display_name: string;
  executable_path: string;
  working_dir?: string | null;
  args?: string | null;
  keywords: string[];
  enabled: boolean;
  is_default_for_intent: boolean;
  confirm_required: boolean;
  created_at: string;
  updated_at: string;
};

export type LocalAppCreateParams = {
  app_key: string;
  intent_type: IntentType;
  display_name: string;
  executable_path: string;
  working_dir?: string | null;
  args?: string | null;
  keywords?: string[];
  enabled?: boolean;
  is_default_for_intent?: boolean;
  confirm_required?: boolean;
};

export type LocalAppUpdateParams = Partial<LocalAppCreateParams>;

export type LocalAppTestResult = {
  success: boolean;
  message: string;
  exit_code?: number | null;
};

export type LocalAppOpenParams = {
  app_key?: string | null;
  intent_type?: IntentType | null;
  reason?: string | null;
};

// ── Local Agent: Pending Actions ──

export type PendingActionStatus = 'waiting_confirmation' | 'executing' | 'executed' | 'cancelled' | 'expired' | 'failed';

export type PendingAction = {
  id: string;
  user_id: string;
  conversation_id?: string | null;
  action_type: string;
  app_key?: string | null;
  display_name?: string | null;
  description: string;
  status: PendingActionStatus;
  expires_at?: string | null;
  confirmed_at?: string | null;
  cancelled_at?: string | null;
  executed_at?: string | null;
  result_message?: string | null;
  created_at: string;
};

// ── Local Agent: Action Progress (for execution log) ──

export type ActionProgress = {
  task_id?: string | null;
  action: string;
  app_key?: string | null;
  display_name?: string | null;
  status: 'starting' | 'running' | 'completed' | 'failed' | 'cancelled';
  message: string;
  timestamp: string;
};

export type ActionLogEntry = {
  timestamp: string;
  message: string;
  status: ActionProgress['status'];
  appKey?: string | null;
  displayName?: string | null;
};

export type StreamEvent =
  | { type: 'conversation'; conversationId: string; title: string; routeMode: RouteMode; userMessage: MessageOut }
  | { type: 'chunk'; delta: string }
  | { type: 'audio'; text: string; audio: string; emotion: string | null; emotionState?: EmotionState | null }
  | { type: 'done'; assistantMessages: MessageOut[]; emotionState?: EmotionState | null; pendingAction?: PendingAction | null }
  | { type: 'emotion'; emotion: string; emotionState?: EmotionState | null }
  | { type: 'progress'; skillName: string; message: string; percent: number }
  | { type: 'error'; code: string; hint: string }
  | { type: 'pending_action'; pendingAction: PendingAction }
  | { type: 'action'; action: ActionProgress };

export type Live2DModelItem = {
  id: string;
  name: string;
  entry: string;
  thumbnail?: string;
  defaultScale?: number;
  defaultX?: number;
  defaultY?: number;
  emotionMapping?: Live2DEmotionMapping;
};

export type BackgroundItem = {
  id: string;
  name: string;
  url?: string;
  gradient?: string;
};

export type MusicTrack = {
  id: string;
  title: string;
  artist?: string;
  url: string;
};

export type PetSettings = {
  modelId?: string;
  backgroundId: string;
  opacity: number;
  reminderMode: ReminderMode;
  scale: number;
  x: number;
  y: number;
};

export type UserConfigField = {
  key: string;
  value: string | number | boolean;
  source: 'user' | 'env' | 'default';
  encrypted: boolean;
};

export type UserConfigResponse = {
  fields: UserConfigField[];
};

export type UserSkill = {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  enabled: boolean;
  installed_from: string;
  source_url?: string | null;
  content?: string;
  created_at: string;
  updated_at: string;
};

export type MarketSkill = {
  name: string;
  description: string;
  tags: string[];
  version: string;
  author: string;
  official: boolean;
};

export type ConfigField = UserConfigField;

export type ConfigListResponse = UserConfigResponse;

export type ConfigUpdateRequest = Partial<{
  ai_api_key: string | null;
  ai_base_url: string | null;
  ai_model: string | null;
  ai_request_timeout_seconds: number | null;
  ai_supports_image_input: boolean | null;
  ai_lightweight_max_tokens: number | null;
  ai_vision_base_url: string | null;
  ai_vision_api_key: string | null;
  ai_vision_model: string | null;
  roleplay_llm_model: string | null;
  roleplay_llm_temperature: number | null;
  decision_llm_model: string | null;
  decision_llm_temperature: number | null;
  google_search_api_key: string | null;
  google_search_cx: string | null;
  edge_tts_voice: string | null;
  asr_engine: string | null;
  whisper_api_key: string | null;
}>;

export type SkillSummary = Omit<UserSkill, 'content'>;

export type SkillDetail = SkillSummary & {
  content: string;
};

export type SkillInstallRequest = {
  install_type: 'text';
  content: string;
};

export type ReminderEventType =
  | 'reminder.due_soon'
  | 'reminder.due_now'
  | 'reminder.snoozed'
  | 'reminder.dismissed';

export type ReminderEvent = {
  type: ReminderEventType;
  todo_id: string;
  user_id: string;
  title: string;
  due_at: string | null;
  message: string;
  reminder_count: number;
  delivery: string;
};

export type MemoryTimelineItem = {
  memory_id: string;
  content: string;
  importance: number;
  created_at: string;
  source_msg_id?: string | null;
  related_conversation_id?: string | null;
  tags: string[];
  pinned?: boolean;
  time_bucket: 'today' | 'this_week' | 'this_month' | 'earlier' | string;
};

export type MemorySearchResult = {
  memory_id: string;
  content: string;
  importance: number;
  created_at: string;
  source_msg_id?: string | null;
  related_conversation_id?: string | null;
  score?: number | null;
  source_message_summary?: string | null;
  pinned?: boolean;
  tags?: string[];
};

export type MemoryContextMessage = {
  id: string;
  role: MessageRole | string;
  content: string;
  created_at: string;
};

export type MemoryContext = {
  memory_id: string;
  source_msg_id?: string | null;
  conversation_id?: string | null;
  messages: MemoryContextMessage[];
  detail?: string | null;
};

export type PersonaVerbosity = 'quiet' | 'balanced' | 'talkative';

export type PersonaWarmth = 'calm' | 'warm' | 'playful';

export type PersonaInitiative = 'passive' | 'balanced' | 'proactive';

export type PersonaWorkStyle = 'casual' | 'focused' | 'strict';

export type PersonaSettings = {
  user_id: string;
  verbosity: PersonaVerbosity;
  warmth: PersonaWarmth;
  initiative: PersonaInitiative;
  work_style: PersonaWorkStyle;
  updated_at: string;
};

export type PersonaSettingsUpdateRequest = Partial<Pick<
  PersonaSettings,
  'verbosity' | 'warmth' | 'initiative' | 'work_style'
>>;

export type GoalStatus = 'active' | 'paused' | 'completed';

export type GoalItem = {
  id: string;
  user_id: string;
  title: string;
  description?: string | null;
  category?: string | null;
  status: GoalStatus;
  cadence_days: number;
  last_checked_at?: string | null;
  next_check_at?: string | null;
  reminder_enabled: boolean;
  completed_at?: string | null;
  paused_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type GoalCreateRequest = {
  title: string;
  description?: string | null;
  category?: string | null;
  cadence_days?: number;
  reminder_enabled?: boolean;
};

export type GoalUpdateRequest = Partial<{
  title: string;
  description: string | null;
  category: string | null;
  status: GoalStatus;
  cadence_days: number;
  reminder_enabled: boolean;
}>;

export type GoalCheckin = {
  goal_id: string;
  user_id: string;
  title: string;
  category?: string | null;
  status: GoalStatus;
  checked: boolean;
  next_check_at?: string | null;
  message: string;
};

export type EmotionLabel =
  | 'neutral'
  | 'happy'
  | 'worried'
  | 'stressed'
  | 'tired'
  | 'lonely'
  | string;

export type EmotionState = {
  emotion_label: EmotionLabel;
  confidence?: number | null;
  intensity?: number | null;
  reply_style_hint?: string | null;
};

// ── Conversation mode ──

export type ConversationMode = 'companion' | 'work' | 'focus' | 'night';

export type ModeSettings = {
  mode: ConversationMode;
  updated_at: string;
};

export type ModeUpdateRequest = {
  mode: ConversationMode;
};

// Full response from GET/PUT /modes/conversation (B12)
export type ConversationModeResponse = {
  mode: ConversationMode;
  mode_label: string;
  description: string;
  behavior: {
    mode: ConversationMode;
    mode_label: string;
    description: string;
    tool_policy: { allowed_tool_groups: string[]; blocked_tool_groups: string[] };
    reply_policy: { max_sentences: number; style: string; prioritize_conciseness: boolean };
    reminder_policy: { enabled: boolean; reduce_frequency: boolean; urgent_only: boolean; tone: string };
    decision_tendency: { chat_weight: number; agent_weight: number; prefer_todo_create: boolean; prefer_task_planning: boolean; suppress_idle_chat: boolean };
  };
  updated_at: string;
};

// ── Vision / multimodal ──

export type VisionConfidence = {
  score: number;
  label: string;
};

export type VisionAnalyzeRequest = {
  question?: string | null;
};

export type VisionAnalyzeResponse = {
  analysis_id: string;
  summary: string;
  objects: string[];
  scene?: string | null;
  text_in_image?: string | null;
  confidence: VisionConfidence;
  created_at: string;
  provider: string;
  fallback_used: boolean;
};

export type UploadedImagePreview = {
  preview_id: string;
  url: string;
  width: number;
  height: number;
  file_name: string;
};

// ── Diary ──

export type DiaryItem = {
  diary_id: string;
  date: string;
  title: string;
  summary: string;
  mood?: string | null;
  created_at: string;
};

export type DiaryDetail = DiaryItem & {
  content: string;
  tags: string[];
  source_conversation_ids: string[];
};

export type DiaryGenerateRequest = {
  date?: string | null;
  style?: string | null;
  force?: boolean;
};

export type DiaryGenerateResponse = {
  diary_id: string;
  date: string;
  title: string;
  summary: string;
  content: string;
  mood?: string | null;
  tags: string[];
};

// ── Live2D interaction ──

export type Live2DHitArea = 'head' | 'body' | 'hand' | 'unknown';

export type Live2DInteractionEvent = {
  hit_area: Live2DHitArea;
  x: number;
  y: number;
  timestamp: string;
  interaction_type?: string;
  metadata?: Record<string, unknown> | null;
};

export type Live2DInteractionFeedback = {
  event_id: string;
  interaction_type?: string;
  animation?: string | null;
  expression?: string | null;
  message?: string | null;
};

// ── Group chat characters ──

export type AssistantRole = 'narrator' | 'observer' | 'participant' | 'moderator';

export type CharacterProfile = {
  id: string;
  name: string;
  persona: string;
  avatar_url?: string | null;
  color?: string | null;
  role_type?: string | null;
  created_at: string;
};

export type GroupChatMessage = {
  id: string;
  character_id: string;
  character_name: string;
  content: string;
  role: AssistantRole;
  created_at: string;
};

export type AuxiliaryCharacterState = {
  character_id: string;
  active: boolean;
  last_spoke_at?: string | null;
  involvement: number;
};
