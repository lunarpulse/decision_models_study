const m0 = modeFromLocation();
setMode(m0, false, false);
health(); loadPresets(); setInterval(health, 15000);
setTimeout(() => {   // never a silent blank floor: if this build failed to build it, say so
  const el = document.getElementById("domainfloor");
  if (MODE === "domain" && el && el.hidden === false && !el.innerHTML.trim())
    el.innerHTML = `<div class="card"><p><b>The domain floor failed to initialize.</b> This page copy
      may be stale (browser or edge cache) — reload with a cache-buster (<code>?mode=domain&amp;v=2</code>)
      or check the studio service. If you see this, the console version predates the fix.</p></div>`;
}, 4000);
