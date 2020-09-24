from datetime import timedelta, time as dtime
import schedule
import multiprocessing 
from trsettings import *
from trtrader import *

### START WITH A NEW MASTER BOOK ###
### LEAVE: CREATE_NEW_MASTER_BOOK = False ###
remove_master_book_onetime_for_clean_initiation()

################################################################################################
HOLIDAYS_2020 = ['20200930', '20201001', '20201002', '20201009', '20201225']
HOLIDAYS = list(map(lambda x: datetime.strptime(x, '%Y%m%d').date(), HOLIDAYS_2020))
################################################################################################
VERSION_CHK_TIME = "08:00"
TRTRADE_RUN_TIME = "09:15"
TRTRADE_FIN_TIME = "15:15"
VERSION_CHK_TIME = (datetime.now() + timedelta(seconds = 1)).strftime("%H:%M:%S") 
TRTRADE_RUN_TIME = (datetime.now() + timedelta(minutes = 0.3)).strftime("%H:%M:%S") 
TRTRADE_FIN_TIME = (datetime.now() + timedelta(minutes = 7)).strftime("%H:%M:%S") 
TRTRADE_RUN_INTERVAL = 10 # second # time to rerun trtrader during TRTRADE_RUN_TIME until TRTRADE_FIN_TIME
RUN_PENDING_INTERVAL = 10 # time to rerun different processes under controller schedule, e.g., vershin checker, 
################################################################################################
TRTRADE_RUN_DTIME = dtime.fromisoformat(TRTRADE_RUN_TIME)
TRTRADE_FIN_DTIME = dtime.fromisoformat(TRTRADE_FIN_TIME)
################################################################################################
MAX_VERSION_CHECK_TIME = 3*60 # time to allow version checker to run / time to let Kiwoom API to update 
VERCHECK_SUCCESS_LOOP_INTERVAL = 5  # interval to check if version checking is successful 
WORKING_DAY_DEFINITION = [0, 1, 2, 3, 4, 5, 6]  # starts from MON... 
SYS_EXIT_ON_VERSION_CHECK_FAILURE = False

class Controller():
    def __init__(self): 
        schedule.every().day.at(VERSION_CHK_TIME).do(self.run_verchecker)
        schedule.every().day.at(TRTRADE_RUN_TIME).do(self.run_)

        if datetime.now().time() > TRTRADE_RUN_DTIME and datetime.now().time() < TRTRADE_FIN_DTIME:
            tl_print("Controller executed during trtrade run time - trtrader runs (API version check skipped)")
            self.run_()  
        
        while 1: 
            try:
                schedule.run_pending()
                time.sleep(RUN_PENDING_INTERVAL)
                print(time.strftime("c%M:%S"), end="\r") # Exception for trade_log_print (tl_print)
                # print('.', end='')
            except KeyboardInterrupt:
                tl_print("Keyboard Interrupt at controller main loop")
                sys.exit()

    # uses multiprocessing for clean termination
    def run_verchecker(self): 
        con_stat = multiprocessing.Value('i', 0)
        vercheck_proc = multiprocessing.Process(target=self.version_check_func, args=(con_stat,), daemon=True) # daemons are killed when main program exits 
                                                                                                               # use 'join' to tell the main program to wait until all daemons finish jobs
        tl_print("Version checker runs at "+ time.strftime("%Y/%m/%d %H:%M:%S"))
        vercheck_proc.start()
        t_end = time.time() + MAX_VERSION_CHECK_TIME
        while time.time() < t_end: 
            if con_stat.value == 1:
                tl_print("Version check successful")
                vercheck_proc.terminate()
                return
            time.sleep(VERCHECK_SUCCESS_LOOP_INTERVAL)
        tl_print("Version check FAILED --- NEED ATTENTION")
        vercheck_proc.terminate()
        if SYS_EXIT_ON_VERSION_CHECK_FAILURE: 
            tl_print("TrTrader exits...")
            sys.exit()
        else: 
            tl_print("Trtrader controller continues...")
        return

    def version_check_func(self, con_stat):
        app = QApplication([''])
        km = Kiwoom()
        if km.connect_status == True: 
            con_stat.value = 1
        del km
        app.quit()

    # uses multiprocessing for clean termination
    def run_(self):
        try:
            if datetime.now().date().weekday() in WORKING_DAY_DEFINITION and datetime.now().date() not in HOLIDAYS:
                main_proc = multiprocessing.Process(target=self.main_routine_func, daemon=True)
                tl_print("TrTrader runs at "+ time.strftime("%Y/%m/%d %H:%M:%S"))
                main_proc.start()
                # next whlie statement is for waiting until main proc finishes
                while main_proc.is_alive(): 
                    time.sleep(RUN_PENDING_INTERVAL)
            else: 
                tl_print("Not a market open day - continues to controller loop")
        except KeyboardInterrupt: 
            tl_print("Keyboard Interrupt Detected at run_ of controller ")
    
    def main_routine_func(self):
        app = QApplication([''])
        trtrader = TrTrader()
        while datetime.now().time() < TRTRADE_FIN_DTIME:
            try: # try-except for trtrader to close properly when keyboard interrupt occurs
                trtrader.run_()
                time.sleep(TRTRADE_RUN_INTERVAL)
            except KeyboardInterrupt: 
                tl_print("Keyboard Interrupt Detected at main_routine_func of controller ")
                break
        tl_print("TrTrader finishes at TRTRADE_FIN_DTIME, current time: "+time.strftime("%Y/%m/%d %H:%M:%S"))
        trtrader.close_()
        del trtrader
        app.quit()

    def master_book_visualize(self): 
        # print(self.trtrader.master_book)
        # user pretty printing of dataframe 
        # pick stock code and print return rate and reinvestment information (amount invested / current total value)
        # consider table or graph (using matplotlib)
        # (if needed) save it to file 
        pass

    def result_summary(self): # or performance management
        pass
        # return summary_statistics 
        # use this function as a basis for optimizer and backtester (to be developed later)
        # implement "PHASE" concept 

    def event_alert(self):
        pass
        # fire alerts whenever necessary       

class UserInfoManagement():
    pass
    # Real Server vs Simulator
    # Account management / password together

class BackTester():
    pass
    # utilize: start price, high price, low price, end price per stock per day
    # regarding high/low price, a certain discount factor may be applied 
    # may implement this class in trtrader.py file
    # may not be in a class form
    # of course, in backtesting, there is no need to use waiting interval

class Optimizer():
    pass
    # determine which parameters to optimize: UB/LB/LLB/CB(cash bound)/ticket size
    # determine which parameters to maximize: return rate/current total value
    # consider to build the best experiment design for optimization process
    # in designing optimizer, we may analyze per type of stocks in price evolution (e.g., band style, spike style, 
    # continual evaluation sytle, continual devaluation style)
    # application of AI/ML

class Economics():
    pass
    # Macro economic phase defining and finding


if __name__ == "__main__":
    ct = Controller()
