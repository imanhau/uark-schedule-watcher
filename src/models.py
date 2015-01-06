from google.appengine.ext import ndb


class Watcher(ndb.Model):
    email = ndb.StringProperty(indexed=False)
    class_num = ndb.IntegerProperty(indexed=False)
    active = ndb.BooleanProperty(default=True)
    strm = ndb.IntegerProperty(indexed=False)
    created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
