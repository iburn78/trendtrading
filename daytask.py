from Kiwoom import *
from trtrader import *
from datetime import datetime, time as dtime
from controller import MKT_CLOSE_TIME, MKT_OPEN_TIME, VERSION_CHECK_MSG, TRTRADE_RUN_INTERVAL, HOLIDAYS

### VERSION CHECK

if datetime.now().time() < MKT_OPEN_TIME:
    app = QApplication([''])
    km = Kiwoom()

    if km.connect_status == True: 
        km.trade_log_write(VERSION_CHECK_MSG)
    else: 
        km.trade_log_write("VERSION CHECK FAILED: ATTENTION REQUIRED ---")

    del km
    app.quit()

### Main Routine

else: 
    app = QApplication([''])
    trtrader = TrTrader()
    while 1: 
        try: 
            if datetime.now().time() > MKT_OPEN_TIME and datetime.now().time() < MKT_CLOSE_TIME: 
                if datetime.now().date().weekday() in [0, 1, 2, 3, 4] and datetime.now().date() not in HOLIDAYS:
                    trtrader.run_()
                else:
                    print("Market Closed Day")
                    break
            if datetime.now().time() > MKT_CLOSE_TIME: 
                print("Market Closed Time")
                break
            time.sleep(TRTRADE_RUN_INTERVAL)
        except KeyboardInterrupt:
            print("Keyboard Interrupt Detected")
            break
    
    trtrader.close_()
    del trtrader
    app.quit()