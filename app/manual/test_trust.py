"""Prototype browser check. Not collected by pytest.

Requires Playwright and a built HTML file:
  python -m app.build_mobile --source csv
  python app/manual/test_trust.py
Override the file with HOMESCOUT_APP_FILE.
"""
import os
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_default = _ROOT / "dist" / "westchester_homes_mobile.html"
U = Path(os.environ.get("HOMESCOUT_APP_FILE", _default)).resolve().as_uri()

import asyncio
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
    ctx=await b.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True);pg=await ctx.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    await pg.goto(U);await pg.wait_for_function('window.__ready',timeout=60000)
    await pg.evaluate("void map.jumpTo({center:[-73.77,41.05],zoom:9.5})");await pg.wait_for_timeout(1500);print('all',await pg.inner_text('#count'))
    await pg.click('.chip[data-c=trust]');await pg.wait_for_timeout(1500);print('trust chip',await pg.inner_text('#count'))
    await pg.evaluate("void map.jumpTo({center:[-73.795,40.99],zoom:15.3})");await pg.wait_for_timeout(2500)
    print('trust pills',await pg.evaluate("map.queryRenderedFeatures({layers:['pills']}).filter(f=>f.properties.t===1).length"))
    await pg.evaluate("void setSheet('half')");await pg.wait_for_timeout(600);await pg.screenshot(path='mobile_iphone_trust.png')
    i=await pg.evaluate("(()=>{for(let k=0;k<C.owner_type.v.length;k++)if(g('family_confidence',k)==='same surname'&&g('family_tenure_combined_yrs',k)>=20&&(g('tenure_years_est',k)||0)<10)return k})()")
    await pg.evaluate(f"openDetail({i},true)");await pg.wait_for_timeout(1500);await pg.click('#detail .tabs button[data-t=ow]');await pg.wait_for_timeout(800)
    await pg.screenshot(path='mobile_iphone_trust_detail.png');print(await pg.evaluate("document.querySelector('#t-ow').innerText.slice(0,400)"))
    await pg.evaluate("closeOv('detail')");await pg.click('.chip[data-c=more]');await pg.locator('#sec-owner').scroll_into_view_if_needed();await pg.wait_for_timeout(300);await pg.screenshot(path='mobile_iphone_trust_filters.png')
    print('errors',errs);await b.close()
asyncio.run(main())
