// ============ GLOBAL STATE & CONFIG ============
const API_BASE = '/api';
let currentUser = null;
let accessToken = null;
let companies = [];
let users = [];
let tickets = [];
let currentTicketId = null;
let currentTab = 'dashboard';
let searchDebounceTimer = null;
let userSearchDebounceTimer = null;
let ticketsPage = 1;
let usersPage = 1;
const PAGE_SIZE = 20;

// Translations
const translations = {
    en: {
        dashboard: 'Dashboard', tickets: 'Tickets', companies: 'Companies', users: 'Users',
        login: 'Sign In', logout: 'Logout', email: 'Email', password: 'Password',
        newTicket: 'New Ticket', newCompany: 'New Company', newUser: 'New User',
        edit: 'Edit', delete: 'Delete', view: 'View', save: 'Save', cancel: 'Cancel',
        title: 'Title', description: 'Description', category: 'Category', priority: 'Priority',
        status: 'Status', company: 'Company', assignee: 'Assignee', creator: 'Creator',
        created: 'Created', updated: 'Updated', slaDue: 'SLA Due', actions: 'Actions',
        open: 'Open', inProgress: 'In Progress', waitingCustomer: 'Waiting Customer',
        waitingThirdParty: 'Waiting 3rd Party', closed: 'Closed', cancelled: 'Cancelled',
        low: 'Low', medium: 'Medium', high: 'High', urgent: 'Urgent', critical: 'Critical',
        technical: 'Technical', billing: 'Billing', featureRequest: 'Feature Request',
        bugReport: 'Bug Report', generalInquiry: 'General Inquiry', accessRequest: 'Access Request',
        security: 'Security', other: 'Other', admin: 'Admin', agent: 'Agent', client: 'Client',
        active: 'Active', inactive: 'Inactive', search: 'Search', filter: 'Filter',
        overdueOnly: 'Overdue Only', noTickets: 'No tickets found', noCompanies: 'No companies found',
        noUsers: 'No users found', confirmDelete: 'Are you sure?', error: 'Error',
        success: 'Success', warning: 'Warning', info: 'Info', comments: 'Comments',
        attachments: 'Attachments', history: 'History', addComment: 'Add Comment',
        internalNote: 'Internal note (agents only)', upload: 'Upload', noFile: 'No file selected',
        ticketDetails: 'Ticket Details', recentTickets: 'Recent Tickets',
        myAssignedTickets: 'My Assigned Tickets', totalTickets: 'Total Tickets',
        openTickets: 'Open Tickets', inProgressTickets: 'In Progress', closedTickets: 'Closed',
        overdueTickets: 'Overdue', totalCompanies: 'Total Companies', totalUsers: 'Total Users',
        ticketsByStatus: 'Tickets by Status', ticketsByPriority: 'Tickets by Priority',
        name: 'Name', phone: 'Phone', address: 'Address', city: 'City', country: 'Country',
        timezone: 'Timezone', slaHours: 'SLA Hours', ticketCount: 'Tickets', userCount: 'Users',
        language: 'Language', lastLogin: 'Last Login', role: 'Role', password: 'Password',
        newPassword: 'New Password', confirmPassword: 'Confirm Password',
        passwordChanged: 'Password changed successfully', profileUpdated: 'Profile updated',
        loginError: 'Invalid email or password', sessionExpired: 'Session expired, please login again',
        unauthorized: 'Unauthorized access', forbidden: 'Access denied',
        validationError: 'Please check your input', serverError: 'Server error, please try again',
        ticket: 'Ticket', user: 'User', noComments: 'No comments yet', noAttachments: 'No attachments',
        download: 'Download', unassigned: 'Unassigned', allCompanies: 'All Companies',
        noCompany: 'No Company', selectCompany: 'Select a company'
    },
    'pt-BR': {
        dashboard: 'Painel', tickets: 'Tickets', companies: 'Empresas', users: 'Usuários',
        login: 'Entrar', logout: 'Sair', email: 'E-mail', password: 'Senha',
        newTicket: 'Novo Ticket', newCompany: 'Nova Empresa', newUser: 'Novo Usuário',
        edit: 'Editar', delete: 'Excluir', view: 'Ver', save: 'Salvar', cancel: 'Cancelar',
        title: 'Título', description: 'Descrição', category: 'Categoria', priority: 'Prioridade',
        status: 'Status', company: 'Empresa', assignee: 'Responsável', creator: 'Criador',
        created: 'Criado', updated: 'Atualizado', slaDue: 'SLA Vence', actions: 'Ações',
        open: 'Aberto', inProgress: 'Em Progresso', waitingCustomer: 'Aguardando Cliente',
        waitingThirdParty: 'Aguardando Terceiro', closed: 'Fechado', cancelled: 'Cancelado',
        low: 'Baixa', medium: 'Média', high: 'Alta', urgent: 'Urgente', critical: 'Crítica',
        technical: 'Técnico', billing: 'Faturamento', featureRequest: 'Solicitação de Feature',
        bugReport: 'Relatório de Bug', generalInquiry: 'Dúvida Geral', accessRequest: 'Solicitação de Acesso',
        security: 'Segurança', other: 'Outro', admin: 'Admin', agent: 'Agente', client: 'Cliente',
        active: 'Ativo', inactive: 'Inativo', search: 'Buscar', filter: 'Filtrar',
        overdueOnly: 'Apenas Atrasados', noTickets: 'Nenhum ticket encontrado',
        noCompanies: 'Nenhuma empresa encontrada', noUsers: 'Nenhum usuário encontrado',
        confirmDelete: 'Tem certeza?', error: 'Erro', success: 'Sucesso', warning: 'Aviso',
        info: 'Info', comments: 'Comentários', attachments: 'Anexos', history: 'Histórico',
        addComment: 'Adicionar Comentário', internalNote: 'Nota interna (apenas agentes)',
        upload: 'Enviar', noFile: 'Nenhum arquivo selecionado', ticketDetails: 'Detalhes do Ticket',
        recentTickets: 'Tickets Recentes', myAssignedTickets: 'Meus Tickets Atribuídos',
        totalTickets: 'Total de Tickets', openTickets: 'Tickets Abertos',
        inProgressTickets: 'Em Progresso', closedTickets: 'Fechados', overdueTickets: 'Atrasados',
        totalCompanies: 'Total de Empresas', totalUsers: 'Total de Usuários',
        ticketsByStatus: 'Tickets por Status', ticketsByPriority: 'Tickets por Prioridade',
        name: 'Nome', phone: 'Telefone', address: 'Endereço', city: 'Cidade', country: 'País',
        timezone: 'Fuso Horário', slaHours: 'Horas SLA', ticketCount: 'Tickets', userCount: 'Usuários',
        language: 'Idioma', lastLogin: 'Último Login', role: 'Perfil', password: 'Senha',
        newPassword: 'Nova Senha', confirmPassword: 'Confirmar Senha',
        passwordChanged: 'Senha alterada com sucesso', profileUpdated: 'Perfil atualizado',
        loginError: 'E-mail ou senha inválidos', sessionExpired: 'Sessão expirada, faça login novamente',
        unauthorized: 'Não autorizado', forbidden: 'Acesso negado',
        validationError: 'Verifique seus dados', serverError: 'Erro no servidor, tente novamente',
        ticket: 'Ticket', user: 'Usuário', noComments: 'Nenhum comentário ainda', noAttachments: 'Nenhum anexo',
        download: 'Baixar', unassigned: 'Não atribuído', allCompanies: 'Todas as Empresas',
        noCompany: 'Sem Empresa', selectCompany: 'Selecione uma empresa'
    },
    es: {
        dashboard: 'Panel', tickets: 'Tickets', companies: 'Empresas', users: 'Usuarios',
        login: 'Iniciar Sesión', logout: 'Cerrar Sesión', email: 'Correo', password: 'Contraseña',
        newTicket: 'Nuevo Ticket', newCompany: 'Nueva Empresa', newUser: 'Nuevo Usuario',
        edit: 'Editar', delete: 'Eliminar', view: 'Ver', save: 'Guardar', cancel: 'Cancelar',
        title: 'Título', description: 'Descripción', category: 'Categoría', priority: 'Prioridad',
        status: 'Estado', company: 'Empresa', assignee: 'Asignado', creator: 'Creador',
        created: 'Creado', updated: 'Actualizado', slaDue: 'SLA Vence', actions: 'Acciones',
        open: 'Abierto', inProgress: 'En Progreso', waitingCustomer: 'Esperando Cliente',
        waitingThirdParty: 'Esperando Tercero', closed: 'Cerrado', cancelled: 'Cancelado',
        low: 'Baja', medium: 'Media', high: 'Alta', urgent: 'Urgente', critical: 'Crítica',
        technical: 'Técnico', billing: 'Facturación', featureRequest: 'Solicitud de Función',
        bugReport: 'Reporte de Error', generalInquiry: 'Consulta General', accessRequest: 'Solicitud de Acceso',
        security: 'Seguridad', other: 'Otro', admin: 'Admin', agent: 'Agente', client: 'Cliente',
        active: 'Activo', inactive: 'Inactivo', search: 'Buscar', filter: 'Filtrar',
        overdueOnly: 'Solo Atrasados', noTickets: 'No se encontraron tickets',
        noCompanies: 'No se encontraron empresas', noUsers: 'No se encontraron usuarios',
        confirmDelete: '¿Está seguro?', error: 'Error', success: 'Éxito', warning: 'Advertencia',
        info: 'Info', comments: 'Comentarios', attachments: 'Adjuntos', history: 'Historial',
        addComment: 'Añadir Comentario', internalNote: 'Nota interna (solo agentes)',
        upload: 'Subir', noFile: 'Ningún archivo seleccionado', ticketDetails: 'Detalles del Ticket',
        recentTickets: 'Tickets Recientes', myAssignedTickets: 'Mis Tickets Asignados',
        totalTickets: 'Total Tickets', openTickets: 'Tickets Abiertos',
        inProgressTickets: 'En Progreso', closedTickets: 'Cerrados', overdueTickets: 'Atrasados',
        totalCompanies: 'Total Empresas', totalUsers: 'Total Usuarios',
        ticketsByStatus: 'Tickets por Estado', ticketsByPriority: 'Tickets por Prioridad',
        name: 'Nombre', phone: 'Teléfono', address: 'Dirección', city: 'Ciudad', country: 'País',
        timezone: 'Zona Horaria', slaHours: 'Horas SLA', ticketCount: 'Tickets', userCount: 'Usuarios',
        language: 'Idioma', lastLogin: 'Último Acceso', role: 'Rol', password: 'Contraseña',
        newPassword: 'Nueva Contraseña', confirmPassword: 'Confirmar Contraseña',
        passwordChanged: 'Contraseña cambiada', profileUpdated: 'Perfil actualizado',
        loginError: 'Correo o contraseña inválidos', sessionExpired: 'Sesión expirada, inicie sesión de nuevo',
        unauthorized: 'No autorizado', forbidden: 'Acceso denegado',
        validationError: 'Verifique sus datos', serverError: 'Error del servidor, intente de nuevo',
        ticket: 'Ticket', user: 'Usuario', noComments: 'Sin comentarios', noAttachments: 'Sin adjuntos',
        download: 'Descargar', unassigned: 'Sin asignar', allCompanies: 'Todas las Empresas',
        noCompany: 'Sin Empresa', selectCompany: 'Seleccione una empresa'
    }
};

