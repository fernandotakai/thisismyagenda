from google.appengine.api import users
from google.appengine.ext import db

from datetime import datetime

import logging

class Task(db.Model):
     description = db.StringProperty()
     due_on = db.DateTimeProperty()
     created_on = db.DateTimeProperty(auto_now_add=True)
     user = db.UserProperty(auto_current_user_add=True)


     @staticmethod
     def tasks_by_user(user=None):
         if user is None:
             user = users.get_current_user()

         return Task.gql('where user = :1', user) 

     @staticmethod
     def tasks_by_user_today(user=None):
         if user is None:
             user = users.get_current_user()

         d = datetime.now()
         d1 = datetime(d.year, d.month, d.day, 00, 00, 01)
         d2 = datetime(d.year, d.month, d.day, 23, 59, 59)

         return Task.gql('where user = :1 and due_on >= :2 and due_on <= :3', user, d1, d2).fetch(10)
