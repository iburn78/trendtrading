try: 
    ts = open('data/trtrader_status.txt', 'r')
    tsr = ts.read()
    ts.close()

    tl = open('data/trade_log.txt', 'r')
    tlr = tl.read()
    tl.close()

    ts_brief = open('data/trtrader_status_brief.txt', 'r')
    tsr_brief = ts_brief.read()
    ts_brief.close()

    tl_brief = open('data/trade_log.txt', 'r') # need to reread
    tlr_brief_line = tl_brief.readlines()[-50:]
    tl_brief.close()

    tlr_brief = ''
    for i in range(len(tlr_brief_line)):
        tlr_brief += str(tlr_brief_line[i])

except Exception as e: 
    tsr = ''
    tlr = ''
    tsr_brief = ''
    # tlr_brief = ''
    print(e)

index_html = ''

with open('aws/base.html') as bf:
    for cnt, line in enumerate(bf):
        if line.strip()[:5] == "<L01>": 
            index_html += "<pre>" + tsr_brief + "</pre>"
        elif line.strip()[:5] == "<L02>":
            index_html += "<pre>" + tlr_brief + "</pre>"
        else: 
            index_html += line

header = '''
<html><head>
<meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
</head><body><pre>
'''
tsr = header + tsr + "</pre></html>"
tlr = header + tlr + "</pre></html>"

w = open('data/index.html', 'w')
w.write(index_html)
w.close()

w = open('data/trtrader_status.html', 'w')
w.write(tsr)
w.close()

w = open('data/trade_log.html', 'w')
w.write(tlr)
w.close()