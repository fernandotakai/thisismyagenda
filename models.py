from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import db

import uuid
from datetime import datetime
import pytz

import logging

ATTR_DOES_NOT_EXIST="__ATTR_DOES_NOT_EXIST__"

class Model(db.Model):
     def from_form(self, form):
         for key, value in form._fields.items():
             if getattr(self, key, ATTR_DOES_NOT_EXIST) != ATTR_DOES_NOT_EXIST:
                 setattr(self, key, value.data)

class Task(Model):
     description = db.StringProperty()
     due_on = db.DateTimeProperty()
     created_on = db.DateTimeProperty(auto_now_add=True)
     user = db.UserProperty(auto_current_user_add=True)
     finished = db.BooleanProperty(default=False)

     @staticmethod
     def tasks_by_user(user=None):
         if user is None:
             user = users.get_current_user()
         elif isinstance(user, (str, unicode)):
             user = users.User(user)

         return Task.gql('where user = :1 and finished = False', user) 

     @staticmethod
     def tasks_by_user_today(user=None):
         if user is None:
             user = users.get_current_user()
         elif isinstance(user, (str, unicode)):
             user = users.User(user)

         d = datetime.now()
         d1 = datetime(d.year, d.month, d.day, 00, 00, 01)
         d2 = datetime(d.year, d.month, d.day, 23, 59, 59)

         return Task.gql('where user = :1 and due_on >= :2 and due_on <= :3 and finished = False', user, d1, d2).fetch(10)

     @staticmethod
     def tasks_due():
         gql = "where finished = False and due_on <= :1"
         return Task.gql(gql, datetime.now())

     def show_due_on(self, tz):
         return self.due_on.replace(tzinfo=pytz.utc).astimezone(tz).strftime("%F - %T - %Z")

class UserSettings(Model):
    user = db.UserProperty(auto_current_user_add=True)
    api_key = db.StringProperty()
    verified = db.BooleanProperty(default=False)
    timezone = db.StringProperty()

    @staticmethod
    def get_or_create(user=None):
        if user is None:
            user = users.get_current_user()
        elif isinstance(user, (str, unicode)):
            user = users.User(user)

        settings = memcache.get("settings_%s" % user.email()) or None

        if not settings:
            settings = UserSettings.gql('where user = :1', user).get()

            if not settings:
                settings = UserSettings(user=user)
                settings.xmpp_address = user.email()
                settings.api_key = uuid.uuid1().hex
                settings.timezone = "UTC"
                settings.put()

            memcache.set("settings_%s" % user.email(), settings)

        return settings

    def get_timezone(self):
        return pytz.timezone(self.timezone)
