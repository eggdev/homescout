"""Prototype browser check. Not collected by pytest.

Requires Playwright and a built HTML file:
  python -m app.build_mobile --source csv
  python app/manual/test_mobile2.py
Override the file with HOMESCOUT_APP_FILE.
"""
import os
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_default = _ROOT / "dist" / "westchester_homes_mobile.html"
U = Path(os.environ.get("HOMESCOUT_APP_FILE", _default)).resolve().as_uri()

import asyncio,time,json
from playwright.async_api import async_playwright
ARGS=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']
FPS="""(ms)=>new Promise(r=>{const t=[];let s=performance.now();function f(n){t.push(n);if(n-s<ms)requestAnimationFrame(f);else{const d=t.slice(1).map((x,i)=>x-t[i]);d.sort((a,b)=>a-b);r({fps:Math.round(1000*(d.length)/(t[t.length-1]-t[0])),p95:Math.round(d[Math.floor(d.length*.95)])})}}requestAnimationFrame(f)})"""
async def drag(cdp,x,y0,y1,steps=12):
    await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y0}]})
    for k in range(1,steps+1):
        await cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x,'y':y0+(y1-y0)*k/steps}]});await asyncio.sleep(.02)
    await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(args=ARGS)
    ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append(str(e)));cdp=await ctx.new_cdp_session(pg)
    t=time.time();await pg.goto(U);await pg.wait_for_function('window.__ready',timeout=60000);print('load',round(time.time()-t,2),await pg.inner_text('#count'))
    await pg.wait_for_timeout(3000);await pg.screenshot(path='mobile_iphone_map.png')
    sh=lambda:pg.evaluate("document.querySelector('#sheet').offsetHeight")
    print('sheet peek',await sh())
    # drag list area up while peek -> sheet should grow, list should not scroll
    await drag(cdp,195,780,420);await pg.wait_for_timeout(500);print('after drag up',await sh(),'listScroll',await pg.evaluate("document.querySelector('#list').scrollTop"))
    await drag(cdp,195,700,200);await pg.wait_for_timeout(500);print('after 2nd drag (full?)',await sh(),await pg.evaluate("document.querySelector('#sheet').classList.contains('full')"))
    # now scroll list (drag up inside list) -> list scrolls, sheet stays
    await pg.evaluate("document.querySelector('#list').scrollTop=600");print('list scrolled',await pg.evaluate("document.querySelector('#list').scrollTop"))
    await pg.evaluate("document.querySelector('#list').scrollTop=0")
    await drag(cdp,195,300,700);await pg.wait_for_timeout(500);print('pull down at top ->',await sh())
    await pg.evaluate("void setSheet('half')");await pg.wait_for_timeout(400);await pg.screenshot(path='mobile_iphone_sheet_half.png');await pg.evaluate("void setSheet('peek')")
    # map anchoring + fps during zoom animation
    await pg.evaluate("void map.jumpTo({center:[-73.80,40.99],zoom:12})");await pg.wait_for_timeout(1500)
    fps_task=pg.evaluate(FPS,1500);await pg.evaluate("void map.easeTo({zoom:16,duration:1400})");print('fps during zoom anim',await fps_task)
    await pg.wait_for_timeout(2500);print('area list:',await pg.inner_text('#count'),'|',await pg.inner_text('#medline'))
    pills=await pg.evaluate("map.queryRenderedFeatures({layers:['pills']}).length");print('pills rendered',pills)
    await pg.screenshot(path='mobile_iphone_pins.png')
    # pinch zoom via CDP
    z0=await pg.evaluate("map.getZoom()");await cdp.send('Input.synthesizePinchGesture',{'x':195,'y':350,'scaleFactor':0.5,'relativeSpeed':800,'gestureSourceType':'touch'});await pg.wait_for_timeout(800)
    print('pinch zoom',round(z0,2),'->',round(await pg.evaluate("map.getZoom()"),2))
    await pg.evaluate("void map.jumpTo({center:[-73.80,40.99],zoom:16.5})");await pg.wait_for_timeout(2000)
    # tap a pin -> preview
    pt=await pg.evaluate("(()=>{const f=map.queryRenderedFeatures({layers:['pills']})[0];const p=map.project(f.geometry.coordinates);return [p.x,p.y,f.properties.i]})()")
    await pg.touchscreen.tap(pt[0],pt[1]);await pg.wait_for_timeout(500);print('preview shown',await pg.evaluate("document.querySelector('#preview').style.display"))
    await pg.screenshot(path='mobile_iphone_preview.png')
    # tap card in list -> highlight
    await pg.evaluate("void setSheet('half')");await pg.wait_for_timeout(400);await pg.locator('#list .card').nth(1).tap();await pg.wait_for_timeout(900)
    print('card tap -> selected',await pg.evaluate("document.querySelectorAll('#list .card.hl').length"),await pg.evaluate("map.getSource('sel')._data.geometry?1:0"))
    # Street View detail for Scarsdale + Yonkers
    for town in ['Scarsdale','Yonkers']:
        i=await pg.evaluate(f"C.city_town?0:0") if False else await pg.evaluate(f"(()=>{{const d=C.city_town.d.indexOf('{town}');for(let i=0;i<C.city_town.v.length;i++)if(C.city_town.v[i]===d&&g('road_dist_m',i)<40)return i}})()")
        await pg.evaluate(f"openDetail({i},true)");await pg.wait_for_timeout(9000)
        ok=await pg.evaluate("document.querySelector('#svh').classList.contains('ok')");fr=[f.url[:60] for f in pg.frames if 'google' in f.url]
        print(town,'sv loaded',ok,fr[:1]);await pg.screenshot(path=f'mobile_iphone_streetview_{town.lower()}.png')
        if town=='Scarsdale': await pg.screenshot(path='mobile_iphone_streetview.png')
        await pg.evaluate("closeOv('detail')")
    await pg.click('.chip[data-c=more]');await pg.wait_for_timeout(400);await pg.screenshot(path='mobile_iphone_filters.png');await pg.click('#fSee')
    await pg.click('#bLayers');await pg.click('.lt[data-l=sd]');await pg.click('.lt[data-l=flood]');await pg.click('#layers .ovh button');await pg.wait_for_timeout(3000);await pg.screenshot(path='mobile_iphone_layers.png')
    print('errors',errs)
    d=await b.new_page(viewport={'width':1280,'height':800});await d.goto(U);await d.wait_for_function('window.__ready');await d.wait_for_timeout(3000);await d.screenshot(path='mobile_desktop_map.png')
    await b.close()
asyncio.run(main())
