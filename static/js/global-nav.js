/**
 * グローバルナビゲーションのJavaScript
 */

class GlobalNav {
    constructor() {
        this.currentPath = window.location.pathname;
        this.init();
    }

    init() {
        this.renderNav();
        this.setupEventListeners();
        this.setActiveLink();
    }

    getNavItems() {
        return [
            {
                title: 'ダッシュボード',
                icon: '📊',
                href: '/dashboard',
                id: 'dashboard'
            },
            {
                title: '新規分析',
                icon: '🔍',
                href: '/dashboard#analysis',
                id: 'analysis'
            },
            {
                title: '分析履歴',
                icon: '📋',
                href: '/dashboard#history',
                id: 'history'
            },
            {
                title: 'トレードレビュー',
                icon: '🎯',
                href: '/trade-review',
                id: 'trade-review'
            },
            {
                title: 'コメント',
                icon: '💬',
                href: '/comments',
                id: 'comments'
            },
            {
                title: 'ツール',
                icon: '🛠️',
                id: 'tools',
                dropdown: [
                    { title: '予測レビュー', href: '/test_review.html' },
                    { title: 'アップロードテスト', href: '/test_upload.html' },
                    { title: '履歴ビュー', href: '/test_history.html' }
                ]
            }
        ];
    }

    renderNav() {
        const navHTML = `
            <nav class="global-nav">
                <div class="global-nav-container">
                    <a href="/dashboard" class="nav-brand">
                        <span class="nav-logo">📈</span>
                        <span class="nav-title">FX分析システム</span>
                    </a>
                    
                    <button class="nav-mobile-toggle" id="navToggle">
                        <span>☰</span>
                    </button>
                    
                    <ul class="nav-menu" id="navMenu">
                        ${this.getNavItems().map(item => this.renderNavItem(item)).join('')}
                    </ul>
                </div>
            </nav>
        `;

        // ナビゲーションを挿入
        document.body.insertAdjacentHTML('afterbegin', navHTML);
    }

    renderNavItem(item) {
        if (item.dropdown) {
            return `
                <li class="nav-item">
                    <a href="#" class="nav-link" data-nav="${item.id}">
                        <span class="nav-icon">${item.icon}</span>
                        <span>${item.title}</span>
                    </a>
                    <div class="nav-dropdown">
                        ${item.dropdown.map(dropItem => `
                            <a href="${dropItem.href}" class="nav-dropdown-item">
                                ${dropItem.title}
                            </a>
                        `).join('')}
                    </div>
                </li>
            `;
        }

        return `
            <li class="nav-item">
                <a href="${item.href}" class="nav-link" data-nav="${item.id}">
                    <span class="nav-icon">${item.icon}</span>
                    <span>${item.title}</span>
                </a>
            </li>
        `;
    }

    setupEventListeners() {
        // モバイルメニュートグル
        const toggle = document.getElementById('navToggle');
        const menu = document.getElementById('navMenu');
        
        toggle.addEventListener('click', () => {
            menu.classList.toggle('active');
        });

        // ドロップダウンのクリックを防ぐ
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.nextElementSibling && link.nextElementSibling.classList.contains('nav-dropdown')) {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                });
            }
        });

        // 外側クリックでモバイルメニューを閉じる
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.global-nav')) {
                menu.classList.remove('active');
            }
        });
    }

    setActiveLink() {
        const links = document.querySelectorAll('.nav-link');
        
        links.forEach(link => {
            const href = link.getAttribute('href');
            if (href === this.currentPath || 
                (this.currentPath === '/' && href === '/dashboard') ||
                (href && href !== '#' && this.currentPath.startsWith(href.split('#')[0]))) {
                link.classList.add('active');
            }
        });
    }
}

// CSSを動的に読み込む
function loadGlobalNavCSS() {
    if (!document.querySelector('link[href*="global-nav.css"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/static/css/global-nav.css';
        document.head.appendChild(link);
    }
}

// 初期化
document.addEventListener('DOMContentLoaded', () => {
    loadGlobalNavCSS();
    new GlobalNav();
});

// グローバルに公開
window.GlobalNav = GlobalNav;