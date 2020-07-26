import multiprocessing 
import time 
import os
from Kiwoom import *

def version_check(): 
    app = QApplication([''])
    km = Kiwoom()

    if km.connect_status == True: 
        print("Version check finished")
    else: 
        print("VERSION CHECK FAILED: ATTENTION REQUIRED ---")
    del km
    while 1: 
        print('process vercheck waiting')
        time.sleep(5)
    app.quit()

def another_func():
    print("Another function running")    
    while 1: 
        print('process anop waiting')
        time.sleep(7)

if __name__ == "__main__":
    all_processes = [] 
    
    verp = multiprocessing.Process(target=version_check, daemon=True) 
    verp.start() 
    print("verp: ", verp.is_alive())
    # verp.join()
    all_processes.append(verp) 

    anop = multiprocessing.Process(target=another_func, daemon=True) 
    anop.start() 
    print("anop: ", anop.is_alive())
    # anop.join()
    all_processes.append(anop) 

    time.sleep(10)

    print('terminate verp')
    verp.terminate()
    print('terminated verp')

    time.sleep(10)
    print('restart verp')
    verp = multiprocessing.Process(target=version_check, daemon=True) 
    verp.start() 
    print("verp: ", verp.is_alive())
    # verp.join()
    all_processes.append(verp) 

    time.sleep(10)

    for process in all_processes: 
        print("can reterminate?")
        process.terminate() 
        print(process.is_alive())