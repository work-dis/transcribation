import { fetch, FormData, InputFile } from 'sdk';
import { OPENROUTER_API_KEY } from './secrets.js';

const OPENROUTER_URL = 'https://openrouter.ai/api/v1/audio/transcriptions';
const MODEL = 'openai/whisper-large-v3-turbo';

export async function transcribeRussianVoice(bytes, filename = 'voice.ogg') {
  if (!OPENROUTER_API_KEY || OPENROUTER_API_KEY.includes('replace-me')) {
    throw new Error('OpenRouter key is not configured');
  }

  const form = new FormData();
  form.append('file', new InputFile(bytes, filename, { type: 'audio/ogg' }));
  form.append('model', MODEL);
  form.append('language', 'ru');
  form.append('response_format', 'json');

  const response = await fetch(OPENROUTER_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${OPENROUTER_API_KEY}`,
    },
    body: form,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Transcription provider returned ${response.status}: ${detail.slice(0, 300)}`);
  }

  const payload = await response.json();
  const text = typeof payload?.text === 'string' ? payload.text.trim() : '';
  if (!text) throw new Error('Transcription provider returned empty text');
  return text;
}