let currentLang = 'en';
function t(key) {
    return translations[currentLang]?.[key] || translations.en[key] || key;
}

// API enum values are snake_case (in_progress), translation keys are camelCase (inProgress)
function tEnum(value) {
    if (!value) return '-';
    return t(String(value).replace(/_([a-z])/g, (_, c) => c.toUpperCase()));
}

let charts = {};

// ============ UTILITY FUNCTIONS ============
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString(currentLang === 'pt-BR' ? 'pt-BR' : currentLang === 'es' ? 'es-ES' : 'en-US', {
        year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    });
}

function formatDateOnly(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString(currentLang === 'pt-BR' ? 'pt-BR' : currentLang === 'es' ? 'es-ES' : 'en-US');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container') || createToastContainer();
    // avoid stacking identical toasts (e.g. several parallel requests failing at once)
    if ([...container.children].some(el => el.textContent === message)) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
    return container;
}

// Performs an API call. On error it shows a toast once and throws an Error with `shown = true`.
async function apiRequest(endpoint, options = {}) {
    const isForm = options.body instanceof FormData;
    const headers = { ...(isForm ? {} : { 'Content-Type': 'application/json' }), ...options.headers };
    if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`;

    let res;
    try {
        res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    } catch (e) {
        const err = new Error(t('serverError'));
        err.shown = true;
        showToast(err.message, 'error');
        throw err;
    }

    if (res.status === 204) return {};
    const data = await res.json().catch(() => ({}));
    if (res.ok) return data;

    let message;
    if (res.status === 401) {
        message = t('sessionExpired');
        logout();
    } else if (res.status === 403) {
        message = typeof data.detail === 'string' ? data.detail : t('forbidden');
    } else {
        message = typeof data.detail === 'string' ? data.detail : t('serverError');
    }
    const err = new Error(message);
    err.status = res.status;
    err.shown = true;
    showToast(message, 'error');
    throw err;
}

function handleError(err) {
    if (!err?.shown) showToast(err?.message || t('serverError'), 'error');
}

function getStatusBadgeClass(status) {
    return `badge-${status}`;
}

function getPriorityBadgeClass(priority) {
    return `badge-${priority}`;
}

function isOverdue(ticket) {
    if (!ticket.sla_due_at) return false;
    const closedStatuses = ['closed', 'cancelled'];
    if (closedStatuses.includes(ticket.status)) return false;
    return new Date(ticket.sla_due_at) < new Date();
}

// ============ AUTH ============
async function login(email, password) {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    try {
        const res = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok) throw new Error(res.status === 401 ? t('loginError') : (typeof data.detail === 'string' ? data.detail : t('loginError')));

        accessToken = data.access_token;
        currentUser = data.user;
        localStorage.setItem('token', accessToken);
        localStorage.setItem('user', JSON.stringify(currentUser));
        if (currentUser.language && translations[currentUser.language]) {
            currentLang = currentUser.language;
            localStorage.setItem('language', currentLang);
            document.getElementById('language-select').value = currentLang;
        }

        showMainApp();
        return true;
    } catch (err) {
        const box = document.getElementById('login-error');
        box.textContent = err.message === 'Failed to fetch' ? t('serverError') : err.message;
        box.classList.remove('hidden');
        return false;
    }
}

function logout() {
    accessToken = null;
    currentUser = null;
    document.body.className = '';
    document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    showLoginScreen();
}

function checkAuth() {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');
    if (token && user) {
        accessToken = token;
        try { currentUser = JSON.parse(user); } catch { logout(); return; }
        // Management panel is for technicians and admins; clients use the portal
        if (currentUser.role === 'client') { location.replace('/dashboard'); return; }
        showMainApp();
        // refresh user data (role/name may have changed); a 401 here logs out automatically
        apiRequest('/auth/me').then(me => {
            currentUser = me;
            localStorage.setItem('user', JSON.stringify(me));
            if (me.role === 'client') { location.replace('/dashboard'); return; }
            updateUIForRole();
        }).catch(() => {});
    } else {
        showLoginScreen();
    }
}

// Login now lives on its own page ("/"); this panel only runs with a session
function showLoginScreen() {
    location.href = '/?next=' + encodeURIComponent('/painel' + location.hash);
}

function showMainApp() {
    document.getElementById('login-screen').classList.remove('active');
    document.getElementById('main-app').classList.add('active');
    updateUIForRole();
    loadCompanies();
    switchTab('dashboard');
    openTicketFromHash();
}

// Deep link used by notification e-mails: /#ticket-123 opens that ticket after login
function openTicketFromHash() {
    const match = /^#ticket-(\d+)$/.exec(window.location.hash);
    if (!match) return;
    history.replaceState(null, '', window.location.pathname);
    openTicketDetail(parseInt(match[1], 10));
}

function isStaff() {
    return currentUser && (currentUser.role === 'admin' || currentUser.role === 'agent');
}

function updateUIForRole() {
    if (!currentUser) return;
    const isAdmin = currentUser.role === 'admin';

    document.body.className = `role-${currentUser.role}`;
    document.getElementById('header-user-name').textContent = currentUser.full_name;
    document.getElementById('header-user-role').textContent = t(currentUser.role);
    document.getElementById('header-user-role').className = `role-badge ${currentUser.role}`;

    // Only hide NAV buttons (hiding the sections with inline styles broke tab switching)
    document.getElementById('nav-users').classList.toggle('hidden', !isAdmin);
    document.getElementById('nav-companies').classList.toggle('hidden', !isStaff());
    document.getElementById('filter-company').classList.toggle('hidden', !isStaff());
    document.getElementById('ticket-assignee-row').classList.toggle('hidden', !isStaff());

    // If the current tab is not allowed for this role, go back to dashboard
    if ((currentTab === 'users' && !isAdmin) || (currentTab === 'companies' && !isStaff())) {
        switchTab('dashboard');
    }
}

// ============ LANGUAGE ============
function setLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('language', lang);
    document.getElementById('language-select').value = lang;
    updateLanguageUI();
}

function updateLanguageUI() {
    // Update all elements with data-i18n attribute
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'email' || el.type === 'password')) {
            el.placeholder = t(key);
        } else {
            el.textContent = t(key);
        }
    });

    // Update select options
    document.querySelectorAll('select[data-i18n-options]').forEach(sel => {
        const keys = sel.dataset.i18nOptions.split(',');
        Array.from(sel.options).forEach((opt, i) => {
            if (keys[i]) opt.textContent = t(keys[i]);
        });
    });

    // Re-render current tab data (only when logged in - otherwise it would hit the API with no token)
    if (currentUser) {
        updateUIForRole();
        switchTab(currentTab);
    }
}

// ============ TABS ============
function switchTab(tabName) {
    if (!currentUser) return;
    if ((tabName === 'users' && currentUser.role !== 'admin') || (tabName === 'companies' && !isStaff())) {
        tabName = 'dashboard';
    }
    currentTab = tabName;

    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `${tabName}-tab`);
    });

    switch(tabName) {
        case 'dashboard': loadDashboard(); break;
        case 'tickets': loadTickets(); break;
        case 'companies': loadCompanies(); break;
        case 'users': loadUsers(); break;
    }
}

// ============ DASHBOARD ============
async function loadDashboard() {
    try {
        const stats = await apiRequest('/dashboard/stats');
        if (!stats) return;

        renderStats(stats);
        renderRecentTickets(stats.recent_tickets);
        renderMyTickets(stats.my_assigned_tickets);
        renderCharts(stats);
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

function renderStats(stats) {
    const grid = document.getElementById('stats-grid');
    const statCards = [
        { key: 'total_tickets', label: t('totalTickets'), icon: '📋', class: 'primary' },
        { key: 'open_tickets', label: t('openTickets'), icon: '📥', class: 'info' },
        { key: 'in_progress_tickets', label: t('inProgressTickets'), icon: '⚙️', class: 'warning' },
        { key: 'closed_tickets', label: t('closedTickets'), icon: '✅', class: 'success' },
        { key: 'overdue_tickets', label: t('overdueTickets'), icon: '⚠️', class: 'danger' },
        { key: 'total_companies', label: t('totalCompanies'), icon: '🏢', class: 'primary' },
        { key: 'total_users', label: t('totalUsers'), icon: '👥', class: 'info' },
    ];

    grid.innerHTML = statCards.map(s => `
        <div class="stat-card ${s.class}">
            <div class="stat-icon">${s.icon}</div>
            <div class="stat-info">
                <div class="stat-number">${stats[s.key] || 0}</div>
                <div class="stat-label">${s.label}</div>
            </div>
        </div>
    `).join('');
}

function slaCell(tk) {
    if (!tk.sla_due_at) return '-';
    return isOverdue(tk) ? `<span class="badge badge-overdue">${formatDate(tk.sla_due_at)}</span>` : formatDate(tk.sla_due_at);
}

// NOTE: never name the map parameter `t` - it shadows the translation function t()
function renderRecentTickets(list) {
    const tbody = document.querySelector('#recent-tickets-table tbody');
    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-state">${t('noTickets')}</td></tr>`;
        return;
    }
    tbody.innerHTML = list.map(tk => `
        <tr onclick="openTicketDetail(${tk.id})" style="cursor:pointer;">
            <td>#${tk.id}</td>
            <td>${escapeHtml(tk.title)}</td>
            <td>${escapeHtml(tk.company_name)}</td>
            <td><span class="badge ${getStatusBadgeClass(tk.status)}">${tEnum(tk.status)}</span></td>
            <td><span class="badge ${getPriorityBadgeClass(tk.priority)}">${tEnum(tk.priority)}</span></td>
            <td>${formatDate(tk.created_at)}</td>
        </tr>
    `).join('');
}

