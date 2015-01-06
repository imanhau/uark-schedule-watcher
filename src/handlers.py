import webapp2

app = webapp2.WSGIApplication([
    webapp2.Route(r'/cron/check', name='cron_check', methods=['GET'],
                  handler='cron.CronHandler:check'),
    webapp2.Route(r'/cron/process', name='cron_process', methods=['POST'],
                  handler='cron.CronHandler:process'),
])
