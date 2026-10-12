// Mockup behaviour only: tabs, expanders, dialogs, single-choice chip groups and example scenarios.
document.querySelectorAll('[role="tablist"]').forEach((list) => {
  list.addEventListener('click', (event) => {
    const tab = event.target.closest('[role="tab"]');
    if (!tab) return;
    list.querySelectorAll('[role="tab"]').forEach((other) => {
      const selected = other === tab;
      other.setAttribute('aria-selected', String(selected));
      document.getElementById(other.getAttribute('aria-controls')).hidden = !selected;
    });
  });
});

document.addEventListener('click', (event) => {
  const toggle = event.target.closest('[data-toggle]');
  if (toggle) {
    const target = document.getElementById(toggle.dataset.toggle);
    target.hidden = !target.hidden;
    toggle.setAttribute('aria-expanded', String(!target.hidden));
    toggle.textContent = target.hidden ? toggle.dataset.closed : toggle.dataset.open;
  }
  const opener = event.target.closest('[data-dialog]');
  if (opener) document.getElementById(opener.dataset.dialog).showModal();
  const closer = event.target.closest('[data-close]');
  if (closer) closer.closest('dialog').close();
  const chip = event.target.closest('[data-group] button.chip');
  if (chip) {
    chip.parentElement.querySelectorAll('button.chip').forEach((other) => other.setAttribute('aria-pressed', String(other === chip)));
  }
  const scenario = event.target.closest('[data-scenario]');
  if (scenario) {
    document.querySelectorAll('[data-show]').forEach((part) => { part.hidden = part.dataset.show !== scenario.dataset.scenario; });
  }
});
