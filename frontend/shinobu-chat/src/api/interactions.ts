import type { Live2DInteractionEvent, Live2DInteractionFeedback } from '../types';
import { requestJson } from './http';

export function recordLive2DInteraction(
  accessToken: string,
  event: Live2DInteractionEvent,
): Promise<Live2DInteractionFeedback> {
  return requestJson<Live2DInteractionFeedback>('/interactions/live2d', {
    method: 'POST',
    accessToken,
    body: event,
  });
}
