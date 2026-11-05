import { api } from 'sdk';
import { transcribeRussianVoice } from '../lib/transcribe.js';

const MAX_TELEGRAM_FILE_BYTES = 20 * 1024 * 1024;
const TELEGRAM_MESSAGE_LIMIT = 4096;

function chunks(text) {
  const result = [];
  for (let offset = 0; offset < text.length; offset += TELEGRAM_MESSAGE_LIMIT) {
    result.push(text.slice(offset, offset + TELEGRAM_MESSAGE_LIMIT));
  }
  return result;
}

export default async function (message) {
  const voice = message?.voice;
  if (!voice) return;

  if (voice.file_size && voice.file_size > MAX_TELEGRAM_FILE_BYTES) {
    await api.sendMessage({
      chat_id: message.chat.id,
      text: 'Файл слишком большой для расшифровки. Отправьте голосовое сообщение до 20 МБ.',
    });
    return;
  }

  const progress = await api.sendMessage({
    chat_id: message.chat.id,
    text: 'Расшифровываю голосовое сообщение…',
  });

  try {
    const bytes = await api.getFileContent(voice.file_id);
    const text = await transcribeRussianVoice(bytes, `voice-${voice.file_unique_id ?? voice.file_id}.ogg`);

    await api.deleteMessage({ chat_id: message.chat.id, message_id: progress.message_id });
    for (const part of chunks(text)) {
      await api.sendMessage({ chat_id: message.chat.id, text: part });
    }
  } catch (error) {
    console.error('voice transcription failed', error);
    await api.editMessageText({
      chat_id: message.chat.id,
      message_id: progress.message_id,
      text: 'Не получилось расшифровать сообщение. Попробуйте отправить его ещё раз.',
    });
  }
}
