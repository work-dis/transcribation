/// <reference types="vite/client" />

interface Window {
  Telegram?: { WebApp?: { ready: () => void; expand: () => void; close: () => void; initData?: string; colorScheme?: string } };
}
