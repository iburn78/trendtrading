from Kiwoom import *
import sys
import sqlite3
from stadownload import BYINVESTOR_DB, INFO_DB, INFO_DB_TABLE

# If manual adjustment is required more than once, it has to be reflected into the split functions ######### REQUIRED
STA_ARG_DICT_SPLIT_EXCEPTION = {
    '005930': {'split_date':'20180504', 'split_ratio':50},  
    '005935': {'split_date':'20180504', 'split_ratio':50}, 
    '000100': {'split_date':'20200408', 'split_ratio':5},
    '204320': {'split_date':'20180508', 'split_ratio':5},
    '013890': {'split_date':'20170523', 'split_ratio':10},
    '200130': {'split_date':'20151005', 'split_ratio':0.2}, 
    '000240': {'split_date':'20121004', 'split_ratio':2}, 
    '018880': {'split_date':'20160216', 'split_ratio':5}, 
    '145020': {'split_date':'20200708', 'split_ratio':3}, 
    '004800': {'split_date':'20180713', 'split_ratio':1/0.39}, # company splited to 4 entities.... may double check the data... 
    '081660': {'split_date':'20180509', 'split_ratio':5}, 
}
STA_ARG_DICT_SPLIT_EXCEPTION_LATER_SPLIT = {    # code in this dict should also exist in STA_ARG_DICT_SPLIT_EXCEPTION
    '200130': {'split_date':'20160115', 'split_ratio':2}, 
}

