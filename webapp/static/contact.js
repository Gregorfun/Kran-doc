(function() {
  function initContactModal() {
    var modal = document.getElementById('contact-modal');
    var openBtns = [];
    var defaultBtn = document.getElementById('contact-open');
    var footerBtn = document.getElementById('contact-footer-open');
    if (defaultBtn) openBtns.push(defaultBtn);
    if (footerBtn) openBtns.push(footerBtn);
    var form = document.getElementById('contact-form');
    var statusEl = document.getElementById('contact-status');
    var msgInput = document.getElementById('contact-message');

    if (!modal || openBtns.length === 0 || !form) {
      return;
    }

    function setStatus(msg, type) {
      if (!statusEl) return;
      statusEl.textContent = msg || '';
      statusEl.className = 'search-status ' + (type || '');
    }

    function openModal() {
      modal.classList.add('is-open');
      modal.setAttribute('aria-hidden', 'false');
      setStatus('');
      if (msgInput) msgInput.focus();
    }

    function closeModal() {
      modal.classList.remove('is-open');
      modal.setAttribute('aria-hidden', 'true');
    }

    openBtns.forEach(function(btn) {
      btn.addEventListener('click', openModal);
    });

    modal.addEventListener('click', function(ev) {
      if (ev.target && ev.target.getAttribute('data-close') === '1') {
        closeModal();
      }
    });

    document.addEventListener('keydown', function(ev) {
      if (ev.key === 'Escape') closeModal();
    });

    form.addEventListener('submit', function(ev) {
      ev.preventDefault();

      var name = (document.getElementById('contact-name').value || '').trim();
      var email = (document.getElementById('contact-email').value || '').trim();
      var message = (document.getElementById('contact-message').value || '').trim();

      if (!message) {
        setStatus('Bitte Nachricht eingeben.', 'error');
        return;
      }
      if (message.length > 1500) {
        setStatus('Nachricht ist zu lang (max 1500 Zeichen).', 'error');
        return;
      }

      setStatus('Sende ...', 'pending');

      fetch('/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, email: email, message: message })
      })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
          if (!data.ok) {
            setStatus(data.error || 'Fehler beim Senden.', 'error');
            return;
          }
          setStatus('Nachricht gesendet.', 'ok');
          form.reset();
          setTimeout(closeModal, 600);
        })
        .catch(function(err) {
          console.error(err);
          setStatus('Fehler beim Senden: ' + err, 'error');
        });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initContactModal);
  } else {
    initContactModal();
  }
})();
