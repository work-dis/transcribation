from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from pathlib import Path
from conversation_core.db import *
from conversation_core.domain import *
from conversation_core.media import LocalMediaStorage, validate_media
from conversation_core.config import settings
from conversation_core.application import ConversationService

@asynccontextmanager
async def lifespan(app): await init_db(); yield
app=FastAPI(title="Conversation Intelligence API", version="0.1.0", lifespan=lifespan)
class CreateConversation(BaseModel): owner_user_id: str|None=None; source_type: SourceType=SourceType.API; title: str|None=None; selected_mode: ProcessingMode|None=None
@app.get("/health")
async def health(): return {"status":"ok"}
@app.post("/v1/conversations")
async def create(payload: CreateConversation):
    async with Session() as s:
        item=ConversationModel(owner_user_id=payload.owner_user_id, source_type=payload.source_type, title=payload.title, selected_mode=payload.selected_mode)
        s.add(item); await s.commit(); await s.refresh(item); return {"id":item.id,"status":item.status,"source_type":item.source_type}
@app.get("/v1/conversations")
async def list_conversations(limit: int=Query(50,le=100)):
    async with Session() as s: return [{"id":x.id,"title":x.title,"status":x.status,"created_at":x.created_at} for x in (await s.execute(select(ConversationModel).order_by(ConversationModel.created_at.desc()).limit(limit))).scalars()]
@app.get("/v1/conversations/{conversation_id}")
async def get(conversation_id: str):
    async with Session() as s:
        x=await get_conversation(s,conversation_id)
        if not x: raise HTTPException(404,"conversation not found")
        return {"id":x.id,"title":x.title,"status":x.status,"source_type":x.source_type,"selected_mode":x.selected_mode}
@app.post("/v1/conversations/{conversation_id}/media")
async def attach(conversation_id: str, file: UploadFile=File(...)):
    async with Session() as s:
        x=await get_conversation(s,conversation_id)
        if not x: raise HTTPException(404,"conversation not found")
        data=await file.read(); validate_media(file.filename or "media",file.content_type,len(data))
        path=LocalMediaStorage().conversation_dir(conversation_id)/(Path(file.filename or "media").name); path.write_bytes(data)
        s.add(MediaAssetModel(conversation_id=conversation_id,filename=file.filename,mime_type=file.content_type,temporary_path=str(path),size_bytes=len(data))); x.status=ConversationStatus.MEDIA_ATTACHED; await s.commit(); return {"status":x.status,"path":str(path)}
@app.post("/v1/conversations/{conversation_id}/transcribe")
async def transcribe(conversation_id: str):
    try:
        t,cached=await ConversationService().transcribe(conversation_id)
        return {"id":t.id,"text":t.raw_text,"language":t.language,"cached":cached}
    except ValueError as e: raise HTTPException(404,str(e)) from e
@app.post("/v1/conversations/{conversation_id}/process/{mode}")
async def process(conversation_id: str, mode: ProcessingMode, force: bool=False):
    try:
        row,cached=await ConversationService().process(conversation_id,mode,force=force)
        return {"mode":mode,"data":row.result_json,"cached":cached}
    except ValueError as e: raise HTTPException(404,str(e)) from e
@app.get("/v1/conversations/{conversation_id}/transcript")
async def transcript(conversation_id: str):
    async with Session() as s:
        t=await get_transcript(s,conversation_id)
        if not t: raise HTTPException(404,"transcript not found")
        return {"id":t.id,"conversation_id":t.conversation_id,"text":t.raw_text,"language":t.language}
@app.get("/v1/conversations/{conversation_id}/processing-results")
async def results(conversation_id: str):
    async with Session() as s: return [{"mode":x.mode,"data":x.result_json} for x in (await s.execute(select(ProcessingResultModel).where(ProcessingResultModel.conversation_id==conversation_id))).scalars()]
@app.get("/v1/conversations/{conversation_id}/processing-results/{mode}")
async def result(conversation_id: str, mode: ProcessingMode):
    async with Session() as s:
        x=await get_result(s,conversation_id,mode)
        if not x: raise HTTPException(404,"result not found")
        return {"mode":x.mode,"data":x.result_json}
