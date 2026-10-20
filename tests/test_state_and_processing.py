import pytest
from conversation_core.application import transition
from conversation_core.domain import ConversationStatus
from conversation_core.processing import chunk_text
def test_valid_transition(): assert transition(ConversationStatus.CREATED, ConversationStatus.MEDIA_ATTACHED) == ConversationStatus.MEDIA_ATTACHED
def test_invalid_transition():
    with pytest.raises(ValueError): transition(ConversationStatus.CREATED, ConversationStatus.COMPLETED)
def test_large_text_chunks(): assert all(len(x)<=10 for x in chunk_text('x'*25,10))
