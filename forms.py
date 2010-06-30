from wtforms import Form, BooleanField, TextField, validators
from wtforms import widgets
from wtforms.fields import Field
from django.utils.datastructures import MultiValueDict

import re

from dateutil import parser

def sanitize_parameter_value(value, strip=True):
    value = re.sub(r"[\x00-\x08\x0e-\x1f]", " ", value)
    value = value.decode("utf-8")
    if strip: value = value.strip()
    return value

class DateTimeField(Field):
    widget = widgets.TextInput()

    def __init__(self, label=u'', validators=None, format='%Y-%m-%d %H:%M:%S', **kwargs):
        super(DateTimeField, self).__init__(label, validators, **kwargs)
        self.format = format

    def _value(self):
        if self.raw_data:
            return u' '.join(self.raw_data)
        else:
            return self.data and self.data.strftime(self.format) or u''

    def process_formdata(self, valuelist):
        if valuelist:
            date_str = u' '.join(valuelist)
            try:
                self.data = parser.parse(date_str, fuzzy=True)
            except ValueError:
                self.data = None
                raise

class TornadoForm(Form):
  def __init__(self, request=None, obj=None, prefix='', formdata=None, **kwargs):
    if request:
      if isinstance(request, dict):
        arguments = request
      else:
        arguments = request.arguments
      formdata = MultiValueDict()
      for name, values in arguments.items():
        formdata.setlist(name, [sanitize_parameter_value(v) for v in values])
    Form.__init__(self, formdata, obj=obj, prefix=prefix, **kwargs)

class CreateTaskForm(TornadoForm):
    description = TextField("Description", validators=[validators.Required(), validators.Length(min=1, max=1024)])
    due_on = DateTimeField("Due on", validators=[validators.Required()])

class SettingsForm(TornadoForm):
    xmpp_enabled = BooleanField("XMPP?", validators=[validators.Required()], default=True)
    xmpp_address = TextField("Address", validators=[])
    email_enabled = BooleanField("Email?", validators=[], default=True)
