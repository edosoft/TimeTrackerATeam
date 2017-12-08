#!/usr/bin/env python

import urllib
import endpoints
import os
import json
from protorpc import messages

from datetime import datetime, timedelta

from messages.checkInMessages import CheckInMessage, CheckInResponseMessage, CheckOutMessage, CheckOutResponseMessage, CheckResponse
from messages.timetrackerlogin import LoginMessage, LoginMessageResponse
from messages.reportMessages import ReportMessage, ReportResponseMessage, JsonMessage
from messages.DateNowMessages import DateNowMessage, DateNowGetMessage
from messages.reportMonthlyMessages import ReportMonthlyMessage, ReportMonthlyResponseMessage, JsonMonthlyMessage, JsonSingleDayMessage
from messages.incidencesMessages import CheckIncidenceMessage, CheckIncidenceResponse, IncidencesReportMessage, IncidencesMessage, IncidencesReportResponseMessage
from messages.incidencesUsersListMessages import IncidencesUsersMessage, incidencesUsersListMessage, IncidencesUserListResponseMessage, JsonEmployee, EmployeeMessage, EmployeeMessageResponse

from google.appengine.api import users
from google.appengine.ext import ndb

from google.appengine.api.taskqueue import taskqueue
from protorpc import message_types
from protorpc import remote

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)
# [END imports]

class Employee(ndb.Model):
    name = ndb.StringProperty(indexed=True)
    email = ndb.StringProperty(indexed=True)
    image = ndb.StringProperty(indexed=False)
    role = ndb.IntegerProperty(indexed=True)
    status = ndb.BooleanProperty(indexed=True)

class Workday(ndb.Model):
    checkin = ndb.DateTimeProperty(indexed=True)
    checkout = ndb.DateTimeProperty(indexed=True)
    employee = ndb.StructuredProperty(Employee, indexed=True)

class Incidences(ndb.Model):
    message = ndb.StringProperty(indexed=True)
    incidenceDate = ndb.DateTimeProperty(indexed=True)
    employee = ndb.StructuredProperty(Employee, indexed=True)
    check = ndb.BooleanProperty(indexed=True)

# [START main_page]
@endpoints.api(name='timetracker', version='v1',
        allowed_client_ids=['678273591464-2donjmj0olnnsvmsp1308fd3ufl818dm.apps.googleusercontent.com'],
        scopes=[endpoints.EMAIL_SCOPE])

