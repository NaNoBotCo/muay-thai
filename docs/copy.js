document.addEventListener("click",function(e){
var b=e.target.closest("[data-copy]");if(!b)return;
navigator.clipboard.writeText(b.dataset.copy).then(function(){
var s=b.querySelector("span");if(!s)return;var t=s.textContent;s.textContent="Copied";
setTimeout(function(){s.textContent=t},1600)})});