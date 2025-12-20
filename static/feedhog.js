/**
 * feedhog.js — client-side UI logic for the Feedhog feed reader.
 *
 * Responsibilities:
 *  - Render relative timestamps for article ages and "generated at" labels.
 *  - Abbreviate source names into compact reference badges.
 *  - Collapse overflow reference badges behind a "+N" toggle.
 *  - Handle keyboard navigation (j/k/g/G/Escape) between feed sections.
 *  - Toggle the keyboard-shortcut help popup.
 */

// ---------------------------------------------------------------------------
// Time helpers
// ---------------------------------------------------------------------------

/**
 * Return a compact age string ("Xh" or "Xd") for a Unix timestamp.
 *
 * @param {number} timestamp - Unix epoch in seconds.
 * @returns {string} e.g. "3h" or "2d"
 */
function calculateAge(timestamp) {
    const now = Date.now() / 1000;
    const hours = Math.floor((now - timestamp) / 3600);
    if (hours >= 24) return `${Math.floor(hours / 24)}d`;
    return `${hours}h`;
}

/**
 * Return a human-readable relative time string for an ISO-8601 timestamp.
 *
 * @param {string} timestamp - ISO-8601 date string (e.g. "2024-06-01T12:00:00").
 * @returns {string} e.g. "3 hours ago", "1 day ago"
 */
function formatRelativeTime(timestamp) {
    const deltaMs = new Date() - new Date(timestamp);
    const s = Math.floor(deltaMs / 1000);
    const m = Math.floor(s / 60);
    const h = Math.floor(m / 60);
    const d = Math.floor(h / 24);

    if (s < 60) return s === 1 ? '1 second ago' : `${s} seconds ago`;
    if (m < 60) return m === 1 ? '1 minute ago' : `${m} minutes ago`;
    if (h < 24) return h === 1 ? '1 hour ago'   : `${h} hours ago`;
    return d === 1 ? '1 day ago' : `${d} days ago`;
}

// ---------------------------------------------------------------------------
// Reference badge helpers
// ---------------------------------------------------------------------------

/**
 * Derive a short uppercase abbreviation from a feed source name.
 * Strips common TLDs, then takes initials (multi-word) or the first 3 chars
 * (single-word).
 *
 * @param {string} source - Feed source name, e.g. "hacker-news" or "lobste.rs".
 * @returns {string} Up to 4 uppercase characters, e.g. "HN", "LRS".
 */
function abbreviate(source) {
    const cleaned = source.replace(/\.(com|net|org|de|co\.uk|io)$/i, '');
    const words = cleaned.split(/[\s\-_/]+/).filter(Boolean);
    if (words.length === 1) return words[0].slice(0, 3).toUpperCase();
    return words.map(w => w[0]).join('').toUpperCase().slice(0, 4);
}

/** Maximum number of reference badges shown before collapsing the rest. */
const REF_SHOW_MAX = 3;

// ---------------------------------------------------------------------------
// DOM initialisation (runs after the page is fully parsed)
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {

    // Fill each reference badge with the abbreviated source name.
    document.querySelectorAll('.ref-badge[data-source]').forEach(el => {
        el.textContent = abbreviate(el.getAttribute('data-source'));
    });

    // Collapse reference lists that exceed REF_SHOW_MAX badges.
    document.querySelectorAll('.references').forEach(container => {
        const badges = Array.from(container.querySelectorAll('.ref-badge'));
        if (badges.length <= REF_SHOW_MAX) return;

        const extra = badges.length - REF_SHOW_MAX;
        badges.slice(REF_SHOW_MAX).forEach(b => b.style.display = 'none');

        // "+N" toggle that reveals the hidden badges on click.
        const more = document.createElement('span');
        more.className = 'ref-more';
        more.textContent = `+${extra}`;
        more.onclick = () => {
            badges.slice(REF_SHOW_MAX).forEach(b => b.style.display = '');
            more.remove();
        };
        container.appendChild(more);
    });

    // Render compact ages next to each article (e.g. "[3h]").
    document.querySelectorAll('.age-indicator[data-timestamp]').forEach(el => {
        const ts = parseFloat(el.getAttribute('data-timestamp'));
        if (!isNaN(ts)) el.textContent = `[${calculateAge(ts)}]`;
    });

    // Render "generated X ago" labels for feed/summary sections.
    document.querySelectorAll('.generated-at[data-timestamp]').forEach(el => {
        const ts = el.getAttribute('data-timestamp');
        if (ts) el.textContent = formatRelativeTime(ts);
    });
});

// ---------------------------------------------------------------------------
// Keyboard-shortcut help popup
// ---------------------------------------------------------------------------

const kbdBtn   = document.getElementById('kbdHelpBtn');
const kbdPopup = document.getElementById('kbdHelpPopup');

/** Toggle the help popup; stop the click from immediately closing it. */
kbdBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    kbdPopup.classList.toggle('visible');
});

