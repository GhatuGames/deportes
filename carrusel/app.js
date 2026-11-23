(function(){
  var b = document.getElementById("copiar");
  var t = document.getElementById("pie");
  var ok = document.getElementById("copiado");
  if (!b || !t) return;
  b.addEventListener("click", function(){
    var texto = t.value;
    function listo(){
      if (ok){ ok.hidden = false; setTimeout(function(){ ok.hidden = true; }, 2200); }
    }
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(texto).then(listo).catch(function(){ t.select(); document.execCommand("copy"); listo(); });
    } else { t.select(); document.execCommand("copy"); listo(); }
  });
})();
