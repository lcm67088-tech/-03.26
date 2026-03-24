/**
 * nplace.io — 공통 JavaScript (v3.1)
 * 인증·라우팅·사이드바·헤더·테마·토스트·모달·유틸
 * updated: 2026-03-23 (refactor) — 폴더구조 정리, 달력 간트차트, 주문 테이블 개선
 */

/* ═══════════════════════════════════════════════
   1. 테마 초기화 (깜빡임 방지 — 최상단 즉시 실행)
═══════════════════════════════════════════════ */
(function () {
  const t = localStorage.getItem('nplace-theme') || 'dark';
  if (t === 'light') document.body.classList.add('light');
})();

/* ═══════════════════════════════════════════════
   2. 백엔드 API 설정
═══════════════════════════════════════════════ */
const BACKEND_API = (() => {
  const h = location.hostname;
  if (h === 'localhost' || h === '127.0.0.1') return 'http://localhost:8001';
  // 샌드박스 환경: 3000-xxxx.e2b.dev → 8001-xxxx.e2b.dev
  if (h.match(/^\d+-/)) return location.protocol + '//' + h.replace(/^\d+-/, '8001-');
  return 'http://localhost:8001';
})();

/** JWT + workspace_id 저장/조회 */
function getToken()       { return localStorage.getItem('nplace-token'); }
function getWorkspaceId() { return localStorage.getItem('nplace-ws-id'); }
function saveToken(token, wsId) {
  localStorage.setItem('nplace-token', token);
  if (wsId) localStorage.setItem('nplace-ws-id', wsId);
}
function clearToken() {
  localStorage.removeItem('nplace-token');
  localStorage.removeItem('nplace-ws-id');
}

/**
 * 공통 API 호출 헬퍼
 * @param {string} path  - /api/v1/...
 * @param {object} opts  - fetch options override
 */
