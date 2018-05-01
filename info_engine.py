# --*-- coding: utf-8 --*--

import os
import sys

from utils.log import NOTICE, log, ERROR, RECORD

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.append(BASE_DIR)

import time
from config import CELERY_BROKER, CELERY_BACKEND, CRAWL_INTERVAL
from db_access import *
from utils.blacklist import blacklist_site, blacklist_company
from utils.content_process import complement_url, check_content
from utils.diff import diff_file
from utils.html_downloader import crawl
from bs4 import BeautifulSoup
from celery import Celery


celery_app = Celery('info_engine', broker=CELERY_BROKER, backend=CELERY_BACKEND)
celery_app.conf.update(CELERY_TASK_RESULT_EXPIRES=3600)

websites = get_websites()

print(websites)

@celery_app.task
def extract(w_id):
    old_html_content = ''
    try:
        # 从数据库取
        currentWebsite = get_website(w_id)

        # 抓取到的内容
        websiteContents = crawl(currentWebsite.url)

        if not websiteContents:
            log(NOTICE, "#{id} {name} {site} 没有取得新内容".format(id=currentWebsite.company.id, name=currentWebsite.company.name_cn.encode('utf-8').strip(), site=currentWebsite.url))
            return


        # 数据库里的内容
        if currentWebsite.html_content:
            old_html_content = currentWebsite.html_content.content

            # 抓取到的内容和旧内容进行对比
            diff_text = diff_file(old_html_content, websiteContents)

            if not diff_text:
                log(NOTICE, "#{id} {name} {site} 没有不同，不会执行了".format(id=currentWebsite.company.id,
                                                                    name=currentWebsite.company.name_cn.encode(
                                                                        'utf-8').strip(), site=currentWebsite.url))
                return
            else:
                parseAndSave(diff_text,currentWebsite)


        else:
            save_html_content(currentWebsite.id, websiteContents)
            log(NOTICE, "#{id} {name} {site} 保存成功".format(id=currentWebsite.company.id, name=currentWebsite.company.name_cn.encode('utf-8').strip(), site=currentWebsite.url))
            # return
            parseAndSave(websiteContents,currentWebsite)

    except Exception as e:
        print(e)
        try:
            currentWebsite = get_website(w_id)
            print(currentWebsite)

            log(ERROR, "#{id} {name} {site} {err}".format(id=currentWebsite.id, name=currentWebsite.company.name_cn.encode('utf-8').strip(), site=currentWebsite.url, err=str(e)))
        except Exception as e:
            log(ERROR, str(e))



def parseAndSave(content,currentWebsite):
    # save_html_content(currentWebsite.id, websiteContents)

    soup = BeautifulSoup(content, 'lxml')

    items = soup.find_all('a')

    print("A Items", len(items))

    COUNT = 0

    if items:
        for a in items:
            if a.string:
                url, text = a.get('href'), a.string.encode('utf-8').strip()

                check_pass = check_content(url, text)

                if check_pass:
                    url = complement_url(url, currentWebsite.url)
                    if url:
                        result = save_info_feed(url, text, currentWebsite.id, currentWebsite.company.id)
                        if result:
                            COUNT += 1

    if COUNT == 0:
        log(NOTICE, "#{id} {name} {site} 没抓到更新 {count} 条".format(id=currentWebsite.company.id,
                                                                 name=currentWebsite.company.name_cn.encode(
                                                                     'utf-8').strip(), site=currentWebsite.url,
                                                                 count=COUNT))
    else:
        log(RECORD, "#{id} {name} {site} 抓到更新 {count} 条".format(id=currentWebsite.company.id,
                                                                name=currentWebsite.company.name_cn.encode(
                                                                    'utf-8').strip(), site=currentWebsite.url,
                                                                count=COUNT))


def crawalAndSave():
    for w in websites[:]:
        if (w.url not in blacklist_site) and (w.company.name_cn not in blacklist_company):
            # extract.delay(w.id)
            extract(w.id)

if __name__ == '__main__':
    while True:
        crawalAndSave()
        # 60 *
        time.sleep(3*CRAWL_INTERVAL)
        websites = get_websites()

