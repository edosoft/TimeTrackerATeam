import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs/Rx';
import { Subject } from 'rxjs/Subject';
import {LocalStorageService, SessionStorageService} from 'ngx-webstorage';

@Injectable()
export class UserService {

  subject: Subject<any> = new Subject<any>();
  public localRoute = "http://localhost:8080/_ah/api/timetracker/v1/";
  public serverRoute = "https://timetrackerateam.appspot.com/_ah/api/timetracker/v1/";

  constructor(private http: HttpClient){

}
  getUserList(): Observable<any>{
    return this.http.get<any>(this.serverRoute + "getUserList")
  }

  getEmployee(email):Observable<any>{
    return this.http.get(this.serverRoute + 'getEmployee?email=' + email);
  }

  setRole(email, role):Observable<any>{
    let body = { "email": email, "role": role};
    return this.http.post(this.serverRoute + 'setRole', body);
  }

  getPersonalIP(email):Observable<any>{
    return this.http.get(this.serverRoute + 'getPersonalIPList?email=' + email)
  }

  getIpFilteredByDate(email, dateIn, dateOut):Observable<any>{
    return this.http.get(this.serverRoute + 'getPersonalIPWithRange?email=' + email + "&dateStart=" + dateIn + "&dateEnd=" + dateOut);
  }

  downloadLogs(): Observable<any>{
    return this.http.get(this.serverRoute + 'downloadLogs');
  }

}
