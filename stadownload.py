import sqlite3
from Kiwoom import *

STA_DATE_PERIOD = '0' # 0: date, 1: period
STA_START_DATE = '0' # ignored if STA_DATE_PERIOD = '0'
STA_END_DATE = '20200831'
STA_UNIT = '1' 
STA_NUMBER_TO_RECEIVE_NEXTPAGE = 20
BYINVESTOR_DB = 'sta/byinvestor.db'
INFO_DB = 'sta/infodb.db'
INFO_DB_TABLE = 'infodb'
INFO_DOWNLOAD_CHUNK = 70 
WAIT_INTERVAL = 60


class STA_download():
    def __init__(self):
        # self.info_download()
        # self.bi_download()
        # self.dc_download()
        self.ss_download()
        pass
    
    # ss: short sales // download to db required
    def ss_download(self): 
        app = QApplication([''])
        self.k = Kiwoom()
        ss = self.shortsales_record('005930')
        print(ss)

    # dc: daecha // download to db required
    def dc_download(self):
        app = QApplication([''])
        self.k = Kiwoom()
        # should iterate over dates and code
        # may require to use multiprocessing
        dt1 = self.daecha_trading_record_mkt('20200901', '20200908')
        dt2 = self.daecha_trading_record_code('20200901', '20200908', '005930')
        print(dt1)
        print(dt2)

    ##################
    # program: arbitrage vs non-arbitrage
    # use opt90013: need to be implemented in Kiwoom
    ##################
    
    ##################
    # figure fgn money distribution out and relative performance
    ##################

    ##################
    # validate Morgan Stanley assumption / analysis
    ##################

    # bi: by investors
    def bi_download(self):
        if not os.path.exists(BYINVESTOR_DB): 
            print("byinvestor.db file exis")
            sys.exit()
        topsize = 200
        stepsize = 2
        toptotal = self.get_top_n_code(topsize)
        for i in range(0, topsize, stepsize):
            codelist = toptotal[i:i+stepsize]
            print(codelist, i)
            bi_singlerun_proc = multiprocessing.Process(target=self.bi_download_singlerun, args=(codelist,), daemon=True) 
            bi_singlerun_proc.start()
            bi_singlerun_proc.join()
            bi_singlerun_proc.terminate()
            time.sleep(WAIT_INTERVAL)

    def bi_download_singlerun(self, codelist):
        app = QApplication([''])
        self.k = Kiwoom()
        for code in codelist:
            print(code)
            bi_buy = self.investor_history_singlecase(code, netbuysell='1')
            bi_sell = self.investor_history_singlecase(code, netbuysell='2')
            con = sqlite3.connect(BYINVESTOR_DB)
            bi_buy.to_sql(f'buy{code}', con, if_exists='replace', index = False)
            bi_sell.to_sql(f'sell{code}', con, if_exists='replace', index = False)
            con.close()
        
        # bi_net could be easily constructed through the following: 
        # bi_net = bi_buy.copy()
        # bi_net.loc[:, 'ppl':] = bi_buy.loc[:, 'ppl':] + bi_sell.loc[:, 'ppl':]

    def get_top_n_code(self, n):
        if not os.path.exists(INFO_DB): 
            print("infodb.db file does not exist")
            sys.exit()
        con = sqlite3.connect(INFO_DB)
        idb = pd.read_sql_query(f'select * from {INFO_DB_TABLE}', con)
        con.close()
        return list(idb.nlargest(n, 'mktcap')['code'])

    # info: general info per each code
    def info_download(self):
        app = QApplication([''])
        self.k = Kiwoom()
        if os.path.exists(INFO_DB): 
            print("infodb.db file exists")
            sys.exit()
        self.codelist = self.k.get_codelist_by_market(0).split(';')[:-1]
        self.codelist += self.k.get_codelist_by_market(10).split(';')[:-1]
        self.infodb = pd.DataFrame(columns = ['code', 'cprice', 'total_shares', 'trade_shares', 'fgn_weight', 'PER', 'EPS', 'ROE', 'PBR', 'EV', 'BPS', 'mktcap', 
                                              'sales', 'EBIT', 'netprofit', 'date', 'status', 'name', 'note']).astype({
                                            'code': 'object', 'cprice': 'int64', 'total_shares': 'int64', 'trade_shares': 'int64', 'fgn_weight': 'int64', 
                                            'PER': 'float64', 'EPS': 'int64', 'ROE': 'float64', 'PBR': 'float64', 'EV': 'float64', 'BPS': 'int64', 'mktcap': 'int64', 
                                            'sales': 'int64', 'EBIT': 'int64', 'netprofit': 'int64', 'date': 'object', 'status': 'object', 'name': 'object', 'note': 'object'})
        con = sqlite3.connect(INFO_DB)
        resume_location = 0 # that is the last number printed or INFO_DOWNLOAD_CHUNK * num saved 
        self.infodb.to_sql(INFO_DB_TABLE, con, if_exists = 'append', index = False) # adjust 'replace' as needed
        con.close()

        i = 0
        for code in self.codelist[resume_location:]:
            print('.', end="")
            i += 1
            info_code = self.k.get_basic_info(code)
            info_code['date'] = pd.Timestamp.now().strftime("%Y%m%d")
            self.infodb.loc[len(self.infodb)] = info_code
            if i % INFO_DOWNLOAD_CHUNK == 0:
                print(f' {i}')
                con = sqlite3.connect(INFO_DB)
                self.infodb.to_sql(INFO_DB_TABLE, con, if_exists = 'append', index = False)
                con.close()
                self.infodb.drop(self.infodb.index, inplace = True)
                time.sleep(WAIT_INTERVAL)

        con = sqlite3.connect(INFO_DB)
        self.infodb.to_sql(INFO_DB_TABLE, con, if_exists = 'append', index = False)
        con.close()
        self.infodb.drop(self.infodb.index, inplace = True)

        # cur = con.cursor()
        # cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        # cur.execute("drop table 'table_name';")
        # res = cur.fetchall()
        # print(res)

    #OPT10068 - no next page available. should adjust start_date and end_date
    def daecha_trading_record_mkt(self, start_date, end_date):
        self.k.set_input_value('시작일자', start_date)
        self.k.set_input_value('종료일자', end_date)
        self.k.set_input_value('전체구분', '1')
        self.k.set_input_value('종목코드', '')
        self.k.comm_rq_data('OPT10068_req', 'OPT10068', 0, '1000')
        dt = pd.DataFrame(self.k.opt10068_multi_data_set)

        if len(dt) == 0:
            print('Kiwoom data download error')
            sys.exit()
            
        dt = dt.astype({0: 'object', 1: 'int64', 2: 'int64', 3: 'int64', 4: 'int64', 5: 'int64'})
        dt.rename(columns = {0: 'date', 1: 'dc_new', 2: 'dc_ret', 3: 'dc_inc', 4: 'dc_remained', 5: 'dc_amount'}, inplace = True)
        return dt

    #opt20068 - no next page available. should adjust start_date and end_date
    def daecha_trading_record_code(self, start_date, end_date, code):
        self.k.set_input_value('시작일자', start_date)
        self.k.set_input_value('종료일자', end_date)
        self.k.set_input_value('전체구분', '0')
        self.k.set_input_value('종목코드', code)
        self.k.comm_rq_data('opt20068_req', 'opt20068', 0, '1000')
        dt = pd.DataFrame(self.k.opt20068_multi_data_set)

        if len(dt) == 0:
            print('Kiwoom data download error')
            sys.exit()

        dt = dt.astype({0: 'object', 1: 'int64', 2: 'int64', 3: 'int64', 4: 'int64', 5: 'int64'})
        dt.rename(columns = {0: 'date', 1: 'dc_new', 2: 'dc_ret', 3: 'dc_inc', 4: 'dc_remained', 5: 'dc_amount'}, inplace = True)
        return dt


    def shortsales_record(self, code): 
        # opt10014 Short Selling  ---------------------------------
        self.k.set_input_value('종목코드', code)
        self.k.set_input_value('시간구분', STA_DATE_PERIOD) # 0: by date, 1: by period
        self.k.set_input_value('시작일자', STA_START_DATE) # if by date, this input ignored
        self.k.set_input_value('종료일자', STA_END_DATE) # should be later than start date
        self.k.comm_rq_data('opt10014_req', 'opt10014', 0, '2000')
        ss = pd.DataFrame(self.k.opt10014_multi_data_set)

        for i in range(STA_NUMBER_TO_RECEIVE_NEXTPAGE):
            print('.', end='')
            if self.k.remained_data:
                self.k.set_input_value('종목코드', code)
                self.k.set_input_value('시간구분', STA_DATE_PERIOD)
                self.k.set_input_value('시작일자', STA_START_DATE)
                self.k.set_input_value('종료일자', STA_END_DATE)
                self.k.comm_rq_data('opt10014_req', 'opt10014', 2, '2000')
                ss =ss.append(pd.DataFrame(self.k.opt10014_multi_data_set)) 
            else: 
                break
        print()
        if len(ss) == 0:
            print('Kiwoom data download error')
            sys.exit()

        # incrate in %
        # volume in a single share
        # shortwgt in %
        # shortamt in 1000
        # clprice = closing price
        ss.reset_index(drop=True, inplace=True)
        ss = ss.astype({0: 'object', 1: 'int64', 2: 'int64', 3: 'int64', 4: 'float64', 5: 'int64', 6: 'int64', 7: 'float64', 8: 'int64', 9: 'int64'})
        ss.rename(columns = {0: 'date', 1: 'clprice', 2: 'deltakey', 3: 'delta', 4: 'incrate', 5: 'volume', 6: 'shortvol', 7: 'shortwgt', 8: 'shortamt', 9: 'shortprice'}, inplace = True)
        ss.clprice = ss.clprice.abs()
        return ss

    def investor_history_singlecase(self, code, moneyquantity='2', netbuysell='0'):
        # opt10059 By Investor  ---------------------------------
        self.k.set_input_value('일자', STA_END_DATE)
        self.k.set_input_value('종목코드', code)
        self.k.set_input_value('금액수량구분', moneyquantity)  # 1: money amount, 2: quantity of units
        self.k.set_input_value('매매구분', netbuysell)  # 0: net, 1: buy, 2: sell
        self.k.set_input_value('단위구분', STA_UNIT) # 1000: a thousand unit, 1: a unit
        self.k.comm_rq_data('opt10059_req', 'opt10059', 0, '3000')
        bi = pd.DataFrame(self.k.opt10059_multi_data_set)

        for i in range(STA_NUMBER_TO_RECEIVE_NEXTPAGE):
            print('.', end='')
            if self.k.remained_data:
                self.k.set_input_value('일자', STA_END_DATE)
                self.k.set_input_value('종목코드', code)
                self.k.set_input_value('금액수량구분', moneyquantity)  # 1: money amount in 1M KRW, 2: quantity of units
                self.k.set_input_value('매매구분', netbuysell)  # 0: net, 1: buy, 2: sell
                self.k.set_input_value('단위구분', STA_UNIT) # 1000: a thousand unit, 1: a unit
                self.k.comm_rq_data('opt10059_req', 'opt10059', 2, '3000')
                bi = bi.append(pd.DataFrame(self.k.opt10059_multi_data_set))
            else: 
                break
        print()
        if len(bi) == 0:
            print('Kiwoom data download error')
            sys.exit()
        
        # incrate in basis point
        # amount in million KRW
        # t_inst = fininv + insu + trust + finetc + bank + pensvg + prieqt + nation
        # volume or amount = ppl + fgn + t_inst +  corpetc + fgnetc when buy/sell(negative)
        # 0  = ppl + fgn + t_inst + nation + corpetc + fgnetc when buy when net
        bi.reset_index(drop=True, inplace=True)
        bi = bi.astype({0: 'object', 1: 'int64', 2: 'int64', 3: 'int64', 4: 'int64', 5: 'int64', 6: 'int64', 7: 'int64', 8: 'int64', 9: 'int64', 
                        10: 'int64', 11: 'int64', 12: 'int64', 13: 'int64', 14: 'int64', 15: 'int64', 16: 'int64', 17: 'int64', 18: 'int64', 19: 'int64'})
        bi.rename(columns = {0: 'date', 1: 'price', 2: 'deltakey', 3: 'delta', 4: 'incrate', 5: 'volume', 6: 'amount', 7: 'ppl', 8: 'fgn', 9: 't_inst', 10: 'fininv', 
                            11: 'insu', 12: 'trust', 13: 'finetc', 14: 'bank', 15: 'pensvg', 16: 'prieqt', 17: 'nation', 18: 'corpetc', 19: 'fgnetc'}, inplace = True)
        bi.price = bi.price.abs()
        return bi



if __name__=="__main__":
    sta = STA_download()
