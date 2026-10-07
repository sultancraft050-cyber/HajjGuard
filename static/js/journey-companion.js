(() => {
  'use strict';
  const form = document.getElementById('journey-form');
  if (!form) return;
  const ar = document.documentElement.lang.startsWith('ar');
  const text = (en, arabic) => ar ? arabic : en;
  const result = document.getElementById('journey-result');
  const origin = document.getElementById('journey-from');
  const destination = document.getElementById('journey-to');
  const preference = document.getElementById('journey-preference');
  const submit = document.getElementById('journey-submit');
  const titles = {fastest:text('Fastest','الأسرع'),less_crowded:text('Less crowded','أقل ازدحاماً'),wheelchair:text('Wheelchair friendly','مناسب للكراسي المتحركة'),less_walking:text('Less walking','مشي أقل'),cooler:text('Shaded route','مسار مظلل')};
  const unavailable = text('Not measured. Verify conditions before leaving.','غير مقاس. تحقق من الظروف قبل الانطلاق.');
  function paragraph(value, className = '') {
    const p = document.createElement('p'); p.textContent = value; p.className = className; return p;
  }
  function present(journey, key = journey.preference) {
    const route = journey.route_alternatives[key];
    result.replaceChildren();
    if (journey.safety_mode) result.append(paragraph(text('Crowded destination. Consider waiting in a safe area or another route.','الوجهة مزدحمة. انتظر في مكان آمن أو جرّب مساراً آخر.'),'journey-warning'));
    result.append(paragraph(titles[key]));
    result.append(paragraph(route.is_connected ? `${text('Estimated walking time','وقت المشي التقديري')}: ${route.estimated_minutes} ${text('minutes','دقيقة')}` : text('No verified route for this preference. Open the geographic map.','لا يتوفر مسار موثق لهذا التفضيل. افتح الخريطة الجغرافية.')));
    const translatedCrowd = {Comfortable:'مريح',Busy:'مشغول',Crowded:'مزدحم'};
    result.append(paragraph(`${text('Crowd','الازدحام')}: ${journey.crowd ? (ar ? translatedCrowd[journey.crowd] : journey.crowd) : unavailable}`));
    result.append(paragraph(`${text('Best departure time','أفضل وقت للانطلاق')}: ${unavailable}`));
    if (journey.data_stale) result.append(paragraph(text('The last crowd record is stale; it is not a current recommendation.','سجل الازدحام قديم ولا يمثل توصية حالية.')));
    if (journey.data_timestamp) result.append(paragraph(`${text('Last record','آخر سجل')}: ${new Date(journey.data_timestamp).toLocaleString(ar?'ar':'en')}`));
    const steps = document.createElement('ol');
    for (const code of route.path) {
      const li = document.createElement('li');
      li.textContent = Array.from(destination.options).find(o=>o.value===code)?.textContent || code;
      steps.append(li);
    }
    if (route.is_connected) result.append(steps);
    result.append(paragraph(text('Local corridor estimates, not turn-by-turn navigation. Follow on-site instructions.','تقديرات ممرات محلية وليست ملاحة تفصيلية. اتبع التعليمات في الموقع.')));
    if (key==='cooler') result.append(paragraph(text('Shade only; temperature along this route is not measured.','التفضيل مبني على الظل فقط؛ حرارة المسار غير مقاسة.')));
    const alternatives = document.createElement('div'); alternatives.className='journey-alternatives';
    for (const alternative of ['fastest','less_crowded','wheelchair','less_walking','cooler']) {
      const button=document.createElement('button'); button.type='button'; button.textContent=titles[alternative];
      button.setAttribute('aria-pressed', String(alternative===key)); button.addEventListener('click',()=>present(journey,alternative)); alternatives.append(button);
    }
    result.append(alternatives);
    document.dispatchEvent(new CustomEvent('hajjguard:journey', {detail:{route,alternatives:journey.route_alternatives}}));
  }
  function coordinates() {
    return new Promise((resolve,reject)=> {
      if (!navigator.geolocation) return reject(new Error('location'));
      navigator.geolocation.getCurrentPosition(p=>resolve(p.coords),reject,{enableHighAccuracy:true,timeout:10000,maximumAge:0});
    });
  }
  function endpoint(params, prefix, value) {
    if (value.startsWith('place:')) params.set(`${prefix}_place`,value.slice(6));
    else if (value.startsWith('facility:')) params.set(`${prefix}_facility`,value.slice(9));
    else params.set(prefix,value);
  }
  form.addEventListener('submit',async event=> {
    event.preventDefault(); submit.disabled=true; result.replaceChildren(paragraph(text('Planning your journey…','جارٍ تخطيط رحلتك…')));
    try {
      const params=new URLSearchParams({preference:preference.value});
      if (origin.value==='current') {
        const location=await coordinates(); params.set('from_lat',location.latitude); params.set('from_lng',location.longitude);
      } else endpoint(params,'from',origin.value);
      endpoint(params,'to',destination.value);
      const response=await fetch(`/analytics/api/calculate-route/?${params}`,{credentials:'same-origin',cache:'no-store'});
      const data=await response.json();
      if (!response.ok || data.status!=='success') throw new Error('route');
      present(data.route_comparison.journey);
    } catch(error) {
      result.replaceChildren(paragraph(text('Journey unavailable. Check your location permission, connection and corridor coverage, then try again.','الرحلة غير متاحة. تحقق من إذن الموقع والاتصال وتغطية الممرات، ثم حاول مجدداً.')));
    } finally {submit.disabled=false;}
  });
  function addOption(item,prefix,label) {
    for(const select of [origin,destination]) {const option=document.createElement('option');option.value=`${prefix}:${item.id}`;option.textContent=label;select.append(option);}
  }
  Promise.allSettled([
    fetch('/zones/api/visitor-places/',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>data.places.forEach(p=>addOption(p,'place',ar?p.name_ar:p.name_en))),
    fetch('/zones/api/safety-features/',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error();return r.json();}).then(data=>data.features.forEach(f=>addOption(f,'facility',f.name)))
  ]).then(()=> {
    const query=new URLSearchParams(location.search);
    for(const [key,select] of [['from',origin],['to',destination],['preference',preference]]) if(query.has(key)) select.value=query.get(key);
  });
  document.addEventListener('hajjguard:destination',event=> {
    destination.value=event.detail.value; document.getElementById('journey').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
  });
})();
