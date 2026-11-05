from apps.transcriber_bot.main import _mime_for, split_text


def test_split_text_respects_telegram_limit():
    parts = split_text("a" * 9000)
    assert [len(part) for part in parts] == [4096, 4096, 808]


def test_mime_for_telegram_audio():
    assert _mime_for("voice.ogg") == "audio/ogg"
    assert _mime_for("recording.mp3") == "audio/mpeg"
