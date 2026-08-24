/*
 * File: shared.js
 * Project: victor-travel
 * Description: Shared theme, language, footer for travel portal
 */

const TravelShared = (function() {
    'use strict';

    let currentLanguage = 'zh';

    const UI_TEXT = {
        zh: {
            themeToggle: '切换深色模式',
            langToggle: '切换语言',
            loading: '正在加载...',
            errorTitle: '😕 加载失败',
            errorMessage: '无法加载数据，请检查网络连接或稍后重试。',
            copied: '已复制'
        },
        en: {
            themeToggle: 'Toggle dark mode',
            langToggle: 'Switch language',
            loading: 'Loading...',
            errorTitle: '😕 Failed to load',
            errorMessage: 'Could not load data. Please check your connection and try again.',
            copied: 'Copied'
        }
    };

    function getUi(key) {
        return UI_TEXT[currentLanguage][key] || UI_TEXT.zh[key];
    }

    function getText(obj) {
        if (!obj || typeof obj !== 'object') return '';
        return obj[currentLanguage] || obj.zh || '';
    }

    function initializeLanguage() {
        const urlParams = new URLSearchParams(window.location.search);
        const urlLang = urlParams.get('lang');
        const savedLang = localStorage.getItem('language');

        if (urlLang === 'zh' || urlLang === 'en') {
            currentLanguage = urlLang;
        } else if (savedLang === 'zh' || savedLang === 'en') {
            currentLanguage = savedLang;
        } else {
            currentLanguage = 'zh';
        }

        localStorage.setItem('language', currentLanguage);
        document.documentElement.lang = currentLanguage === 'zh' ? 'zh-CN' : 'en';
        updateLanguageButton();
        applyStaticUiText();
        applyLanguageVisibility();

        document.getElementById('lang-toggle').addEventListener('click', toggleLanguage);
    }

    function toggleLanguage() {
        setLanguage(currentLanguage === 'zh' ? 'en' : 'zh');
    }

    function setLanguage(lang) {
        currentLanguage = lang;
        localStorage.setItem('language', lang);

        const url = new URL(window.location);
        url.searchParams.set('lang', lang);
        window.history.replaceState({}, '', url);

        document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
        updateLanguageButton();
        applyStaticUiText();
        applyLanguageVisibility();

        if (typeof window.onLanguageChange === 'function') {
            window.onLanguageChange();
        }
    }

    function updateLanguageButton() {
        document.querySelector('.lang-text').textContent =
            currentLanguage === 'zh' ? 'EN' : '中文';
    }

    function applyStaticUiText() {
        const t = UI_TEXT[currentLanguage];
        const map = {
            'loading-text': t.loading,
            'error-title': t.errorTitle,
            'error-message': t.errorMessage
        };

        Object.entries(map).forEach(function([id, text]) {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        });

        document.getElementById('theme-toggle').setAttribute('aria-label', t.themeToggle);
        document.getElementById('lang-toggle').setAttribute('aria-label', t.langToggle);
    }

    function applyLanguageVisibility() {
        document.querySelectorAll('[data-lang]').forEach(function(el) {
            el.hidden = el.getAttribute('data-lang') !== currentLanguage;
        });
    }

    function bindThemeControls() {
        document.getElementById('theme-toggle').addEventListener('click', toggleTheme);

        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
            if (!localStorage.getItem('theme')) {
                applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    function syncThemeIcon() {
        const themeIcon = document.querySelector('.theme-icon');
        const currentTheme = document.documentElement.getAttribute('data-theme');
        themeIcon.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
    }

    function applyTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        syncThemeIcon();
    }

    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    }

    function initShell() {
        initializeLanguage();
        bindThemeControls();
        syncThemeIcon();
    }

    function renderFooter(site) {
        const footer = document.getElementById('footer-text');
        footer.textContent = '';
        footer.appendChild(document.createTextNode('Created by '));

        const authorLink = document.createElement('a');
        authorLink.href = site.parentSite;
        authorLink.target = '_blank';
        authorLink.rel = 'noopener noreferrer';
        authorLink.textContent = 'Victor42';
        footer.appendChild(authorLink);
        footer.appendChild(document.createTextNode(' & '));

        const vikLink = document.createElement('a');
        vikLink.href = 'https://github.com/agent-vik/about-me';
        vikLink.target = '_blank';
        vikLink.rel = 'noopener noreferrer';
        vikLink.textContent = 'Vik';
        footer.appendChild(vikLink);
        footer.appendChild(document.createTextNode(' | '));

        const codeLink = document.createElement('a');
        codeLink.href = site.github;
        codeLink.target = '_blank';
        codeLink.rel = 'noopener noreferrer';
        codeLink.textContent = 'Code';
        footer.appendChild(codeLink);
    }

    async function copyText(text) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
            return;
        }

        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }

    return {
        initShell,
        getText,
        getUi,
        getLanguage: function() { return currentLanguage; },
        renderFooter,
        copyText
    };
})();