class STA():
    def __init__(self):
        self.infodb = self.read_infodb()
        self.tblist, self.codelist = self.read_bicode()
        i = j = 0
        # self.codelist = ['200130'] # code to test
        for code in self.codelist[j:]: 
            print('processing:', code, i)
            i += 1
            [bi_net, bi_buy, bi_sell] = self.bi_stock_split_adjustment(*self.read_bidb(code), code)
            bi_net = self.reverse_date(bi_net)
            bi_buy = self.reverse_date(bi_buy)
            bi_sell = self.reverse_date(bi_sell)
            bis = self.bi_share_adjustment(code, bi_net, bi_buy, bi_sell)
            self.bi_graph_processing(code, *bis)

    def read_infodb(self):
        con = sqlite3.connect(INFO_DB)
        infodb = pd.read_sql_query(f'select * from {INFO_DB_TABLE}', con)
        con.close()
        return infodb
    
    def read_bicode(self): 
        con = sqlite3.connect(BYINVESTOR_DB)
        cur = con.cursor()
        tl = cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        con.close()
        tablelist = [t[0] for t in tl]
        return tablelist, list(dict.fromkeys([i[-6:] for i in tablelist])) # extracts only code without duplications
        
    def read_bidb(self, code):
        tblist_code = []
        for i in self.tblist: 
            if code in i: tblist_code.append(i)

        con = sqlite3.connect(BYINVESTOR_DB)
        bi_buy = pd.DataFrame()
        bi_sell = pd.DataFrame()
        for t in tblist_code:
            a = pd.read_sql_query(f"SELECT * from {t}", con)
            if 'buy' in t: bi_buy = a
            if 'sell' in t: bi_sell = a
        con.close()
        if len(bi_buy) == 0 or len(bi_sell) == 0: 
            print("read_bidb error")
            sys.exit()
        
        bi_net = bi_buy.copy()
        bi_net.loc[:, 'ppl':] = bi_buy.loc[:, 'ppl':] + bi_sell.loc[:, 'ppl':]

        return [bi_net, bi_buy, bi_sell]

    # for 005930 Samsung, split date = '20180504', ratio = 50
    # date is the first day with the splitted price
    # ss: short sales
    def ss_stock_split_adjustment(self, ss, code):
        if code in STA_ARG_DICT_SPLIT_EXCEPTION: 
            return self.ss_stock_split_adjustment_onetime(ss, **STA_ARG_DICT_SPLIT_EXCEPTION[code])
        try:
            sp = yf.Ticker(f'{code}.ks').splits
        except:
            print('split data not found in yfinance: ', code)
            return self.ss_stock_split_adjustment_onetime(ss, '', 1)
        for d in sp.index: 
            ss = self.ss_stock_split_adjustment_onetime(ss, d.strftime("%Y%m%d"), sp[d])
        return ss

    def ss_stock_split_adjustment_onetime(self, ss, split_date, split_ratio=1):
        top = ss.loc[ss.date >= split_date].copy()
        bot = ss.loc[ss.date < split_date].copy()
        bot.iloc[:, [1, 3, 9]] = bot.iloc[:, [1, 3, 9]]/split_ratio
        bot.iloc[:, [5, 6]] = bot.iloc[:, [5, 6]]*split_ratio
        bot.iloc[:, [1, 3, 9]] = bot.iloc[:, [1, 3, 9]].round().astype('int64')
        ss = top.append(bot).reset_index(drop=True)
        ss.drop(ss.loc[ss.volume == 0].index, inplace = True)
        return ss

    # for 005930 Samsung, split date = '20180504', ratio = 50
    # date is the first day with the splitted price
    # bi: by investors
    def bi_stock_split_adjustment(self, bi_net, bi_buy, bi_sell, code):
        exp_list = [STA_ARG_DICT_SPLIT_EXCEPTION, STA_ARG_DICT_SPLIT_EXCEPTION_LATER_SPLIT]
        for exp in exp_list:
            if code in exp: 
                bi_net = self.bi_stock_split_adjustment_onetime(bi_net, **exp[code])
                bi_buy = self.bi_stock_split_adjustment_onetime(bi_buy, **exp[code])
                bi_sell = self.bi_stock_split_adjustment_onetime(bi_sell, **exp[code])
        if code in STA_ARG_DICT_SPLIT_EXCEPTION:
            return [bi_net, bi_buy, bi_sell]
        try:
            sp = yf.Ticker(f'{code}.ks').splits
        except:
            print('split data not found in yfinance: ', code)
            bi_net = self.bi_stock_split_adjustment_onetime(bi_net, '', 1)
            bi_buy = self.bi_stock_split_adjustment_onetime(bi_buy, '', 1)
            bi_sell = self.bi_stock_split_adjustment_onetime(bi_sell, '', 1)
            return [bi_net, bi_buy, bi_sell]
        if len(sp>0): print('-----------------------------'); print(sp)
        for d in sp.index: 
            bi_net = self.bi_stock_split_adjustment_onetime(bi_net, d.strftime("%Y%m%d"), sp[d])
            bi_buy = self.bi_stock_split_adjustment_onetime(bi_buy, d.strftime("%Y%m%d"), sp[d])
            bi_sell = self.bi_stock_split_adjustment_onetime(bi_sell, d.strftime("%Y%m%d"), sp[d])
        return [bi_net, bi_buy, bi_sell]

    def bi_stock_split_adjustment_onetime(self, bi, split_date, split_ratio=1, moneyquantity = '2'): 
        top = bi.loc[bi.date >= split_date].copy()
        bot = bi.loc[bi.date < split_date].copy()
        bot.iloc[:, [1, 3]] = bot.iloc[:, [1, 3]]/split_ratio
        bot.iloc[:, 5] = bot.iloc[:, 5]*split_ratio
        if moneyquantity == '2': # if quantity
            bot.iloc[:, 7:] = bot.iloc[:, 7:]*split_ratio
        elif moneyquantity == '1': # if money
            pass
        else: 
            print('stock_split parameter error')
        bot.iloc[:, 1:] = bot.iloc[:, 1:].round().astype('int64')
        bi = top.append(bot).reset_index(drop=True)
        bi.drop(bi.loc[bi.volume == 0].index, inplace = True)
        return bi

    def reverse_date(self, df):
        return df.loc[::-1].reset_index(drop=True)

    # fgn weight uses the latest number from kiwoom which may not match with analysis period
    def bi_share_adjustment(self, code, bi_net, bi_buy, bi_sell):
        MARGIN_FACTOR = 0.01
        info = self.infodb.loc[self.infodb.code == code].to_dict(orient='records')[0]
        fgn_adjustment = round(info['total_shares']*info['fgn_weight'] - bi_net['fgn'].sum())
        fgnmin = bi_net['fgn'].cumsum().min()
        if fgn_adjustment + fgnmin <= 0: 
            print('###############')
            fgn_adjustment = -fgnmin + info['trade_shares']*MARGIN_FACTOR
            print('fgn_adjustment error:', code,'- set at -fgnmin + trade_share*MARGIN_FACTOR:', fgn_adjustment, 'where MARGIN_FACTOR:', MARGIN_FACTOR)
        pplmin = bi_net['ppl'].cumsum().min()
        instmin = bi_net['t_inst'].cumsum().min()
        adj = info['trade_shares'] - fgn_adjustment + pplmin + instmin
        if adj < 0: 
            print('###############')
            print('By investor adj error:', code)
            print('total_shares:', info['total_shares'], 'trade_shares:', info['trade_shares'], 'fgn_weight:', info['fgn_weight'])
            print('orignal fgn_adjustment:', fgn_adjustment, 'fgnmin:', fgnmin, 'pplmin:', pplmin, 'instmin:', instmin, 'adj:', adj)
            fgn_adjustment = -fgnmin + info['trade_shares']*MARGIN_FACTOR
            adj = info['trade_shares']*MARGIN_FACTOR 
            print('\nfgn_adjustment set at -fgnmin + trade_share*MARGIN_FACTOR:', fgn_adjustment, 'where MARGIN_FACTOR:', MARGIN_FACTOR)
            print('adj set at trade_share*MARGIN_FACTOR:', adj)
            print('###############')

        bi_net['ppl_ap'] = bi_net['price'].astype('float64')
        bi_net['ppl_ca'] = bi_net['ppl'].cumsum() - pplmin + adj
        bi_net['ppl_en'] = 0

        for i in range(1, len(bi_net)):
            bi_net.at[i, 'ppl_ap'] = round((bi_net.at[i-1, 'ppl_ap']*bi_net.at[i-1, 'ppl_ca']+bi_net.at[i,'price']*bi_buy.at[i,'ppl'])/(bi_net.at[i-1,'ppl_ca']+bi_buy.at[i,'ppl']), 1)
            bi_net.at[i, 'ppl_en'] = round((bi_net.at[i, 'price']-bi_net.at[i-1, 'ppl_ap'])*(-bi_sell.at[i,'ppl'])+bi_net.at[i-1,'ppl_en'])

        bi_net['fgn_ap'] = bi_net['price'].astype('float64')
        bi_net['fgn_ca'] = bi_net['fgn'].cumsum() + fgn_adjustment
        bi_net['fgn_en'] = 0

        for i in range(1, len(bi_net)):
            bi_net.at[i, 'fgn_ap'] = round((bi_net.at[i-1, 'fgn_ap']*bi_net.at[i-1, 'fgn_ca']+bi_net.at[i,'price']*bi_buy.at[i,'fgn'])/(bi_net.at[i-1,'fgn_ca']+bi_buy.at[i,'fgn']), 1)
            bi_net.at[i, 'fgn_en'] = round((bi_net.at[i, 'price']-bi_net.at[i-1, 'fgn_ap'])*(-bi_sell.at[i,'fgn'])+bi_net.at[i-1,'fgn_en'])

        bi_net['t_inst_ap'] = bi_net['price'].astype('float64')
        bi_net['t_inst_ca'] = bi_net['t_inst'].cumsum() - instmin + adj
        bi_net['t_inst_en'] = 0

        for i in range(1, len(bi_net)):
            bi_net.at[i, 't_inst_ap'] = round((bi_net.at[i-1, 't_inst_ap']*bi_net.at[i-1, 't_inst_ca']+bi_net.at[i,'price']*bi_buy.at[i,'t_inst'])/(bi_net.at[i-1,'t_inst_ca']+bi_buy.at[i,'t_inst']), 1)
            bi_net.at[i, 't_inst_en'] = round((bi_net.at[i, 'price']-bi_net.at[i-1, 't_inst_ap'])*(-bi_sell.at[i,'t_inst'])+bi_net.at[i-1,'t_inst_en'])

        return [bi_net, bi_buy, bi_sell]


    def bi_graph_processing(self, code, bi_net, bi_buy, bi_sell):
        info = self.infodb.loc[self.infodb.code == code].to_dict(orient='records')[0]
        plt.rc('font', family='Malgun Gothic')
        plt.rc('axes', unicode_minus=False)
        fig, (ax0, ax1, ax2, ax3)= plt.subplots(4, 1, sharex=True, figsize = (10, 15), dpi = 150)
        bi_net.loc[:, ['price']].plot(ax = ax0, title = f"{info['name']} ({code}) from {bi_net.date[0]} to {bi_net.date[len(bi_net)-1]}, price")
        bi_net.loc[:, ['ppl_en', 'fgn_en', 't_inst_en']].plot(ax = ax1, title = "en: cumulative earnings")
        bi_net.loc[:, ['ppl_ca', 'fgn_ca', 't_inst_ca']].plot(ax = ax2, title = "ca: cumulative amount of shares")
        bi_net.loc[:, ['ppl_ap', 'fgn_ap', 't_inst_ap']].plot(ax = ax3, title = "ap: average price")
        # plt.show()
        plt.savefig(f"graphs/{info['name']}_{code}.png")
        plt.close(fig) # release memory


if __name__=="__main__":
    sta = STA()
