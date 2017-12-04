import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs/Rx';
import { Subject } from 'rxjs/Subject';
import {LocalStorageService, SessionStorageService} from 'ngx-webstorage';

@Injectable()
export class CheckInService {
  timeIn:string;
  subject: Subject<any> = new Subject<any>();
  public localRoute = "http://localhost:8080/_ah/api/timetracker/v1/";
  public serverRoute = "https://timetrackerateam.appspot.com/_ah/api/timetracker/v1/";

  constructor( private http: HttpClient, private sessionSt:SessionStorageService) { }

  postCheckIn():Observable<any>{
    console.log(this.sessionSt.retrieve('email'))
    let body = {"email": this.sessionSt.retrieve('email')}
    return this.http.post(this.serverRoute + "check_in", body);
  }

  postCheckOut():Observable<any>{
    let body = {"email": this.sessionSt.retrieve('email')}
    return this.http.post(this.serverRoute + "check_out", body);
  }

  getCheckIn():Observable<any>{
    let body = {"email": this.sessionSt.retrieve('email')}
    return this.http.get(this.serverRoute + "getCheckin?email=" + body);
  }

  getWeeklyReport(): Observable<any>{
    return this.http.get<any>(this.serverRoute + "weeklyReport");
  }

  getDateNow(): Observable<any>{
    return this.http.get<any>(this.serverRoute + "getDateNow");
  }

  getMontlyReport(): Observable<any>{
    return this.http.get<any>(this.serverRoute + "monthlyReport");    
  }
  getUserList(): Observable<any>{
    return this.http.get<any>(this.serverRoute + "getUser")
  }
}
