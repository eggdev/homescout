"""Prototype browser check. Not collected by pytest.

Requires Playwright and a built HTML file:
  python -m app.build_mobile --source csv
  python app/manual/test_app.py
Override the file with HOMESCOUT_APP_FILE.
"""
import os
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_default = _ROOT / "dist" / "westchester_homes.html"
U = Path(os.environ.get("HOMESCOUT_APP_FILE", _default)).resolve().as_uri()

import asyncio,time
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(); pg=await b.new_page(viewport={'width':1400,'height':900})
        errs=[];pg.on('pageerror',lambda e:errs.append(str(e)))
        t=time.time();await pg.goto(U);await pg.wait_for_function('window.__ready',timeout=60000)
        print('load s',round(time.time()-t,2),'count',await pg.inner_text('#cnt'),'median',await pg.inner_text('#med'))
        # town filter: Scarsdale
        d=pg.locator('details.f',has_text='Town / city');await d.locator('summary').click();await d.locator('input[value="Scarsdale"]').check()
        print('scarsdale',await pg.inner_text('#cnt'))
        d=pg.locator('details.f',has_text='Senior owner signal');await d.locator('summary').click();await d.locator('input[value="Yes – senior exemption"]').check()
        print('+senior',await pg.inner_text('#cnt'),'apply ms',await pg.evaluate('window.__lastApplyMs'))
        d=pg.locator('details.f',has_text='Living area');await d.locator('summary').click();await d.locator('input[type=number]').nth(0).fill('3000');await d.locator('input[type=number]').nth(0).dispatch_event('change')
        print('+3000sqft',await pg.inner_text('#cnt'))
        await d.locator('.u').uncheck();print('-unknown',await pg.inner_text('#cnt'))
        h=await pg.evaluate('location.hash');pg2=await b.new_page();await pg2.goto(U+h);await pg2.wait_for_function('window.__ready');print('hash restore',await pg2.inner_text('#cnt'))
        await pg.locator('#tb tr').first.click();await pg.wait_for_timeout(1500);print('card',(await pg.inner_text('#card'))[:80].replace('\n',' | '))
        await pg.screenshot(path='screenshot.png')
        await pg.click('#reset');print('reset',await pg.inner_text('#cnt'))
        d=pg.locator('details.f',has_text='Include homes estimated');await d.locator('input').check();print('incl low',await pg.inner_text('#cnt'))
        async with pg.expect_download() as dl: await pg.click('#exp')
        f=await (await dl.value).path();print('csv lines',sum(1 for _ in open(f)))
        print('errors',errs);await b.close()
asyncio.run(main())
