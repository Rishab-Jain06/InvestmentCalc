(function(){
  const MQ = window.matchMedia('(max-width: 760px)');
  function labelFor(el){
    return el.dataset.mobileTitle || el.querySelector('h1,h2,h3,.eyebrow')?.textContent?.trim() || 'Section';
  }
  function setState(el, collapsed){
    el.classList.toggle('mobile-collapsed', !!collapsed);
    const btn = el.querySelector(':scope > .mobile-section-toggle');
    if(btn){
      btn.setAttribute('aria-expanded', String(!collapsed));
      const text = btn.querySelector('span');
      const icon = btn.querySelector('b');
      if(text) text.textContent = labelFor(el);
      if(icon) icon.textContent = collapsed ? '▾' : '▴';
    }
  }
  function setupOne(el){
    if(el.dataset.mobileCollapseReady === '1') return;
    el.dataset.mobileCollapseReady = '1';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'mobile-section-toggle';
    btn.innerHTML = `<span>${labelFor(el)}</span><b aria-hidden="true">▴</b>`;
    btn.addEventListener('click', () => setState(el, !el.classList.contains('mobile-collapsed')));
    el.insertBefore(btn, el.firstChild);
    setState(el, MQ.matches && el.classList.contains('mobile-default-collapsed'));
  }
  function setup(){
    document.querySelectorAll('.mobile-collapsible').forEach(setupOne);
    document.querySelectorAll('.mobile-collapsible').forEach(el => {
      if(!MQ.matches){
        el.classList.remove('mobile-collapsed');
        const btn = el.querySelector(':scope > .mobile-section-toggle');
        if(btn) btn.setAttribute('aria-expanded','true');
      }else if(el.classList.contains('mobile-default-collapsed') && !el.dataset.mobileTouched){
        setState(el, true);
      }
    });
  }
  window.InvestifyMobile = window.InvestifyMobile || {};
  window.InvestifyMobile.openSection = function(el){
    if(!el) return;
    setupOne(el);
    el.dataset.mobileTouched = '1';
    setState(el, false);
  };
  document.addEventListener('DOMContentLoaded', setup);
  MQ.addEventListener?.('change', setup);
})();
