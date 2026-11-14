// Shared helpers for the portal pages. Uses the same localStorage keys as app.js
// ('token', 'user'), so logging in on any page logs in everywhere.
const Portal = (() => {
    const LABELS = {
        status: {
            open: 'Aberto', in_progress: 'Em atendimento', waiting_customer: 'Aguardando você',
            waiting_third_party: 'Aguardando terceiros', closed: 'Resolvido', cancelled: 'Cancelado',
        },
        // Staff see the neutral wording for waiting_customer
        statusStaff: { waiting_customer: 'Aguardando cliente' },
        priority: { low: 'Baixa', medium: 'Média', high: 'Alta', urgent: 'Urgente', critical: 'Crítica' },
        category: {
            technical: 'Suporte técnico', billing: 'Financeiro', feature_request: 'Sugestão de melhoria',
            bug_report: 'Erro no sistema', general_inquiry: 'Dúvida geral', access_request: 'Solicitação de acesso',
            security: 'Segurança', other: 'Outro',
        },
        role: { admin: 'Administrador', agent: 'Técnico', client: 'Cliente' },
    };

    const token = () => { try { return localStorage.getItem('token'); } catch { return null; } };
    const user = () => { try { return JSON.parse(localStorage.getItem('user')); } catch { return null; } };
    const isStaff = (u = user()) => !!u && (u.role === 'admin' || u.role === 'agent');

    function saveSession(accessToken, u) {
        localStorage.setItem('token', accessToken);
        localStorage.setItem('user', JSON.stringify(u));
    }

    function logout() {
        try { localStorage.removeItem('token'); localStorage.removeItem('user'); } catch { /* ignore */ }
        location.href = '/';
    }

    function goToLogin() {
        location.href = '/?next=' + encodeURIComponent(location.pathname + location.search);
    }

    // Everyone lands on the dashboard; it adapts to the role
    function homeFor(u) {
        return u ? '/dashboard' : '/';
    }

    // Only same-site relative paths, so ?next= can't redirect to another site
    function safeNext(next) {
        return next && next.startsWith('/') && !next.startsWith('//') ? next : null;
    }

    async function api(endpoint, options = {}) {
        const isForm = options.body instanceof FormData;
        const headers = { ...(isForm || !options.body ? {} : { 'Content-Type': 'application/json' }), ...options.headers };
        const t = token();
        if (t && !options.public) headers.Authorization = `Bearer ${t}`;

        let res;
        try {
            res = await fetch('/api' + endpoint, { ...options, headers });
        } catch {
            throw new Error('Não foi possível conectar ao servidor.');
        }
        if (res.status === 204) return {};
        const data = await res.json().catch(() => ({}));
        if (res.ok) return data;

        if (res.status === 401 && !options.public) {
            goToLogin();
            throw new Error('Sua sessão expirou. Entre novamente.');
        }
        const err = new Error(typeof data.detail === 'string' ? data.detail : 'Erro no servidor. Tente novamente.');
        err.status = res.status;
        throw err;
    }

    // Redirects to /login when there is no session (or the role is not allowed).
    // Returns the fresh user from /auth/me.
    async function requireAuth(roles) {
        if (!token()) { goToLogin(); return new Promise(() => {}); }
        const me = await api('/auth/me');
        localStorage.setItem('user', JSON.stringify(me));
        if (roles && !roles.includes(me.role)) {
            location.href = homeFor(me);
            return new Promise(() => {});
        }
        return me;
    }

    function header(active) {
        const u = user();
        const links = [];
        if (u) links.push(['dashboard', '/dashboard', 'Dashboard']);
        if (u) links.push(['abrir', '/abrir-chamado', 'Abrir chamado']);
        links.push(['acompanhar', '/acompanhar', 'Acompanhar ticket']);
        if (isStaff(u)) links.push(['tecnico', '/tecnico', 'Área técnica']);
        if (isStaff(u)) links.push(['gestao', '/painel', 'Gestão']);
        if (u) links.push(['perfil', '/perfil', 'Meu perfil']);

        const nav = links.map(([key, href, label]) =>
            `<a href="${href}" class="${key === active ? 'active' : ''}">${label}</a>`).join('');
        const right = u
            ? `<span class="who">${esc(u.full_name)}</span><button class="btn btn-secondary btn-sm" id="portal-logout">Sair</button>`
            : `<a class="btn btn-primary btn-sm" href="/">Entrar</a>`;

        const el = document.createElement('header');
        el.className = 'portal-header';
        el.innerHTML = `<div class="portal-header-inner">
            <a class="brand" href="${homeFor(u)}">🎫 Central de Chamados</a>
            <nav class="portal-nav">${nav}</nav>
            <div class="portal-user">${right}</div></div>`;
        document.body.prepend(el);
        el.querySelector('#portal-logout')?.addEventListener('click', logout);
    }

    function esc(s) {
        return String(s ?? '').replace(/[&<>"']/g, c =>
            ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    // API datetimes are naive UTC
    function parseDate(s) {
        if (!s) return null;
        return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(s) ? s : s + 'Z');
    }

    function fmtDate(s) {
        const d = parseDate(s);
        return d ? d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '-';
    }

    function relTime(s) {
        const d = parseDate(s);
        if (!d) return '-';
        const diff = (Date.now() - d.getTime()) / 1000;
        const abs = Math.abs(diff);
        const fmt = new Intl.RelativeTimeFormat('pt-BR', { numeric: 'auto' });
        const sign = diff > 0 ? -1 : 1;
        if (abs < 60) return 'agora';
        if (abs < 3600) return fmt.format(sign * Math.round(abs / 60), 'minute');
        if (abs < 86400) return fmt.format(sign * Math.round(abs / 3600), 'hour');
        return fmt.format(sign * Math.round(abs / 86400), 'day');
    }

    function statusBadge(status, staff = false) {
        const label = (staff && LABELS.statusStaff[status]) || LABELS.status[status] || status;
        return `<span class="badge st-${esc(status)}">${label}</span>`;
    }

    function priorityBadge(p) {
        return `<span class="badge pr-${esc(p)}">${LABELS.priority[p] || p}</span>`;
    }

    function formatCode(code) {
        return code ? `${code.slice(0, 5)}-${code.slice(5)}` : '-';
    }

    function toast(message, type = '') {
        let box = document.querySelector('.toasts');
        if (!box) {
            box = document.createElement('div');
            box.className = 'toasts';
            document.body.appendChild(box);
        }
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        box.appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }

    return {
        LABELS, token, user, isStaff, saveSession, logout, homeFor, safeNext, api, requireAuth, header,
        esc, fmtDate, relTime, statusBadge, priorityBadge, formatCode, toast,
    };
})();
