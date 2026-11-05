import { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Tab = 'home' | 'records' | 'balance';
type RecordItem = { id: string; title: string; date: string; duration: string; preview: string; text: string; summary?: string };

const demoRecords: RecordItem[] = [
  { id: 'demo-1', title: 'Запись встречи', date: 'Сегодня, 10:24', duration: '18 мин', preview: 'Обсудили задачи на неделю и следующие шаги команды.', text: 'Здесь появится полный текст вашей расшифровки.', summary: 'Краткие итоги, решения и задачи появятся после обработки записи.' },
];

function Icon({ name }: { name: 'home' | 'list' | 'wallet' | 'arrow' | 'chevron' | 'spark' | 'copy' }) {
  const path: Record<string, string> = {
    home: 'M3 11 12 3l9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z', list: 'M5 6h14M5 12h14M5 18h9', wallet: 'M4 7h16v12H4zM4 7l2-3h12l2 3M16 13h4', arrow: 'M5 12h14m-6-6 6 6-6 6', chevron: 'm9 18 6-6-6-6', spark: 'm12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z', copy: 'M8 8h11v12H8zM5 16H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v1',
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d={path[name]} /></svg>;
}

function App() {
  const [tab, setTab] = useState<Tab>('home');
  const [selected, setSelected] = useState<RecordItem | null>(null);
  const [records, setRecords] = useState<RecordItem[]>([]);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    webApp?.ready();
    webApp?.expand();
    const api = import.meta.env.VITE_API_BASE_URL;
    if (api && webApp?.initData) {
      fetch(`${api}/v1/miniapp/records`, { headers: { Authorization: `tma ${webApp.initData}` } })
        .then((response) => response.ok ? response.json() : [])
        .then((items: RecordItem[]) => setRecords(items));
    }
  }, []);

  const visibleRecords = records.length ? records : demoRecords;
  const title = useMemo(() => ({ home: 'Главная', records: 'Мои записи', balance: 'Баланс' })[tab], [tab]);

  const copyText = async () => {
    if (!selected) return;
    await navigator.clipboard?.writeText(selected.text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  if (selected) return <div className="shell"><header className="topbar"><button className="back" onClick={() => setSelected(null)} aria-label="Назад"><Icon name="chevron" /></button><div><span className="kicker">ЗАПИСЬ</span><h1>{selected.title}</h1></div><button className="icon-button" onClick={copyText} aria-label="Копировать"><Icon name="copy" /></button></header><main className="content detail"><div className="meta"><span>{selected.date}</span><span>{selected.duration}</span></div><section className="card"><div className="section-head"><h2>Текст</h2><button className="text-button" onClick={copyText}>{copied ? 'Скопировано' : 'Копировать'}</button></div><p className="transcript">{selected.text}</p></section><section className="card"><div className="section-head"><h2>Итоги</h2><span className="badge">AI</span></div><p className="transcript">{selected.summary || 'Итоги для этой записи ещё не готовы.'}</p></section></main></div>;

  return <div className="shell"><header className="topbar"><div className="brand"><span className="brand-mark"><Icon name="spark" /></span><div><span className="kicker">VOICETYPE</span><h1>{title}</h1></div></div><span className="avatar">VT</span></header><main className="content">{tab === 'home' && <Home onOpen={() => setTab('records')} onRecord={(item) => setSelected(item)} records={visibleRecords} />} {tab === 'records' && <Records records={visibleRecords} onOpen={setSelected} />} {tab === 'balance' && <Balance />}</main><nav className="bottom-nav" aria-label="Навигация"><NavButton active={tab === 'home'} icon="home" label="Главная" onClick={() => setTab('home')} /><NavButton active={tab === 'records'} icon="list" label="Записи" onClick={() => setTab('records')} /><NavButton active={tab === 'balance'} icon="wallet" label="Баланс" onClick={() => setTab('balance')} /></nav></div>;
}

function Home({ onOpen, onRecord, records }: { onOpen: () => void; onRecord: (item: RecordItem) => void; records: RecordItem[] }) { return <><section className="hero"><div><span className="hero-icon"><Icon name="spark" /></span><h2>Ваши разговоры<br />в порядке</h2><p>Отправьте запись боту — текст и итоги появятся здесь.</p></div><button className="round-arrow" onClick={onOpen} aria-label="Открыть записи"><Icon name="arrow" /></button></section><section className="balance-card"><div><span>Доступно сейчас</span><strong>0 <small>мин</small></strong></div><div><span>AI-действия</span><strong>0</strong></div><button onClick={() => window.alert('Пополнение будет доступно через Telegram Stars')}>Пополнить <Icon name="arrow" /></button></section><div className="section-row"><h2>Последние записи</h2><button className="link-button" onClick={onOpen}>Все записи <Icon name="arrow" /></button></div><div className="record-list">{records.slice(0, 3).map((item) => <button className="record-card" key={item.id} onClick={() => onRecord(item)}><span className="record-icon"><Icon name="list" /></span><span className="record-copy"><b>{item.title}</b><small>{item.date} · {item.duration}</small><em>{item.preview}</em></span><Icon name="chevron" /></button>)}</div><p className="hint">История хранит последние 20 расшифровок.</p></> }
function Records({ records, onOpen }: { records: RecordItem[]; onOpen: (item: RecordItem) => void }) { return <><div className="page-intro"><span className="kicker">ИСТОРИЯ</span><h2>Все записи</h2><p>Последние 20 расшифровок в одном месте.</p></div><div className="record-list">{records.map((item) => <button className="record-card" key={item.id} onClick={() => onOpen(item)}><span className="record-icon"><Icon name="list" /></span><span className="record-copy"><b>{item.title}</b><small>{item.date} · {item.duration}</small><em>{item.preview}</em></span><Icon name="chevron" /></button>)}</div></> }
function Balance() { return <><div className="page-intro"><span className="kicker">БАЛАНС</span><h2>Ваш баланс</h2><p>Минуты используются для расшифровки, AI-действия — для итогов и анализа.</p></div><section className="balance-large"><div><span>Минуты расшифровки</span><strong>0</strong><small>минут доступно</small></div><div><span>AI-действия</span><strong>0</strong><small>действий доступно</small></div></section><section className="card callout"><span className="hero-icon"><Icon name="spark" /></span><h3>Пополнить баланс</h3><p>Покупка пакетов через Telegram Stars появится здесь.</p><button className="primary" onClick={() => window.alert('Откройте раздел «Тарифы и оплата» в боте')}>Открыть тарифы <Icon name="arrow" /></button></section></> }
function NavButton({ active, icon, label, onClick }: { active: boolean; icon: 'home' | 'list' | 'wallet'; label: string; onClick: () => void }) { return <button className={active ? 'nav-button active' : 'nav-button'} onClick={onClick}><Icon name={icon} /><span>{label}</span></button> }

createRoot(document.getElementById('root')!).render(<App />);
