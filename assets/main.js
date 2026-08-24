/*
 * File: main.js
 * Project: victor-travel
 * Description: Catalog page shell — theme/lang + parent link i18n
 */

document.addEventListener('DOMContentLoaded', function() {
    TravelShared.initShell();
    TravelShared.renderFooter(readSite());
    syncParentLink();
});

window.onLanguageChange = function() {
    syncParentLink();
};

function readSite() {
    const el = document.getElementById('site-data');
    return el ? JSON.parse(el.textContent) : { parentSite: 'https://victor42.work/', github: '#' };
}

function syncParentLink() {
    const site = readSite();
    const link = document.getElementById('parent-link');
    if (!link) return;
    link.href = site.parentSite;
    const label = TravelShared.getText(site.parentLabel || { zh: '小玩意', en: 'Gadgets' });
    link.textContent = `← ${label}`;
}
