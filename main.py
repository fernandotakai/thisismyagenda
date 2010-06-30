import tornado.web
import tornado.wsgi
import tornado.escape
import wsgiref.handlers
import os

from google.appengine.api import users
from google.appengine.api import mail
from google.appengine.api import xmpp

import models
import forms

from dateutil.parser import *

import logging

XMPP_MESSAGE="""Hi!,
Your task '%s' should be done now! (%s)
"""

EMAIL_MESSAGE="""Hi!,
Your task %s should be done now! (%s)

Best regards,

This is your agenda.
"""

class BaseHandler(tornado.web.RequestHandler):
    """Implements Google Accounts authentication methods."""
    def get_current_user(self):
        user = users.get_current_user()
        if user: user.administrator = users.is_current_user_admin()
        return user

    def get_login_url(self):
        return users.create_login_url(self.request.uri)

    def render_string(self, template_name, **kwargs):
        # Let the templates access the users module to generate login URLs
        return tornado.web.RequestHandler.render_string(
            self, template_name, users=users, **kwargs)

class IndexHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("index.html", tasks=models.Task.tasks_by_user_today())

class ListTasksHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("list.html", tasks=models.Task.tasks_by_user())

class CreateTaskHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("create.html", form=forms.CreateTaskForm())

    @tornado.web.authenticated
    def post(self):
        form = forms.CreateTaskForm(self.request)

        if form.validate():
            task = models.Task()
            form.populate_obj(task)
            task.put()

            self.redirect("/")
        else:
            self.render("create.html", form=forms.CreateTaskForm())

class EditTaskHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, key):
        task = models.Task.get(key)

        if not task:
            raise tornado.web.HTTPError(404)

        form = forms.CreateTaskForm(self.request, task)

        self.render('edit.html', form=form, task=task)

    @tornado.web.authenticated
    def post(self, key):
        task = models.Task.get(key)
        form = forms.CreateTaskForm(self.request)

        if not task:
            raise tornado.web.HTTPError(404)

        if task.user != self.current_user:
            raise tornado.web.HTTPError(403)

        if form.validate():
            form.populate_obj(task)
            task.put()
            self.redirect('/')
        else:
            self.render("edit.html", form=form, task=task)

class DeleteTaskHandler(BaseHandler):

    @tornado.web.authenticated
    def post(self, key):
        task = models.Task.get(key)

        if not task:
            raise tornado.web.HTTPError(404)

        if task.user != self.current_user:
            raise tornado.web.HTTPError(403)

        task.delete()

        self.write(dict(result="ok"))

class VerifyTasksHandler(tornado.web.RequestHandler):
    def get(self):
        for task in models.Task.tasks_due():
            if xmpp.get_presence(task.user.email()):
                xmpp.send_message(task.user.email(), XMPP_MESSAGE % (task.description, task.due_on))
            else:
                mail.send_mail('fernando.takai@gmail.com', task.user.email(),
                                 'Task due', EMAIL_MESSAGE % (task.description, task.due_on))

            task.finished = True
            task.put()

class SettingsHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        settings = models.UserSettings.get_or_create()
        form = forms.SettingsForm(self.request, settings)
        self.render("settings.html", settings=settings, form=form)

    @tornado.web.authenticated
    def post(self):
        form = forms.SettingsForm(self.request)
        settings = models.UserSettings.get_or_create()

        if form.validate():
            form.populate_obj(settings)
            settings.put()
            self.redirect("/")
        else:
            self.render("settings.html", settings=settings, form=form)

class DatePreviewHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        date = self.get_argument("date")
        date_obj = parse(date, fuzzy=True)

        self.write(dict(date=date_obj.strftime("%Y-%m-%d - %H:%M:%S")))

class XMPPHandler(tornado.web.RequestHandler):

    def list_tasks(self, email):
        tasks = ""

        for task in models.Task.tasks_by_user(email):
            logging.error(task)
            tasks += "* Task: %s due on %s\n" % (task.description, task.due_on.strftime("%F - %T"))

        if len(tasks) == 0:
            tasks = "You have no tasks. Go procrastinate!"

        xmpp.send_message(email, tasks)

    def post(self):
        _from = self.get_argument("from")
        body = self.get_argument("body")

        # from must be client@address/resource
        if "/" in _from:
            _from = _from.split("/", 1)[0]

        if body.startswith("/list"):
            self.list_tasks(_from)

settings = {
    "template_path": os.path.join(os.path.dirname(__file__), "templates"),
}

application = tornado.wsgi.WSGIApplication([
    (r"/", IndexHandler),
    (r"/create/?", CreateTaskHandler),
    (r"/list/?", ListTasksHandler),
    (r"/edit/([^/]+)/?", EditTaskHandler),
    (r"/delete/([^/]+)/?", DeleteTaskHandler),
    (r"/_ah/xmpp/message/chat/", XMPPHandler),
    (r"/tasks/verify/?", VerifyTasksHandler),
    (r"/tasks/date/?", DatePreviewHandler),
    (r"/settings", SettingsHandler),
], **settings)

def main():
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()
