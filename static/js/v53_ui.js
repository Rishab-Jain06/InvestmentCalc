(function(){
  const mobile=window.matchMedia('(max-width:760px)');
  function tuneAnalysisDetails(){
    document.querySelectorAll('#trade-analysis .analysis-detail').forEach(d=>{
      if(d.dataset.v53Ready==='1')return;
      d.dataset.v53Ready='1';
      if(mobile.matches)d.open=false;
      d.addEventListener('toggle',()=>{
        if(d.open){
          const canvas=d.querySelector('canvas');
          if(canvas&&window.Chart){const c=Chart.getChart(canvas);setTimeout(()=>c?.resize(),50);}
        }
      });
    });
  }
  function retune(){tuneAnalysisDetails();}
  document.addEventListener('DOMContentLoaded',retune);
  const observer=new MutationObserver(retune);
  observer.observe(document.documentElement,{childList:true,subtree:true});
  mobile.addEventListener?.('change',()=>{
    document.querySelectorAll('#trade-analysis .analysis-detail').forEach(d=>{if(mobile.matches)d.open=false;else d.open=true;});
  });
})();
