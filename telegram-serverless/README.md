# Telegram voice transcriber

Минимальный Telegram Serverless-бот: получает голосовое сообщение и возвращает русскую транскрипцию.

## Подготовка

1. В `@BotFather` открыть бота → `Serverless` → включить функцию и получить CLI Access Token.
2. В этом каталоге установить зависимости:

   ```bash
   npm install
   ```

3. Создать локальный файл с ключом:

   ```bash
   cp tgcloud/lib/secrets.example.js tgcloud/lib/secrets.js
   ```

   В `tgcloud/lib/secrets.js` указать отдельный OpenRouter API key с небольшим лимитом расходов. Файл исключён из Git.

4. Авторизовать CLI и развернуть:

   ```bash
   npx tgcloud login
   npx tgcloud push
   npx tgcloud webhook sync
   ```

После этого бот должен отвечать на обычные голосовые сообщения. Telegram Serverless получает файл через Bot API, поэтому максимальный размер входного файла для этого варианта — 20 МБ.

Ключ OpenRouter не следует использовать из основного production-контура без отдельного лимита: текущая документация Telegram Serverless описывает внешние HTTP-запросы, но не описывает отдельный secret manager для произвольных API-ключей.
