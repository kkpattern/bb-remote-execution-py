import logging
import os
import os.path
import sys

import win32serviceutil
import win32service
import win32event
import servicemanager
import socket

from bbworker.main import WorkerMain


class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = "bbworker"
    _svc_display_name_ = "Buildbarn worker"

    def __init__(self, args):
        logging.info("init service.")
        self._main = WorkerMain(os.path.abspath("bbworker_service.yaml"))
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def SvcStop(self):
        logging.info("service stop.")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._main.graceful_shutdown()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        logging.info("service run.")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        self.Main()

    def Main(self):
        self._main.run()


def _handle_exception(exc_type, exc_value, exc_traceback):
    logging.critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


sys.excepthook = _handle_exception

if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        # Application should run as a one-file bundle.
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    os.chdir(application_path)
    log_foramt = "%(asctime)s:%(levelname)s:thread-%(thread)d:%(message)s"
    logging.basicConfig(
        filename="bbworker_service.log", level=logging.INFO, format=log_foramt
    )
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AppServerSvc)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        if len(sys.argv) == 2 and sys.argv[-1] == "name":
            print(AppServerSvc._svc_name_)
        else:
            win32serviceutil.HandleCommandLine(AppServerSvc)