async function apiCall(path, opts = {}) {
  const token = getToken();
  const headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${BACKEND_API}${path}`, { ...opts, headers });
  if (res.status === 401) { doLogout(); throw new Error('인증이 만료되었습니다'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `API 오류 (${res.status})`);
  return data;
}

/* ═══════════════════════════════════════════════
   2-B. 인증 데이터 (데모용 폴백)
═══════════════════════════════════════════════ */
const DEMO_USERS = [
  {
    email: 'admin@nplace.io',
    password: 'password123',
    name: '김대표',
    plan: 'pro',
    isAdmin: false,
    workspace: '맛있는 식당 본점',
    wsPlan: 'pro',
    balance: 52000,
  },
  {
    email: 'superadmin@nplace.io',
    password: 'admin1234!',
    name: '이관리자',
    plan: 'enterprise',
    isAdmin: true,
    workspace: 'nplace.io 운영팀',
    wsPlan: 'enterprise',
    balance: 0,
  },
];

/* ═══════════════════════════════════════════════
   3. 전역 상태 (localStorage 기반)
═══════════════════════════════════════════════ */
function loadSession() {
  try {
    const s = localStorage.getItem('nplace-session');
    return s ? JSON.parse(s) : null;
  } catch { return null; }
}
function saveSession(user) {
  localStorage.setItem('nplace-session', JSON.stringify(user));
}
function clearSession() {
  localStorage.removeItem('nplace-session');
}

// 현재 세션 유저
let CURRENT_USER = loadSession();

// 보호 페이지에서 미로그인 시 리다이렉트
const PUBLIC_PAGES = ['index.html', ''];
(function guardRoute() {
  const page = location.pathname.split('/').pop() || 'index.html';
  if (!PUBLIC_PAGES.includes(page) && !CURRENT_USER) {
    location.href = 'index.html';
  }
  // 어드민 전용 페이지 접근 제한
  const ADMIN_ONLY = ['admin.html'];
  if (ADMIN_ONLY.includes(page) && CURRENT_USER && !CURRENT_USER.isAdmin) {
    location.href = 'dashboard.html';
  }
})();

const STATE = {
  get theme() { return localStorage.getItem('nplace-theme') || 'dark'; },
  unreadCount: 5,
  sidebarCollapsed: false,
};

/* ═══════════════════════════════════════════════
   4. SVG 아이콘 팩토리
═══════════════════════════════════════════════ */
function svg(path, size = 16) {
  return `<svg width="${size}" height="${size}" fill="none" stroke="currentColor"
    stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"
    viewBox="0 0 24 24">${path}</svg>`;
}
const iconDashboard  = () => svg('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>');
const iconMapPin     = () => svg('<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>');
const iconCart       = () => svg('<circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/>');
const iconBell       = () => svg('<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>');
const iconCreditCard = () => svg('<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>');
const iconUsers      = () => svg('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>');
const iconUser       = () => svg('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>');
const iconChart      = () => svg('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>');
const iconBuilding   = () => svg('<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>');
const iconSettings   = () => svg('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>');
const iconLogout     = () => svg('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>');
const iconZap        = () => svg('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>');
const iconChevronL   = () => svg('<polyline points="15 18 9 12 15 6"/>', 12);
const iconChevronR   = () => svg('<polyline points="9 18 15 12 9 6"/>', 12);
const iconClose      = () => svg('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>', 16);
const iconSearch     = () => svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>', 16);
const iconPlus       = () => svg('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>', 16);
const iconRefresh    = () => svg('<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>', 16);
const iconCheck      = () => svg('<polyline points="20 6 9 17 4 12"/>', 14);
const iconNotif      = () => svg('<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>', 18);
const iconFilter     = () => svg('<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>', 16);
const iconEdit       = () => svg('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>', 15);
const iconTrash      = () => svg('<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>', 15);
const iconEye        = () => svg('<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>', 15);
const iconEyeOff     = () => svg('<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>', 15);
const iconShield     = () => svg('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>', 16);
const iconUpload     = () => svg('<polyline points="16 16 12 12 8 16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>', 16);
const iconDownload   = () => svg('<polyline points="8 17 12 21 16 17"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.88 18.09A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.72"/>', 16);
const iconSun        = () => svg('<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>', 18);
const iconMoon       = () => svg('<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>', 18);
const iconDatabase   = () => svg('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>');
const iconTag        = () => svg('<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/>');
const iconTrending   = () => svg('<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>');
const iconActivity   = () => svg('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>');
const iconLayers     = () => svg('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>');
const iconPackage    = () => svg('<line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>');
const iconDollar     = () => svg('<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>');
const iconFileText   = () => svg('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>');

/* ═══════════════════════════════════════════════
   5. 메뉴 정의
═══════════════════════════════════════════════ */
const USER_MENU = [
  {
    group: '메인', items: [
      { href: 'dashboard.html',     icon: iconDashboard(),  label: '대시보드' },
      { href: 'places.html',        icon: iconMapPin(),     label: '플레이스 관리' },
      { href: 'orders.html',        icon: iconCart(),       label: '주문 관리' },
      { href: 'place-status.html',  icon: iconChart(),      label: '플레이스 현황' },
    ]
  },
  {
    group: '분석', items: [
      { href: 'notifications.html', icon: iconBell(),       label: '알림', badgeKey: 'unread' },
    ]
  },
  {
    group: '설정', items: [
      { href: 'billing.html',       icon: iconCreditCard(), label: '구독·결제' },
      { href: 'team.html',          icon: iconUsers(),      label: '팀원 관리' },
      { href: 'account.html',       icon: iconUser(),       label: '계정 설정' },
    ]
  },
];

const ADMIN_MENU = [
  {
    group: '어드민', items: [
      { href: 'admin.html',         icon: iconShield(),     label: '어드민 대시보드' },
      { href: 'orders.html',        icon: iconCart(),       label: '주문 관리' },
      { href: 'admin-media.html',   icon: iconBuilding(),   label: '매체사 관리' },
    ]
  },
  {
    group: '운영', items: [
      { href: 'team.html',          icon: iconUsers(),      label: '유저 관리' },
      { href: 'billing.html',       icon: iconDollar(),     label: '정산·결제' },
      { href: 'notifications.html', icon: iconBell(),       label: '알림 관리', badgeKey: 'unread' },
    ]
  },
  {
    group: '시스템', items: [
      { href: 'account.html',       icon: iconSettings(),   label: '시스템 설정' },
    ]
  },
];

/* ═══════════════════════════════════════════════
   6. 알림 Mock 데이터
═══════════════════════════════════════════════ */
const NOTIF_DATA = [
  { id: 1, icon: '🏆', title: '순위 상승!', msg: '맛있는 식당 "치킨맛집" 키워드 3위 진입', time: '방금 전', color: '#22c55e', unread: true, type: 'ranking' },
  { id: 2, icon: '✅', title: '주문 완료', msg: '블로그 리뷰 10개 작업이 완료되었습니다', time: '5분 전', color: '#00d4ff', unread: true, type: 'order' },
  { id: 3, icon: '📦', title: '작업 진행 중', msg: '인스타그램 홍보 작업이 시작되었습니다', time: '1시간 전', color: '#a78bfa', unread: true, type: 'order' },
  { id: 4, icon: '💳', title: '결제 완료', msg: 'Pro 플랜 월간 구독료 ₩79,000 결제 완료', time: '2시간 전', color: '#fcd34d', unread: false, type: 'payment' },
  { id: 5, icon: '👤', title: '멤버 초대', msg: '김매니저님이 워크스페이스에 합류했습니다', time: '어제', color: '#60a5fa', unread: false, type: 'workspace' },
  { id: 6, icon: '📉', title: '순위 하락 경보', msg: '"배달음식 맛집" 키워드가 15위로 하락했습니다', time: '어제', color: '#f87171', unread: false, type: 'ranking' },
  { id: 7, icon: '🔧', title: '크롤링 완료', msg: '오늘 오전 6시 자동 크롤링이 완료되었습니다', time: '2일 전', color: '#94a3b8', unread: false, type: 'system' },
];

/* ═══════════════════════════════════════════════
   7. 사이드바 렌더링
═══════════════════════════════════════════════ */
function renderSidebar(activePage, isAdmin) {
  const u = CURRENT_USER;
  const menu = isAdmin ? ADMIN_MENU : USER_MENU;
  const active = activePage || location.pathname.split('/').pop() || 'index.html';
  const unread = STATE.unreadCount;

  const navHTML = menu.map(group => `
    <div class="nav-group">
      <div class="nav-group-label">${group.group}</div>
      ${group.items.map(item => {
        const isActive = active === item.href;
        const badge = item.badgeKey === 'unread' && unread > 0
          ? `<span class="nav-badge">${unread > 99 ? '99+' : unread}</span>` : '';
        return `<a href="${item.href}" class="nav-item${isActive ? ' active' : ''}" title="${item.label}">
          <span class="nav-icon">${item.icon}</span>
          <span class="nav-label">${item.label}</span>
          ${badge}
        </a>`;
      }).join('')}
    </div>
  `).join('');

  const planLabels = { free: 'Free', starter: 'Starter', pro: 'Pro', enterprise: 'Enterprise' };
  const wsPlan = u ? u.wsPlan || 'free' : 'free';

  return `
  <aside class="sidebar" id="sidebar">
    <a href="${isAdmin ? 'admin.html' : 'dashboard.html'}" class="sidebar-logo">
      <div class="logo-mark">N</div>
      <span class="logo-text">nplace.io${isAdmin ? '<span class="logo-admin"> ADMIN</span>' : ''}</span>
    </a>
    <nav class="sidebar-nav">${navHTML}</nav>
    <div class="sidebar-footer">
      <div class="workspace-card">
        <div class="workspace-info">
          <div class="ws-name">${u ? u.workspace : 'Workspace'}</div>
          <span class="plan-badge plan-${wsPlan}">${planLabels[wsPlan] || 'Free'}</span>
        </div>
        <a href="upgrade.html" class="ws-upgrade-btn" title="플랜 변경">${iconZap()}</a>
      </div>
    </div>
    <button class="sidebar-toggle" id="sidebar-toggle-btn" onclick="toggleSidebar()" title="사이드바 접기">
      <span id="toggle-icon">${iconChevronL()}</span>
    </button>
  </aside>`;
}

/* ═══════════════════════════════════════════════
   8. 헤더 렌더링
═══════════════════════════════════════════════ */
function renderHeader(title, isAdmin) {
  const u = CURRENT_USER;
  if (!u) return '';
  const planColors = { free: '#94a3b8', starter: '#60a5fa', pro: '#a78bfa', enterprise: '#fcd34d' };
  const planLabels = { free: 'Free', starter: 'Starter', pro: 'Pro', enterprise: 'Enterprise' };
  const pc = planColors[u.plan] || '#94a3b8';
  const isLight = STATE.theme === 'light';

  return `
  <header class="header" id="main-header">
    <div class="header-left">
      <button class="mobile-menu-btn" onclick="toggleMobileSidebar()" title="메뉴">
        <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
      <div class="header-title">${title}</div>
    </div>
    <div class="header-right">
      <!-- 테마 토글 -->
      <button class="icon-btn theme-toggle-btn" id="theme-toggle-btn"
        onclick="toggleTheme()" title="${isLight ? '다크모드로 전환' : '라이트모드로 전환'}">
        ${isLight ? iconMoon() : iconSun()}
      </button>

      <!-- 알림 -->
      <div class="dropdown-wrap" id="notif-wrap">
        <button class="icon-btn notif-btn" id="notif-btn" onclick="toggleNotifDropdown()">
          ${iconNotif()}
          ${STATE.unreadCount > 0 ? '<span class="notif-dot"></span>' : ''}
        </button>
        <div class="notif-dropdown" id="notif-dropdown">
          <div class="notif-dd-header">
            <span class="notif-dd-title">알림 <span class="notif-count">${STATE.unreadCount}개 미읽음</span></span>
            <button class="btn-link" onclick="markAllRead()">전체 읽음</button>
          </div>
          <div class="notif-list">
            ${NOTIF_DATA.slice(0, 5).map(n => `
              <div class="notif-dd-item${n.unread ? ' unread' : ''}">
                <div class="notif-dd-icon" style="background:${n.color}22">${n.icon}</div>
                <div class="notif-dd-body">
                  <div class="notif-dd-ttl">${n.title}</div>
                  <div class="notif-dd-msg">${n.msg}</div>
                  <div class="notif-dd-time">${n.time}</div>
                </div>
              </div>
            `).join('')}
          </div>
          <a href="notifications.html" class="notif-dd-footer">알림 센터 전체 보기 →</a>
        </div>
      </div>

      <!-- 유저 메뉴 -->
      <div class="dropdown-wrap" id="user-wrap">
        <button class="user-menu-btn" id="user-menu-btn" onclick="toggleUserDropdown()">
          <div class="avatar">${u.name[0]}</div>
          <div class="user-info">
            <div class="u-name">${u.name}</div>
            <div class="u-plan" style="color:${pc}">${planLabels[u.plan] || 'Free'}</div>
          </div>
          <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <div class="user-dropdown" id="user-dropdown">
          <div class="user-dd-header">
            <div class="user-dd-name">${u.name}</div>
            <div class="user-dd-email">${u.email}</div>
          </div>
          <a href="account.html" class="dropdown-item">${iconUser()} 계정 설정</a>
          <a href="billing.html" class="dropdown-item">${iconCreditCard()} 구독·결제</a>
          <a href="upgrade.html" class="dropdown-item">${iconZap()} 플랜 변경</a>
          <div class="dd-divider"></div>
          ${u.isAdmin ? `<a href="admin.html" class="dropdown-item admin-item">${iconShield()} 어드민 패널</a><div class="dd-divider"></div>` : ''}
          <a href="#" class="dropdown-item danger-item" onclick="doLogout();return false;">${iconLogout()} 로그아웃</a>
        </div>
      </div>
    </div>
  </header>`;
}

/* ═══════════════════════════════════════════════
   9. 레이아웃 초기화 (공통 진입점)
═══════════════════════════════════════════════ */
function renderLayout({ title = 'nplace.io', activePage = '', isAdmin = false } = {}) {
  // 어드민 계정이면 항상 어드민 메뉴 표시
  const useAdmin = isAdmin || (CURRENT_USER && CURRENT_USER.isAdmin);
  const app = document.getElementById('app');
  if (!app) return;

  app.innerHTML = `
    <div class="app-shell">
      ${renderSidebar(activePage, useAdmin)}
      <div class="main-area" id="main-area">
        ${renderHeader(title, useAdmin)}
        <main class="page-content" id="page-content"></main>
      </div>
    </div>`;

  // 외부 클릭 → 드롭다운 닫기
  document.addEventListener('click', e => {
    if (!e.target.closest('#notif-wrap')) closeDropdown('notif-dropdown');
    if (!e.target.closest('#user-wrap'))  closeDropdown('user-dropdown');
  });

  // 사이드바 접힘 복원
  if (STATE.sidebarCollapsed) _applySidebarCollapsed(true);
}

// 구버전 호환 별칭
function initLayout(activePage, title, isAdmin = false) {
  renderLayout({ title, activePage, isAdmin });
}

/* ═══════════════════════════════════════════════
   10. 사이드바 토글
═══════════════════════════════════════════════ */
function toggleSidebar() {
  STATE.sidebarCollapsed = !STATE.sidebarCollapsed;
  _applySidebarCollapsed(STATE.sidebarCollapsed);
}
function _applySidebarCollapsed(collapsed) {
  const sb = document.getElementById('sidebar');
  const ma = document.getElementById('main-area');
  const ic = document.getElementById('toggle-icon');
  if (!sb) return;
  sb.classList.toggle('collapsed', collapsed);
  if (ma) ma.classList.toggle('collapsed', collapsed);
  if (ic) ic.innerHTML = collapsed ? iconChevronR() : iconChevronL();
}
function toggleMobileSidebar() {
  const sb = document.getElementById('sidebar');
  if (sb) sb.classList.toggle('mobile-open');
}

/* ═══════════════════════════════════════════════
   11. 드롭다운
═══════════════════════════════════════════════ */
function toggleNotifDropdown() {
  closeDropdown('user-dropdown');
  document.getElementById('notif-dropdown')?.classList.toggle('open');
}
function toggleUserDropdown() {
  closeDropdown('notif-dropdown');
  document.getElementById('user-dropdown')?.classList.toggle('open');
}
function closeDropdown(id) {
  document.getElementById(id)?.classList.remove('open');
}
function markAllRead() {
  STATE.unreadCount = 0;
  document.querySelectorAll('.notif-dot').forEach(el => el.remove());
  document.querySelectorAll('.notif-dd-item.unread').forEach(el => el.classList.remove('unread'));
  const cnt = document.querySelector('.notif-count');
  if (cnt) cnt.textContent = '0개 미읽음';
  toast('모든 알림을 읽음으로 처리했습니다', 'success');
}

/* ═══════════════════════════════════════════════
   12. 테마 토글
═══════════════════════════════════════════════ */
function applyTheme(theme) {
  localStorage.setItem('nplace-theme', theme);
  document.body.classList.toggle('light', theme === 'light');
  const btn = document.getElementById('theme-toggle-btn');
  if (btn) {
    btn.title = theme === 'light' ? '다크모드로 전환' : '라이트모드로 전환';
    btn.innerHTML = theme === 'light' ? iconMoon() : iconSun();
  }
}
function toggleTheme() {
  applyTheme(STATE.theme === 'dark' ? 'light' : 'dark');
}

/* ═══════════════════════════════════════════════
   13. 인증
═══════════════════════════════════════════════ */

/** 실제 API 로그인 (JWT 발급) */
async function doLoginAPI(email, password) {
  const data = await apiCall('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  // access_token + workspace_id 저장 (로그인 응답에 workspace 객체 포함)
  const wsId = data.workspace?.id || data.workspace_id || data.user?.workspace_id || null;
  saveToken(data.access_token, wsId);

  // workspace_id가 없으면 /workspaces/me 로 조회
  if (!wsId) {
    try {
      const wsArr = await apiCall('/api/v1/workspaces/me');
      const firstWs = Array.isArray(wsArr) ? wsArr[0] : wsArr?.items?.[0];
      if (firstWs) localStorage.setItem('nplace-ws-id', firstWs.id);
    } catch(_) {}
  }

  const session = {
    email: data.user?.email || email,
    name: data.user?.name || email,
    plan: data.workspace?.plan || data.user?.plan || 'pro',
    isAdmin: data.user?.role === 'admin' || data.user?.role === 'superadmin',
    workspace: data.workspace?.name || data.user?.workspace_name || '내 워크스페이스',
    wsPlan: data.workspace?.plan || 'pro',
    balance: 0,
    fromAPI: true,
  };
  saveSession(session);
  CURRENT_USER = session;
  return session;
}

/** 데모 로그인 (폴백) */
function doLogin(email, password) {
  const u = DEMO_USERS.find(u => u.email === email && u.password === password);
  if (!u) return null;
  const session = { ...u };
  delete session.password;
  saveSession(session);
  CURRENT_USER = session;
  return session;
}
function doLogout() {
  clearToken();
  clearSession();
  CURRENT_USER = null;
  toast('로그아웃 되었습니다', 'info');
  setTimeout(() => { location.href = 'index.html'; }, 600);
}

/* ═══════════════════════════════════════════════
   14. 모달
═══════════════════════════════════════════════ */
function openModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.add('open'); document.body.style.overflow = 'hidden'; }
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) { el.classList.remove('open'); document.body.style.overflow = ''; }
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
    document.body.style.overflow = '';
  }
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(el => {
      el.classList.remove('open');
      document.body.style.overflow = '';
    });
  }
});

/* ═══════════════════════════════════════════════
   15. 토스트
═══════════════════════════════════════════════ */
function toast(msg, type = 'success', duration = 3000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }
  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.innerHTML = `<span class="toast-icon">${icons[type] || '✓'}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.animation = 'slideInRight 0.3s ease reverse';
    setTimeout(() => el.remove(), 300);
  }, duration);
}
function showToast(msg, type = 'success') { toast(msg, type); }

