import logging
import requests
import webapp2

from bs4 import BeautifulSoup
from datetime import (datetime, timedelta)
from models import Watcher
from google.appengine.api import (mail, taskqueue)


class CronHandler(webapp2.RequestHandler):

    def check(self):
        """Submits a taskqueue job for active watchers."""
        watchers = Watcher.gql('WHERE active = TRUE').fetch()
        for w in watchers:
            if w.class_num is None or w.email is None or w.strm is None:
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
        content = _fetch(watcher.class_num, watcher.strm)
        soup = BeautifulSoup(content)
        course = _parse_course(soup, watcher.class_num)
        if not course:
            logging.warning('Invalid course number: %s' % watcher.class_num)
            _disable_watcher(watcher)
            return
        if course.get('Status') != 'Open':
            logging.info('Course closed. wid=%d' % wid)
            return
        logging.info('Course open. wid=%d' % wid)
        _notify(watcher, course)
        _disable_watcher(watcher)


def _fetch(class_num, strm):
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


def _parse_course(soup, class_num):
    """The HTML hierchy is as following:
        <div id='table'>
            <table>
                <tr>
                    <th>status
                    <th>course_id
                    ...
                <tr>
                    <td>
                    ...
    """
    for tr in soup.select('#table > table > tr'):
        class_num_td = tr.select('.ClassNumber')
        class_num_td = class_num_td[0] if len(class_num_td) == 1 else None
        if (class_num_td and class_num_td.text.isdigit()
                and int(class_num_td.text) == class_num):
            return {td['class'][0]: td.text for td in tr.select('td')}


def _notify(watcher, course):
    date = '{:%m/%d/%Y %I:%M %p}'.format(_centralnow())
    course_name = course.get('CourseID', '(Oops)')
    message = _email_tmpl().format(date, course)
    mail.send_mail(sender='UArk Schedule Watcher <bekt17@gmail.com>',
                   to=watcher.email,
                   subject='Course Open: %s' % course_name,
                   body=message)


def _centralnow():
    return datetime.utcnow() - timedelta(hours=6)


def _email_tmpl():
    msg = """
Hey, you are receiving this email because you signed up at bekt.net.

Just a heads up that as of {}, {} is now OPEN.

Cheers!"""
    return msg
