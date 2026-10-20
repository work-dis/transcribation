"""Recorder adapter boundary. Real deployment must provide an MTProto/tgcalls backend."""
class TelegramMTProtoRecorderProvider:
    async def _unsupported(self): raise NotImplementedError("Install and configure a maintained MTProto call media backend; capture is not faked")
    async def list_available_groups(self, recorder_id): return await self._unsupported()
    async def detect_active_call(self, recorder_id, chat_id): return await self._unsupported()
    async def join_call(self, recorder_id, chat_id): return await self._unsupported()
    async def leave_call(self, recorder_id, chat_id): return await self._unsupported()
    async def start_capture(self, recorder_id, chat_id): return await self._unsupported()
    async def stop_capture(self, recorder_id, chat_id): return await self._unsupported()
