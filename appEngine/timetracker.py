#!/usr/bin/env python

import os
import urllib
import json
import endpoints
import os
import json

from datetime import datetime, timedelta

from messages.checkInMessages import CheckInMessage, CheckInResponseMessage, CheckOutMessage, CheckOutResponseMessage, CheckInGetMessage
from messages.timetrackerlogin import LoginMessage, LoginMessageResponse
from messages.reportMessages import ReportMessage, ReportResponseMessage, jsonMessage

from google.appengine.api import users
from google.appengine.ext import ndb

from google.appengine.api.taskqueue import taskqueue
from google.appengine.ext import ndb
from protorpc import message_types
from protorpc import remote

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [END imports]

DEFAULT_GUESTBOOK_NAME = 'default_guestbook'

def guestbook_key(guestbook_name=DEFAULT_GUESTBOOK_NAME):
    """Constsructs a Datastore key for a Guestbook entity.

    We use guestbook_name as the key.
    """
    return ndb.Key('Guestbook', guestbook_name)

class Workday(ndb.Model):
    checkin = ndb.DateTimeProperty(indexed=True)
    checkout = ndb.DateTimeProperty(indexed=True)


class Employee(ndb.Model):
    name = ndb.StringProperty(indexed=True)
    email = ndb.StringProperty(indexed=True)
    role = ndb.StringProperty(indexed=True)
    workday = ndb.StructuredProperty(Workday, repeated=True)

employee = Employee()
# [START main_page]
@endpoints.api(name='timetracker', version='v1',
        allowed_client_ids=['678273591464-2donjmj0olnnsvmsp1308fd3ufl818dm.apps.googleusercontent.com'],
        scopes=[endpoints.EMAIL_SCOPE])

class MainPage(remote.Service):
    def set_checkin(self, date):
        query = Employee.query()
        query = query.filter(Employee.email == employee.email).get()
        workday = Workday(checkin=date, checkout=date+timedelta(hours=8))
        query.workday.append(workday)
        checkin = "me modifique"
        print checkin
        query.put()

    def set_checkout(self, date):
        query = Employee.query()
        query = query.filter(Employee.email == employee.email).get()
        # date2 = date + timedelta(hours=8)
        workday = Workday(checkout=date)
        query.workday.append(workday)
        query.put()

    def filter_checkin(self, date):
        query = Employee.query()
        query = query.filter(Employee.email == employee.email).get()
        for a in query.workday:
            if datetime(a.checkin.year,a.checkin.month,a.checkin.day) == datetime(date.year,date.month,date.day):
                return True
        return False

    @endpoints.method(CheckInMessage, CheckInResponseMessage,
    path = 'check_in', http_method = 'POST', name = 'check_in')
    def check_in(self, request):
        date = datetime.now()
        if self.filter_checkin(date):
            return CheckInResponseMessage(response_code = 500, response_status = "Solo se permite un checkin diario", response_date = date.strftime("%y%b%d%H:%M:%S"))
        else:
            if date.hour >= 7 and date.hour < 9:
                self.set_checkin(date)
                return CheckInResponseMessage(response_code = 200, response_status = "Check in correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
            elif date.hour == 9 and date.minute == 00:
                self.set_checkin(date)
                return CheckInResponseMessage(response_code = 200, response_status = "Check in correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
            elif date.hour < 7 or date.hour > 19:
                return CheckInResponseMessage(response_code = 406, response_status = "Check in fuera de hora", response_date = date.strftime("%y%b%d%H:%M:%S"))
            else:
                self.set_checkin(date)
                print checkin
                return CheckInResponseMessage(response_code = 202, response_status = "Check in correcto. Se ha generado un reporte", response_date = date.strftime("%y%b%d%H:%M:%S"))

    @endpoints.method(CheckOutMessage, CheckOutResponseMessage,
    path = 'check_out', http_method = 'POST', name = 'check_out')
    def check_out(self, request):
        date = datetime.now()
        if date.hour >= 14 and date.hour < 19:
            self.set_checkout(date)
            return CheckOutResponseMessage(response_code = 200, response_status = "Check out correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
        elif date.hour == 19 and date.minute == 00:
            self.set_checkout(date)
            return CheckOutResponseMessage(response_code = 200, response_status = "Check out correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
        elif date.hour < 7 or date.hour > 19:
            return CheckOutResponseMessage(response_code = 406, response_status = "Check out fuera de hora", response_date = date.strftime("%y%b%d%H:%M:%S"))
        else:
            self.set_checkout(date)
            return CheckOutResponseMessage(response_code = 202, response_status = "Check out correcto. Se ha generado un reporte", response_date = date.strftime("%y%b%d%H:%M:%S"))


    @endpoints.method(LoginMessage, LoginMessageResponse, path='login', http_method='POST', name='login')
    def login(self, request):
        current_user = endpoints.get_current_user()
        profile = Employee.query(Employee.email == current_user.email()).get()
        employee.name = request.name
        employee.email = current_user.email()
        if profile is None:
            profile = Employee()
            profile.name = request.name
            profile.email = current_user.email()
            profile.put()
            return LoginMessageResponse(response_code=200, email=profile.email, name=profile.name)
        else:
            return LoginMessageResponse(response_code=300, email=current_user.email(), name=request.name)

    @endpoints.method(CheckInMessage, CheckInGetMessage, path='getCheckin', http_method='GET', name='getCheckin')
    def getCheckin(self, request):
        query = Employee.query()
        query = query.filter(Employee.email == employee.email).get()
        for day in query.workday:
            if day.checkin.isocalendar()[2] == datetime.now().isocalendar()[2] and day.checkin.isocalendar()[1] == datetime.now().isocalendar()[1] and day.checkin.isocalendar()[0] == datetime.now().isocalendar()[0]:
                return CheckInGetMessage(response_date=str(day.checkin))
        return CheckInGetMessage(response_date="No hay fecha de checkin")




    # @endpoints.method(ReportMessage, ReportResponseMessage, path='report', http_method='GET', name='report')
    # def report(self, request):
    #     day = datetime.today()
    #     if datetime.today().isocalendar()[2] != 1:
    #         query = Employee.query().fetch()
    #         for currentEmployee in query:
    #             report = 
    #             report =  report + "name:" + currentEmployee.name
    #             report1 = report + self.singleReport(currentEmployee, day)
    #         return ReportResponseMessage(response_code=200, response_report=report)
    #     return ReportResponseMessage(response_code=502, response_report="no existe reporte")

    # def singleReport(self, employee, date):
    #     report = {}
    #     weekdays = ['twilday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    #     currentDay = date.today()
    #     currentWeek = currentDay.isocalendar()[1]
    #     for day in employee.workday:
    #         if day.checkin.isocalendar()[1] == currentWeek:
    #             dayWorkTime = day.checkout.hour - day.checkin.hour
    #             print weekdays[day.checkin.isocalendar()[2]]
    #             #cogemos el dia de la semana del isocalendar que va de 1 a 7
    #             report =({weekdays[day.checkin.isocalendar()[2]]: dayWorkTime})
    #     return json.dumps(report, dayWorkTime)
                
                
                
                


           

# [END guestbook] dayWorkTime = day.check_out - day.check_in

application = endpoints.api_server([MainPage], restricted=False)
