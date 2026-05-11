export type RouteMode = 'auto' | 'chat' | 'agent';
export type MessageRole = 'user' | 'assistant' | 'system';
export type ReminderMode = 'none' | 'toast' | 'sound';
export type AvatarTool = 'lollipop' | 'fist' | 'hammer';

export type Live2DEmotionMappingItem = {
  expression?: string;
  motion?: string;
};

export type Live2DEmotionMapping = Record<string, Live2DEmotionMappingItem>;

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

export type ChatMessage = ApiMessage & {
  status?: 'sending' | 'streaming' | 'sent' | 'failed';
  local?: boolean;
};

export type StreamEvent =
  | {
      type: 'conversation';
      payload: {
        conversation_id: string;
        route_mode: RouteMode;
        title: string;
        user_message: ApiMessage;
      };
    }
  | { type: 'chunk'; payload: { delta: string } }
  | {
      type: 'done';
      payload: {
        conversation_id: string;
        assistant_message: ApiMessage;
      };
    };

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
