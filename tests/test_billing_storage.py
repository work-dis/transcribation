import asyncio

from apps.transcriber_bot import storage


def test_payment_is_idempotent_and_usage_is_refunded(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "voicetype.db"))
        await storage.init_db()

        assert await storage.record_payment(42, "one_1", "charge-1", 235, 60, 60)
        assert not await storage.record_payment(42, "one_1", "charge-1", 235, 60, 60)
        assert await storage.get_balance(42) == (60, 60)

        assert await storage.charge_usage(42, 3, 2)
        assert await storage.get_balance(42) == (57, 58)
        await storage.refund_usage(42, 3, 2)
        assert await storage.get_balance(42) == (60, 60)

    asyncio.run(scenario())


def test_usage_cannot_overdraw_balance(tmp_path, monkeypatch):
    async def scenario():
        monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "voicetype.db"))
        await storage.init_db()
        await storage.add_balance(42, 2, 1)

        assert not await storage.charge_usage(42, 3, 1)
        assert await storage.get_balance(42) == (2, 1)

    asyncio.run(scenario())
