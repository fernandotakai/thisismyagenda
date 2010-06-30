import tornado.web
import tornado.wsgi
import tornado.escape
import wsgiref.handlers
import os

from google.appengine.api import users
from google.appengine.ext import db

import models

from datetime import datetime

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
        self.render("create.html")

    @tornado.web.authenticated
    def post(self):
        description = self.get_argument("description")
        due_on_string = self.get_argument("due_on_string")

        due_on = datetime.strptime(due_on_string, "%Y-%m-%d - %H:%M:%S")
        
        task = models.Task(description=description, due_on=due_on)
        task.put()

        self.redirect("/")

class EditTaskHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, key):
        task = models.Task.get(key)

        if not task:
            raise tornado.web.HTTPError(404)

        self.render('edit.html', task=task)

    @tornado.web.authenticated
    def post(self, key):
        key = self.get_argument("key")
        description = self.get_argument("description")
        due_on_string = self.get_argument("due_on_string")
        due_on = datetime.strptime(due_on_string, "%Y-%m-%d - %H:%M:%S")
        
        task = models.Task.get(key)

        if not task:
            raise tornado.web.HTTPError(404)

        task.description = description
        task.due_on = due_on

        task.put()

        self.redirect('/')

settings = {
    "template_path": os.path.join(os.path.dirname(__file__), "templates"),
    "static_path": os.path.join(os.path.dirname(__file__), "static")
}

application = tornado.wsgi.WSGIApplication([
    (r"/", IndexHandler),
    (r"/create/?", CreateTaskHandler),
    (r"/list/?", ListTasksHandler),
    (r"/edit/([^/]+)/?", EditTaskHandler),
], **settings)

def main():
    wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
    main()