/* ═══════════════════════════════════════════════
   16. 숫자·날짜 포맷
═══════════════════════════════════════════════ */
function formatKRW(n) { return '₩' + Number(n).toLocaleString('ko-KR'); }
function formatNum(n) {
  if (n >= 100000000) return (n / 100000000).toFixed(1) + '억';
  if (n >= 10000) return (n / 10000).toFixed(1) + '만';
  return Number(n).toLocaleString();
}
function formatDate(d) {
  const dt = new Date(d);
  return dt.toLocaleDateString('ko-KR', { year: 'numeric', month: 'short', day: 'numeric' });
}
function formatDateTime(d) {
  const dt = new Date(d);
  return dt.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/* ═══════════════════════════════════════════════
   17. 순위·상태 뱃지
═══════════════════════════════════════════════ */
function rankChange(current, prev) {
  if (!prev) return `<span style="color:var(--text3)">-</span>`;
  const diff = prev - current;
  if (diff > 0) return `<span style="color:var(--green);font-weight:700">▲${diff}</span>`;
  if (diff < 0) return `<span style="color:var(--red);font-weight:700">▼${Math.abs(diff)}</span>`;
  return `<span style="color:var(--text3)">-</span>`;
}
function rankBadge(rank) {
  if (!rank) return `<span style="color:var(--text3)">-</span>`;
  const cls = rank === 1 ? 'rank-1' : rank <= 3 ? 'rank-top3' : rank <= 10 ? 'rank-top10' : 'rank-other';
  return `<span class="rank-badge ${cls}">${rank}</span>`;
}

// ORDER_STATUS: DB OrderStatus enum 기준 (pending/confirmed/in_progress/completed/cancelled/refunded/disputed)
const ORDER_STATUS = {
  pending:     { label: '결제 대기', cls: 'badge-yellow' },
  confirmed:   { label: '확인 완료', cls: 'badge-blue' },
  in_progress: { label: '진행 중',  cls: 'badge-purple' },
  completed:   { label: '완료',     cls: 'badge-green' },
  cancelled:   { label: '취소',     cls: 'badge-gray' },
  refunded:    { label: '환불 완료', cls: 'badge-red' },
  disputed:    { label: '분쟁 처리', cls: 'badge-orange' },  // DB: disputed (구 refund_requested)
};
function orderBadge(status) {
  const s = ORDER_STATUS[status] || { label: status, cls: 'badge-gray' };
  return `<span class="badge ${s.cls}">${s.label}</span>`;
}

/* ═══════════════════════════════════════════════
   18. 페이지네이션
═══════════════════════════════════════════════ */
function renderPagination(current, total, onPageFn) {
  if (total <= 1) return '';
  const pages = Array.from({ length: total }, (_, i) => i + 1);
  return `
    <div class="pagination">
      <button class="page-btn" ${current === 1 ? 'disabled' : ''} onclick="${onPageFn}(${current - 1})">‹</button>
      ${pages.map(p => `<button class="page-btn${p === current ? ' active' : ''}" onclick="${onPageFn}(${p})">${p}</button>`).join('')}
      <button class="page-btn" ${current === total ? 'disabled' : ''} onclick="${onPageFn}(${current + 1})">›</button>
    </div>`;
}

/* ═══════════════════════════════════════════════
   19. 계정 설정 모달 (전역 공통)
═══════════════════════════════════════════════ */
let ACCOUNT_DATA = {
  name: CURRENT_USER?.name || '',
  email: CURRENT_USER?.email || '',
  phone: '010-1234-5678',
  bizNo: '',
  company: '',
  ceo: '',
  taxEmail: '',
};

function openAccountModal() {
  let modal = document.getElementById('account-settings-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'account-settings-modal';
    modal.className = 'modal-overlay';
    modal.style.cssText = 'align-items:flex-start;padding-top:60px;overflow-y:auto';
    modal.onclick = e => { if (e.target === modal) closeModal('account-settings-modal'); };
    document.body.appendChild(modal);
  }
  modal.innerHTML = `
  <div class="modal modal-lg">
    <div class="modal-header">
      <span class="modal-title">${iconUser()} 계정 설정</span>
      <button class="modal-close" onclick="closeModal('account-settings-modal')">${iconClose()}</button>
    </div>
    <div class="modal-body">
      <div class="form-section-title">기본 정보</div>
      <div class="form-row-2">
        <div class="input-group">
          <label class="input-label">이름</label>
          <input class="input" id="acc-name" value="${ACCOUNT_DATA.name}" placeholder="이름">
        </div>
        <div class="input-group">
          <label class="input-label">휴대폰 번호</label>
          <input class="input" id="acc-phone" value="${ACCOUNT_DATA.phone}" placeholder="010-0000-0000">
        </div>
      </div>
      <div class="input-group">
        <label class="input-label">이메일 (로그인 ID)</label>
        <input class="input" id="acc-email" value="${ACCOUNT_DATA.email}" type="email">
      </div>
      <div class="divider"></div>
      <div class="form-section-title">사업자 정보 <span class="section-sub">(세금계산서 발행 시 사용)</span></div>
      <div class="input-group">
        <label class="input-label">사업자등록번호</label>
        <input class="input" id="acc-biz-no" value="${ACCOUNT_DATA.bizNo}" placeholder="000-00-00000" maxlength="12">
      </div>
      <div class="form-row-2">
        <div class="input-group">
          <label class="input-label">상호명</label>
          <input class="input" id="acc-company" value="${ACCOUNT_DATA.company}" placeholder="상호명">
        </div>
        <div class="input-group">
          <label class="input-label">대표자명</label>
          <input class="input" id="acc-ceo" value="${ACCOUNT_DATA.ceo}" placeholder="대표자명">
        </div>
      </div>
      <div class="input-group">
        <label class="input-label">세금계산서 수신 이메일</label>
        <input class="input" id="acc-tax-email" value="${ACCOUNT_DATA.taxEmail}" type="email" placeholder="세금계산서 수신 이메일">
      </div>
      <div class="divider"></div>
      <div class="form-section-title">비밀번호 변경</div>
      <div class="input-group">
        <label class="input-label">현재 비밀번호</label>
        <input class="input" type="password" id="acc-cur-pw" placeholder="현재 비밀번호">
      </div>
      <div class="form-row-2">
        <div class="input-group">
          <label class="input-label">새 비밀번호</label>
          <input class="input" type="password" id="acc-new-pw" placeholder="8자 이상">
        </div>
        <div class="input-group">
          <label class="input-label">비밀번호 확인</label>
          <input class="input" type="password" id="acc-new-pw2" placeholder="비밀번호 재입력">
        </div>
      </div>
    </div>
    <div class="modal-footer">
      <button class="btn btn-secondary" onclick="closeModal('account-settings-modal')">취소</button>
      <button class="btn btn-primary" onclick="saveAccountSettings()">💾 저장하기</button>
    </div>
  </div>`;
  openModal('account-settings-modal');
}

function saveAccountSettings() {
  const name  = document.getElementById('acc-name')?.value.trim();
  const email = document.getElementById('acc-email')?.value.trim();
  const phone = document.getElementById('acc-phone')?.value.trim();
  const bizNo = document.getElementById('acc-biz-no')?.value.trim();
  const company = document.getElementById('acc-company')?.value.trim();
  const ceo   = document.getElementById('acc-ceo')?.value.trim();
  const taxEmail = document.getElementById('acc-tax-email')?.value.trim();
  const curPw = document.getElementById('acc-cur-pw')?.value;
  const newPw = document.getElementById('acc-new-pw')?.value;
  const newPw2 = document.getElementById('acc-new-pw2')?.value;

  if (!name) return toast('이름을 입력해 주세요', 'error');
  if (!email || !email.includes('@')) return toast('올바른 이메일을 입력해 주세요', 'error');
  if (newPw || newPw2 || curPw) {
    if (!curPw) return toast('현재 비밀번호를 입력해 주세요', 'error');
    if (newPw.length < 8) return toast('새 비밀번호는 8자 이상이어야 합니다', 'error');
    if (newPw !== newPw2) return toast('새 비밀번호가 일치하지 않습니다', 'error');
  }
  Object.assign(ACCOUNT_DATA, { name, email, phone, bizNo, company, ceo, taxEmail });
  if (CURRENT_USER) { CURRENT_USER.name = name; CURRENT_USER.email = email; saveSession(CURRENT_USER); }
  closeModal('account-settings-modal');
  toast('계정 정보가 저장되었습니다', 'success');
}

/* ═══════════════════════════════════════════════
   20. Chart.js 헬퍼 (테마 연동)
═══════════════════════════════════════════════ */
function chartColors() {
  const isLight = document.body.classList.contains('light');
  return {
    grid:  isLight ? 'rgba(0,0,0,0.06)'  : 'rgba(255,255,255,0.05)',
    ticks: isLight ? 'rgba(0,0,0,0.4)'   : 'rgba(255,255,255,0.4)',
    tooltip: {
      bg:    isLight ? '#ffffff'          : '#1a1a24',
      border:isLight ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)',
      title: isLight ? '#0f172a'          : '#ffffff',
      body:  isLight ? 'rgba(0,0,0,0.6)' : 'rgba(255,255,255,0.7)',
    }
  };
}
