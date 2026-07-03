/* Kev Wing Wah : site behaviour
   Vanilla JS, no dependencies. Each block guards for missing elements
   so the same file runs on every page. */
(function () {
  'use strict';

  /* ---- Current year in the footer ------------------------------------ */
  document.querySelectorAll('#year').forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });

  /* ---- Sticky header gains a shadow once the page scrolls ------------ */
  var header = document.querySelector('.site-header');
  if (header) {
    var onScroll = function () {
      header.classList.toggle('is-scrolled', window.scrollY > 8);
    };
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ---- Mobile navigation toggle -------------------------------------- */
  var toggle = document.getElementById('nav-toggle');
  var links = document.getElementById('nav-links');
  if (toggle && links) {
    var setOpen = function (open) {
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
      links.classList.toggle('is-open', open);
    };

    toggle.addEventListener('click', function () {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });

    // Close after tapping a link, or on Escape.
    links.addEventListener('click', function (e) {
      if (e.target.closest('a')) { setOpen(false); }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { setOpen(false); }
    });
    // Reset state if the viewport grows back to desktop width.
    // Keep this in sync with the nav breakpoint in styles.css.
    window.matchMedia('(min-width: 1024px)').addEventListener('change', function (ev) {
      if (ev.matches) { setOpen(false); }
    });
  }

  /* ---- Menu page only ------------------------------------------------- */
  if (document.body.dataset.page !== 'menu') { return; }

  var sections = Array.prototype.slice.call(document.querySelectorAll('.menu-section'));
  var allItems = Array.prototype.slice.call(document.querySelectorAll('.menu-item'));
  var emptyMsg = document.getElementById('menu-empty');
  var controls = document.querySelector('.menu-controls');

  /* Anchor jumps must clear the sticky header plus the sticky controls.
     The controls height changes as chips wrap, so measure it and update
     scroll-padding on load and on resize. When the controls are static
     (mobile), only the header needs clearing. */
  var setScrollOffset = function () {
    var headerH = header ? header.offsetHeight : 0;
    var stuck = controls && getComputedStyle(controls).position === 'sticky';
    var extra = stuck ? controls.offsetHeight : 0;
    document.documentElement.style.scrollPaddingTop = (headerH + extra + 12) + 'px';
  };
  setScrollOffset();
  window.addEventListener('resize', setScrollOffset);
  // Re-measure once web fonts finish loading, since they change heights.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(setScrollOffset);
  }
  window.addEventListener('load', setScrollOffset);

  // Show the dish count next to each category heading.
  sections.forEach(function (section) {
    var count = section.querySelectorAll('.menu-item').length;
    var label = section.querySelector('.count');
    if (label) { label.textContent = count + (count === 1 ? ' dish' : ' dishes'); }
  });

  /* Live search: filter items by name, code, and contents. */
  var input = document.getElementById('menu-search-input');
  var resultsStatus = document.getElementById('menu-results-status');
  if (input) {
    // Cache lowercase search text for each item once.
    allItems.forEach(function (item) {
      item._text = item.textContent.toLowerCase().replace(/\s+/g, ' ').trim();
    });

    var runFilter = function () {
      var terms = input.value.toLowerCase().split(/\s+/).filter(Boolean);
      var shown = 0;

      allItems.forEach(function (item) {
        var match = terms.every(function (t) { return item._text.indexOf(t) !== -1; });
        item.classList.toggle('is-hidden', !match);
        if (match) { shown++; }
      });

      // Hide a category whose items are all filtered out.
      sections.forEach(function (section) {
        var visible = section.querySelectorAll('.menu-item:not(.is-hidden)').length;
        section.classList.toggle('is-hidden', visible === 0);
      });

      if (emptyMsg) { emptyMsg.classList.toggle('is-visible', shown === 0); }
      // Announce match counts to screen readers. The visible empty-state
      // message is its own live region, so only speak when there are hits.
      if (resultsStatus) {
        resultsStatus.textContent =
          terms.length === 0 ? '' :
          shown === 0 ? '' :
          shown + (shown === 1 ? ' dish matches' : ' dishes match');
      }
    };

    input.addEventListener('input', runFilter);
  }

  /* Category chips: clear any active search before jumping, so the
     target section is never hidden when the browser scrolls to it. */
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chips a'));
  chips.forEach(function (a) {
    a.addEventListener('click', function () {
      if (input && input.value) {
        input.value = '';
        input.dispatchEvent(new Event('input', { bubbles: true }));
      }
    });
  });

  /* Highlight the category chip for whichever section is in view. */
  if (chips.length && 'IntersectionObserver' in window) {
    var chipFor = {};
    chips.forEach(function (a) { chipFor[a.getAttribute('href').slice(1)] = a; });

    var setActiveChip = function (id) {
      chips.forEach(function (a) {
        a.classList.remove('is-active');
        a.removeAttribute('aria-current');
      });
      var active = chipFor[id];
      if (active) {
        active.classList.add('is-active');
        active.setAttribute('aria-current', 'true');
      }
    };

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) { setActiveChip(entry.target.id); }
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

    sections.forEach(function (section) { observer.observe(section); });
  }
})();
