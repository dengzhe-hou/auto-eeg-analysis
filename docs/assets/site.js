const tabs = [...document.querySelectorAll('[role="tab"]')];
function selectClient(tab, focus = false) {
  for (const item of tabs) {
    const selected = item === tab;
    item.setAttribute('aria-selected', String(selected));
    item.tabIndex = selected ? 0 : -1;
    document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
  }
  if (focus) tab.focus();
}
tabs.forEach((tab, index) => {
  tab.addEventListener('click', () => selectClient(tab));
  tab.addEventListener('keydown', event => {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = tabs.length - 1;
    if (next !== undefined) {
      event.preventDefault();
      selectClient(tabs[next], true);
    }
  });
});
const copyStatus = document.getElementById('copy-status');
document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    const code = document.getElementById(button.dataset.copy);
    try {
      await navigator.clipboard.writeText(code.textContent);
      copyStatus.textContent = copyStatus.dataset.copySuccess;
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      copyStatus.textContent = copyStatus.dataset.copyFallback;
    }
  });
});

const pageSections = [...document.querySelectorAll('.page-section[id]')];
if (pageSections.length) {
  const language = document.documentElement.lang;
  const directoryLabels = language.startsWith('zh')
    ? { name: '页面目录', button: '目录' }
    : language.startsWith('ja')
      ? { name: 'ページ内の目次', button: '目次' }
      : { name: 'On this page', button: 'Contents' };
  const directory = document.createElement('nav');
  directory.className = 'section-nav';
  directory.setAttribute('aria-label', directoryLabels.name);
  const directoryButton = document.createElement('button');
  directoryButton.type = 'button';
  directoryButton.className = 'section-nav-toggle';
  directoryButton.textContent = directoryLabels.button;
  directoryButton.setAttribute('aria-controls', 'section-navigation');
  const directoryPanel = document.createElement('div');
  directoryPanel.className = 'section-nav-panel';
  directoryPanel.id = 'section-navigation';
  const directoryLinks = pageSections.map(section => {
    const link = document.createElement('a');
    link.href = `#${section.id}`;
    link.textContent = section.querySelector('h2').textContent.trim();
    directoryPanel.append(link);
    return link;
  });
  directory.append(directoryButton, directoryPanel);
  document.body.append(directory);

  const wideDirectory = window.matchMedia('(min-width: 1440px)');
  let directoryOpen = false;
  function displayDirectory() {
    directoryButton.hidden = wideDirectory.matches;
    directoryPanel.hidden = !wideDirectory.matches && !directoryOpen;
    directoryButton.setAttribute('aria-expanded', String(directoryOpen));
  }
  directoryButton.addEventListener('click', () => {
    directoryOpen = !directoryOpen;
    displayDirectory();
  });
  directoryPanel.addEventListener('click', event => {
    if (event.target.closest('a') && !wideDirectory.matches) {
      directoryOpen = false;
      displayDirectory();
      directoryButton.focus({ preventScroll: true });
    }
  });
  document.addEventListener('click', event => {
    if (directoryOpen && !directory.contains(event.target)) {
      directoryOpen = false;
      displayDirectory();
    }
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && directoryOpen) {
      directoryOpen = false;
      displayDirectory();
      directoryButton.focus();
    }
  });
  wideDirectory.addEventListener('change', () => {
    directoryOpen = false;
    displayDirectory();
  });
  displayDirectory();

  function markCurrentSection() {
    let current = pageSections[0];
    for (const section of pageSections) {
      if (section.getBoundingClientRect().top <= window.innerHeight * 0.25) current = section;
    }
    if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 4) {
      current = pageSections[pageSections.length - 1];
    }
    directoryLinks.forEach((link, index) => {
      if (pageSections[index] === current) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  }
  let directoryFrame = 0;
  function queueDirectoryUpdate() {
    if (!directoryFrame) directoryFrame = requestAnimationFrame(() => {
      directoryFrame = 0;
      markCurrentSection();
    });
  }
  window.addEventListener('scroll', queueDirectoryUpdate, { passive: true });
  window.addEventListener('resize', queueDirectoryUpdate);
  window.addEventListener('load', markCurrentSection, { once: true });
  markCurrentSection();
}
