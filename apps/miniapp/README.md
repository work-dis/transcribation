# VoiceType Mini App

Пользовательский Telegram Mini App: главная, последние записи, просмотр текста и итогов, баланс.

## Vercel

Импортируйте репозиторий отдельно от админской панели и укажите:

```text
Root Directory: apps/miniapp
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

После публикации добавьте URL приложения в `.env.transcriber`:

```text
MINI_APP_URL=https://your-miniapp-domain.example.com
```

Бот покажет кнопку «Открыть кабинет» в главном меню только если `MINI_APP_URL` задан.

История подключается к API через `VITE_API_BASE_URL` и передаёт Telegram `initData` в заголовке `Authorization: tma ...`. До подключения API приложение показывает безопасное пустое демо-состояние, чтобы интерфейс можно было проверить в браузере.
