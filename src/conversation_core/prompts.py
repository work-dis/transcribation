from .domain import ProcessingMode

BASE = "Use only information supported by the transcript. Never invent names, dates, amounts, tasks, decisions, or intent. Preserve important names, numbers, URLs and company names."
PROMPTS = {
 ProcessingMode.CLEAN_TRANSCRIPT: "You are editing raw speech into readable written text. Preserve useful meaning; add punctuation and paragraphs; remove filler and meaningless repetition. Do not summarize or invent. Return only cleaned text.",
 ProcessingMode.SUMMARY: "Analyze a real conversation. Return JSON with title, short_summary, key_points. Do not invent participants, decisions or commitments.",
 ProcessingMode.MEETING_PROTOCOL: "Create practical meeting minutes. Return JSON with title, short_summary, decisions, tasks (task, assignee, deadline, context), open_questions. Suggestions are not decisions; unknown fields are null.",
 ProcessingMode.CONVERSATION_ANALYSIS: "Analyze deeply but factually. Return JSON with title, short_summary, key_points, decisions, tasks, open_questions, entities, important_facts, objections, agreements, commitments, risks_or_uncertainties. Do not infer emotional state.",
}
def prompt_for(mode: ProcessingMode, transcript: str) -> str:
    return f"{PROMPTS[mode]}\n{BASE}\n\nTranscript:\n{transcript}"
