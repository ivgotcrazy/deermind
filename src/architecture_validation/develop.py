"""Bounded B2 real integration run; development examples only."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from .common import BASE, write_json, now
from .harness import Server


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();path=BASE/'runs'/a.run
    if path.exists():raise SystemExit('Refusing to overwrite a development run')
    results=[]
    with Server(path,'real') as srv,sync_playwright() as pw:
        browser=pw.chromium.launch();q=srv.task();page=srv.page(browser,'development',q)
        texts=['42÷6＝8，8×15＝120。请只指出要检查哪一步，不要给答案。','我重算42÷6＝7，7×15＝105。除法是我自己重新算的。']
        for n,text in enumerate(texts,1):
            t=srv.submit('development',text,q,str(n));r=srv.settled('development',t['id'],300);results.append(r)
            print({'turn':n,'status':r['status'],'error':r['error']},flush=True)
            if r['status']!='COMPLETED':break
        page.screenshot(path=str(path/'browser.png'),full_page=True)
        write_json(path/'dom.json',{'text':page.locator('#conversation').inner_text(),'rendered':page.evaluate('window.buildTest.rendered')})
        srv.export();browser.close()
    write_json(BASE/'reports'/f'{a.run}.json',{'created':now(),'run_dir':str(path.relative_to(BASE)),'turns':results})


if __name__=='__main__':main()
