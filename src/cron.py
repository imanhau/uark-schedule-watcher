import logging
import requests
import webapp2

from bs4 import BeautifulSoup
from datetime import (datetime, timedelta)
from models import Watcher
from google.appengine.api import (mail, taskqueue)


# From: https://scheduleofclasses.uark.edu/
STRM = 1153


class CronHandler(webapp2.RequestHandler):

    def check(self):
        """Submits a taskqueue job for active watchers."""
        watchers = Watcher.gql('WHERE active = TRUE').fetch()
        for w in watchers:
            if w.class_num is None or w.email is None:
                _disable_watcher(w)
            else:
                taskqueue.add(url='/cron/process', params={'wid': w.key.id()})

    def process(self):
        """Fetches class schedules and notifies if course status is open."""
        wid = int(self.request.get('wid', 1))
        watcher = Watcher.get_by_id(wid)
        if watcher is None or watcher.active is False:
            logging.warning('Invalid watcher. wid=%d' % wid)
            return
        content = _fetch(watcher.class_num)
        soup = BeautifulSoup(content)
        if not _is_course_valid(soup):
            logging.warning('Invalid course number: %s' % watcher.class_num)
            _disable_watcher(watcher)
            return
        if not _is_course_open(soup):
            logging.info('Course closed. wid=%d' % wid)
            return
        logging.info('Course open. wid=%d' % wid)
        _notify(watcher, soup)
        _disable_watcher(watcher)


def _fetch(class_num, strm=STRM):
    url = 'https://scheduleofclasses.uark.edu/Main?strm=' + str(strm)
    payload = {
        'campus': 'FAY',
        'class_nbr': class_num,
        'Search': 'Search',
    }
    r = requests.post(url, data=payload)
    r.raise_for_status()
    return r.text


def _disable_watcher(watcher):
    watcher.active = False
    watcher.put()


def _is_course_valid(soup):
    tr = _select_tr(soup)
    return len(tr) == 2


def _is_course_open(soup):
    tr = _select_tr(soup)
    td = tr[1].select('.Status')
    return len(td) == 1 and td[0].text == 'Open'


def _select_tr(soup):
    return soup.select('#table > table > tr')


def _notify(watcher, soup):
    tr = _select_tr(soup)
    course = tr[1].select('.CourseID')[0].text
    date = '{:%m/%d/%Y %I:%M %p}'.format(_centralnow())
    message = """
    Hey, you are receiving this email because you signed up at bekt.net.

    Just a heads up that as of {}, {} is now OPEN.

    Cheers!
    """.format(date, course)
    mail.send_mail(sender='UArk Schedule Watcher <bekt17@gmail.com>',
                   to=watcher.email,
                   subject='Course Open: %s' % course,
                   body=message)


def _centralnow():
    return datetime.utcnow() - timedelta(hours=6)
