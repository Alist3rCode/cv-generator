/**
 * autosave.js — Auto-save fields with per-field save/reset buttons.
 *
 * API publique :
 *   initAutoSave(form, opts)  — initialise tous les champs du formulaire
 *   asWrapInput(field, form, opts) — wrapping manuel (lignes dynamiques)
 *   asBindSelect(sel, form, opts)  — binding select manuel
 *
 * opts :
 *   beforeSubmit  — fn() appelée avant chaque soumission fetch (ex : sync Quill)
 *   quill         — instance Quill (pour le champ description)
 *   quillHidden   — input[type=hidden] lié à Quill
 */
(function () {
  'use strict';

  /* ── Soumission via fetch ───────────────────────────────────────── */
  function submitFetch(form, beforeSubmit, onSuccess) {
    if (beforeSubmit) beforeSubmit();
    var mode = form.dataset.autosaveMode || 'edit';
    if (mode === 'create') {
      form.submit();
      return;
    }
    var fd = new FormData(form);
    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'fetch' },
      body: fd,
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        if (data.redirect) { window.location.href = data.redirect; return; }
        if (onSuccess) onSuccess();
        // __formDirty est recalculé dans onSuccess — ne pas écraser ici
      })
      .catch(function (err) {
        console.warn('[AutoSave] error:', err);
      });
  }

  /* ── Recalculer __formDirty après nettoyage local ─────────────── */
  function recheckDirty(form) {
    window.__formDirty = !!form.querySelector('.as-field-wrap.is-dirty, .as-textarea-wrap.is-dirty');
  }

  /* ── Créer un bouton icon ─────────────────────────────────────── */
  function makeBtn(icon, extraClass) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'as-btn ' + (extraClass || '');
    btn.innerHTML = '<i class="bi ' + icon + '"></i>';
    return btn;
  }

  /* ── Wrapper champ 1 ligne ────────────────────────────────────── */
  function wrapInput(field, form, opts) {
    if (field.closest('.as-field-wrap')) return;

    var wrap = document.createElement('div');
    wrap.className = 'as-field-wrap';
    field.parentNode.insertBefore(wrap, field);
    wrap.appendChild(field);

    var origVal  = field.value;
    var saveBtn  = makeBtn('bi-floppy', 'as-save');
    var resetBtn = makeBtn('bi-arrow-counterclockwise', 'as-reset');
    wrap.appendChild(saveBtn);
    wrap.appendChild(resetBtn);

    function check() {
      var dirty = field.value !== origVal;
      wrap.classList.toggle('is-dirty', dirty);
      if (dirty) window.__formDirty = true;
    }
    function doSave() {
      submitFetch(form, opts && opts.beforeSubmit, function () {
        origVal = field.value;
        wrap.classList.remove('is-dirty');
        recheckDirty(form);
      });
    }
    function doReset() {
      field.value = origVal;
      wrap.classList.remove('is-dirty');
      recheckDirty(form);
    }

    field.addEventListener('input', check);
    saveBtn.addEventListener('click', doSave);
    resetBtn.addEventListener('click', doReset);
  }

  /* ── Wrapper textarea multi-ligne ─────────────────────────────── */
  function wrapTextarea(field, form, opts) {
    if (field.closest('.as-textarea-wrap')) return;

    var wrap = document.createElement('div');
    wrap.className = 'as-textarea-wrap';
    field.parentNode.insertBefore(wrap, field);
    wrap.appendChild(field);

    var origVal  = field.value;
    var stack    = document.createElement('div');
    stack.className = 'as-btn-stack';
    var resetBtn = makeBtn('bi-arrow-counterclockwise', 'as-reset');
    var saveBtn  = makeBtn('bi-floppy', 'as-save');
    stack.appendChild(resetBtn);
    stack.appendChild(saveBtn);
    wrap.appendChild(stack);

    function check() {
      var dirty = field.value !== origVal;
      wrap.classList.toggle('is-dirty', dirty);
      if (dirty) window.__formDirty = true;
    }
    function doSave() {
      submitFetch(form, opts && opts.beforeSubmit, function () {
        origVal = field.value;
        wrap.classList.remove('is-dirty');
        recheckDirty(form);
      });
    }
    function doReset() {
      field.value = origVal;
      wrap.classList.remove('is-dirty');
      recheckDirty(form);
    }

    field.addEventListener('input', check);
    saveBtn.addEventListener('click', doSave);
    resetBtn.addEventListener('click', doReset);
  }

  /* ── Wrapper éditeur Quill ────────────────────────────────────── */
  function wrapQuill(quill, hiddenInput, form, opts) {
    var container = quill.root.parentElement; // .ql-container
    if (container.closest('.as-textarea-wrap')) return;

    var wrap = document.createElement('div');
    wrap.className = 'as-textarea-wrap';
    container.parentNode.insertBefore(wrap, container);
    wrap.appendChild(container);

    var origVal  = hiddenInput.value;
    var stack    = document.createElement('div');
    stack.className = 'as-btn-stack';
    var resetBtn = makeBtn('bi-arrow-counterclockwise', 'as-reset');
    var saveBtn  = makeBtn('bi-floppy', 'as-save');
    stack.appendChild(resetBtn);
    stack.appendChild(saveBtn);
    wrap.appendChild(stack);

    function check() {
      var cur   = quill.root.innerHTML;
      var dirty = cur !== origVal && !(origVal === '' && cur === '<p><br></p>');
      wrap.classList.toggle('is-dirty', dirty);
      if (dirty) window.__formDirty = true;
    }
    function doSave() {
      hiddenInput.value = quill.root.innerHTML;
      submitFetch(form, opts && opts.beforeSubmit, function () {
        origVal = quill.root.innerHTML;
        wrap.classList.remove('is-dirty');
        recheckDirty(form);
      });
    }
    function doReset() {
      quill.root.innerHTML = origVal;
      wrap.classList.remove('is-dirty');
      recheckDirty(form);
    }

    quill.on('text-change', check);
    saveBtn.addEventListener('click', doSave);
    resetBtn.addEventListener('click', doReset);
  }

  /* ── Select auto-save ─────────────────────────────────────────── */
  function bindSelect(sel, form, opts) {
    sel.addEventListener('change', function () {
      submitFetch(form, opts && opts.beforeSubmit, function () {
        recheckDirty(form);
      });
    });
  }

  /* ── API publique ─────────────────────────────────────────────── */
  window.initAutoSave = function (form, opts) {
    opts = opts || {};

    var inputSel = [
      'input[type=text]', 'input[type=tel]', 'input[type=url]',
      'input[type=month]', 'input[type=date]',
    ].map(function (s) { return s + ':not([disabled]):not([data-no-autosave])'; }).join(',');
    form.querySelectorAll(inputSel).forEach(function (f) { wrapInput(f, form, opts); });

    form.querySelectorAll('textarea:not([disabled]):not([data-no-autosave])').forEach(function (f) {
      wrapTextarea(f, form, opts);
    });

    form.querySelectorAll('select:not([disabled]):not([data-no-autosave])').forEach(function (s) {
      bindSelect(s, form, opts);
    });

    if (opts.quill && opts.quillHidden) {
      wrapQuill(opts.quill, opts.quillHidden, form, opts);
    }
  };

  window.asWrapInput  = function (f, form, opts) { wrapInput(f, form, opts); };
  window.asBindSelect = function (s, form, opts) { bindSelect(s, form, opts); };

})();
