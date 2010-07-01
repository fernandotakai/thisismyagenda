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
import pytz

import logging

XMPP_MESSAGE="""Hi!,
Your task '%s' should be done now! (%s)
"""

EMAIL_MESSAGE="""Hi!,
Your task %s should be done now! (%s)

Best regards,

This is your agenda.
"""

XMPP_HELP = """this is my help.
/list - list all your tasks
/verify [api] - verifies this account for xmpp commands
/delete [key] - deletes a task
/help - shows this help
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
        tasks = models.Task.tasks_by_user_today()
        
        if tasks.count(1) == 0:
            self.redirect("/list")
            return

        settings = models.UserSettings.get_or_create(self.current_user.email())
        self.render("index.html", tasks=tasks, tz=settings.get_timezone())

class ListTasksHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        settings = models.UserSettings.get_or_create(self.current_user.email())
        self.render("list.html", tasks=models.Task.tasks_by_user(), tz=settings.get_timezone())

class CreateTaskHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("create.html", form=forms.CreateTaskForm())

    @tornado.web.authenticated
    def post(self):
        form = forms.CreateTaskForm(self.request)

        if form.validate():
            settings = models.UserSettings.get_or_create(self.current_user.email())
            user_tz = settings.get_timezone()

            task = models.Task()
            form.populate_obj(task)

            task.due_on = task.due_on.replace(tzinfo=user_tz).astimezone(pytz.utc)

            task.put()

            self.redirect("/")
        else:
            self.render("create.html", form=forms.CreateTaskForm())

class EditTaskHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, key):
        settings = models.UserSettings.get_or_create(self.current_user.email())
        task = models.Task.get(key)

        if not task:
            raise tornado.web.HTTPError(404)

        task.due_on = task.due_on.replace(tzinfo=pytz.utc).astimezone(settings.get_timezone())
        form = forms.CreateTaskForm(self.request, task)

        self.render('edit.html', form=form, task=task)

    @tornado.web.authenticated
    def post(self, key):
        settings = models.UserSettings.get_or_create(self.current_user.email())
        task = models.Task.get(key)
        form = forms.CreateTaskForm(self.request)

        if not task:
            raise tornado.web.HTTPError(404)

        if task.user != self.current_user:
            raise tornado.web.HTTPError(403)

        if form.validate():
            form.populate_obj(task)
            task.due_on = task.due_on.replace(tzinfo=settings.get_timezone()).astimezone(pytz.utc)
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
            settings = models.UserSettings.get_or_create(task.user.email())
            tz = settings.get_timezone()

            if xmpp.get_presence(task.user.email()):
                xmpp.send_message(task.user.email(), XMPP_MESSAGE % (task.description, task.show_due_on(tz)))
            else:
                mail.send_mail('fernando.takai@gmail.com', task.user.email(),
                                 'Task due', EMAIL_MESSAGE % (task.description, task.show_due_on(tz)))

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

    def help(self, to):
        xmpp.send_message(to, XMPP_HELP)

    def list(self, email, when=None):
        settings = models.UserSettings.get_or_create(email)
        tz = settings.get_timezone()
        tasks = ""

        for task in models.Task.tasks_by_user(email):
            tasks += "*%s due on %s (%s) \n\n" % (task.description, task.show_due_on(tz), task.key())

        if len(tasks) == 0:
            tasks = "You have no tasks. Go procrastinate!"

        xmpp.send_message(email, tasks)

    def delete(self, email, key):
        task = models.Task.get(key)
        
        if not task or task.user.email() != email:
            xmpp.send_message(email, "Sorry, could not find that task... try a /list first")
            return

        task.delete()

        xmpp.send_message(email, "Task deleted!")

    def verify(self, email, api_key):
        settings = models.UserSettings.get_or_create(email)
        message = "Sorry, could not validate your key... Go to http://thisismyagenda.appspot.com/settings and make sure it's correct"

        if settings.api_key == api_key:
            settings.verified = True
            message = "Hurray! Validated!"
            settings.put()

        xmpp.send_message(email, message)

    def validate_user(self, email):
        settings = models.UserSettings.get_or_create(email)
        return settings.verified

    def post(self):
        _from = self.get_argument("from")
        body = self.get_argument("body")

        # from must be client@address/resource
        if "/" in _from:
            _from = _from.split("/", 1)[0]

        try:
            body += " "
            command, value = body.split(" ", 1)
        except Exception, e:
            logging.exception("error while parsing xmpp body from %s" % _from)
            self.help(_from)
            return

        if not command.startswith("/"):
            logging.error("Command does not start with /")
            self.help(_from)
            return

        if command != "/verify" and not self.validate_user(_from):
            xmpp.send_message(_from, """Sorry, you didn't validated your email. 
Can you go to http://thisismyagenda.appspot.com/settings, get your api key
and issue a /verify api-key, so you can use me? thx.""")
            return

        cmd = getattr(self, command[1:], None)

        if not cmd:
            self.help(_from)
            return

        try:
            if len(value) > 0:
                cmd(_from, *filter(lambda v: len(v) > 1, value.split(" ")))
            else:
                cmd(_from)
        except (ValueError, TypeError):
            logging.exception('Could not execute command %s' % command)
            self.help(_from)

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
