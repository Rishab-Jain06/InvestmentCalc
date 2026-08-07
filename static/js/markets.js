
document.querySelectorAll(".market-tile").forEach(async tile=>{
  const s=tile.dataset.symbol;
  try{
    const q=await (await fetch(`/api/quote/${encodeURIComponent(s)}`)).json();
    if(q.error)throw Error(q.error);
    tile.querySelector(".m-price").textContent=q.price==null?"—":`$${Number(q.price).toFixed(2)}`;
    const c=Number(q.percent_change||0), e=tile.querySelector(".m-change");
    e.textContent=`${c>=0?"+":""}${c.toFixed(2)}%`;
    e.className=`m-change ${c>=0?"positive":"negative"}`;
  }catch(e){
    tile.querySelector(".m-change").textContent="Unavailable";
  }
});
