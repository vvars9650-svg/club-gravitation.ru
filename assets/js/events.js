fetch('/data/events.json').then(r=>r.json()).then(data=>{window.GRAVITY_EVENTS=data;}).catch(()=>{});
