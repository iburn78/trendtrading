from pywinauto import application
from pywinauto import timings
from pywinauto import findwindows
import time
import os
import json
import sys

with open('C:/Users/user/Projects/kw.crd') as f:
    data = json.load(f)

ff = open('C:/Users/user/Projects/autotrading/log/autoupdate_log.txt', 'a')
ff.write("Autoupdate running at: " + time.ctime(time.time()) + "\n")

try:
    app = application.Application()
    app.start("C:/KiwoomFlash3/Bin/NKMiniStarter.exe")

    title = "번개3 Login"
    dlg = timings.WaitUntilPasses(20, 0.5, lambda: app.window_(title=title))

    pass_ctrl = dlg.Edit2
    pass_ctrl.SetFocus()
    pass_ctrl.TypeKeys(data['kw'])

    cert_ctrl = dlg.Edit3
    cert_ctrl.SetFocus()
    cert_ctrl.TypeKeys('')

    btn_ctrl = dlg.Button0
    btn_ctrl.Click()
except Exception as e:
    ff.write("    ERROR in Location 1\n")
    ff.write(e)
    ff.close()
    sys.exit()

time.sleep(1)
try:
    dlg2 = timings.WaitUntilPasses(20, 0.5, lambda: app.window_(title = '번개3'))
    btn_ctrl2 = dlg2.Button1
    btn_ctrl2.Click()
except: 
    ff.write("    ERROR in Location 2\n")
    ff.close()
    sys.exit()

time.sleep(120)
try:
    os.system("taskkill /im NKmini.exe")
except:
    ff.write("    ERROR in Locaiton 3\n")
    ff.close()
    sys.exit()

time.sleep(1)
try: 
    title2 = findwindows.find_windows(title='', class_name='#32770', control_id=0)[0]
    dlg2 = timings.WaitUntilPasses(20, 0.5, lambda: app.window_(handle=title2))
    btn_ctrl2 = dlg2.Button0
    btn_ctrl2.Click()
    ff.write("    -- success at: " + time.ctime(time.time()) + "\n")

except:
    ff.write("    ERROR in Location 4\n")

ff.close()