/** Close the popup when the user clicks anywhere outside it. */
document.addEventListener('click', () => kbdPopup.classList.remove('visible'));

// ---------------------------------------------------------------------------
// Keyboard navigation between feed sections
// ---------------------------------------------------------------------------

/** Index of the currently highlighted .category-section, or -1 for none. */
let focusedBlockIndex = -1;

/**
 * Group .category-section block indices by their owning category header.
 * In the summary section each block contains its own h2.feed-category-header;
 * in the feeds section the h2 precedes the grid in document order.
 *
 * @returns {number[][]} Array of groups, each group is an array of block indices.
 */
function buildCategoryGroups() {
    const blocks  = Array.from(document.querySelectorAll('.category-section'));
    const headers = Array.from(document.querySelectorAll('h2.feed-category-header'));
    if (headers.length === 0) return blocks.length ? [{header: null, blocks: blocks.map((_, i) => i)}] : [];

    const groups = headers.map(h => ({ header: h, blocks: [] }));
    blocks.forEach((block, bi) => {
        // Summary: header is a descendant of the block itself.
        const inner = block.querySelector('h2.feed-category-header');
        if (inner) {
            const hi = headers.indexOf(inner);
            if (hi >= 0) { groups[hi].blocks.push(bi); return; }
        }
        // Feeds: find the last header that precedes this block in document order.
        for (let hi = headers.length - 1; hi >= 0; hi--) {
            if (headers[hi].compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING) {
                groups[hi].blocks.push(bi);
                break;
            }
        }
    });
    return groups.filter(g => g.blocks.length > 0);
}

/**
 * Handle keyboard shortcuts:
 *  ?        — toggle help popup
 *  Escape   — close popup / clear section focus
 *  j / k    — move focus to next / previous section (wraps around)
 *  g / G    — jump to first / last section
 *  n / N    — jump to first section of next / previous category
 */
document.addEventListener('keydown', (e) => {
    if (e.key === '?') {
        kbdPopup.classList.toggle('visible');
        return;
    }

    if (e.key === 'Escape') {
        kbdPopup.classList.remove('visible');
        const blocks = Array.from(document.querySelectorAll('.category-section'));
        if (focusedBlockIndex >= 0 && focusedBlockIndex < blocks.length) {
            blocks[focusedBlockIndex].classList.remove('block-focused');
        }
        focusedBlockIndex = -1;
        return;
    }

    if (e.key === 'n' || e.key === 'N') {
        const blocks = Array.from(document.querySelectorAll('.category-section'));
        if (blocks.length === 0) return;
        e.preventDefault();
        const groups = buildCategoryGroups();
        if (groups.length === 0) return;

        let currentGroup = -1;
        if (focusedBlockIndex >= 0) {
            for (let gi = 0; gi < groups.length; gi++) {
                if (groups[gi].blocks.includes(focusedBlockIndex)) { currentGroup = gi; break; }
            }
        }

        if (focusedBlockIndex >= 0 && focusedBlockIndex < blocks.length) {
            blocks[focusedBlockIndex].classList.remove('block-focused');
        }

        const nextGroup = e.key === 'n'
            ? (currentGroup === -1 ? 0 : (currentGroup + 1) % groups.length)
            : (currentGroup === -1 ? groups.length - 1 : (currentGroup - 1 + groups.length) % groups.length);

        focusedBlockIndex = groups[nextGroup].blocks[0];
        blocks[focusedBlockIndex].classList.add('block-focused');
        // Scroll to the category header so it's visible at the top.
        const headerEl = groups[nextGroup].header;
        (headerEl || blocks[focusedBlockIndex]).scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
    }

    if (e.key !== 'j' && e.key !== 'k' && e.key !== 'g' && e.key !== 'G') return;

    const blocks = Array.from(document.querySelectorAll('.category-section'));
    if (blocks.length === 0) return;

    e.preventDefault();

    // Remove highlight from the previously focused block.
    if (focusedBlockIndex >= 0 && focusedBlockIndex < blocks.length) {
        blocks[focusedBlockIndex].classList.remove('block-focused');
    }

    if (e.key === 'k') {
        // Previous section, wrapping from first to last.
        focusedBlockIndex = focusedBlockIndex === -1
            ? blocks.length - 1
            : (focusedBlockIndex - 1 + blocks.length) % blocks.length;
    } else if (e.key === 'j') {
        // Next section, wrapping from last to first.
        focusedBlockIndex = focusedBlockIndex === -1
            ? 0
            : (focusedBlockIndex + 1) % blocks.length;
    } else if (e.key === 'g') {
        focusedBlockIndex = 0;
    } else if (e.key === 'G') {
        focusedBlockIndex = blocks.length - 1;
    }

    blocks[focusedBlockIndex].classList.add('block-focused');
    blocks[focusedBlockIndex].scrollIntoView({ behavior: 'smooth', block: 'start' });
});
