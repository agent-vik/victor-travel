/*
 * File: guide.js
 * Project: victor-travel
 * Description: Guide detail page — init shell + footer
 */

document.addEventListener('DOMContentLoaded', function() {
    TravelShared.initShell();
    const el = document.getElementById('site-data');
    const site = el ? JSON.parse(el.textContent) : { parentSite: 'https://victor42.work/', github: '#' };
    TravelShared.renderFooter(site);
});