function renderMyTickets(list) {
    const section = document.getElementById('my-tickets-section');
    const tbody = document.querySelector('#my-tickets-table tbody');

    if (currentUser.role === 'client' || !list.length) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';
    tbody.innerHTML = list.map(tk => `
        <tr onclick="openTicketDetail(${tk.id})" style="cursor:pointer;">
            <td>#${tk.id}</td>
            <td>${escapeHtml(tk.title)}</td>
            <td>${escapeHtml(tk.company_name)}</td>
            <td><span class="badge ${getStatusBadgeClass(tk.status)}">${tEnum(tk.status)}</span></td>
            <td><span class="badge ${getPriorityBadgeClass(tk.priority)}">${tEnum(tk.priority)}</span></td>
            <td>${slaCell(tk)}</td>
        </tr>
    `).join('');
}

const STATUS_COLORS = { open: '#0984e3', in_progress: '#fdcb6e', waiting_customer: '#74b9ff', waiting_third_party: '#a29bfe', closed: '#00b894', cancelled: '#b2bec3' };
const PRIORITY_COLORS = { low: '#00b894', medium: '#fdcb6e', high: '#e17055', urgent: '#d63031', critical: '#6c5ce7' };

function drawDoughnut(key, canvasId, counts, colors) {
    if (typeof Chart === 'undefined') return; // CDN unavailable (offline) - skip charts
    if (charts[key]) charts[key].destroy();   // reusing a canvas without destroy() throws
    const keys = Object.keys(counts);
    charts[key] = new Chart(document.getElementById(canvasId), {
        type: 'doughnut',
        data: {
            labels: keys.map(tEnum),
            datasets: [{ data: keys.map(k => counts[k]), backgroundColor: keys.map(k => colors[k] || '#636e72') }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });
}

function renderCharts(stats) {
    drawDoughnut('status', 'chart-status', stats.tickets_by_status, STATUS_COLORS);
    drawDoughnut('priority', 'chart-priority', stats.tickets_by_priority, PRIORITY_COLORS);
}

// ============ COMPANIES ============
async function loadCompanies() {
    try {
        companies = await apiRequest('/companies?page=1&page_size=100'); // API max page_size is 100
        renderCompanies();
        updateCompanySelects();
    } catch (err) { console.error('Companies load error:', err); }
}

function renderCompanies() {
    const tbody = document.querySelector('#companies-table tbody');
    if (!companies.items.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="empty-state">${t('noCompanies')}</td></tr>`;
        return;
    }
    tbody.innerHTML = companies.items.map(c => `
        <tr>
            <td>${c.id}</td>
            <td>${escapeHtml(c.name)}</td>
            <td>${escapeHtml(c.email || '-')}</td>
            <td>${escapeHtml(c.phone || '-')}</td>
            <td>${escapeHtml((c.city || '') + (c.city && c.country ? ', ' : '') + (c.country || '')) || '-'}</td>
            <td>${c.ticket_count}</td>
            <td>${c.user_count}</td>
            <td><span class="badge ${c.is_active ? 'badge-open' : 'badge-cancelled'}">${c.is_active ? t('active') : t('inactive')}</span></td>
            <td>${formatDate(c.created_at)}</td>
            <td>
                <div class="cell-actions">
                    <button class="btn btn-secondary btn-sm admin-only" onclick="openCompanyModal(${c.id})">${t('edit')}</button>
                    ${c.ticket_count === 0 && c.user_count === 0 ? `<button class="btn btn-danger btn-sm admin-only" onclick="deleteCompany(${c.id})">${t('delete')}</button>` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

function updateCompanySelects() {
    const items = companies.items.map(c => `<option value="${c.id}">${escapeHtml(c.name)}</option>`).join('');
    const placeholders = {
        'ticket-company': t('selectCompany'),
        'filter-company': t('allCompanies'),
        'filter-user-company': t('allCompanies'),
        'user-company': t('noCompany'),
    };
    Object.entries(placeholders).forEach(([id, label]) => {
        const sel = document.getElementById(id);
        if (sel) {
            const val = sel.value;
            sel.innerHTML = `<option value="">${escapeHtml(label)}</option>` + items;
            sel.value = val;
        }
    });
}

async function createCompany(data) { return apiRequest('/companies', { method: 'POST', body: JSON.stringify(data) }); }
async function updateCompany(id, data) { return apiRequest(`/companies/${id}`, { method: 'PUT', body: JSON.stringify(data) }); }
async function deleteCompany(id) {
    if (!confirm(t('confirmDelete'))) return;
    try { await apiRequest(`/companies/${id}`, { method: 'DELETE' }); loadCompanies(); showToast(t('success'), 'success'); }
    catch (err) { handleError(err); }
}

// Company Modal
async function openCompanyModal(id = null) {
    const modal = document.getElementById('company-modal');
    const form = document.getElementById('company-form');
    form.reset();
    document.getElementById('company-id').value = '';
    document.getElementById('company-active-group').style.display = id ? 'block' : 'none';
    document.getElementById('company-modal-title').textContent = id ? t('edit') + ' ' + t('company') : t('newCompany');

    if (id) {
        // list items don't contain address/timezone/sla_hours -> fetch the full record
        let company;
        try { company = await apiRequest(`/companies/${id}`); } catch (err) { return; }
        if (company) {
            document.getElementById('company-id').value = company.id;
            document.getElementById('company-name').value = company.name;
            document.getElementById('company-email').value = company.email || '';
            document.getElementById('company-phone').value = company.phone || '';
            document.getElementById('company-city').value = company.city || '';
            document.getElementById('company-country').value = company.country || '';
            document.getElementById('company-address').value = company.address || '';
            document.getElementById('company-timezone').value = company.timezone || 'UTC';
            document.getElementById('company-sla').value = company.sla_hours;
            document.getElementById('company-active').checked = company.is_active;
        }
    }
    modal.classList.add('active');
}

function closeCompanyModal() { document.getElementById('company-modal').classList.remove('active'); }

document.getElementById('company-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('company-id').value;
    const data = {
        name: document.getElementById('company-name').value,
        email: document.getElementById('company-email').value || null,
        phone: document.getElementById('company-phone').value || null,
        city: document.getElementById('company-city').value || null,
        country: document.getElementById('company-country').value || null,
        address: document.getElementById('company-address').value || null,
        timezone: document.getElementById('company-timezone').value || 'UTC',
        sla_hours: parseInt(document.getElementById('company-sla').value) || 24,
        is_active: document.getElementById('company-active').checked
    };
    try {
        if (id) await updateCompany(id, data);
        else await createCompany(data);
        closeCompanyModal();
        loadCompanies();
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
});

// ============ TICKETS ============
async function loadTickets(page = 1) {
    ticketsPage = page;
    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    // only send filters that have a value (empty "status=" is rejected by the API with 422)
    ['status', 'priority', 'category'].forEach(name => {
        const val = document.getElementById(`filter-${name}`).value;
        if (val) params.append(name, val);
    });

    const companyId = document.getElementById('filter-company').value;
    if (companyId) params.append('company_id', companyId);
    const search = document.getElementById('filter-search').value;
    if (search) params.append('search', search);
    if (document.getElementById('filter-overdue').checked) params.append('overdue_only', 'true');

    try {
        tickets = await apiRequest(`/tickets?${params}`);
        renderTickets();
        renderPagination('tickets-pagination', page, tickets.total_pages, 'loadTickets');
    } catch (err) { console.error('Tickets load error:', err); }
}

function renderTickets() {
    const tbody = document.querySelector('#tickets-table tbody');
    if (!tickets.items.length) {
        tbody.innerHTML = `<tr><td colspan="10" class="empty-state">${t('noTickets')}</td></tr>`;
        return;
    }
    tbody.innerHTML = tickets.items.map(tk => `
        <tr>
            <td>#${tk.id}</td>
            <td>${escapeHtml(tk.title)}</td>
            <td>${escapeHtml(tk.company_name)}</td>
            <td><span class="badge ${getStatusBadgeClass(tk.status)}">${tEnum(tk.status)}</span></td>
            <td><span class="badge ${getPriorityBadgeClass(tk.priority)}">${tEnum(tk.priority)}</span></td>
            <td>${tEnum(tk.category)}</td>
            <td>${escapeHtml(tk.assignee_name || '-')}</td>
            <td>${formatDate(tk.created_at)}</td>
            <td>${slaCell(tk)}</td>
            <td>
                <div class="cell-actions">
                    <button class="btn btn-secondary btn-sm" onclick="openTicketDetail(${tk.id})">${t('view')}</button>
                    <button class="btn btn-secondary btn-sm" onclick="openTicketModal(${tk.id})">${t('edit')}</button>
                </div>
            </td>
        </tr>
    `).join('');
}

function renderPagination(containerId, currentPage, totalPages, onClickFn) {
    const container = document.getElementById(containerId);
    if (totalPages <= 1) { container.innerHTML = ''; return; }

    let html = '';
    if (currentPage > 1) html += `<button onclick="${onClickFn}(${currentPage - 1})">«</button>`;

    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, currentPage + 2);

    for (let i = start; i <= end; i++) {
        html += `<button class="${i === currentPage ? 'active' : ''}" onclick="${onClickFn}(${i})">${i}</button>`;
    }

    if (currentPage < totalPages) html += `<button onclick="${onClickFn}(${currentPage + 1})">»</button>`;

    container.innerHTML = html;
}

// Search debounce
function debounceSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => loadTickets(1), 300);
}

// Ticket Modal
async function openTicketModal(id = null) {
    const modal = document.getElementById('ticket-modal');
    const form = document.getElementById('ticket-form');
    form.reset();
    document.getElementById('ticket-id').value = '';
    // status can only be changed by staff here (clients use the detail view: reopen/cancel)
    document.getElementById('ticket-status-group').style.display = (id && isStaff()) ? 'block' : 'none';
    document.getElementById('ticket-modal-title').textContent = id ? t('edit') + ' ' + t('ticket') : t('newTicket');
    document.getElementById('ticket-company').disabled = !!id; // company can't be changed after creation
    // priority drives the SLA, so only staff can change it after creation (enforced server-side too)
    document.getElementById('ticket-priority').disabled = !!id && !isStaff();

    // Clients only have their own company -> preselect it
    if (!id && companies.items?.length === 1) {
        document.getElementById('ticket-company').value = companies.items[0].id;
    }

    // must finish BEFORE setting the selected value, otherwise the value is lost
    if (isStaff()) await loadAssignees();

    if (id) {
        // list items don't include the description -> fetch the full ticket so it is not wiped on save
        let ticket;
        try { ticket = await apiRequest(`/tickets/${id}`); } catch (err) { return; }
        if (ticket) {
            document.getElementById('ticket-id').value = ticket.id;
            document.getElementById('ticket-title').value = ticket.title;
            document.getElementById('ticket-description').value = ticket.description || '';
            document.getElementById('ticket-company').value = ticket.company_id;
            document.getElementById('ticket-category').value = ticket.category;
            document.getElementById('ticket-priority').value = ticket.priority;
            document.getElementById('ticket-status').value = ticket.status;
            document.getElementById('ticket-assignee').value = ticket.assignee_id || '';
        }
    }
    modal.classList.add('active');
}

function closeTicketModal() { document.getElementById('ticket-modal').classList.remove('active'); }

async function loadAssignees() {
    try {
        const agents = await apiRequest('/users/agents');
        const sel = document.getElementById('ticket-assignee');
        const currentVal = sel.value;
        sel.innerHTML = `<option value="">${t('unassigned')}</option>` + agents.map(a => `<option value="${a.id}">${escapeHtml(a.full_name)}</option>`).join('');
        sel.value = currentVal;
    } catch (err) { console.error('Assignees load error:', err); }
}

document.getElementById('ticket-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('ticket-id').value;
    const companyVal = document.getElementById('ticket-company').value;
    if (!id && !companyVal) { showToast(t('selectCompany'), 'warning'); return; }
    const data = {
        title: document.getElementById('ticket-title').value,
        description: document.getElementById('ticket-description').value || null,
        category: document.getElementById('ticket-category').value,
        priority: document.getElementById('ticket-priority').value,
    };
    if (!id) data.company_id = parseInt(companyVal);
    if (isStaff()) {
        const assignee = document.getElementById('ticket-assignee').value;
        data.assignee_id = assignee ? parseInt(assignee) : null;
        if (id) data.status = document.getElementById('ticket-status').value;
    }

    try {
        if (id) await apiRequest(`/tickets/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        else await apiRequest('/tickets', { method: 'POST', body: JSON.stringify(data) });
        closeTicketModal();
        loadTickets(ticketsPage);
        loadDashboard();
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
});

// ============ TICKET DETAIL ============
async function openTicketDetail(id) {
    const isNewTicket = currentTicketId !== id || !document.getElementById('ticket-detail-modal').classList.contains('active');
    currentTicketId = id;
    try {
        const ticket = await apiRequest(`/tickets/${id}`);
        // load assignee options BEFORE selecting the current assignee
        if (isStaff()) await loadDetailAssignees();
        renderTicketDetail(ticket);
        loadComments(id);
        loadAttachments(id);
        loadHistory(id);
        if (isNewTicket) {
            document.querySelector('.detail-tab[data-detail-tab="info"]').click();
            document.getElementById('comment-form').reset();
        }
        document.getElementById('ticket-detail-modal').classList.add('active');
    } catch (err) { handleError(err); }
}

function closeTicketDetailModal() { document.getElementById('ticket-detail-modal').classList.remove('active'); }

function renderTicketDetail(ticket) {
    // textContent already escapes - escapeHtml() here would show "&amp;" etc.
    document.getElementById('detail-ticket-title').textContent = `#${ticket.id} - ${ticket.title}`;
    document.getElementById('detail-status').textContent = tEnum(ticket.status);
    document.getElementById('detail-status').className = `badge ${getStatusBadgeClass(ticket.status)}`;
    document.getElementById('detail-priority').textContent = tEnum(ticket.priority);
    document.getElementById('detail-priority').className = `badge ${getPriorityBadgeClass(ticket.priority)}`;
    document.getElementById('detail-category').textContent = tEnum(ticket.category);
    document.getElementById('detail-company').textContent = ticket.company.name;
    document.getElementById('detail-assignee').textContent = ticket.assignee?.full_name || '-';
    document.getElementById('detail-creator').textContent = ticket.creator.full_name;
    document.getElementById('detail-created').textContent = formatDate(ticket.created_at);
    document.getElementById('detail-updated').textContent = formatDate(ticket.updated_at);
    document.getElementById('detail-sla').innerHTML = ticket.sla_due_at ? (isOverdue(ticket) ? `<span class="badge badge-overdue">${formatDate(ticket.sla_due_at)}</span>` : formatDate(ticket.sla_due_at)) : '-';
    document.getElementById('detail-description').innerHTML = escapeHtml(ticket.description || '-').replace(/\n/g, '<br>');

    const statusSel = document.getElementById('detail-status-select');
    statusSel.value = ticket.status;
    // clients may only reopen or cancel
    Array.from(statusSel.options).forEach(opt => {
        opt.disabled = !isStaff() && !['open', 'cancelled', ticket.status].includes(opt.value);
    });
    document.getElementById('detail-assignee-select').value = ticket.assignee_id || '';
}

async function loadDetailAssignees() {
    try {
        const agents = await apiRequest('/users/agents');
        const sel = document.getElementById('detail-assignee-select');
        sel.innerHTML = `<option value="">${t('unassigned')}</option>` + agents.map(a => `<option value="${a.id}">${escapeHtml(a.full_name)}</option>`).join('');
    } catch (err) { console.error('Detail assignees load error:', err); }
}

async function updateDetailStatus() {
    const status = document.getElementById('detail-status-select').value;
    try {
        await apiRequest(`/tickets/${currentTicketId}/status`, { method: 'PUT', body: JSON.stringify({ status }) });
        openTicketDetail(currentTicketId);
        loadTickets(ticketsPage);
        loadDashboard();
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
}

async function updateDetailAssignee() {
    const assigneeId = document.getElementById('detail-assignee-select').value;
    try {
        await apiRequest(`/tickets/${currentTicketId}/assign`, { method: 'PUT', body: JSON.stringify({ assignee_id: assigneeId ? parseInt(assigneeId) : null }) });
        openTicketDetail(currentTicketId);
        loadTickets(ticketsPage);
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
}

// Comments
async function loadComments(ticketId) {
    try {
        const comments = await apiRequest(`/tickets/${ticketId}/comments`);
        const list = document.getElementById('comments-list');
        if (!comments.length) { list.innerHTML = `<div class="empty-state">${t('noComments')}</div>`; return; }
        list.innerHTML = comments.map(c => `
            <div class="comment-item ${c.is_internal ? 'comment-internal' : ''}">
                <div class="comment-header">
                    <span class="comment-author">${escapeHtml(c.author_name)} ${c.is_internal ? `<span class="badge badge-warning" style="font-size:0.6rem;margin-left:0.5rem;">${t('internalNote')}</span>` : ''}</span>
                    <span class="comment-time">${formatDate(c.created_at)}</span>
                </div>
                <div class="comment-content">${escapeHtml(c.content).replace(/\n/g, '<br>')}</div>
            </div>
        `).join('');
    } catch (err) { console.error('Comments load error:', err); }
}

document.getElementById('comment-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const content = document.getElementById('comment-content').value;
    const isInternal = document.getElementById('comment-internal').checked;
    try {
        await apiRequest(`/tickets/${currentTicketId}/comments`, { method: 'POST', body: JSON.stringify({ content, is_internal: isInternal }) });
        document.getElementById('comment-content').value = '';
        loadComments(currentTicketId);
        loadTickets(ticketsPage);
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
});

// Attachments
async function loadAttachments(ticketId) {
    try {
        const attachments = await apiRequest(`/tickets/${ticketId}/attachments`);
        const list = document.getElementById('attachments-list');
        attachmentNames = Object.fromEntries(attachments.map(a => [a.id, a.original_filename]));
        if (!attachments.length) { list.innerHTML = `<div class="empty-state">${t('noAttachments')}</div>`; return; }
        list.innerHTML = attachments.map(a => `
            <div class="attachment-item">
                <div class="attachment-info">
                    <div class="attachment-icon">📄</div>
                    <div>
                        <div class="attachment-name">${escapeHtml(a.original_filename)}</div>
                        <div class="attachment-meta">${formatFileSize(a.file_size)} • ${escapeHtml(a.uploaded_by_name)} • ${formatDate(a.created_at)}</div>
                    </div>
                </div>
                <div class="attachment-actions">
                    <button class="btn btn-secondary btn-sm" onclick="downloadAttachment(${a.id})">${t('download')}</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteAttachment(${a.id})">${t('delete')}</button>
                </div>
            </div>
        `).join('');
    } catch (err) { console.error('Attachments load error:', err); }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
    return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

document.getElementById('attachment-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('attachment-file');
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        await apiRequest(`/tickets/${currentTicketId}/attachments`, { method: 'POST', body: formData });
        fileInput.value = '';
        loadAttachments(currentTicketId);
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
});

// Files are protected by auth, so a plain <a href> can't be used (it wouldn't send the token)
let attachmentNames = {};
async function downloadAttachment(id) {
    try {
        const res = await fetch(`${API_BASE}/tickets/attachments/${id}/download`, {
            headers: { 'Authorization': `Bearer ${accessToken}` }
        });
        if (res.status === 401) { logout(); showToast(t('sessionExpired'), 'error'); return; }
        if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || t('serverError'));
        const url = URL.createObjectURL(await res.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = attachmentNames[id] || 'download';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { handleError(err); }
}

async function deleteAttachment(id) {
    if (!confirm(t('confirmDelete'))) return;
    try {
        await apiRequest(`/tickets/attachments/${id}`, { method: 'DELETE' });
        loadAttachments(currentTicketId);
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
}

// History (placeholder)
async function loadHistory(ticketId) {
    const list = document.getElementById('history-list');
    list.innerHTML = `<div class="empty-state">History tracking coming in Phase 2</div>`;
}

// ============ USERS ============
async function loadUsers(page = 1) {
    usersPage = page;
    const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
    const role = document.getElementById('filter-user-role').value;
    const companyId = document.getElementById('filter-user-company').value;
    const search = document.getElementById('filter-user-search').value;
    if (role) params.append('role', role);
    if (companyId) params.append('company_id', companyId);
    if (search) params.append('search', search);

    try {
        users = await apiRequest(`/users?${params}`);
        renderUsers();
        renderPagination('users-pagination', page, users.total_pages, 'loadUsers');
    } catch (err) { console.error('Users load error:', err); }
}

function renderUsers() {
    const tbody = document.querySelector('#users-table tbody');
    if (!users.items.length) { tbody.innerHTML = `<tr><td colspan="9" class="empty-state">${t('noUsers')}</td></tr>`; return; }
    tbody.innerHTML = users.items.map(u => `
        <tr>
            <td>${u.id}</td>
            <td>${escapeHtml(u.full_name)}</td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="badge badge-${u.role}">${t(u.role)}</span></td>
            <td>${escapeHtml(u.company?.name || '-')}</td>
            <td>${escapeHtml(u.language)}</td>
            <td><span class="badge ${u.is_active ? 'badge-open' : 'badge-cancelled'}">${u.is_active ? t('active') : t('inactive')}</span></td>
            <td>${u.last_login ? formatDate(u.last_login) : '-'}</td>
            <td>
                <div class="cell-actions">
                    <button class="btn btn-secondary btn-sm" onclick="openUserModal(${u.id})">${t('edit')}</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// User Modal
function openUserModal(id = null) {
    const modal = document.getElementById('user-modal');
    const form = document.getElementById('user-form');
    form.reset();
    document.getElementById('user-id').value = '';
    // a hidden *required* field blocks form submission in the browser -> toggle `required` too
    const pwd = document.getElementById('user-password');
    pwd.required = !id;
    document.getElementById('user-password-group').style.display = id ? 'none' : '';
    document.getElementById('user-active-group').style.display = id ? 'block' : 'none';
    document.getElementById('user-modal-title').textContent = id ? t('edit') + ' ' + t('user') : t('newUser');

    if (id) {
        const user = users.items.find(u => u.id === id);
        if (user) {
            document.getElementById('user-id').value = user.id;
            document.getElementById('user-fullname').value = user.full_name;
            document.getElementById('user-email').value = user.email;
            document.getElementById('user-role-select').value = user.role;
            document.getElementById('user-company').value = user.company_id || '';
            document.getElementById('user-language').value = user.language;
            document.getElementById('user-active').checked = user.is_active;
        }
    }
    modal.classList.add('active');
}

function closeUserModal() { document.getElementById('user-modal').classList.remove('active'); }

document.getElementById('user-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('user-id').value;
    const data = {
        full_name: document.getElementById('user-fullname').value,
        email: document.getElementById('user-email').value,
        role: document.getElementById('user-role-select').value,
        company_id: document.getElementById('user-company').value ? parseInt(document.getElementById('user-company').value) : null,
        language: document.getElementById('user-language').value,
    };
    if (id) data.is_active = document.getElementById('user-active').checked;
    else data.password = document.getElementById('user-password').value;

    try {
        if (id) await apiRequest(`/auth/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
        else await apiRequest('/auth/register', { method: 'POST', body: JSON.stringify(data) });
        closeUserModal();
        loadUsers(usersPage);
        loadCompanies(); // user counts changed
        showToast(t('success'), 'success');
    } catch (err) { handleError(err); }
});

function debounceUserSearch() {
    clearTimeout(userSearchDebounceTimer);
    userSearchDebounceTimer = setTimeout(() => loadUsers(1), 300);
}

// ============ MODAL CLOSE ON BACKDROP/ESC ============
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.remove('active'); });
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.querySelectorAll('.modal').forEach(m => m.classList.remove('active')); });

// ============ DETAIL TABS ============
document.querySelectorAll('.detail-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.detail-tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`detail-${tab.dataset.detailTab}`).classList.add('active');
    });
});

// ============ INIT ============
document.addEventListener('DOMContentLoaded', () => {
    // Load saved language
    const savedLang = localStorage.getItem('language') || 'en';
    document.getElementById('language-select').value = savedLang;
    setLanguage(savedLang);

    // Login form
    document.getElementById('login-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        await login(email, password);
    });

    // Logout
    document.getElementById('logout-btn').addEventListener('click', logout);

    // Language select
    document.getElementById('language-select').addEventListener('change', (e) => setLanguage(e.target.value));

    // Tab navigation (nav buttons + "View All" links)
    document.querySelectorAll('.nav-btn, a[data-tab]').forEach(btn => {
        btn.addEventListener('click', (e) => { e.preventDefault(); switchTab(btn.dataset.tab); });
    });

    checkAuth();
});
// Chart.js is now loaded with a <script> tag in index.html (loading it here raced with the first render)
