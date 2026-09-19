document.addEventListener("click",function(e){
var b=e.target.closest("[data-copy]");if(!b)return;
navigator.clipboard.writeText(b.dataset.copy).then(function(){
var s=b.querySelector("span");if(!s)return;var t=s.textContent;s.textContent="Copied";
setTimeout(function(){s.textContent=t},1600)})});
(function(){var h=document.querySelector("header.top");if(!h)return;
var b=document.body,last=window.pageYOffset,hh=h.offsetHeight;
addEventListener("resize",function(){hh=h.offsetHeight},{passive:true});
addEventListener("scroll",function(){var y=window.pageYOffset,d=y-last;
if(y<=hh||d<-4){b.classList.remove("nav-away")}
else if(d>4){b.classList.add("nav-away")}
if(Math.abs(d)>1)last=y},{passive:true});
addEventListener("focusin",function(e){if(h.contains(e.target))
b.classList.remove("nav-away")});})();