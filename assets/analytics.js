/*
 * File: analytics.js
 * Project: victor-travel
 * Description: GA4 — page views + language change (production host only)
 */

(function () {
    'use strict';

    const measurementId = 'G-14SGRFWENB';
    const productionHosts = new Set([
        'travel.victor42.work'
    ]);

    if (!productionHosts.has(window.location.hostname)) {
        return;
    }

    window.dataLayer = window.dataLayer || [];
    window.gtag = function gtag() {
        window.dataLayer.push(arguments);
    };
    window.gtag('js', new Date());
    window.gtag('config', measurementId, {
        send_page_view: false
    });

    const script = document.createElement('script');
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
    document.head.appendChild(script);

    function trackPageView() {
        const path = window.location.pathname + window.location.search;
        window.gtag('event', 'page_view', {
            page_path: path,
            page_title: document.title
        });
    }

    function trackLanguage(lang) {
        window.gtag('event', 'language_change', {
            event_category: 'engagement',
            event_label: lang
        });
    }

    function observeLanguageToggle() {
        const toggle = document.getElementById('lang-toggle');
        if (!toggle || toggle.dataset.gaBound === '1') return;
        toggle.dataset.gaBound = '1';
        toggle.addEventListener('click', function () {
            window.setTimeout(function () {
                trackPageView();
                const stored = localStorage.getItem('language');
                if (stored) trackLanguage(stored);
            }, 60);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            trackPageView();
            observeLanguageToggle();
        });
    } else {
        trackPageView();
        observeLanguageToggle();
    }

    window.TravelAnalytics = { trackPageView, trackLanguage };
})();
