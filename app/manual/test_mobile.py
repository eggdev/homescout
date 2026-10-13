"""Prototype browser check. Not collected by pytest.

Requires Playwright and a built HTML file:
  python -m app.build_mobile --source csv
  python app/manual/test_mobile.py
Override the file with HOMESCOUT_APP_FILE.
"""
import os
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_default = _ROOT / "dist" / "westchester_homes_mobile.html"
U = Path(os.environ.get("HOMESCOUT_APP_FILE", _default)).resolve().as_uri()

import asyncio,time
from playwright.async_api import async_playwright
async def run(b,vp,tag,mobile):
    ctx=await b.new_context(viewport=vp,device_scale_factor=2 if mobile else 1,is_mobile=mobile,has_touch=mobile);pg=await ctx.new_page()
    errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
    t=time.time();await pg.goto(U);await pg.wait_for_function('window.__ready',timeout=60000);print(tag,'load',round(time.time()-t,2),await pg.inner_text('#count'))
    await pg.wait_for_timeout(2500);await pg.screenshot(path=f'mobile_{tag}_map.png')
    if mobile:
        await pg.evaluate("void setSheet('half')");await pg.wait_for_timeout(500);await pg.screenshot(path=f'mobile_{tag}_sheet_half.png')
    await pg.click('.chip[data-c=sen]');print(' senior chip',await pg.inner_text('#count'))
    await pg.click('.chip[data-c=more]');await pg.wait_for_timeout(300)
    await pg.click('#sec-bb [data-bb=bedrooms] button[data-n="3"]');await pg.click('#sec-bb [data-bb=bedrooms] button[data-n="4"]');print(' beds 3-4',await pg.inner_text('#fSee'))
    await pg.click('.fl[data-c=_sun] .opt[data-v=Sunny]');print(' +sunny',await pg.inner_text('#fSee'))
    await pg.screenshot(path=f'mobile_{tag}_filters.png')
    await pg.locator('#sec-price').scroll_into_view_if_needed();await pg.screenshot(path=f'mobile_{tag}_filters_price.png')
    await pg.click('#fReset');print(' reset',await pg.inner_text('#fSee'));await pg.click('#fSee')
    await pg.click('#bLayers');await pg.click('.lt[data-l=sd]');await pg.click('.lt[data-l=mn]');await pg.click('.lt[data-l=flood]');await pg.wait_for_timeout(300);await pg.screenshot(path=f'mobile_{tag}_layers.png')
    await pg.click('#layers .ovh button')
    await pg.fill('#q','Scarsd');await pg.wait_for_timeout(200);await pg.click('#sugg div >> nth=0');print(' search Scarsdale',await pg.inner_text('#count'))
    await pg.wait_for_timeout(1500);await pg.evaluate("void map.setView([40.9893,-73.7951],16)");await pg.wait_for_timeout(2500);await pg.screenshot(path=f'mobile_{tag}_pins.png');print(' pins',await pg.locator('.pricepin').count())
    if mobile: await pg.evaluate("void setSheet('half')")
    await pg.locator('.card').first.click();await pg.wait_for_timeout(800);await pg.screenshot(path=f'mobile_{tag}_detail.png')
    await pg.click('#detail .tabs button[data-t=cl]');await pg.wait_for_timeout(800);await pg.screenshot(path=f'mobile_{tag}_detail_climate.png')
    await pg.click('#dSun');await pg.wait_for_timeout(2000);await pg.fill('#sunSlider','900') if False else await pg.evaluate("document.querySelector('#sunSlider').value=900;document.querySelector('#sunSlider').dispatchEvent(new Event('input'))")
    await pg.wait_for_timeout(500);await pg.screenshot(path=f'mobile_{tag}_sun.png');print(' sun',await pg.inner_text('#sunInfo'))
    print(' errors',errs);await ctx.close()
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch()
        await run(b,{'width':390,'height':844},'iphone',True);await run(b,{'width':1280,'height':800},'desktop',False);await b.close()
asyncio.run(main())
