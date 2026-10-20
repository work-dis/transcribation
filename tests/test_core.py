from conversation_core.domain import ProcessingMode
from conversation_core.processing import chunk_text, dedupe_items
from conversation_core.media import validate_media
def test_all_modes(): assert len(ProcessingMode)==5
def test_chunk_and_dedupe(): assert len(chunk_text('a'*25,10))==3; assert dedupe_items(['a','a','b'])==['a','b']
def test_media_validation(): validate_media('voice.ogg','audio/ogg',100)