class MainPage(remote.Service):

    def set_checkin(self, date, email):
        query = Employee.query()
        query = query.filter(Employee.email == email).get()
        workday = Workday (
            checkin=date,
            employee=Employee (name=query.name,email=query.email,role=query.role)
        )
        workday.put()

    def set_checkout(self, date, email):
        query = Workday.query()
        query = query.filter(Workday.employee.email == email)
        query = query.filter(Workday.checkout == None).get()
        query.checkout = date
        query.put()

    def filter_checkin(self, date, email):
        query = Workday.query()
        if query is None:
            return False
        else:
            query = query.filter(Workday.employee.email == email).fetch()
            for workday in query:
                if datetime(workday.checkin.year, workday.checkin.month, workday.checkin.day) == datetime(date.year, date.month, date.day):
                    return True
            return False

    def singleReport(self, currentEmployee, date):
        print "Estoy dentro de singleReport"
        report = JsonMessage()
        currentDay = date
        currentWeek = currentDay.isocalendar()[1]
        query = Workday.query()
        query = query.filter(Workday.employee.email == currentEmployee.email).fetch()
        report.name = currentEmployee.name
        report.monday = 0
        report.tuesday = 0
        report.wednesday = 0
        report.thursday = 0
        report.friday = 0
        monday = 0
        tuesday = 0
        wednesday = 0
        thursday = 0
        friday = 0

        for worked in query:
            if worked.checkin.isocalendar()[0] == date.year and worked.checkin.isocalendar()[1] == currentWeek and worked.checkout != None:
                if worked.checkin.isocalendar()[2] == 1:
                    monday = int((worked.checkout - worked.checkin).total_seconds())/60
                    report.monday = monday/60
                elif worked.checkin.isocalendar()[2] == 2:
                    tuesday = int((worked.checkout - worked.checkin).total_seconds())/60
                    report.tuesday = tuesday/60
                elif worked.checkin.isocalendar()[2] == 3:
                    wednesday = int((worked.checkout - worked.checkin).total_seconds())/60
                    report.wednesday = wednesday/60
                elif worked.checkin.isocalendar()[2] == 4:
                    thursday = int((worked.checkout - worked.checkin).total_seconds())/60
                    report.thursday = thursday/60
                elif worked.checkin.isocalendar()[2] == 5:
                    friday = int((worked.checkout - worked.checkin).total_seconds())/60
                    report.friday = friday/60
        total = monday + tuesday + wednesday + thursday + friday
        report.total = '{:02d}:{:02d}'.format(*divmod(total, 60))
        print "Este es el total", total
        return report

    def singleMonthlyReport(self, currentEmployee, date):
        reportMonth = JsonMonthlyMessage()
        currentmonth = date.month - 1
        query = Workday.query()
        query = query.filter(Workday.employee.email == currentEmployee.email).fetch()
        reportMonth.hours_day = []
        reportMonth.name = currentEmployee.name
        reportMonth.month = int(currentmonth)
        reportMonth.jornadas = 0
        reportMonth.total = 0
        if(currentmonth == 1): reportMonth.year = date.year - 1
        else: reportMonth.year = date.year

        for worked in query:
            reportDay = JsonSingleDayMessage()
            if worked.checkin.isocalendar()[0] == date.year and worked.checkin.month == currentmonth and worked.checkout != None:
                reportDay.hour = int((worked.checkout - worked.checkin).total_seconds())/3600
                reportDay.day = worked.checkin.day
                reportMonth.hours_day.append(reportDay)
                reportMonth.jornadas = reportMonth.jornadas + 1
                reportMonth.total = reportMonth.total+reportDay.hour


        return reportMonth

    def set_incidences(self, message, date, email, check):
        query = Employee.query()
        query = query.filter(Employee.email == email).get()
        finalMessage = query.name + message
        incidences = Incidences (
            message= finalMessage,
            incidenceDate=date,
            employee=Employee (name=query.name,email=query.email,role=query.role,image=query.image),
            check=check
        )
        incidences.put()

    def incidencesList(self, oneIncidence):
        incidence = IncidencesMessage()
        incidence.date = str(oneIncidence.incidenceDate)
        incidence.message = oneIncidence.message
        return incidence

    @endpoints.method(CheckInMessage, CheckInResponseMessage,
    path = 'check_in', http_method = 'POST', name = 'check_in')
    def check_in(self, request):
        date = datetime.now()
        if self.filter_checkin(date, request.email):
            return CheckInResponseMessage(response_code = 500, response_status = "Solo se permite un checkin diario", response_date = date.strftime("%y%b%d%H:%M:%S"))
        else:
            if date.hour >= 7 and date.hour < 9:
                self.set_checkin(date, request.email)
                return CheckInResponseMessage(response_code = 200, response_status = "Check in correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
            elif date.hour == 9 and date.minute == 00:
                self.set_checkin(date, request.email)
                return CheckInResponseMessage(response_code = 200, response_status = "Check in correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
            elif date.hour < 7 or date.hour > 19:
                return CheckInResponseMessage(response_code = 406, response_status = "Check in fuera de hora", response_date = date.strftime("%y%b%d%H:%M:%S"))
            else:
                self.set_checkin(date, request.email)
                message = " ha llegado fuera de los limites horarios"
                check = False
                self.set_incidences(message, date, request.email, check)
                return CheckInResponseMessage(response_code = 202, response_status = "Check in correcto. Se ha generado un reporte", response_date = date.strftime("%y%b%d%H:%M:%S"))

    @endpoints.method(CheckOutMessage, CheckOutResponseMessage,
    path = 'check_out', http_method = 'POST', name = 'check_out')
    def check_out(self, request):
        date = datetime.now()
        if date.hour >= 14 and date.hour < 19:
            self.set_checkout(date, request.email)
            return CheckOutResponseMessage(response_code = 200, response_status = "Check out correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
        elif date.hour == 19 and date.minute == 00:
            self.set_checkout(date, request.email)
            return CheckOutResponseMessage(response_code = 200, response_status = "Check out correcto", response_date = date.strftime("%y%b%d%H:%M:%S"))
        elif date.hour < 7 or date.hour > 19:
            return CheckOutResponseMessage(response_code = 406, response_status = "Check out fuera de hora", response_date = date.strftime("%y%b%d%H:%M:%S"))
        else:
            self.set_checkout(date, request.email)
            message = " ha realizado un checkout antes de la hora minima"
            check = False
            self.set_incidences(message, date, request.email, check)
            return CheckOutResponseMessage(response_code = 202, response_status = "Check out correcto. Se ha generado un reporte", response_date = date.strftime("%y%b%d%H:%M:%S"))

    @endpoints.method(LoginMessage, LoginMessageResponse, path='login', http_method='POST', name='login')
    def login(self, request):
        current_user = endpoints.get_current_user()
        profile = Employee.query(Employee.email == current_user.email()).get()
        if profile is None:
            employee = Employee(
                name=request.name,
                email=current_user.email(),
                image=request.image,
                role=0
            )
            employee.put()
            return LoginMessageResponse(response_code=200, email=employee.email, name=employee.name)
        else:
            return LoginMessageResponse(response_code=300, email=current_user.email(), name=request.name)

    @endpoints.method(CheckInMessage, CheckResponse, path='checkWorkedDay', http_method='GET', name='checkWorkedDay')
    def checkWorkedDay(self, request):
        query = Workday.query()
        query = query.filter(Workday.employee.email == request.email).fetch()
        for day in query:
            if day.checkin != None:
                print day.checkin
                if day.checkout != None:
                    print day.checkout
                    if day.checkin.isocalendar()[2] == datetime.now().isocalendar()[2] and day.checkin.isocalendar()[1] == datetime.now().isocalendar()[1] and day.checkin.isocalendar()[0] == datetime.now().isocalendar()[0]:
                        if day.checkout.isocalendar()[2] == datetime.now().isocalendar()[2] and day.checkout.isocalendar()[1] == datetime.now().isocalendar()[1] and day.checkout.isocalendar()[0] == datetime.now().isocalendar()[0]:
                            return CheckResponse(response_date=str(day.checkin))
                else:
                    return CheckResponse(response_date="No has hecho checkout")
        return CheckResponse(response_date="No has hecho checkin")

    @endpoints.method(CheckInMessage, CheckResponse, path='getCheckin', http_method='GET', name='getCheckin')
    def getCheckin(self, request):
        query = Workday.query()
        query = query.filter(Workday.employee.email == request.email).fetch()
        for day in query:
            if(day.checkin != None):
                if day.checkin.isocalendar()[2] == datetime.now().isocalendar()[2] and day.checkin.isocalendar()[1] == datetime.now().isocalendar()[1] and day.checkin.isocalendar()[0] == datetime.now().isocalendar()[0]:
                    return CheckResponse(response_date=str(day.checkin))
        return CheckResponse(response_date="No hay fecha de checkin")

    @endpoints.method(CheckOutMessage, CheckResponse, path='getCheckout', http_method='GET', name='getCheckout')
    def getCheckout(self, request):
        query = Workday.query()
        query = query.filter(Workday.employee.email == request.email).fetch()
        for day in query:
            if(day.checkout != None):
                if day.checkout.isocalendar()[2] == datetime.now().isocalendar()[2] and day.checkout.isocalendar()[1] == datetime.now().isocalendar()[1] and day.checkout.isocalendar()[0] == datetime.now().isocalendar()[0]:
                    return CheckResponse(response_date=str(day.checkout))
        return CheckResponse(response_date="No hay fecha de checkout")

    @endpoints.method(CheckIncidenceMessage, CheckIncidenceResponse, path='setCheckIncidence', http_method='POST', name='setCheckIncidence')
    def setCheckIncidence(self, request):
        query = Incidences.query()
        query = query.filter(Incidences.employee.email == request.email).fetch()
        for incidence in query:
            incidence.check=True
            incidence.put()
        return CheckIncidenceResponse()

    @endpoints.method(ReportMessage, ReportResponseMessage, path='weeklyReport', http_method='GET', name='weeklyReport')
    def report(self, request):
        workedDays = []
        day = datetime.today()
        if datetime.today().isocalendar()[2] != 1:
            query = Employee.query()
            for currentEmployee in query:
                workedDays.append(self.singleReport(currentEmployee, day))
            return ReportResponseMessage(response_report=workedDays)
        else:
            return ReportResponseMessage(response_report=[])


    @endpoints.method(ReportMonthlyMessage, ReportMonthlyResponseMessage, path='monthlyReport', http_method='GET', name='monthlyReport')
    def reportMonthly(self, request):
        workedDays = []
        date = datetime.today()
        query = Employee.query()
        for currentEmployee in query:
            workedDays.append(self.singleMonthlyReport(currentEmployee, date))
        return ReportMonthlyResponseMessage(response_report=workedDays)


    @endpoints.method(IncidencesReportMessage, IncidencesReportResponseMessage, path='incidencesReport', http_method='GET', name='incidencesReport')
    def incidencesReport(self, request):
        incidences = []
        query = Incidences.query()
        query = query.filter(Incidences.employee.email == request.email)
        for oneIncidence in query:
            incidences.append(self.incidencesList(oneIncidence))
        return IncidencesReportResponseMessage(incidences=incidences)


    @endpoints.method(IncidencesUsersMessage, IncidencesUserListResponseMessage, path='incidencesUsersList', http_method='GET', name='incidencesUsersList')
    def incidencesUsersList(self, request):
        users = []
        allIncidences = Incidences.query()
        for oneIncidence in allIncidences:
            employee = incidencesUsersListMessage()
            employee.name = oneIncidence.employee.name
            employee.email = oneIncidence.employee.email
            employee.image = oneIncidence.employee.image
            query = Incidences.query().filter(Incidences.employee.email == oneIncidence.employee.email)
            query = query.filter(Incidences.check != True).fetch()
            employee.incidencesNumber = len(query)
            users.append(employee)
        allUsers = []
        for user in users:
            if user not in allUsers:
                allUsers.append(user)
        return IncidencesUserListResponseMessage(users=allUsers)


    @endpoints.method(DateNowMessage, DateNowGetMessage, path='getDateNow', http_method='GET', name='getDateNow')
    def getDateNow(self, request):
        date = datetime.now()
        return DateNowGetMessage(response_date=str(date))

    @endpoints.method(EmployeeMessage, EmployeeMessageResponse, path='getEmployee', http_method='GET', name='getEmployee')
    def getEmployee(self, request):
        query = Employee.query()
        query = query.filter(Employee.email == request.email).get()
        print "Impresion", query
        employee = JsonEmployee(
            name=query.name,
            email=query.email,
            image=query.image
        )
        return EmployeeMessageResponse(employee=employee)

    ''' Endpoints to Mock Database '''

    @endpoints.method(DateNowMessage, DateNowMessage, path='mockEmployees', http_method='POST', name='mockEmployees')
    def mockEmployees(self, request):
        employee=Employee(name="Elinor Farryn", email="efarryn0@cocolog-nifty.com", image="http://dummyimage.com/116x156.png/dddddd/000000",role=1, status=False).put()
        employee=Employee(name="Risa Jauncey", email="rjauncey0@wikipedia.org", image="http://dummyimage.com/167x105.png/dddddd/000000",role=1, status=False).put()
        employee=Employee(name="Dominic Esselin", email="desselin0@bloglines.com", image="http://dummyimage.com/224x248.png/ff4444/ffffff", role=0, status=False).put()
        employee=Employee(name="Cassy Kos", email="ckos0@creativecommons.org", image="http://dummyimage.com/193x206.png/ff4444/ffffff", role=0, status=False).put()
        employee=Employee(name="Gregorio Nannetti", email="gnannetti0@tmall.com", image="http://dummyimage.com/213x210.bmp/5fa2dd/ffffff", role=1, status=False).put()
        employee=Employee(name="Lavinia Berntssen", email="lberntssen0@reference.com", image="http://dummyimage.com/216x210.jpg/ff4444/ffffff", role=0, status=True).put()
        employee=Employee(name="Julianna Dedon", email="Employee:[{jdedon0@unc.edu", image="http://dummyimage.com/214x197.png/dddddd/000000", role=1, status=False).put()
        employee=Employee(name="Alexine Maxstead", email="amaxstead0@wikipedia.org", image="http://dummyimage.com/247x196.bmp/cc0000/ffffff", role=1, status=False).put()
        employee=Employee(name="Laurel Brosetti", email="lbrosetti0@taobao.com", image="http://dummyimage.com/183x193.bmp/cc0000/ffffff", role=0, status=False).put()
        employee=Employee(name="Vivia Egger", email="vegger0@walmart.com", image="http://dummyimage.com/208x236.png/ff4444/ffffff", role=1, status=True).put()
        employee=Employee(name="Oliviero Hutchens", email="ohutchens0@ehow.com", image="http://dummyimage.com/109x143.jpg/dddddd/000000", role=1, status=False).put()
        employee=Employee(name="Jacynth Levett", email="jlevett0@parallels.com", image="http://dummyimage.com/107x111.bmp/dddddd/000000", role=0, status=False).put()
        employee=Employee(name="Arney Coolahan", email="acoolahan0@google.ru", image="http://dummyimage.com/197x185.jpg/cc0000/ffffff", role=0, status=False).put()
        employee=Employee(name="Brynna Hatchette", email="bhatchette0@hubpages.com", image="http://dummyimage.com/104x173.bmp/dddddd/000000", role=0, status=True).put()
        employee=Employee(name="Arch Lunney", email="alunney0@cyberchimps.com", image="http://dummyimage.com/229x223.bmp/5fa2dd/ffffff", role=0, status=True).put()
        employee=Employee(name="Lucky Melesk", email="lmelesk0@comsenz.com", image="http://dummyimage.com/205x203.bmp/cc0000/ffffff", role=0, status=False).put()
        employee=Employee(name="Janet Hadenton", email="jhadenton0@baidu.com", image="http://dummyimage.com/170x178.bmp/ff4444/ffffff", role=1, status=True).put()
        employee=Employee(name="Shara Petraitis", email="spetraitis0@gmpg.org", image="http://dummyimage.com/119x127.bmp/5fa2dd/ffffff", role=0, status=True).put()
        employee=Employee(name="Tremaine Cucuzza", email="tcucuzza0@yelp.com", image="http://dummyimage.com/105x244.jpg/cc0000/ffffff", role=1, status=False).put()
        employee=Employee(name="Sadella Everard", email="severard0@printfriendly.com", image="http://dummyimage.com/128x126.bmp/cc0000/ffffff", role=0, status=True).put()
        return DateNowMessage()

    @endpoints.method(DateNowMessage, DateNowMessage, path='mockWorkdays', http_method='POST', name='mockWorkdays')
    def mockWorkdays(self, request):
        workday = Workday(checkin=datetime.strptime("2017-12-10 20:50:10", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-10 22:52:26", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Elinor Farryn", email="efarryn0@cocolog-nifty.com", image="http://dummyimage.com/116x156.png/dddddd/000000",role=1,status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-10 16:20:54", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-10 19:16:08", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Risa Jauncey", email="rjauncey0@wikipedia.org", image="http://dummyimage.com/167x105.png/dddddd/000000",role=1,status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-11 08:38:29", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-11 09:44:41", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Dominic Esselin", email="desselin0@bloglines.com", image="http://dummyimage.com/224x248.png/ff4444/ffffff", role=0, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-11 03:13:31", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-11 04:46:04", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Cassy Kos", email="ckos0@creativecommons.org", image="http://dummyimage.com/193x206.png/ff4444/ffffff", role=0, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-11 09:18:37", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-11 11:37:51", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Gregorio Nannetti", email="gnannetti0@tmall.com", image="http://dummyimage.com/213x210.bmp/5fa2dd/ffffff", role=1, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-07 02:13:47", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-07 03:42:37", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Lavinia Berntssen", email="lberntssen0@reference.com", image="http://dummyimage.com/216x210.jpg/ff4444/ffffff", role=0, status=True)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-09 11:34:11", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-09 12:50:16", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Julianna Dedon", email="Employee:[{jdedon0@unc.edu", image="http://dummyimage.com/214x197.png/dddddd/000000", role=1, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-09 03:51:56", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-09 05:11:24", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Alexine Maxstead", email="amaxstead0@wikipedia.org", image="http://dummyimage.com/247x196.bmp/cc0000/ffffff", role=1, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-10 16:40:59", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-10 17:56:01", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Laurel Brosetti", email="lbrosetti0@taobao.com", image="http://dummyimage.com/183x193.bmp/cc0000/ffffff", role=0, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-09 14:52:29", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-09 17:07:41", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Vivia Egger", email="vegger0@walmart.com", image="http://dummyimage.com/208x236.png/ff4444/ffffff", role=1, status=True)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-11 12:46:28", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-11 15:32:54", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Oliviero Hutchens", email="ohutchens0@ehow.com", image="http://dummyimage.com/109x143.jpg/dddddd/000000", role=1, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-10 14:32:46", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-10 16:47:49", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Jacynth Levett", email="jlevett0@parallels.com", image="http://dummyimage.com/107x111.bmp/dddddd/000000", role=0, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-10 13:34:16", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-10 16:30:52", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Arney Coolahan", email="acoolahan0@google.ru", image="http://dummyimage.com/197x185.jpg/cc0000/ffffff", role=0, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-07 20:16:32", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-07 21:37:54", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Brynna Hatchette", email="bhatchette0@hubpages.com", image="http://dummyimage.com/104x173.bmp/dddddd/000000", role=0, status=True)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-08 03:18:24", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-08 05:41:29", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Arch Lunney", email="alunney0@cyberchimps.com", image="http://dummyimage.com/229x223.bmp/5fa2dd/ffffff", role=0, status=True)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-10 19:36:44", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-10 20:49:19", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Lucky Melesk", email="lmelesk0@comsenz.com", image="http://dummyimage.com/205x203.bmp/cc0000/ffffff", role=0, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-08 15:09:37", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-08 16:21:06", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Janet Hadenton", email="jhadenton0@baidu.com", image="http://dummyimage.com/170x178.bmp/ff4444/ffffff", role=1, status=True)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-09 21:03:27", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-09 23:20:33", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Shara Petraitis", email="spetraitis0@gmpg.org", image="http://dummyimage.com/119x127.bmp/5fa2dd/ffffff", role=0, status=True)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-11 15:55:42", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-11 17:42:17", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Tremaine Cucuzza", email="tcucuzza0@yelp.com", image="http://dummyimage.com/105x244.jpg/cc0000/ffffff", role=1, status=False)).put()
        workday = Workday(checkin=datetime.strptime("2017-12-08 08:26:52", "%Y-%m-%d %H:%M:%S"), checkout=datetime.strptime("2017-12-08 09:43:05", "%Y-%m-%d %H:%M:%S"), employee=Employee(name="Sadella Everard", email="severard0@printfriendly.com", image="http://dummyimage.com/128x126.bmp/cc0000/ffffff", role=0, status=True)).put()
        return DateNowMessage()

    @endpoints.method(DateNowMessage, DateNowMessage, path='mockIncidences', http_method='POST', name='mockIncidences')
    def mockIncidences(self, request):
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-10 20:50:10", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Elinor Farryn", email="efarryn0@cocolog-nifty.com", image="http://dummyimage.com/116x156.png/dddddd/000000",role=1,status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-10 16:20:54", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Risa Jauncey", email="rjauncey0@wikipedia.org", image="http://dummyimage.com/167x105.png/dddddd/000000",role=1,status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-11 08:38:29", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Dominic Esselin", email="desselin0@bloglines.com", image="http://dummyimage.com/224x248.png/ff4444/ffffff", role=0, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-11 03:13:31", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Cassy Kos", email="ckos0@creativecommons.org", image="http://dummyimage.com/193x206.png/ff4444/ffffff", role=0, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-11 09:18:37", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Gregorio Nannetti", email="gnannetti0@tmall.com", image="http://dummyimage.com/213x210.bmp/5fa2dd/ffffff", role=1, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-07 02:13:47", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Lavinia Berntssen", email="lberntssen0@reference.com", image="http://dummyimage.com/216x210.jpg/ff4444/ffffff", role=0, status=True)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-09 11:34:11", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Julianna Dedon", email="jdedon0@unc.edu", image="http://dummyimage.com/214x197.png/dddddd/000000", role=1, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-09 03:51:56", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Alexine Maxstead", email="amaxstead0@wikipedia.org", image="http://dummyimage.com/247x196.bmp/cc0000/ffffff", role=1, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-10 16:40:59", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Laurel Brosetti", email="lbrosetti0@taobao.com", image="http://dummyimage.com/183x193.bmp/cc0000/ffffff", role=0, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-09 14:52:29", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Vivia Egger", email="vegger0@walmart.com", image="http://dummyimage.com/208x236.png/ff4444/ffffff", role=1, status=True)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-11 12:46:28", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Oliviero Hutchens", email="ohutchens0@ehow.com", image="http://dummyimage.com/109x143.jpg/dddddd/000000", role=1, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-10 14:32:46", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Jacynth Levett", email="jlevett0@parallels.com", image="http://dummyimage.com/107x111.bmp/dddddd/000000", role=0, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-10 13:34:16", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Arney Coolahan", email="acoolahan0@google.ru", image="http://dummyimage.com/197x185.jpg/cc0000/ffffff", role=0, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-07 20:16:32", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Brynna Hatchette", email="bhatchette0@hubpages.com", image="http://dummyimage.com/104x173.bmp/dddddd/000000", role=0, status=True)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-08 03:18:24", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Arch Lunney", email="alunney0@cyberchimps.com", image="http://dummyimage.com/229x223.bmp/5fa2dd/ffffff", role=0, status=True)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-10 19:36:44", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Lucky Melesk", email="lmelesk0@comsenz.com", image="http://dummyimage.com/205x203.bmp/cc0000/ffffff", role=0, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-08 15:09:37", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Janet Hadenton", email="jhadenton0@baidu.com", image="http://dummyimage.com/170x178.bmp/ff4444/ffffff", role=1, status=True)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-09 21:03:27", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Shara Petraitis", email="spetraitis0@gmpg.org", image="http://dummyimage.com/119x127.bmp/5fa2dd/ffffff", role=0, status=True)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-11 15:55:42", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Tremaine Cucuzza", email="tcucuzza0@yelp.com", image="http://dummyimage.com/105x244.jpg/cc0000/ffffff", role=1, status=False)).put()
        incidence = Incidences(incidenceDate=datetime.strptime("2017-12-08 08:26:52", "%Y-%m-%d %H:%M:%S"), check=False, message="Checkin fuera de hora", employee=Employee(name="Sadella Everard", email="severard0@printfriendly.com", image="http://dummyimage.com/128x126.bmp/cc0000/ffffff", role=0, status=True)).put()
        return DateNowMessage()

application = endpoints.api_server([MainPage], restricted=False)
